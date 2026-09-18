#!/usr/bin/env python3
"""Synthetic causal guards for the independent 2024 V3 extension (TEST ONLY)."""
from __future__ import annotations

import pandas as pd

import v3_pre2026_extension as ext


def main() -> None:
    assert ext.INPUT_CUTOFF == pd.Timestamp("2025-03-31")
    assert ext.SHORT_START == pd.Timestamp("2024-01-01")
    assert ext.SHORT_END == pd.Timestamp("2024-12-31")

    # Short extension: a label completing on/after prediction-month start must
    # never enter training. Avoid expensive fitting by inspecting the exact
    # train/pred frames passed into fit_month.
    feature_backup = ext.short_base.FEATURES
    fit_backup = ext.short.fit_month
    ext.short_base.FEATURES = []
    seen_short: list[tuple[set[str], set[str]]] = []

    rows = []
    for i in range(10000):
        rows.append({
            "date": pd.Timestamp("2023-06-01") + pd.Timedelta(days=i % 120),
            "symbol": f"T{i:05d}",
            "target_end_date": pd.Timestamp("2023-12-20"),
            "target5_no": 0.01,
            "y_top10": 0,
            "y_loss10": 0,
        })
    rows.append({
        "date": pd.Timestamp("2023-12-29"),
        "symbol": "SHORT_LEAK",
        "target_end_date": pd.Timestamp("2024-01-03"),
        "target5_no": 9.99,
        "y_top10": 1,
        "y_loss10": 0,
    })
    rows.append({
        "date": pd.Timestamp("2024-01-10"),
        "symbol": "SHORT_PRED",
        "target_end_date": pd.Timestamp("2024-01-17"),
        "target5_no": 0.02,
        "y_top10": 0,
        "y_loss10": 0,
    })
    short_df = pd.DataFrame(rows)

    def fake_short_fit(train: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
        seen_short.append((set(train["symbol"]), set(pred["symbol"])))
        out = pred.copy()
        out["r_top10"] = 0.5
        out["r_loss10"] = 0.5
        out["core_score"] = 0.0
        return out

    ext.short.fit_month = fake_short_fit
    try:
        scored = ext.short_scores_2024(short_df)
    finally:
        ext.short.fit_month = fit_backup
        ext.short_base.FEATURES = feature_backup

    assert seen_short
    first_train, first_pred = seen_short[0]
    assert "SHORT_LEAK" not in first_train
    assert "SHORT_PRED" in first_pred
    assert set(scored["model_period"]) == {"2024-01"}

    # Swing extension: same rule at the half-year boundary.
    swing_features_backup = ext.swing.FEATURES
    swing_fit_backup = ext.swing.fit_period
    ext.swing.FEATURES = []
    seen_swing: list[tuple[set[str], set[str]]] = []

    rows = []
    for i in range(300):
        rows.append({
            "date": pd.Timestamp("2023-06-01") + pd.Timedelta(days=i % 120),
            "symbol": f"S{i:04d}",
            "target10_end": pd.Timestamp("2023-12-15"),
            "target10_no": 0.01,
        })
    rows.append({
        "date": pd.Timestamp("2023-12-20"),
        "symbol": "SWING_LEAK",
        "target10_end": pd.Timestamp("2024-01-08"),
        "target10_no": 9.99,
    })
    rows.append({
        "date": pd.Timestamp("2024-02-01"),
        "symbol": "SWING_PRED",
        "target10_end": pd.Timestamp("2024-02-15"),
        "target10_no": 0.02,
    })
    swing_df = pd.DataFrame(rows)

    def fake_swing_fit(train: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
        seen_swing.append((set(train["symbol"]), set(pred["symbol"])))
        out = pred.copy()
        out["score_R"] = 0.5
        return out

    ext.swing.fit_period = fake_swing_fit
    try:
        swing_scored = ext.swing_scores_2024(swing_df)
    finally:
        ext.swing.fit_period = swing_fit_backup
        ext.swing.FEATURES = swing_features_backup

    assert seen_swing
    first_train, first_pred = seen_swing[0]
    assert "SWING_LEAK" not in first_train
    assert "SWING_PRED" in first_pred
    assert set(swing_scored["quality_model_period"]) == {"2024H1"}

    print("v3_pre2026_extension_selftest: OK")


if __name__ == "__main__":
    main()
