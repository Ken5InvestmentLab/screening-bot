from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from tvfree_screener.batch02 import core_multi_event_quality as research


class MultiEventSelectionTests(unittest.TestCase):
    def _frame(self) -> pd.DataFrame:
        return pd.DataFrame({
            "date": pd.to_datetime([
                "2024-01-04", "2024-01-04", "2024-01-04", "2024-01-04",
                "2024-01-04", "2024-01-04", "2024-01-04", "2024-01-05",
                "2024-01-05", "2024-01-08",
            ]),
            "symbol": ["7203", "1301", "4063", "9984", "6758", "8306", "9432", "7203", "2914", "7203"],
            "cdf_ret": [0.9, 0.7, 0.8, 0.6, 0.5, 0.4, 0.3, 0.95, 0.65, 0.85],
            "cdf_hit10": [0.5] * 10,
            "cdf_loss10": [0.1] * 10,
        })

    def test_multiple_names_per_day_and_five_name_cap(self) -> None:
        dates = pd.to_datetime(["2024-01-04", "2024-01-05", "2024-01-08"])
        picks, _ = research.select_multi_per_day(
            self._frame(), research.VARIANTS["balanced"], dates, cooldown_sessions=0,
        )
        first_day = picks.loc[picks["date"].eq(pd.Timestamp("2024-01-04"))]
        self.assertEqual(len(first_day), 5)
        self.assertEqual(first_day["symbol"].tolist(), ["7203", "4063", "1301", "9984", "6758"])
        self.assertGreater(len(first_day), 1)

    def test_cooldown_suppresses_only_the_next_xtks_session(self) -> None:
        dates = pd.to_datetime(["2024-01-04", "2024-01-05", "2024-01-08"])
        picks, _ = research.select_multi_per_day(
            self._frame(), research.VARIANTS["balanced"], dates, cooldown_sessions=1,
        )
        self.assertNotIn(
            "7203",
            picks.loc[picks["date"].eq(pd.Timestamp("2024-01-05")), "symbol"].tolist(),
        )
        self.assertIn(
            "7203",
            picks.loc[picks["date"].eq(pd.Timestamp("2024-01-08")), "symbol"].tolist(),
        )

    def test_outcome_columns_cannot_enter_feature_pool(self) -> None:
        with self.assertRaisesRegex(ValueError, "outcome columns"):
            research.build_event_pool(pd.DataFrame({"gross_return": [0.2]}), [], spec_hash="x")

    def test_feature_pool_retains_multiple_event_names_on_same_day(self) -> None:
        dates = pd.date_range("2022-07-01", periods=100, freq="B")
        rows = []
        for symbol in ("1301", "7203"):
            close = 100.0
            closes = []
            for i in range(len(dates)):
                daily_return = (0.002, 0.006, 0.010, 0.014, 0.018)[i % 5]
                close *= 1 + daily_return
                closes.append(close)
            for i, day in enumerate(dates):
                c = closes[i]
                previous = closes[i - 1] if i else c / 1.01
                rows.append({
                    "date": day, "symbol": symbol, "open": previous, "high": c * 1.01,
                    "low": c * 0.97, "close": c, "volume": 100_000,
                    "ret1": c / previous - 1 if i else 0.01,
                    "ret3": 0.035, "ret5": 0.06, "ret10": 0.12,
                    "ret20": 0.25, "ret40": 0.45,
                    "volr5_inclusive": 1.2, "volr20_inclusive": 1.5,
                    "pos20": 0.8, "pos60": 0.8, "range_pct": 0.04,
                    "close_location": 0.75, "gap": 0.0,
                })
        panel = pd.DataFrame(rows)
        pool = research.build_event_pool(panel, dates, spec_hash="frozen-test")
        self.assertFalse(pool.columns.duplicated().any())
        day = pool.loc[pool["date"].eq(pool["date"].min())]
        self.assertEqual(set(day["symbol"].astype(str)), {"1301", "7203"})
        self.assertTrue(day["event_count"].ge(1).all())

    def test_linear_head_is_finite_and_deterministic(self) -> None:
        n = 120
        train = pd.DataFrame({name: np.linspace(-1.0, 1.0, n) for name in research.MODEL_FEATURES})
        pred = train.iloc[:3].copy()
        target = pd.Series(np.linspace(-0.2, 0.3, n))
        first = research.fit_linear_head(train, pred, target)
        second = research.fit_linear_head(train, pred, target)
        self.assertEqual(first.shape, (3,))
        self.assertTrue(np.isfinite(first).all())
        np.testing.assert_allclose(first, second, rtol=0.0, atol=0.0)

    def test_training_labels_must_be_purged_before_prediction_start(self) -> None:
        n = 1005
        frame = pd.DataFrame({name: np.random.default_rng(3).normal(size=n) for name in research.MODEL_FEATURES})
        frame["exit_date"] = pd.Timestamp("2023-12-28")
        frame["gross_return"] = np.linspace(-0.2, 0.2, n)
        pred = frame.iloc[:3].copy()
        pred["date"] = pd.Timestamp("2024-01-04")
        pred["period_start"] = pd.Timestamp("2024-01-04")
        frame.loc[0, "exit_date"] = pd.Timestamp("2024-01-04")
        with self.assertRaisesRegex(ValueError, "purged"):
            research.fit_half(frame, pred)

    def test_cohort_summary_is_net_of_cost_and_bounded_to_test_period(self) -> None:
        picks = pd.DataFrame({
            "date": pd.to_datetime(["2024-01-04", "2024-01-04"]),
            "symbol": ["1301", "7203"],
            "family": [research.FAMILY] * 2,
            "spec_hash": ["x"] * 2,
            "gross_return": [0.10, 0.0],
            "label_resolved": [True, True],
            "label_status": ["RESOLVED", "RESOLVED"],
        })
        summary = research.selection_summary(
            picks,
            pd.to_datetime(["2024-01-04", "2024-01-05", "2024-01-08"]),
            start="2024-01-04",
            end="2024-01-08",
        )
        daily = summary["complete_daily_cohorts"]
        self.assertAlmostEqual(daily["mean"], 0.045)
        self.assertEqual(daily["active_days"], 1)
        self.assertEqual(daily["abstain_days"], 2)


if __name__ == "__main__":
    unittest.main()
