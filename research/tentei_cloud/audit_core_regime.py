#!/usr/bin/env python3
"""Previous-day market-regime audit for the fixed reconstructed 4H Core/SAFE rule.

Research-only. No production writes.

Core definition is fixed from the existing 天底極致 Cloud SAFE research:
- production-like universe filters
- RSI(12) < 45
- previous 3 completed reconstructed 4H/session closes descending
- current close > BB(20) midline
- ATR(14)/close < 5%
- 5-business-day same-symbol cooldown

This uses reconstructed 4H/session bars from genuine Yahoo 1H history, so it is
NOT claimed to be the original historical 4H Core signal set.

Only prior-trading-day market context is attached. No thresholds are fit to
candidate outcomes. 2025/2026 outcomes have been inspected before, so results
are retrospective causal evidence, not a pristine holdout.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from reconstruct_4h_from_1h import load, aggregate, enrich_session, add_daily_context, cooldown
from mtf_monster_model import metrics
from audit_market_regime import build_market_regime, attach_regime

TARGET = 0.075

PERIODS = [
    ("DEV", "2024-11-01", "2025-06-30"),
    ("2025H2", "2025-07-01", "2025-12-31"),
    ("2026_01_02", "2026-01-01", "2026-02-28"),
    ("2026_03_04", "2026-03-01", "2026-04-30"),
    ("2026_05_06", "2026-05-01", "2026-06-30"),
    ("2026_07_08", "2026-07-01", "2026-08-31"),
]

GATE_DESCRIPTIONS = {
    "ALL": "keep all Core candidates",
    "NOT_RISK_OFF": "exclude only prior-day median_ret5<=0 AND breadth20_delta5<=0",
    "R5_POS": "prior-day cross-sectional median 5D return > 0",
    "B5_50": "prior-day >=50% of symbols above 5D SMA",
    "R20_POS": "prior-day cross-sectional median 20D return > 0",
    "R5_AND_RISING": "prior-day median 5D return >0 AND 20D breadth rising vs 5 sessions earlier",
}


def make_core_pool(raw: pd.DataFrame) -> pd.DataFrame:
    s = aggregate(raw, 780)
    s = enrich_session(s)
    s, dates = add_daily_context(s, raw)

    eligible = s[
        (s["prev_daily_close"] <= 1000)
        & (s["prev_daily_volume"] >= 10000)
        & (s["volume"] >= 5000)
    ].copy()

    gate = (
        (eligible["rsi12"] < 45)
        & eligible["pre_down3"].fillna(False)
        & (eligible["close"] > eligible["bb_mid"])
        & (eligible["atr14_pct"] < 0.05)
    )
    q = cooldown(eligible[gate].copy(), dates, 5)
    return q[q["ret5bd"].notna()].copy()


def gate_masks(x: pd.DataFrame) -> dict[str, pd.Series]:
    r5 = x["median_ret5"].notna() & (x["median_ret5"] > 0)
    r20 = x["median_ret20"].notna() & (x["median_ret20"] > 0)
    b5 = x["breadth5"].notna() & (x["breadth5"] >= 0.50)
    rising = x["breadth20_delta5"].notna() & (x["breadth20_delta5"] > 0)

    risk_off_known = x["median_ret5"].notna() & x["breadth20_delta5"].notna()
    risk_off = risk_off_known & (x["median_ret5"] <= 0) & (x["breadth20_delta5"] <= 0)

    return {
        "ALL": pd.Series(True, index=x.index),
        # Missing context is fail-open for the veto.
        "NOT_RISK_OFF": ~risk_off,
        "R5_POS": r5,
        "B5_50": b5,
        "R20_POS": r20,
        "R5_AND_RISING": r5 & rising,
    }


def evaluate(x: pd.DataFrame, period_name: str, period_mask: pd.Series) -> list[dict]:
    rows = []
    base_n = int(period_mask.sum())
    for name, mask in gate_masks(x).items():
        q = x[period_mask & mask.fillna(False)].copy()
        m = metrics("CORE_REGIME", name, period_name, q, TARGET)
        m["base_n"] = base_n
        m["coverage"] = (len(q) / base_n) if base_n else None
        rows.append(m)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", action="append", required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()

    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)

    raw = load(a.inputs)
    core = make_core_pool(raw)
    regime = build_market_regime(raw)
    x = attach_regime(core, regime)
    x["date_dt"] = pd.to_datetime(x["date"], errors="coerce")

    rows = []
    for pname, start, end in PERIODS:
        pm = (x["date_dt"] >= pd.Timestamp(start)) & (x["date_dt"] <= pd.Timestamp(end))
        rows.extend(evaluate(x, pname, pm))

    oos = (x["date_dt"] >= pd.Timestamp("2025-07-01")) & (x["date_dt"] <= pd.Timestamp("2026-08-31"))
    rows.extend(evaluate(x, "ALL_OOS", oos))

    summary = pd.DataFrame(rows)
    summary.to_csv(out / "core_regime_metrics.csv", index=False)

    keep = [
        "date", "session", "session_time", "symbol", "close", "ret5bd",
        "rsi12", "pre_down3", "bb_mid", "atr14_pct",
        "regime_date", "median_ret1", "median_ret5", "median_ret20",
        "adv_frac", "breadth5", "breadth20", "breadth20_delta5",
    ]
    x[[k for k in keep if k in x.columns]].to_csv(out / "core_regime_context.csv", index=False)

    meta = {
        "raw_start": str(raw["date"].min()),
        "raw_end": str(raw["date"].max()),
        "core_candidate_pool_n": int(len(x)),
        "core_definition": (
            "reconstructed split-13:00 4H/session; RSI12<45; pre_down3; "
            "close>BB20 mid; ATR14/close<5%; production-like universe filters; "
            "5BD same-symbol cooldown"
        ),
        "gate_definitions": GATE_DESCRIPTIONS,
        "regime_information_timing": "previous trading day only",
        "status": "RETROSPECTIVE_CAUSAL_EXPLORATION_ONLY",
        "original_4h_exact_reproduction": False,
        "production_writes": False,
    }
    (out / "core_regime_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print("\nMETRICS")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
