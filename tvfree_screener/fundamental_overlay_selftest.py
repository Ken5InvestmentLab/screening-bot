#!/usr/bin/env python3
"""Synthetic causal checks for fundamental/dilution overlay (TEST ONLY)."""
from __future__ import annotations

import pandas as pd

import fundamental_overlay as fo


def main() -> None:
    signals = pd.DataFrame([
        {"date": "2025-04-01", "symbol": "1111", "target5_no": 0.05},
        {"date": "2025-06-01", "symbol": "1111", "target5_no": 0.02},
        {"date": "2025-04-01", "symbol": "2222", "target5_no": -0.03},
    ])
    snapshots = pd.DataFrame([
        {"symbol":"1111","available_date":"2025-03-15","shares_outstanding":100,"remaining_warrant_shares":20,"ms_warrant_flag":False,"equity":50,"assets":100,"revenue":100,"operating_income":10,"net_income":8,"operating_cf":12},
        # Future disclosure relative to first signal; must only affect June signal.
        {"symbol":"1111","available_date":"2025-05-15","shares_outstanding":100,"remaining_warrant_shares":60,"ms_warrant_flag":True,"equity":15,"assets":100,"revenue":100,"operating_income":-5,"net_income":-7,"operating_cf":-3},
        {"symbol":"2222","available_date":"2025-03-20","shares_outstanding":100,"remaining_warrant_shares":0,"ms_warrant_flag":False,"equity":40,"assets":100,"revenue":100,"operating_income":5,"net_income":4,"operating_cf":6},
    ])
    z = fo.add_overlay_metrics(fo.attach_point_in_time_snapshot(signals, snapshots))

    a = z[(z.symbol == "1111") & (z.date == pd.Timestamp("2025-04-01"))].iloc[0]
    b = z[(z.symbol == "1111") & (z.date == pd.Timestamp("2025-06-01"))].iloc[0]
    assert a.available_date == pd.Timestamp("2025-03-15")
    assert b.available_date == pd.Timestamp("2025-05-15")
    assert abs(a.dilution_ratio - 0.20) < 1e-12
    assert abs(b.dilution_ratio - 0.60) < 1e-12
    assert not bool(a.financial_risk_exclude)
    assert bool(b.financial_risk_exclude)

    lanes = fo.build_lanes(signals, snapshots)
    assert len(lanes["baseline"]) == 3
    assert len(lanes["dilution_le_0.35"]) == 2
    assert len(lanes["financial_risk_filter"]) == 2
    assert len(lanes["combined_dilution35_finrisk"]) == 2

    # Missing fundamental data must not be silently converted into a safe numeric score.
    missing = pd.DataFrame([{"date":"2025-04-01","symbol":"9999"}])
    m = fo.add_overlay_metrics(fo.attach_point_in_time_snapshot(missing, snapshots)).iloc[0]
    assert pd.isna(m.dilution_ratio)
    assert pd.isna(m.available_date)

    # Same-day disclosure must be excluded by the conservative default.
    same_day_signals = pd.DataFrame([
        {"date":"2025-05-15","symbol":"1111"},
        {"date":"2025-05-16","symbol":"1111"},
    ])
    strict = fo.attach_point_in_time_snapshot(same_day_signals, snapshots)
    on_day = strict[strict.date == pd.Timestamp("2025-05-15")].iloc[0]
    next_day = strict[strict.date == pd.Timestamp("2025-05-16")].iloc[0]
    assert on_day.available_date == pd.Timestamp("2025-03-15")
    assert next_day.available_date == pd.Timestamp("2025-05-15")

    # Same-day data is permitted only with explicit decision/public timestamps.
    timestamped_snapshots = snapshots.copy()
    timestamped_snapshots["available_at"] = [
        "2025-03-15 15:00:00",
        "2025-05-15 16:30:00",
        "2025-03-20 15:00:00",
    ]
    timestamped_signals = pd.DataFrame([
        {"date":"2025-05-15","symbol":"1111","decision_at":"2025-05-15 16:00:00"},
        {"date":"2025-05-15","symbol":"1111","decision_at":"2025-05-15 17:00:00"},
    ])
    timed = fo.attach_point_in_time_snapshot(
        timestamped_signals,
        timestamped_snapshots,
        availability_policy="same_day_if_timestamped",
    ).sort_values("decision_at")
    assert timed.iloc[0].available_date == pd.Timestamp("2025-03-15")
    assert timed.iloc[1].available_date == pd.Timestamp("2025-05-15")

    print("fundamental overlay self-test: PASS")


if __name__ == "__main__":
    main()
