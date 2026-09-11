#!/usr/bin/env python3
"""Recover the historical TV-Free V3 Short lane structure (TEST ONLY).

Known historical architecture recovered from prior research:
  monthly relative-ranking Core
  -> recent-40 confirmed-outcome Meta
  -> Attack while Meta is ON
  -> Deep Reversal while Meta is OFF
  -> one-business-day same-symbol cooldown
  -> next-session-open to 5BD close

The exact old thresholds were not committed. This runner therefore tests only a
small, predeclared recovery grid and uses a strict blind protocol:
  1) rank combinations on 2024 only;
  2) expose 2025 only for the top 5 2024 combinations;
  3) lock at most one combination from 2025;
  4) expose 2026 Mar-Aug only when a combination passed 2025.

2026 is never used to choose a Meta rule, event family, threshold, or score.
No Discord, Spreadsheet, TradingView, or production writes exist here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import short_event_experiment as events

OUT = Path("tvfree_screener/out")
CORE_2024 = OUT / "v3_short_2024_extension_core.csv"
CORE_2025_PLUS = OUT / "v3_short_reconstruction_core.csv"

ATTACK_NAMES = [
    "lowvol_ignition_A",
    "lowvol_ignition_B",
    "bounded_breakout_A",
    "bounded_breakout_B",
]
DEEP_NAMES = [
    "capitulation_reversal_A",
    "capitulation_reversal_B",
]
META_RULES = {
    "r40_win50": lambda x: x["recent40_win"] >= 0.50,
    "r40_win55": lambda x: x["recent40_win"] >= 0.55,
    "r40_mean0_win50": lambda x: (x["recent40_mean"] >= 0.0) & (x["recent40_win"] >= 0.50),
    "r40_mean0_win55": lambda x: (x["recent40_mean"] >= 0.0) & (x["recent40_win"] >= 0.55),
}

DEV_PERIODS = {
    "2024H1": ("2024-01-01", "2024-06-30"),
    "2024H2": ("2024-07-01", "2024-12-31"),
}
VAL_PERIODS = {
    "2025H1": ("2025-01-01", "2025-06-30"),
    "2025H2": ("2025-07-01", "2025-12-31"),
}
FIXED_2026 = ("2026-03-01", "2026-08-31")


def summarize(s: pd.Series) -> dict:
    x = pd.to_numeric(s, errors="coerce").dropna()
    if x.empty:
        return {"n": 0}
    return {
        "n": int(len(x)),
        "mean": float(x.mean()),
        "median": float(x.median()),
        "win_rate": float((x > 0).mean()),
        "hit5_rate": float((x >= 0.05).mean()),
        "hit10_rate": float((x >= 0.10).mean()),
        "hit20_rate": float((x >= 0.20).mean()),
        "loss10_rate": float((x <= -0.10).mean()),
        "max": float(x.max()),
        "min": float(x.min()),
    }


def load_core() -> pd.DataFrame:
    parts = []
    for path in [CORE_2024, CORE_2025_PLUS]:
        if not path.exists():
            raise FileNotFoundError(f"required prior TEST output missing: {path}")
        z = pd.read_csv(path, parse_dates=["date", "target_end_date"], dtype={"symbol": str})
        parts.append(z)
    core = pd.concat(parts, ignore_index=True)
    core = core.sort_values(["date", "core_score"], ascending=[True, False])
    core = core.drop_duplicates("date", keep="first").reset_index(drop=True)
    return core


def recent_confirmed_meta(core: pd.DataFrame, dates: pd.Index) -> pd.DataFrame:
    """Build recent-40 Meta using only outcomes confirmed before each date."""
    core = core.sort_values("date").copy()
    rows = []
    for date in pd.Index(pd.to_datetime(dates)).sort_values():
        hist = core[
            (core["date"] < date)
            & (core["target_end_date"] < date)
            & core["target5_no"].notna()
        ].tail(40)
        rows.append({
            "date": pd.Timestamp(date),
            "recent40_n": int(len(hist)),
            "recent40_mean": float(hist["target5_no"].mean()) if len(hist) else np.nan,
            "recent40_median": float(hist["target5_no"].median()) if len(hist) else np.nan,
            "recent40_win": float((hist["target5_no"] > 0).mean()) if len(hist) else np.nan,
            "recent40_hit10": float((hist["target5_no"] >= 0.10).mean()) if len(hist) else np.nan,
            "recent40_loss10": float((hist["target5_no"] <= -0.10).mean()) if len(hist) else np.nan,
        })
    return pd.DataFrame(rows)


def select_event_lanes(q: pd.DataFrame) -> dict[str, pd.DataFrame]:
    specs = events.event_specs(q)
    needed = set(ATTACK_NAMES + DEEP_NAMES)
    missing = needed - set(specs)
    if missing:
        raise RuntimeError(f"missing event specs: {sorted(missing)}")
    out = {}
    for name in sorted(needed):
        mask, score = specs[name]
        out[name] = events.select_one_per_day(q, mask, score)
    return out


def hybrid_picks(
    meta: pd.DataFrame,
    meta_rule: str,
    attack: pd.DataFrame,
    deep: pd.DataFrame,
    trading_dates: pd.Index,
) -> pd.DataFrame:
    m = meta.copy()
    eligible_meta = m["recent40_n"] >= 40
    m["meta_on"] = False
    m.loc[eligible_meta, "meta_on"] = META_RULES[meta_rule](m.loc[eligible_meta])

    a = attack.copy()
    a["lane"] = "Attack"
    d = deep.copy()
    d["lane"] = "DeepReversal"
    a = a.merge(m[["date", "meta_on"]], on="date", how="left")
    d = d.merge(m[["date", "meta_on"]], on="date", how="left")
    chosen = pd.concat([
        a[a["meta_on"].fillna(False)],
        d[~d["meta_on"].fillna(False)],
    ], ignore_index=True)
    if chosen.empty:
        return chosen
    chosen = chosen.sort_values(["date", "event_score"], ascending=[True, False])

    date_idx = {pd.Timestamp(x): i for i, x in enumerate(pd.Index(trading_dates).sort_values())}
    last_symbol = None
    last_idx = None
    rows = []
    for date, day in chosen.groupby("date", sort=True):
        idx = date_idx.get(pd.Timestamp(date))
        row = day.iloc[0]
        if (
            idx is not None
            and last_idx is not None
            and idx == last_idx + 1
            and str(row["symbol"]) == last_symbol
        ):
            continue
        rows.append(row)
        last_symbol = str(row["symbol"])
        last_idx = idx
    return pd.DataFrame(rows).reset_index(drop=True)


def period_stats(picks: pd.DataFrame, periods: dict[str, tuple[str, str]]) -> dict:
    out = {}
    for name, (a, b) in periods.items():
        z = picks[(picks["date"] >= a) & (picks["date"] <= b)]
        out[name] = summarize(z["target5_no"])
    return out


def pooled_stats(picks: pd.DataFrame, a: str, b: str) -> dict:
    z = picks[(picks["date"] >= a) & (picks["date"] <= b)]
    return summarize(z["target5_no"])


def dev_utility(stats: dict, pooled: dict) -> float | None:
    h1, h2 = stats["2024H1"], stats["2024H2"]
    if h1.get("n", 0) < 8 or h2.get("n", 0) < 8:
        return None
    if h1["mean"] <= 0 or h2["mean"] <= 0:
        return None
    if pooled.get("mean", -1) < 0.005:
        return None
    if max(h1["loss10_rate"], h2["loss10_rate"]) > 0.15:
        return None
    return float(
        min(h1["mean"], h2["mean"])
        + 0.35 * pooled["mean"]
        + 0.10 * max(0.0, pooled["median"])
        + 0.02 * pooled["hit10_rate"]
        - 0.06 * max(h1["loss10_rate"], h2["loss10_rate"])
    )


def validation_pass(stats: dict, pooled: dict) -> bool:
    h1, h2 = stats["2025H1"], stats["2025H2"]
    return bool(
        h1.get("n", 0) >= 8
        and h2.get("n", 0) >= 8
        and h1["mean"] > 0
        and h2["mean"] > 0
        and pooled.get("mean", -1) >= 0.0075
        and pooled.get("win_rate", 0) >= 0.50
        and max(h1["loss10_rate"], h2["loss10_rate"]) <= 0.15
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(OUT / "tse_daily.csv"))
    ap.add_argument("--symbol-batch", type=int, default=200)
    args = ap.parse_args()

    raw = pd.read_csv(args.cache, parse_dates=["date"], dtype={"symbol": str})
    for c in ["open", "high", "low", "close", "volume"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw = raw.dropna(subset=["date", "symbol", "open", "high", "low", "close", "volume"])

    core = load_core()
    trading_dates = pd.Index(pd.to_datetime(raw["date"].dropna().unique())).sort_values()
    meta = recent_confirmed_meta(core, trading_dates)

    q = events.build_candidates(raw, args.symbol_batch)
    selections = select_event_lanes(q)

    candidates = {}
    for meta_rule in META_RULES:
        for attack_name in ATTACK_NAMES:
            for deep_name in DEEP_NAMES:
                name = f"{meta_rule}__{attack_name}__{deep_name}"
                picks = hybrid_picks(
                    meta,
                    meta_rule,
                    selections[attack_name],
                    selections[deep_name],
                    trading_dates,
                )
                dev = period_stats(picks, DEV_PERIODS)
                dev_pool = pooled_stats(picks, "2024-01-01", "2024-12-31")
                candidates[name] = {
                    "meta_rule": meta_rule,
                    "attack": attack_name,
                    "deep_reversal": deep_name,
                    "picks": picks,
                    "development_2024": dev,
                    "development_2024_pooled": dev_pool,
                    "development_utility": dev_utility(dev, dev_pool),
                }

    ranked = sorted(
        [
            (c["development_utility"], name)
            for name, c in candidates.items()
            if c["development_utility"] is not None
        ],
        reverse=True,
    )
    validation_opened = [name for _, name in ranked[:5]]

    accepted = []
    for name in validation_opened:
        c = candidates[name]
        val = period_stats(c["picks"], VAL_PERIODS)
        val_pool = pooled_stats(c["picks"], "2025-01-01", "2025-12-31")
        c["validation_2025"] = val
        c["validation_2025_pooled"] = val_pool
        c["validation_pass"] = validation_pass(val, val_pool)
        if c["validation_pass"]:
            accepted.append((
                min(val["2025H1"]["mean"], val["2025H2"]["mean"]),
                val_pool["mean"],
                name,
            ))

    locked = sorted(accepted, reverse=True)[0][2] if accepted else None
    report = {
        "status": "research_only_no_production_writes",
        "historical_reference": {
            "2026_MarAug": {
                "n": 29,
                "mean": 0.0542,
                "median": 0.0206,
                "win_rate": 0.655,
                "hit10_rate": 0.138,
                "loss10_rate": 0.069,
            },
            "known_architecture": "relative-ranking Core -> recent-40 confirmed Meta -> Attack ON / Deep Reversal OFF -> one-business-day same-symbol cooldown",
            "exact_old_thresholds_recovered": False,
        },
        "protocol": "2024 development for all fixed combinations -> top 5 only on 2025 -> lock at most one -> 2026 only after pass",
        "meta_rules": list(META_RULES),
        "attack_families": ATTACK_NAMES,
        "deep_reversal_families": DEEP_NAMES,
        "development_ranked": [
            {"name": name, "utility": float(score)}
            for score, name in ranked
        ],
        "validation_opened": validation_opened,
        "locked_candidate": locked,
        "candidates": {},
    }

    for name, c in candidates.items():
        item = {
            "meta_rule": c["meta_rule"],
            "attack": c["attack"],
            "deep_reversal": c["deep_reversal"],
            "development_2024": c["development_2024"],
            "development_2024_pooled": c["development_2024_pooled"],
            "development_utility": c["development_utility"],
        }
        if name in validation_opened:
            item["validation_2025"] = c["validation_2025"]
            item["validation_2025_pooled"] = c["validation_2025_pooled"]
            item["validation_pass"] = c["validation_pass"]
        if name == locked:
            fixed = c["picks"][
                (c["picks"]["date"] >= FIXED_2026[0])
                & (c["picks"]["date"] <= FIXED_2026[1])
            ].copy()
            item["fixed_2026_MarAug"] = summarize(fixed["target5_no"])
            item["fixed_2026_monthly"] = {
                str(month): summarize(group["target5_no"])
                for month, group in fixed.groupby(fixed["date"].dt.to_period("M"))
            }
            keep = [
                "date", "symbol", "lane", "event_score", "target5_no",
                "prev_close", "close", "volume",
            ]
            fixed[[c for c in keep if c in fixed.columns]].to_csv(
                OUT / "v3_short_legacy_recovery_locked_2026.csv", index=False
            )
        report["candidates"][name] = item

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "v3_short_legacy_recovery_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
