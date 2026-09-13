from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import no_tv_v11_independent_selector as v11
import no_tv_v11_1_risk_guard as risk
import no_tv_v18_rank_rolling as v18
import no_tv_v43_2025_uncapped as v43

ATR_CAP = 2.8640659721217943
CONS_THRESHOLD = 0.95
TOP_K = 10
COOLDOWNS = (0, 3, 5)
DEV_END = "2025-06-30"
VALID_START = "2025-07-01"


def topk_consensus(scored: pd.DataFrame) -> pd.DataFrame:
    policy = v43.POLICIES["fixed_min95_both"]
    x = v18.consensus_scores(scored, policy["guard"])
    x = x[
        (x["cons_min"] >= CONS_THRESHOLD)
        & (pd.to_numeric(x["market_median_atr"], errors="coerce") <= ATR_CAP)
    ].copy()
    if x.empty:
        return x
    x = x.sort_values(
        ["date", "session", "cons_min", "symbol"],
        ascending=[True, True, False, True],
    )
    x["candidate_rank"] = (
        x.groupby(["date", "session"], sort=False).cumcount() + 1
    )
    return x[x["candidate_rank"] <= TOP_K].copy()


def build_topk_pool(data: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for dates in v43.blocks(data):
        block_start = dates[0]
        available = v43.available_before(data, block_start)
        block = data[
            data["date"].isin(dates) & data["perf_5bd"].notna()
        ].copy()
        if available.empty or block.empty:
            continue
        if len(available) < 1000:
            raise RuntimeError(
                f"too little training data before {block_start}: {len(available)}"
            )

        models = v11.fit_models(available, v11.features())
        scored = v11.attach(block, models, v11.features())
        topk = topk_consensus(scored)
        if not topk.empty:
            parts.append(topk.assign(block_start=block_start))
        print(
            f"V44 {block_start}..{dates[-1]} topk_rows={len(topk)}",
            flush=True,
        )

    if not parts:
        raise RuntimeError("no V44 Top-K candidates")
    out = pd.concat(parts, ignore_index=True)
    return out.sort_values(
        ["date", "session", "candidate_rank", "symbol"]
    ).reset_index(drop=True)


def attach_execution(
    pool: pd.DataFrame,
    frozen_daily: str,
) -> tuple[pd.DataFrame, dict[str, int]]:
    symbols = set(pool["symbol"].astype(str))
    parts = []
    all_dates: set[str] = set()

    for chunk in pd.read_csv(
        frozen_daily,
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
        raise RuntimeError("no matching frozen daily rows for Top-K pool")

    daily = pd.concat(parts, ignore_index=True)
    daily = daily.sort_values(["symbol", "date"]).reset_index(drop=True)
    g = daily.groupby("symbol", sort=False)
    daily["next_open"] = g["open"].shift(-1)
    daily["d5_close"] = g["close"].shift(-5)

    mapped = daily[["symbol", "date", "next_open", "d5_close"]]
    x = pool.copy()
    x["symbol"] = (
        x["symbol"].astype(str).str.replace(r"\.0$", "", regex=True)
    )
    x = x.merge(mapped, on=["symbol", "date"], how="left", validate="many_to_one")
    x["ret_nextopen_5bd"] = x["d5_close"] / x["next_open"] - 1

    sessions = sorted(d for d in all_dates if v43.EVAL_START <= d <= v43.EVAL_END)
    day_index = {d: i for i, d in enumerate(sessions)}
    missing = sorted(set(x["date"].astype(str)) - set(day_index))
    if missing:
        raise RuntimeError(f"missing trading-day indexes: {missing[:5]}")
    return x, day_index


def select_with_replacement(
    pool: pd.DataFrame,
    day_index: dict[str, int],
    cooldown_days: int,
) -> pd.DataFrame:
    last_selected: dict[str, int] = {}
    rows = []

    ordered = pool.sort_values(
        ["date", "session", "candidate_rank", "symbol"],
        ascending=[True, True, True, True],
    )
    for (date, session), g in ordered.groupby(["date", "session"], sort=True):
        di = day_index[str(date)]
        picked = None
        for row in g.itertuples(index=False):
            symbol = str(row.symbol)
            prior = last_selected.get(symbol)
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


def perf_stats(d: pd.DataFrame) -> dict:
    r = pd.to_numeric(d["ret_nextopen_5bd"], errors="coerce").dropna().to_numpy(float)
    if not len(r):
        return {"n": 0}
    s = np.sort(r)
    c = d.loc[pd.to_numeric(d["ret_nextopen_5bd"], errors="coerce").notna(), "symbol"].astype(str).value_counts()
    n = len(r)

    x = d.copy()
    x["ret_nextopen_5bd"] = pd.to_numeric(x["ret_nextopen_5bd"], errors="coerce")
    x = x[x["ret_nextopen_5bd"].notna()].copy()
    x["week"] = pd.to_datetime(x["date"]).dt.to_period("W").astype(str)
    x["month"] = pd.to_datetime(x["date"]).dt.to_period("M").astype(str)

    def removed_best(group_col: str) -> float | None:
        if x.empty or x[group_col].nunique() <= 1:
            return None
        means = x.groupby(group_col)["ret_nextopen_5bd"].mean()
        best = means.idxmax()
        q = x[x[group_col] != best]["ret_nextopen_5bd"]
        return float(q.mean() * 100) if len(q) else None

    return {
        "n": int(n),
        "mean_pct": float(np.mean(r) * 100),
        "median_pct": float(np.median(r) * 100),
        "win_pct": float(np.mean(r > 0) * 100),
        "hit10_pct": float(np.mean(r >= 0.10) * 100),
        "hit20_pct": float(np.mean(r >= 0.20) * 100),
        "loss10_pct": float(np.mean(r <= -0.10) * 100),
        "loss20_pct": float(np.mean(r <= -0.20) * 100),
        "top3_ex_mean_pct": float(np.mean(s[:-3]) * 100) if n > 3 else None,
        "unique_symbols": int(len(c)),
        "max_symbol_share": float(c.iloc[0] / n),
        "top2_symbol_share": float(c.head(2).sum() / n),
        "top5_symbol_share": float(c.head(5).sum() / n),
        "hhi": float(((c / n) ** 2).sum()),
        "best_week_removed_mean_pct": removed_best("week"),
        "best_month_removed_mean_pct": removed_best("month"),
    }


def choose_policy(dev: dict[str, dict]) -> dict:
    base = dev["0"]
    eligible = []
    for cd in ("3", "5"):
        st = dev[cd]
        mean_ok = st.get("mean_pct", -999) >= 0.80 * base["mean_pct"]
        concentration_ok = (
            st.get("max_symbol_share", 1.0)
            <= 0.75 * base["max_symbol_share"]
        )
        rec = {
            "cooldown_days": int(cd),
            "mean_retention_pass": bool(mean_ok),
            "concentration_pass": bool(concentration_ok),
            "eligible": bool(mean_ok and concentration_ok),
            "stats": st,
        }
        if rec["eligible"]:
            eligible.append(rec)

    if not eligible:
        return {
            "decision": "NO_PROMOTION",
            "reason": "No 3/5-day cooldown met preregistered development gates.",
        }

    eligible.sort(
        key=lambda r: (
            r["stats"].get("top3_ex_mean_pct", -999),
            -r["stats"].get("max_symbol_share", 1.0),
        ),
        reverse=True,
    )
    winner = eligible[0]
    return {
        "decision": "VALIDATE",
        "cooldown_days": winner["cooldown_days"],
        "development_stats": winner["stats"],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frozen-daily", required=True)
    ap.add_argument("--max-workers", type=int, default=16)
    ap.add_argument(
        "--output-dir",
        default="research_artifacts/v44_consensus_topk_cooldown",
    )
    a = ap.parse_args()

    data, prefilter, fetch = v43.build_dataset(
        a.frozen_daily,
        a.max_workers,
    )
    pool = build_topk_pool(data)
    pool, day_index = attach_execution(pool, a.frozen_daily)

    selections = {
        cd: select_with_replacement(pool, day_index, cd)
        for cd in COOLDOWNS
    }

    dev = {}
    valid = {}
    all_stats = {}
    for cd, selected in selections.items():
        d = selected[pd.to_datetime(selected["date"]) <= DEV_END].copy()
        v = selected[pd.to_datetime(selected["date"]) >= VALID_START].copy()
        dev[str(cd)] = perf_stats(d)
        valid[str(cd)] = perf_stats(v)
        all_stats[str(cd)] = perf_stats(selected)

    decision = choose_policy(dev)
    validation_decision = None
    if decision["decision"] == "VALIDATE":
        cd = str(decision["cooldown_days"])
        validation_decision = {
            "cooldown_days": int(cd),
            "validation_stats": valid[cd],
            "baseline_validation_stats": valid["0"],
        }

    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    pool.to_csv(out / "v44_topk_pool.csv", index=False)
    for cd, selected in selections.items():
        selected.to_csv(
            out / f"v44_selected_cooldown_{cd}.csv",
            index=False,
        )

    result = {
        "scope": "2025 uncapped prequential fixed-min95 Consensus Top-K cooldown-with-replacement audit",
        "warning": "2025 outcomes were previously inspected at Top-1 level; replacement outcomes are retrospective evidence, not pristine OOS.",
        "fixed": {
            "consensus_threshold": CONS_THRESHOLD,
            "top_k": TOP_K,
            "atr_cap": ATR_CAP,
            "cooldowns": list(COOLDOWNS),
            "entry_return": "D+1 open -> D+5 close",
        },
        "prefilter": prefilter,
        "hourly_fetch": fetch,
        "topk_rows": int(len(pool)),
        "topk_groups": int(pool.groupby(["date", "session"]).ngroups),
        "development": dev,
        "validation": valid,
        "all_2025": all_stats,
        "preregistered_decision": decision,
        "validation_decision": validation_decision,
        "production_writes": False,
    }
    (out / "v44_consensus_topk_cooldown.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
