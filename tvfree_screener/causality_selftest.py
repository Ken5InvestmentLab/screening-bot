#!/usr/bin/env python3
"""Synthetic causal-safety checks for the TradingView-free research path.

TEST ONLY. Uses fabricated data and monkeypatches model fitting so it can verify
selection/training boundaries without tuning or reading 2026 performance.

Checks:
- feature values on historical rows are prefix-invariant when only future rows are appended,
- next-session-open -> 5BD target semantics are correct,
- Short monthly training excludes outcomes ending on/after the prediction month,
- Swing semiannual training excludes outcomes ending on/after the prediction period.

No network, Discord, Spreadsheet, TradingView, or production writes are used.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import run as base
import v3_short_reconstruction as short
import v3_swing_v2 as swing


def synthetic_ohlcv(days: int = 90) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=days)
    rows = []
    for symbol, offset in [("1111", 0.0), ("2222", 20.0)]:
        for i, date in enumerate(dates):
            close = 100.0 + offset + i * 0.5 + np.sin(i / 4.0)
            rows.append({
                "date": date,
                "symbol": symbol,
                "open": close - 0.2,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 20_000 + i * 10,
            })
    return pd.DataFrame(rows)


def check_prefix_invariance_and_entry() -> None:
    raw = synthetic_ohlcv(90)
    base_prefix = raw[raw["date"] <= raw["date"].drop_duplicates().sort_values().iloc[79]].copy()

    f_prefix = base.build_features(base_prefix).sort_values(["symbol", "date"]).reset_index(drop=True)
    f_full = base.build_features(raw).sort_values(["symbol", "date"]).reset_index(drop=True)
    cutoff = base_prefix["date"].max()
    f_full_hist = f_full[f_full["date"] <= cutoff].reset_index(drop=True)

    cols = ["symbol", "date"] + base.FEATURES
    left = f_prefix[cols].copy()
    right = f_full_hist[cols].copy()
    pd.testing.assert_frame_equal(left, right, check_dtype=False, rtol=1e-12, atol=1e-12)

    one = f_full[f_full["symbol"] == "1111"].reset_index(drop=True)
    i = 65
    expected_next_open = raw[raw["symbol"] == "1111"].sort_values("date").reset_index(drop=True).loc[i + 1, "open"]
    expected_exit_close = raw[raw["symbol"] == "1111"].sort_values("date").reset_index(drop=True).loc[i + 5, "close"]
    assert np.isclose(one.loc[i, "next_open"], expected_next_open)
    assert np.isclose(one.loc[i, "target5_no"], expected_exit_close / expected_next_open - 1.0)


def check_short_training_boundary() -> None:
    old_features = short.base.FEATURES
    old_start, old_end, old_fit = short.MODEL_START, short.MODEL_END, short.fit_month
    try:
        short.base.FEATURES = []
        short.MODEL_START = pd.Timestamp("2025-01-01")
        short.MODEL_END = pd.Timestamp("2025-01-31")

        rows = []
        # Sufficient causal training rows, all known before Jan 2025.
        for i in range(10_050):
            rows.append({
                "date": pd.Timestamp("2024-12-01"),
                "target_end_date": pd.Timestamp("2024-12-20"),
                "y_top10": i % 2,
                "y_loss10": (i + 1) % 2,
                "symbol": str(1000 + (i % 50)),
            })
        # Deliberately leaky-labelled row: must never enter training.
        rows.append({
            "date": pd.Timestamp("2024-12-15"),
            "target_end_date": pd.Timestamp("2025-01-03"),
            "y_top10": 1,
            "y_loss10": 0,
            "symbol": "LEAK",
        })
        rows.append({
            "date": pd.Timestamp("2025-01-10"),
            "target_end_date": pd.Timestamp("2025-01-17"),
            "y_top10": 0,
            "y_loss10": 0,
            "symbol": "PRED",
        })
        q = pd.DataFrame(rows)

        def fake_fit(train: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
            assert "LEAK" not in set(train["symbol"])
            assert train["target_end_date"].max() < pd.Timestamp("2025-01-01")
            out = pred.copy()
            out["p_top10"] = 0.5
            out["p_loss10"] = 0.5
            out["r_top10"] = 1.0
            out["r_loss10"] = 1.0
            out["core_score"] = -1.0
            return out

        short.fit_month = fake_fit
        scored = short.causal_monthly_scores(q)
        assert set(scored["symbol"]) == {"PRED"}
    finally:
        short.base.FEATURES = old_features
        short.MODEL_START, short.MODEL_END, short.fit_month = old_start, old_end, old_fit


def check_swing_training_boundary() -> None:
    old_features = swing.FEATURES
    old_periods, old_fit = swing.PREDICTION_PERIODS, swing.fit_period
    try:
        swing.FEATURES = []
        swing.PREDICTION_PERIODS = [("2025H1", "2025-01-01", "2025-06-30")]
        rows = []
        for i in range(320):
            rows.append({
                "date": pd.Timestamp("2024-12-01"),
                "target10_end": pd.Timestamp("2024-12-20"),
                "target10_no": 0.01 if i % 2 else -0.01,
                "symbol": str(2000 + (i % 40)),
            })
        rows.append({
            "date": pd.Timestamp("2024-12-15"),
            "target10_end": pd.Timestamp("2025-01-10"),
            "target10_no": 0.50,
            "symbol": "LEAK",
        })
        rows.append({
            "date": pd.Timestamp("2025-02-03"),
            "target10_end": pd.Timestamp("2025-02-17"),
            "target10_no": 0.02,
            "symbol": "PRED",
        })
        events = pd.DataFrame(rows)

        def fake_fit(train: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
            assert "LEAK" not in set(train["symbol"])
            assert train["target10_end"].max() < pd.Timestamp("2025-01-01")
            out = pred.copy()
            out["score_R"] = 0.25
            return out

        swing.fit_period = fake_fit
        scored = swing.causal_quality_predictions(events)
        assert set(scored["symbol"]) == {"PRED"}
    finally:
        swing.FEATURES = old_features
        swing.PREDICTION_PERIODS, swing.fit_period = old_periods, old_fit


def main() -> None:
    check_prefix_invariance_and_entry()
    check_short_training_boundary()
    check_swing_training_boundary()
    print("causality self-test: PASS")


if __name__ == "__main__":
    main()
