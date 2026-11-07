#!/usr/bin/env python3
"""Distinct event-family search for TV-Free V3 Short Attack (TEST ONLY).

Selection is based only on 2024-2025 evidence. 2026 Mar-Aug is evaluated only
if a variant first passes the pre-2026 robustness gate. No Discord/Sheets or
production writes are present.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("tvfree_screener/out")
PRICE_FLOOR = 20.0
PRICE_CAP = 1000.0
PREV_VOLUME_MIN = 10_000.0
SIGNAL_VOLUME_MIN = 5_000.0

PERIODS = {
    "2024H1": ("2024-01-01", "2024-06-30"),
    "2024H2": ("2024-07-01", "2024-12-31"),
    "2025H1": ("2025-01-01", "2025-06-30"),
    "2025H2": ("2025-07-01", "2025-12-31"),
}


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


def build_candidates(raw: pd.DataFrame, symbol_batch: int = 200) -> pd.DataFrame:
    raw = raw.sort_values(["symbol", "date"]).copy()
    symbols = raw["symbol"].drop_duplicates().tolist()
    parts = []

    for i in range(0, len(symbols), symbol_batch):
        names = set(symbols[i:i + symbol_batch])
        z = raw[raw["symbol"].isin(names)].copy().sort_values(["symbol", "date"])
        g = z.groupby("symbol", sort=False, group_keys=False)

        z["prev_close"] = g["close"].shift(1)
        z["prev_volume"] = g["volume"].shift(1)
        z["ret1"] = g["close"].pct_change(fill_method=None)
        for n in [3, 5, 10, 20, 40]:
            z[f"ret{n}"] = g["close"].pct_change(n, fill_method=None)
        z["prev_ret5"] = z.groupby("symbol", sort=False)["ret5"].shift(1)

        for n in [5, 10, 20]:
            vm = g["volume"].transform(lambda s: s.rolling(n, min_periods=n).mean())
            z[f"volr{n}"] = z["volume"] / vm.replace(0, np.nan)

        z["rv10"] = z["ret1"].groupby(z["symbol"]).transform(
            lambda s: s.rolling(10, min_periods=10).std(ddof=0)
        )
        z["rv40"] = z["ret1"].groupby(z["symbol"]).transform(
            lambda s: s.rolling(40, min_periods=40).std(ddof=0)
        )
        z["prev_rv10"] = z.groupby("symbol", sort=False)["rv10"].shift(1)
        z["prev_rv40"] = z.groupby("symbol", sort=False)["rv40"].shift(1)

        z["range_pct"] = (z["high"] - z["low"]) / z["close"].replace(0, np.nan)
        z["avg_range10"] = z["range_pct"].groupby(z["symbol"]).transform(
            lambda s: s.rolling(10, min_periods=10).mean()
        )
        z["prev_avg_range10"] = z.groupby("symbol", sort=False)["avg_range10"].shift(1)

        intraday_range = (z["high"] - z["low"]).replace(0, np.nan)
        z["close_loc"] = (z["close"] - z["low"]) / intraday_range
        z["gap"] = z["open"] / z["prev_close"] - 1.0

        for n in [20, 60]:
            hi = g["high"].transform(lambda s: s.rolling(n, min_periods=n).max())
            lo = g["low"].transform(lambda s: s.rolling(n, min_periods=n).min())
            z[f"pos{n}"] = (z["close"] - lo) / (hi - lo).replace(0, np.nan)
            z[f"prev_hi{n}"] = hi.groupby(z["symbol"]).shift(1)

        z["break20"] = z["close"] / z["prev_hi20"] - 1.0
        z["break60"] = z["close"] / z["prev_hi60"] - 1.0
        z["next_open"] = g["open"].shift(-1)
        z["target5_no"] = g["close"].shift(-5) / z["next_open"] - 1.0

        eligible = (
            (z["prev_volume"] >= PREV_VOLUME_MIN)
            & (z["volume"] >= SIGNAL_VOLUME_MIN)
            & (z["close"] >= PRICE_FLOOR)
            & (z["prev_close"] <= PRICE_CAP)
        )
        keep = [
            "date", "symbol", "open", "high", "low", "close", "volume",
            "prev_close", "prev_volume", "ret1", "ret3", "ret5", "ret10",
            "ret20", "ret40", "prev_ret5", "volr5", "volr10", "volr20",
            "rv10", "rv40", "prev_rv10", "prev_rv40", "range_pct",
            "avg_range10", "prev_avg_range10", "close_loc", "gap", "pos20",
            "pos60", "break20", "break60", "target5_no",
        ]
        parts.append(z.loc[eligible, keep])

    return pd.concat(parts, ignore_index=True).replace([np.inf, -np.inf], np.nan)


def event_specs(q: pd.DataFrame) -> dict[str, tuple[pd.Series, pd.Series]]:
    """Fixed, intentionally small event grid defined before 2026 evaluation."""
    specs = {}

    specs["compression_expansion_A"] = (
        (q.prev_rv10 <= 0.75 * q.prev_rv40)
        & (q.ret1 >= 0.025)
        & (q.range_pct >= 1.35 * q.prev_avg_range10)
        & (q.volr20 >= 1.25)
        & (q.close_loc >= 0.65),
        q.ret1 + 0.015 * np.log1p(q.volr20) + 0.02 * q.close_loc,
    )
    specs["compression_expansion_B"] = (
        (q.prev_rv10 <= 0.65 * q.prev_rv40)
        & (q.ret1 >= 0.03)
        & (q.range_pct >= 1.50 * q.prev_avg_range10)
        & (q.volr20 >= 1.50)
        & (q.close_loc >= 0.70),
        q.ret1 + 0.015 * np.log1p(q.volr20) + 0.02 * q.close_loc,
    )

    specs["capitulation_reversal_A"] = (
        (q.prev_ret5 <= -0.08)
        & (q.ret1 >= 0.025)
        & (q.volr20 >= 1.20)
        & (q.close_loc >= 0.65)
        & (q.gap >= -0.04),
        -q.prev_ret5 + q.ret1 + 0.01 * np.log1p(q.volr20),
    )
    specs["capitulation_reversal_B"] = (
        (q.prev_ret5 <= -0.12)
        & (q.ret1 >= 0.035)
        & (q.volr20 >= 1.50)
        & (q.close_loc >= 0.70)
        & (q.gap >= -0.03),
        -q.prev_ret5 + q.ret1 + 0.01 * np.log1p(q.volr20),
    )

    specs["gap_volume_A"] = (
        q.gap.between(0.015, 0.10)
        & (q.volr20 >= 1.80)
        & (q.ret1 >= 0.02)
        & (q.close_loc >= 0.70),
        q.gap + q.ret1 + 0.015 * np.log1p(q.volr20) + 0.02 * q.close_loc,
    )
    specs["gap_volume_B"] = (
        q.gap.between(0.025, 0.08)
        & (q.volr20 >= 2.50)
        & (q.ret1 >= 0.03)
        & (q.close_loc >= 0.78),
        q.gap + q.ret1 + 0.015 * np.log1p(q.volr20) + 0.02 * q.close_loc,
    )

    specs["lowvol_ignition_A"] = (
        (q.prev_rv10 <= 0.80 * q.prev_rv40)
        & q.ret5.between(0.03, 0.12)
        & (q.ret1 >= 0.025)
        & q.volr20.between(1.30, 4.00)
        & (q.pos60 >= 0.55)
        & (q.close_loc >= 0.65),
        q.ret5 + 0.5 * q.ret1 + 0.015 * np.log1p(q.volr20),
    )
    specs["lowvol_ignition_B"] = (
        (q.prev_rv10 <= 0.70 * q.prev_rv40)
        & q.ret5.between(0.04, 0.10)
        & (q.ret1 >= 0.03)
        & q.volr20.between(1.50, 3.50)
        & (q.pos60 >= 0.65)
        & (q.close_loc >= 0.70),
        q.ret5 + 0.5 * q.ret1 + 0.015 * np.log1p(q.volr20),
    )

    specs["bounded_breakout_A"] = (
        q.break20.between(0.0, 0.05)
        & (q.prev_rv10 <= 1.05 * q.prev_rv40)
        & q.ret5.between(0.02, 0.12)
        & q.volr20.between(1.0, 3.5)
        & (q.close_loc >= 0.65),
        q.break20 + 0.5 * q.ret5 + 0.01 * np.log1p(q.volr20),
    )
    specs["bounded_breakout_B"] = (
        q.break60.between(0.0, 0.04)
        & (q.prev_rv10 <= 0.90 * q.prev_rv40)
        & q.ret5.between(0.03, 0.10)
        & q.volr20.between(1.2, 3.0)
        & (q.close_loc >= 0.70),
        q.break60 + 0.5 * q.ret5 + 0.01 * np.log1p(q.volr20),
    )
    return specs


def select_one_per_day(q: pd.DataFrame, mask: pd.Series, score: pd.Series) -> pd.DataFrame:
    z = q.loc[mask.fillna(False) & q["target5_no"].notna()].copy()
    z["event_score"] = score.loc[z.index]
    all_dates = pd.Index(pd.to_datetime(q["date"].dropna().unique())).sort_values()
    date_idx = {pd.Timestamp(d): i for i, d in enumerate(all_dates)}
    last_selected_idx: dict[str, int] = {}
    rows = []

    for date, day in z.sort_values(
        ["date", "event_score"], ascending=[True, False]
    ).groupby("date", sort=True):
        current_idx = date_idx[pd.Timestamp(date)]
        chosen = None
        for _, row in day.sort_values("event_score", ascending=False).iterrows():
            symbol = str(row.symbol)
            if last_selected_idx.get(symbol) == current_idx - 1:
                continue
            chosen = row
            break
        if chosen is not None:
            last_selected_idx[str(chosen.symbol)] = current_idx
            rows.append(chosen)
    return pd.DataFrame(rows).reset_index(drop=True)


def robust_utility(period_stats: dict) -> float | None:
    adequate = [period_stats[k] for k in PERIODS if period_stats[k].get("n", 0) >= 8]
    if len(adequate) < 3:
        return None
    means = [x["mean"] for x in adequate]
    medians = [x["median"] for x in adequate]
    if sum(x > 0 for x in means) < 3:
        return None
    if sum(x >= 0 for x in medians) < 3:
        return None
    if min(means) < -0.01:
        return None
    return float(
        min(means)
        + 0.35 * np.median(means)
        + 0.20 * np.median(medians)
        + 0.03 * np.median([x["hit10_rate"] for x in adequate])
        - 0.08 * max(x["loss10_rate"] for x in adequate)
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default="tvfree_screener/out/tse_daily.csv")
    ap.add_argument("--symbol-batch", type=int, default=200)
    args = ap.parse_args()

    raw = pd.read_csv(args.cache, parse_dates=["date"], dtype={"symbol": str})
    for c in ["open", "high", "low", "close", "volume"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw = raw.dropna(subset=["date", "symbol", "open", "high", "low", "close", "volume"])

    q = build_candidates(raw, args.symbol_batch)
    specs = event_specs(q)
    report = {
        "status": "research_only_no_production_writes",
        "selection_data": "2024-2025_only",
        "entry": "next_session_open",
        "cooldown": "same symbol blocked only when selected on immediately prior trading date",
        "variants": {},
    }
    selections = {}

    for name, (mask, score) in specs.items():
        sel = select_one_per_day(q, mask, score)
        selections[name] = sel
        period_stats = {}
        for period, (a, b) in PERIODS.items():
            z = sel[(sel["date"] >= a) & (sel["date"] <= b)]
            period_stats[period] = summarize(z["target5_no"])
        report["variants"][name] = {
            "pre2026": period_stats,
            "robust_utility": robust_utility(period_stats),
            "total_pre2026_n": int(sum(x["n"] for x in period_stats.values())),
        }

    eligible = [
        (v["robust_utility"], name)
        for name, v in report["variants"].items()
        if v["robust_utility"] is not None
    ]
    if eligible:
        eligible.sort(reverse=True)
        locked = eligible[0][1]
        report["locked_candidate"] = locked
        fixed = selections[locked]
        fixed = fixed[(fixed["date"] >= "2026-03-01") & (fixed["date"] <= "2026-08-31")]
        report["fixed_2026_MarAug"] = summarize(fixed["target5_no"])
        report["fixed_2026_monthly"] = {
            str(month): summarize(group["target5_no"])
            for month, group in fixed.groupby(fixed["date"].dt.to_period("M"))
        }
    else:
        # Deliberately do not open 2026 if nothing passes the pre-2026 gate.
        report["locked_candidate"] = None
        report["fixed_2026_MarAug"] = None

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "short_event_experiment_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
