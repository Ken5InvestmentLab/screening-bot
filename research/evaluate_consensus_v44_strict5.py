from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

EVAL_START = "2025-01-06"
EVAL_END = "2025-12-30"
VALID_START = "2025-07-01"
STRICT_COOLDOWN = 5


def select_with_replacement(
    pool: pd.DataFrame,
    day_index: dict[str, int],
    cooldown_days: int,
) -> pd.DataFrame:
    last_selected: dict[str, int] = {}
    rows: list[dict] = []
    ordered = pool.sort_values(
        ["date", "session", "candidate_rank", "symbol"],
        ascending=[True, True, True, True],
    )
    for (date, session), g in ordered.groupby(["date", "session"], sort=True):
        d = str(date)[:10]
        if d not in day_index:
            raise RuntimeError(f"missing trading-day index for {d}")
        di = day_index[d]
        picked = None
        for row in g.itertuples(index=False):
            sym = str(row.symbol)
            prior = last_selected.get(sym)
            if (
                cooldown_days > 0
                and prior is not None
                and di - prior < cooldown_days
            ):
                continue
            picked = row
            break
        if picked is None:
            continue
        rec = picked._asdict()
        rec["cooldown_days"] = cooldown_days
        rec["replacement_rank"] = int(rec["candidate_rank"])
        rows.append(rec)
        last_selected[str(rec["symbol"])] = di
    return pd.DataFrame(rows)


