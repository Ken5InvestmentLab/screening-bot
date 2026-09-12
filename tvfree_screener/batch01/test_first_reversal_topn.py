from __future__ import annotations

import unittest

import pandas as pd

from .selection import PolicySpec, apply_selection_policy, rank_candidate_pool


class FirstReversalTopNTests(unittest.TestCase):
    def test_dd60_rank_keeps_missing_candidate_last_and_top_n_can_select_multiple(self) -> None:
        calendar = pd.DatetimeIndex(pd.to_datetime(["2023-07-03"]))
        pool = pd.DataFrame({
            "date": [calendar[0]] * 3,
            "symbol": ["1111", "2222", "3333"],
            "identity_key": ["1111", "2222", "3333"],
            "family": ["fr"] * 3,
            "spec_hash": ["pool-a"] * 3,
            "dd60": [-0.20, -0.10, float("nan")],
        })
        pool["dd60_rank_value"] = pool["dd60"].fillna(-2.0)
        pool["dd60_rank_missing"] = pool["dd60"].isna()
        ranked = rank_candidate_pool(
            pool,
            sessions=calendar,
            feature_columns=["dd60", "dd60_rank_value", "dd60_rank_missing"],
            ranking_terms=[("dd60_rank_value", False)],
        )
        self.assertEqual(ranked.symbol.tolist(), ["2222", "1111", "3333"])
        selected = apply_selection_policy(
            ranked,
            sessions=calendar,
            policy=PolicySpec("core", 2, "dd60-top2"),
        )
        self.assertEqual(selected.selected.symbol.tolist(), ["2222", "1111"])
        self.assertEqual(selected.daily.selected_count.tolist(), [2])
        self.assertEqual(selected.candidate_trace.selection_status.tolist(), ["SELECTED", "SELECTED", "ABOVE_TOP_N"])


if __name__ == "__main__":
    unittest.main()
