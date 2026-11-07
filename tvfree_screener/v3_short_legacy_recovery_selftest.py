#!/usr/bin/env python3
"""Synthetic causality checks for legacy V3 Short recovery."""
from __future__ import annotations

import pandas as pd

import v3_short_legacy_recovery as r


def test_recent_confirmed_only() -> None:
    core = pd.DataFrame({
        "date": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"]),
        "target_end_date": pd.to_datetime(["2025-01-10", "2025-03-10", "2025-01-15"]),
        "target5_no": [0.10, 9.99, -0.05],
        "core_score": [1.0, 1.0, 1.0],
        "symbol": ["A", "B", "C"],
    })
    m = r.recent_confirmed_meta(core, pd.Index(pd.to_datetime(["2025-02-01"])))
    row = m.iloc[0]
    assert row["recent40_n"] == 2, row
    assert abs(row["recent40_mean"] - 0.025) < 1e-12, row


def test_meta_lane_switch_and_global_cooldown() -> None:
    dates = pd.to_datetime(["2025-01-06", "2025-01-07", "2025-01-08"])
    meta = pd.DataFrame({
        "date": dates,
        "recent40_n": [40, 40, 40],
        "recent40_mean": [0.01, -0.01, 0.01],
        "recent40_win": [0.60, 0.40, 0.60],
    })
    attack = pd.DataFrame({
        "date": [dates[0], dates[2]],
        "symbol": ["A", "A"],
        "event_score": [2.0, 2.0],
        "target5_no": [0.1, 0.1],
    })
    deep = pd.DataFrame({
        "date": [dates[1]],
        "symbol": ["B"],
        "event_score": [1.0],
        "target5_no": [0.02],
    })
    out = r.hybrid_picks(
        meta,
        "r40_win50",
        attack,
        deep,
        pd.Index(dates),
    )
    assert list(out["lane"]) == ["Attack", "DeepReversal", "Attack"], out


if __name__ == "__main__":
    test_recent_confirmed_only()
    test_meta_lane_switch_and_global_cooldown()
    print("legacy V3 recovery synthetic checks: PASS")
