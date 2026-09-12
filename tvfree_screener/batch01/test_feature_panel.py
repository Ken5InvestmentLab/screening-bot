from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from .feature_panel import (
    FEATURE_COLUMNS,
    LOCAL_FEATURE_COLUMNS,
    build_market_return_table,
    build_feature_panel,
    compute_symbol_features,
    _rowwise_nanmedian,
)


def sessions(count: int = 90) -> pd.DatetimeIndex:
    return pd.bdate_range("2022-01-03", periods=count)


def make_bars(days: pd.DatetimeIndex, symbol: str, slope: float = 0.2) -> pd.DataFrame:
    close = 100 + np.arange(len(days), dtype=float) * slope
    return pd.DataFrame({
        "date": days,
        "symbol": symbol,
        "open": close - 0.1,
        "high": close + 0.5,
        "low": close - 0.5,
        "close": close,
        "volume": 10000 + np.arange(len(days), dtype=float) * 10,
    })


class FeaturePanelTests(unittest.TestCase):
    def test_rowwise_partition_median_matches_numpy_with_missing_values(self) -> None:
        rng = np.random.default_rng(91)
        values = rng.normal(size=(40, 31)).astype("float32")
        values[rng.random(values.shape) < 0.35] = np.nan
        values[0, :] = np.nan
        expected = np.nanmedian(values, axis=1)
        actual = _rowwise_nanmedian(values)
        np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-7, equal_nan=True)

    def test_features_are_causal_and_exclude_outcome_columns(self) -> None:
        days = sessions()
        bars = make_bars(days, "1111")
        base = compute_symbol_features(bars, sessions=days)
        changed = bars.copy()
        changed.loc[changed.index[-1], ["open", "high", "low", "close", "volume"]] = [
            300.0, 350.0, 250.0, 320.0, 999999.0,
        ]
        altered = compute_symbol_features(changed, sessions=days)
        pd.testing.assert_frame_equal(base.iloc[:-1].reset_index(drop=True), altered.iloc[:-1].reset_index(drop=True))
        self.assertFalse(any(c.startswith(("target", "future_", "label_")) for c in base.columns))
        self.assertTrue(set(LOCAL_FEATURE_COLUMNS).issubset(base.columns))

    def test_missing_official_session_is_not_replaced_by_previous_observed_row(self) -> None:
        days = sessions()
        missing_day = days[70]
        bars = make_bars(days.delete(70), "1111")
        panel = compute_symbol_features(bars, sessions=days)
        row_after_gap = panel.loc[panel.date.eq(days[71])].iloc[0]
        self.assertTrue(pd.isna(row_after_gap.ret1))
        row_before_gap = panel.loc[panel.date.eq(days[69])].iloc[0]
        self.assertTrue(pd.notna(row_before_gap.ret1))
        self.assertNotIn(missing_day, set(panel.date))

    def test_streak_and_sharp_drop_age_reset_at_missing_session_gaps(self) -> None:
        days = sessions()
        closes = 100 + np.arange(len(days), dtype=float) * 0.1
        closes[61:65] = [94.0, 93.0, 96.0, 95.0]
        closes[66:68] = [96.0, 97.0]
        bars = pd.DataFrame({
            "date": days.delete(65),
            "symbol": "1111",
            "open": closes[np.arange(len(days)) != 65],
            "high": closes[np.arange(len(days)) != 65] * 1.01,
            "low": closes[np.arange(len(days)) != 65] * 0.99,
            "close": closes[np.arange(len(days)) != 65],
            "volume": 10000.0,
        })
        panel = compute_symbol_features(bars, sessions=days).set_index("date")
        self.assertEqual(float(panel.loc[days[61], "days_since_drop5"]), 0.0)
        self.assertEqual(float(panel.loc[days[62], "consecutive_down"]), 2.0)
        self.assertEqual(float(panel.loc[days[63], "consecutive_down"]), 0.0)
        self.assertEqual(float(panel.loc[days[64], "days_since_drop5"]), 3.0)
        self.assertTrue(pd.isna(panel.loc[days[66], "ret1"]))
        self.assertTrue(pd.isna(panel.loc[days[66], "consecutive_down"]))
        self.assertTrue(pd.isna(panel.loc[days[67], "days_since_drop5"]))

    def test_market_lag_uses_previous_official_session(self) -> None:
        days = sessions()
        first = make_bars(days, "1111", slope=0.4)
        second = make_bars(days, "2222", slope=-0.15)
        second["open"] = second["close"] + 0.1
        second["high"] = second["close"] + 0.5
        second["low"] = second["close"] - 0.5
        panel = build_feature_panel(pd.concat([first, second], ignore_index=True), sessions=days)
        self.assertTrue(set(FEATURE_COLUMNS).issubset(panel.columns))
        prior = panel.loc[panel.date.eq(days[65]), "ret5"].median()
        observed = panel.loc[panel.date.eq(days[66]), "market_median_ret5_lag1"]
        self.assertTrue(observed.eq(prior).all())
        self.assertFalse(panel.loc[panel.date.eq(days[65]), "market_median_ret5_lag1"].isna().all())

    def test_cached_market_table_uses_exact_session_close_returns(self) -> None:
        days = sessions()
        bars = pd.concat([
            make_bars(days, "1111", slope=0.4),
            make_bars(days, "2222", slope=-0.15),
        ], ignore_index=True)
        market = build_market_return_table(bars, sessions=days).set_index("date")
        expected = pd.concat([
            make_bars(days, "1111", slope=0.4).set_index("date")["close"].pct_change(5),
            make_bars(days, "2222", slope=-0.15).set_index("date")["close"].pct_change(5),
        ], axis=1).median(axis=1)
        self.assertAlmostEqual(
            float(market.loc[days[65], "market_median_ret5"]),
            float(expected.loc[days[65]]),
            places=6,
        )
        self.assertAlmostEqual(
            float(market.loc[days[66], "market_median_ret5_lag1"]),
            float(expected.loc[days[65]]),
            places=6,
        )

    def test_duplicate_or_non_calendar_rows_reject(self) -> None:
        days = sessions()
        bars = make_bars(days[:65], "1111")
        with self.assertRaisesRegex(ValueError, "duplicate symbol/date"):
            compute_symbol_features(pd.concat([bars, bars.iloc[[0]]]), sessions=days)
        holiday_like = pd.Timestamp("2022-01-01")
        invalid = bars.copy()
        invalid.loc[0, "date"] = holiday_like
        with self.assertRaisesRegex(ValueError, "outside the official session calendar"):
            compute_symbol_features(invalid, sessions=days)


if __name__ == "__main__":
    unittest.main()
