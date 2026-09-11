#!/usr/bin/env python3
"""Causal previous-day market regime audit for reconstructed 4H TAIL candidates.

Research-only.
Regime features are computed from the broad symbol universe using DAILY bars and
shifted by one trading day before being attached to a candidate.

Fixed, interpretable gates:
- R5_POS: cross-sectional median 5D return > 0
- R20_POS: median 20D return > 0
- B20_50: >=50% of symbols above 20D SMA
- B5_50: >=50% above 5D SMA
- ADV_50: >=50% positive on the prior day
- R5_B20: R5_POS and B20_50
- R5_OR_B20: R5_POS or B20_50
- B20_RISING: 20D breadth higher than 5 trading days earlier
- R5_OR_RISING: keep if median 5D return is positive OR breadth is improving
- R5_AND_RISING: stronger trend/recovery confirmation
- RISK_OFF_ONLY: diagnostic bucket where median 5D <=0 AND breadth is not improving

No threshold is fit to candidate outcomes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from reconstruct_4h_from_1h import load
from mtf_monster_model import make_candidate_pool, metrics

TARGET = 0.075

PERIODS = [
    ("DEV", "2024-11-01", "2025-06-30"),
    ("2025H2", "2025-07-01", "2025-12-31"),
    ("2026_01_02", "2026-01-01", "2026-02-28"),
    ("2026_03_04", "2026-03-01", "2026-04-30"),
    ("2026_05_06", "2026-05-01", "2026-06-30"),
    ("2026_07_08", "2026-07-01", "2026-08-31"),
]


def build_market_regime(raw: pd.DataFrame) -> pd.DataFrame:
    daily = (
        raw.sort_values("timestamp")
        .groupby(["symbol","date"], as_index=False)
        .agg(close=("close","last"), volume=("volume","sum"))
        .sort_values(["symbol","date"])
    )

    pieces = []
    for _, g in daily.groupby("symbol", sort=False):
        g = g.sort_values("date").copy()
        c = g["close"].astype(float)
        g["ret1"] = c.pct_change(1)
        g["ret5"] = c.pct_change(5)
        g["ret20"] = c.pct_change(20)
        g["sma5"] = c.rolling(5, min_periods=5).mean()
        g["sma20"] = c.rolling(20, min_periods=20).mean()
        g["above5"] = c > g["sma5"]
        g["above20"] = c > g["sma20"]
        pieces.append(g)
    d = pd.concat(pieces, ignore_index=True)

    regime = (
        d.groupby("date")
        .agg(
            symbols=("symbol","nunique"),
            median_ret1=("ret1","median"),
            median_ret5=("ret5","median"),
            median_ret20=("ret20","median"),
            adv_frac=("ret1", lambda s: float((s.dropna() > 0).mean()) if s.notna().any() else np.nan),
            breadth5=("above5", lambda s: float(s.mean())),
            breadth20=("above20", lambda s: float(s.mean())),
            median_abs_ret1=("ret1", lambda s: float(s.dropna().abs().median()) if s.notna().any() else np.nan),
        )
        .reset_index()
        .sort_values("date")
    )
    regime["breadth20_lag5"] = regime["breadth20"].shift(5)
    regime["breadth20_delta5"] = regime["breadth20"] - regime["breadth20_lag5"]

    # Attach as-of information from the previous trading day only.
    regime["candidate_date"] = regime["date"].shift(-1)
    prev = regime.dropna(subset=["candidate_date"]).copy()
    prev = prev.rename(columns={"date":"regime_date"})
    return prev


def attach_regime(cands: pd.DataFrame, regime: pd.DataFrame) -> pd.DataFrame:
    return cands.merge(
        regime,
        left_on="date",
        right_on="candidate_date",
        how="left",
        suffixes=("","_market"),
    )


def gate_masks(x: pd.DataFrame):
    r5 = x["median_ret5"] > 0
    r20 = x["median_ret20"] > 0
    b20 = x["breadth20"] >= 0.50
    b5 = x["breadth5"] >= 0.50
    adv = x["adv_frac"] >= 0.50
    rising = x["breadth20_delta5"] > 0
    risk_off = (~r5.fillna(False)) & (~rising.fillna(False))
    return {
        "ALL": pd.Series(True, index=x.index),
        "R5_POS": r5,
        "R20_POS": r20,
        "B20_50": b20,
        "B5_50": b5,
        "ADV_50": adv,
        "R5_B20": r5 & b20,
        "R5_OR_B20": r5 | b20,
        "B20_RISING": rising,
        "R5_OR_RISING": r5 | rising,
        "R5_AND_RISING": r5 & rising,
        "RISK_OFF_ONLY": risk_off,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", action="append", required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)

    raw = load(a.inputs)
    c = make_candidate_pool(raw)
    c = c[c["ret5bd"].notna()].copy()
    regime = build_market_regime(raw)
    x = attach_regime(c, regime)
    x["date_dt"] = pd.to_datetime(x["date"], errors="coerce")

    masks = gate_masks(x)
    rows = []

    for pname, start, end in PERIODS:
        period_mask = (x["date_dt"] >= pd.Timestamp(start)) & (x["date_dt"] <= pd.Timestamp(end))
        base_n = int(period_mask.sum())
        for gate, gm in masks.items():
            q = x[period_mask & gm.fillna(False)].copy()
            m = metrics("REGIME_GATE", gate, pname, q, TARGET)
            m["base_n"] = base_n
            m["coverage"] = (len(q) / base_n) if base_n else None
            rows.append(m)

    summary = pd.DataFrame(rows)
    summary.to_csv(out / "regime_gate_by_period.csv", index=False)

    # Aggregate OOS excludes DEV.
    oos_mask = (x["date_dt"] >= pd.Timestamp("2025-07-01")) & (x["date_dt"] <= pd.Timestamp("2026-08-31"))
    agg = []
    base_n = int(oos_mask.sum())
    for gate, gm in masks.items():
        q = x[oos_mask & gm.fillna(False)].copy()
        m = metrics("REGIME_GATE", gate, "ALL_OOS", q, TARGET)
        m["base_n"] = base_n
        m["coverage"] = (len(q) / base_n) if base_n else None
        agg.append(m)
    aggregate = pd.DataFrame(agg)
    aggregate.to_csv(out / "regime_gate_aggregate.csv", index=False)

    keep = [
        "date","session","session_time","symbol","close","ret5bd",
        "regime_date","symbols","median_ret1","median_ret5","median_ret20",
        "adv_frac","breadth5","breadth20","breadth20_delta5","median_abs_ret1",
    ]
    x[[k for k in keep if k in x.columns]].to_csv(out / "candidate_regime_context.csv", index=False)

    regime.to_csv(out / "market_regime_daily.csv", index=False)

    meta = {
        "raw_start": str(raw["date"].min()),
        "raw_end": str(raw["date"].max()),
        "candidate_pool_n": int(len(x)),
        "regime_feature_policy": "previous trading day only",
        "fixed_gates": list(masks.keys()),
        "production_writes": False,
        "warning": "Exploratory after earlier 2026 research. Gates are interpretable fixed thresholds, not fitted to candidate outcomes.",
    }
    (out / "regime_gate_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print("\nAGGREGATE OOS")
    print(aggregate.to_string(index=False))
    print("\nBY PERIOD")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