def load_daily(path: Path, symbols: set[str]) -> tuple[pd.DataFrame, dict[str, int]]:
    parts = []
    all_dates: set[str] = set()
    for chunk in pd.read_csv(
        path,
        usecols=["date", "open", "close", "symbol"],
        dtype={"symbol": str},
        chunksize=500_000,
        low_memory=False,
    ):
        chunk["date"] = chunk["date"].astype(str).str[:10]
        all_dates.update(chunk["date"].dropna().unique().tolist())
        chunk["symbol"] = (
            chunk["symbol"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.strip()
        )
        q = chunk[chunk["symbol"].isin(symbols)].copy()
        if len(q):
            parts.append(q)

    if not parts:
        raise RuntimeError("no matching frozen daily rows")

    daily = pd.concat(parts, ignore_index=True)
    daily = daily.sort_values(["symbol", "date"]).reset_index(drop=True)
    g = daily.groupby("symbol", sort=False)
    daily["next_open"] = g["open"].shift(-1)
    daily["d5_close"] = g["close"].shift(-5)

    dates = sorted(d for d in all_dates if EVAL_START <= d <= EVAL_END)
    day_index = {d: i for i, d in enumerate(dates)}
    return daily[["symbol", "date", "next_open", "d5_close"]], day_index


def attach_returns(sel: pd.DataFrame, mapped: pd.DataFrame) -> pd.DataFrame:
    x = sel.copy()
    x["date"] = x["date"].astype(str).str[:10]
    x["symbol"] = (
        x["symbol"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    )
    x = x.merge(mapped, on=["symbol", "date"], how="left", validate="many_to_one")
    x["ret_nextopen_5bd"] = x["d5_close"] / x["next_open"] - 1
    return x


def selection_diagnostics(d: pd.DataFrame) -> dict:
    if d.empty:
        return {
            "selected_rows": 0,
            "replacement_fraction": None,
            "replacement_rank_mean": None,
            "replacement_rank_median": None,
            "replacement_rank_max": None,
        }
    r = pd.to_numeric(d.get("replacement_rank"), errors="coerce").dropna()
    if r.empty:
        return {
            "selected_rows": int(len(d)),
            "replacement_fraction": None,
            "replacement_rank_mean": None,
            "replacement_rank_median": None,
            "replacement_rank_max": None,
        }
    return {
        "selected_rows": int(len(d)),
        "replacement_fraction": float(np.mean(r.to_numpy(float) > 1)),
        "replacement_rank_mean": float(r.mean()),
        "replacement_rank_median": float(r.median()),
        "replacement_rank_max": int(r.max()),
    }


def stats(d: pd.DataFrame) -> dict:
    x = d.copy()
    x["ret_nextopen_5bd"] = pd.to_numeric(x["ret_nextopen_5bd"], errors="coerce")
    x = x[x["ret_nextopen_5bd"].notna()].copy()
    r = x["ret_nextopen_5bd"].to_numpy(float)
    if not len(r):
        return {"n": 0}
    s = np.sort(r)
    counts = x["symbol"].astype(str).value_counts()
    return {
        "n": int(len(r)),
        "mean_pct": float(np.mean(r) * 100),
        "median_pct": float(np.median(r) * 100),
        "win_pct": float(np.mean(r > 0) * 100),
        "hit10_pct": float(np.mean(r >= 0.10) * 100),
        "hit20_pct": float(np.mean(r >= 0.20) * 100),
        "loss10_pct": float(np.mean(r <= -0.10) * 100),
        "loss20_pct": float(np.mean(r <= -0.20) * 100),
        "top3_ex_mean_pct": float(np.mean(s[:-3]) * 100) if len(r) > 3 else None,
        "unique_symbols": int(len(counts)),
        "max_symbol_share": float(counts.iloc[0] / len(r)),
        "top2_symbol_share": float(counts.head(2).sum() / len(r)),
        "top5_symbol_share": float(counts.head(5).sum() / len(r)),
        "hhi": float(((counts / len(r)) ** 2).sum()),
    }


def dev_eligible(result: dict) -> tuple[bool, dict]:
    dev = result["development"]
    base = dev["0"]
    strict = dev["5"]
    mean_ok = strict["mean_pct"] >= 0.80 * base["mean_pct"]
    concentration_ok = (
        strict["max_symbol_share"] <= 0.75 * base["max_symbol_share"]
    )
    return bool(mean_ok and concentration_ok), {
        "mean_retention_pass": bool(mean_ok),
        "concentration_pass": bool(concentration_ok),
        "baseline": base,
        "cooldown5": strict,
    }


def h2_gate(base: dict, strict: dict) -> dict:
    checks = {
        "n_gte_20": strict.get("n", 0) >= 20,
        "mean_positive": strict.get("mean_pct", -999.0) > 0.0,
        "mean_retention_80pct": (
            strict.get("mean_pct", -999.0) >= 0.80 * base.get("mean_pct", 999.0)
        ),
        "median_nonnegative": strict.get("median_pct", -999.0) >= 0.0,
        "top3_ex_mean_positive": strict.get("top3_ex_mean_pct", -999.0) > 0.0,
        "max_symbol_share_reduced_25pct": (
            strict.get("max_symbol_share", 1.0)
            <= 0.75 * base.get("max_symbol_share", 0.0)
        ),
    }
    return {"checks": checks, "pass": bool(all(checks.values()))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v44-json", required=True, type=Path)
    ap.add_argument("--dev-pool", required=True, type=Path)
    ap.add_argument("--validation-blind-pool", required=True, type=Path)
    ap.add_argument("--frozen-daily", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    a = ap.parse_args()

    result = json.loads(a.v44_json.read_text(encoding="utf-8"))
    eligible, dev_receipt = dev_eligible(result)

    out = a.output_dir
    out.mkdir(parents=True, exist_ok=True)

    summary = {
        "scope": "strict 5BD no-overlap V44 addendum",
        "parent_run": 34767664140,
        "cooldown_days": STRICT_COOLDOWN,
        "development_eligibility": dev_receipt,
        "h2_outcome_opened": False,
        "production_writes": False,
    }

    if not eligible:
        summary["decision"] = "STRICT_NO_OVERLAP_FAIL_DEV"
        (out / "v44_strict5.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    dev = pd.read_csv(a.dev_pool, dtype={"symbol": str})
    blind = pd.read_csv(a.validation_blind_pool, dtype={"symbol": str})
    pool = pd.concat([dev, blind], ignore_index=True, sort=False)
    pool["date"] = pool["date"].astype(str).str[:10]

    symbols = set(pool["symbol"].astype(str))
    mapped, day_index = load_daily(a.frozen_daily, symbols)

    baseline_all = select_with_replacement(pool, day_index, 0)
    strict_all = select_with_replacement(pool, day_index, STRICT_COOLDOWN)
    baseline_h2 = baseline_all[baseline_all["date"].astype(str) >= VALID_START].copy()
    strict_h2 = strict_all[strict_all["date"].astype(str) >= VALID_START].copy()

    baseline_h2 = attach_returns(baseline_h2, mapped)
    strict_h2 = attach_returns(strict_h2, mapped)

    base_stats = stats(baseline_h2)
    strict_stats = stats(strict_h2)
    gate = h2_gate(base_stats, strict_stats)

    summary.update({
        "h2_outcome_opened": True,
        "baseline_h2": base_stats,
        "strict5_h2": strict_stats,
        "baseline_h2_selection": selection_diagnostics(baseline_h2),
        "strict5_h2_selection": selection_diagnostics(strict_h2),
        "h2_group_fill_rate_vs_baseline": (
            float(len(strict_h2) / len(baseline_h2)) if len(baseline_h2) else None
        ),
        "h2_gate": gate,
        "decision": (
            "STRICT_NO_OVERLAP_PASS"
            if gate["pass"]
            else "STRICT_NO_OVERLAP_FAIL_H2"
        ),
    })

    baseline_h2.to_csv(out / "v44_strict5_baseline_h2.csv", index=False)
    strict_h2.to_csv(out / "v44_strict5_selected_h2.csv", index=False)
    (out / "v44_strict5.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
