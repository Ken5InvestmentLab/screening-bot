#!/usr/bin/env python3
"""Independent 2024 extension for frozen TV-Free V3 runners (TEST ONLY).

This file does not alter the existing Short Core or Swing S runners. It imports
their frozen feature/model/scoring functions and evaluates only 2024H1/H2 using
causal training data. Input rows are truncated after 2025-03-31 so no 2026 data
can influence this extension even accidentally.

Purpose: add two earlier pre-2026 regimes without changing the already frozen
run-#80 2025/2026 outputs.

No production writes. No threshold tuning.
"""
from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path

import pandas as pd

import run as short_base
import v3_short_reconstruction as short
import v3_swing as swing_base
import v3_swing_v2 as swing

OUT = Path("tvfree_screener/out")
INPUT_CUTOFF = pd.Timestamp("2025-03-31")
SHORT_START = pd.Timestamp("2024-01-01")
SHORT_END = pd.Timestamp("2024-12-31")
PERIODS = {
    "2024H1_extension": ("2024-01-01", "2024-06-30"),
    "2024H2_extension": ("2024-07-01", "2024-12-31"),
}


def short_scores_2024(eligible: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for period in pd.period_range(
        SHORT_START.to_period("M"), SHORT_END.to_period("M"), freq="M"
    ):
        start = period.start_time
        end = period.end_time.normalize()
        train = eligible[eligible["target_end_date"] < start].copy()
        pred = eligible[
            (eligible["date"] >= start) & (eligible["date"] <= end)
        ].copy()
        train = train.dropna(subset=short_base.FEATURES + ["y_top10", "y_loss10"])
        pred = pred.dropna(subset=short_base.FEATURES)
        if len(train) < 10000 or pred.empty:
            print(f"skip Short {period}: train={len(train)} pred={len(pred)}")
            continue
        print(f"fit Short {period}: train={len(train)} pred={len(pred)}")
        scored = short.fit_month(train, pred)
        scored["model_period"] = str(period)
        parts.append(scored)
    if not parts:
        raise RuntimeError("no causal Short 2024 periods generated")
    return pd.concat(parts, ignore_index=True)


def short_report(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    features = short_base.build_features(raw)
    eligible = short.attach_training_heads(short.eligible_exact(features))
    scored = short_scores_2024(eligible)
    core = short.select_daily_best(scored)
    defensive = core[core["med_ret5"] >= short.DEFENSIVE_MED_RET5_MIN].copy()

    report = {}
    for name, (a, b) in PERIODS.items():
        z = core[(core["date"] >= a) & (core["date"] <= b)]
        dz = defensive[(defensive["date"] >= a) & (defensive["date"] <= b)]
        report[name] = {
            "core_5BD": short.stats(z["target5_no"]),
            "defensive_5BD": short.stats(dz["target5_no"]),
        }
    return core, defensive, report


def swing_scores_2024(events: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for label, a, b in [
        ("2024H1", "2024-01-01", "2024-06-30"),
        ("2024H2", "2024-07-01", "2024-12-31"),
    ]:
        start = pd.Timestamp(a)
        end = pd.Timestamp(b)
        train = events[
            (events["target10_end"] < start) & events["target10_no"].notna()
        ].copy()
        pred = events[
            (events["date"] >= start) & (events["date"] <= end)
        ].copy()
        train = train.dropna(subset=swing.FEATURES)
        pred = pred.dropna(subset=swing.FEATURES)
        if len(train) < 300 or pred.empty:
            print(f"skip Swing {label}: train={len(train)} pred={len(pred)}")
            continue
        print(f"fit Swing {label}: train={len(train)} pred={len(pred)}")
        scored = swing.fit_period(train, pred)
        scored["quality_model_period"] = label
        parts.append(scored)
    if not parts:
        raise RuntimeError("no causal Swing 2024 periods generated")
    return pd.concat(parts, ignore_index=True)


def swing_report(raw: pd.DataFrame, symbol_batch: int) -> tuple[pd.DataFrame, dict]:
    candidates = swing_base.add_cross_sectional_factors(
        swing_base.build_candidates_lowmem(raw, symbol_batch)
    )
    events = candidates[candidates["momcross"]].copy()
    scored = swing_scores_2024(events)
    daily = swing.select_daily_best(scored)
    swing_s = daily[
        (daily["breadth_ma20"] > swing.BREADTH_MA20_MIN)
        & (daily["score_R"] >= swing.LOCKED_SCORE_R_MIN)
    ].copy()

    report = {}
    for name, (a, b) in PERIODS.items():
        z = swing_s[(swing_s["date"] >= a) & (swing_s["date"] <= b)]
        report[name] = swing.stats_horizons(z)
    return swing_s, report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(OUT / "tse_daily.csv"))
    ap.add_argument("--symbol-batch", type=int, default=200)
    args = ap.parse_args()

    raw = pd.read_csv(args.cache, parse_dates=["date"], dtype={"symbol": str})
    for c in ["open", "high", "low", "close", "volume"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw = raw.dropna(subset=["date", "symbol", "close"])
    raw = raw[raw["date"] <= INPUT_CUTOFF].copy()

    core, defensive, short_periods = short_report(raw)
    keep_short = [
        "date", "symbol", "prev_close", "close", "volume", "med_ret5",
        "r_top10", "r_loss10", "core_score", "next_open", "target5_no",
        "target_end_date", "model_period",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    core[[c for c in keep_short if c in core.columns]].to_csv(
        OUT / "v3_short_2024_extension_core.csv", index=False
    )
    defensive[[c for c in keep_short if c in defensive.columns]].to_csv(
        OUT / "v3_short_2024_extension_defensive.csv", index=False
    )
    del core, defensive
    gc.collect()

    swing_s, swing_periods = swing_report(raw, args.symbol_batch)
    swing_s.to_csv(OUT / "v3_swing_2024_extension_s.csv", index=False)

    report = {
        "status": "research_only_no_production_writes",
        "purpose": "independent 2024 extension; frozen 2025/2026 runners unchanged",
        "input_cutoff": INPUT_CUTOFF.strftime("%Y-%m-%d"),
        "causality": {
            "short": "monthly train rows require target_end_date before prediction month",
            "swing": "half-year train rows require target10_end before prediction half-year",
            "entry": "next_session_open",
        },
        "frozen_sources": {
            "short_loss_penalty": short.CORE_LOSS_PENALTY,
            "short_model": "v3_short_reconstruction.fit_month",
            "swing_breadth_min": swing.BREADTH_MA20_MIN,
            "swing_score_R_min": swing.LOCKED_SCORE_R_MIN,
            "swing_model": "v3_swing_v2.fit_period",
        },
        "short": short_periods,
        "swing": swing_periods,
        "notes": [
            "No 2026 input rows are loaded into this extension.",
            "No threshold/hyperparameter is selected from these results inside this runner.",
            "The original run-#80 outputs remain the durable 2025/2026 baseline.",
        ],
    }
    with open(OUT / "v3_pre2026_extension_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
