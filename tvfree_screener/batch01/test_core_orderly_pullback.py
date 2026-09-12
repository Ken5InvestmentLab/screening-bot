from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from .core_orderly_pullback import FAMILY_SPEC, build_candidate_pool, rank_orderly_pool
from .core_orderly_pullback_audit import _family_gate
from .selection import PolicySpec, apply_selection_policy


class OrderlyPullbackTests(unittest.TestCase):
    @staticmethod
    def panel() -> tuple[pd.DataFrame, pd.DatetimeIndex]:
        sessions = pd.date_range("2023-01-04", periods=25, freq="B")
        rows = []
        for symbol, daily_returns, vol_trend in (
            ("1001", np.full(25, 0.005), 0.5),
            ("1002", np.tile([0.02, -0.018], 13)[:25], 0.9),
            ("1003", np.full(25, 0.004), 0.4),
            ("1004", np.full(25, 0.004), 0.4),
        ):
            for index, day in enumerate(sessions):
                rows.append({
                    "date": day, "symbol": symbol,
                    "open": 100.0, "high": 102.0, "low": 98.0,
                    "close": 100.0, "volume": 1000.0,
                    "ret1": float(daily_returns[index]),
                    "ret5": 0.01, "ret20": 0.05,
                    "volume_trend5_20": vol_trend,
                })
        frame = pd.DataFrame(rows)
        last = sessions[-1]
        frame.loc[frame["date"].eq(last) & frame["symbol"].isin(["1001", "1002", "1003", "1004"]), "ret5"] = -0.02
        frame.loc[frame["date"].eq(last) & frame["symbol"].eq("1001"), "ret20"] = 0.10
        frame.loc[frame["date"].eq(last) & frame["symbol"].eq("1002"), "ret20"] = 0.05
        frame.loc[frame["date"].eq(last) & frame["symbol"].eq("1003"), "volume"] = 0.0
        prior = sessions[-2]
        frame.loc[frame["date"].eq(prior) & frame["symbol"].eq("1004"), "ret1"] = np.nan
        return frame, sessions

    def test_prefilter_and_path_quality_are_signal_time_only(self) -> None:
        panel, sessions = self.panel()
        panel["future_return"] = np.arange(len(panel), dtype=float)
        pool = build_candidate_pool(panel, spec_hash="frozen")
        result = rank_orderly_pool(pool, sessions=sessions)
        final = result.loc[result["date"].eq(sessions[-1])]
        self.assertEqual(set(final["symbol"]), {"1001", "1002"})
        self.assertEqual(len(final), 2)
        self.assertNotIn("future_return", result.columns)
        self.assertGreater(
            float(final.set_index("symbol").loc["1001", "path_efficiency20"]),
            float(final.set_index("symbol").loc["1002", "path_efficiency20"]),
        )
        self.assertGreater(float(final.set_index("symbol").loc["1001", "score"]), 0.5)

    def test_future_column_perturbation_does_not_change_candidate_pool(self) -> None:
        panel, _sessions = self.panel()
        first = build_candidate_pool(panel.assign(future_label=0.0), spec_hash="frozen")
        second = build_candidate_pool(panel.assign(future_label=1e9), spec_hash="frozen")
        pd.testing.assert_frame_equal(first, second)

    def test_top_n_policy_can_select_multiple_names_on_one_day(self) -> None:
        panel, sessions = self.panel()
        pool = build_candidate_pool(panel, spec_hash="frozen")
        ranked = rank_orderly_pool(pool, sessions=sessions)
        policy = PolicySpec("core", 2, "orderly-pullback-top2")
        selected = apply_selection_policy(
            ranked, sessions=sessions, policy=policy,
        ).selected
        same_day = selected.loc[selected["date"].eq(sessions[-1])]
        self.assertEqual(set(same_day["symbol"]), {"1001", "1002"})
        self.assertTrue(FAMILY_SPEC["selection"]["multiple_names_per_day"])

    def test_missing_return_in_path_invalidates_only_that_candidate(self) -> None:
        panel, sessions = self.panel()
        result = build_candidate_pool(panel, spec_hash="frozen")
        final = result.loc[result["date"].eq(sessions[-1])]
        self.assertNotIn("1004", set(final["symbol"]))

    def test_family_gate_rejects_negative_or_unmeasurable_pool(self) -> None:
        signal = {"round_trip_cost_scenarios": {"0.005": {
            "mean": 0.02, "median": 0.01, "mean_excluding_top3_winners": 0.005,
        }}}
        positive_cohorts = {
            "mean": 0.02, "median": 0.01, "mean_excluding_top3_winners": 0.005,
        }
        self.assertEqual(_family_gate(signal, positive_cohorts)[0], "KEEP")
        self.assertEqual(_family_gate(signal, {key: None for key in positive_cohorts})[0], "INCONCLUSIVE_INCOMPLETE_POOL_COHORT_COVERAGE")
        signal["round_trip_cost_scenarios"]["0.005"]["mean"] = -0.001
        self.assertEqual(_family_gate(signal, positive_cohorts)[0], "REJECT")


if __name__ == "__main__":
    unittest.main()
