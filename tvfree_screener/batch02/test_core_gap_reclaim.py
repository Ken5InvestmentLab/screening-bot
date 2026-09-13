from __future__ import annotations

import unittest

import pandas as pd

from tvfree_screener.batch02.core_gap_reclaim import build_candidate_pool, rank_candidates, select_candidates


class GapReclaimTests(unittest.TestCase):
    def test_pool_requires_partial_gap_recovery_and_high_close(self) -> None:
        frame = pd.DataFrame({
            "date": pd.to_datetime(["2023-01-02", "2023-01-02", "2023-01-02"]),
            "symbol": pd.Series(["1111", "2222", "3333"], dtype="string"),
            "open": [96.0, 96.0, 96.0],
            "high": [100.0, 100.0, 100.0],
            "low": [95.0, 95.0, 95.0],
            "close": [99.0, 100.2, 97.5],
            "volume": [1000.0, 1000.0, 1000.0],
            "gap": [-0.04, -0.04, -0.04],
            "close_location": [0.8, 1.04, 0.5],
        })

        pool, counts = build_candidate_pool(frame, start="2023-01-02", end="2023-01-02")

        self.assertEqual(pool["symbol"].tolist(), ["1111"])
        self.assertAlmostEqual(float(pool.iloc[0]["previous_close_from_gap"]), 100.0)
        self.assertAlmostEqual(float(pool.iloc[0]["gap_reclaim_fraction"]), 0.75)
        self.assertAlmostEqual(float(pool.iloc[0]["score"]), 0.775)
        self.assertEqual(counts["candidate_rows"], 1)

    def test_q80_ties_can_select_multiple_and_cooldown_uses_xtks_sessions(self) -> None:
        first = pd.DataFrame({
            "date": [pd.Timestamp("2023-01-02")] * 5,
            "symbol": pd.Series(["1111", "2222", "3333", "4444", "5555"], dtype="string"),
            "score": [0.9] * 5,
            "gap_reclaim_fraction": [0.8] * 5,
            "close_location": [1.0] * 5,
        })
        next_session = first.copy()
        next_session["date"] = pd.Timestamp("2023-01-03")
        later_session = first.copy()
        later_session["date"] = pd.Timestamp("2023-01-04")
        ranked = rank_candidates(pd.concat([first, next_session, later_session], ignore_index=True))
        sessions = pd.DatetimeIndex(pd.to_datetime(["2023-01-02", "2023-01-03", "2023-01-04"]))

        selected = select_candidates(ranked, sessions)

        self.assertEqual(int(selected["date"].eq(pd.Timestamp("2023-01-02")).sum()), 5)
        self.assertEqual(int(selected["date"].eq(pd.Timestamp("2023-01-03")).sum()), 0)
        self.assertEqual(int(selected["date"].eq(pd.Timestamp("2023-01-04")).sum()), 5)
        self.assertEqual(selected["symbol"].nunique(), 5)

    def test_future_columns_do_not_affect_candidate_pool_or_rank(self) -> None:
        frame = pd.DataFrame({
            "date": pd.to_datetime(["2023-01-02", "2023-01-02"]),
            "symbol": pd.Series(["1111", "2222"], dtype="string"),
            "open": [96.0, 95.0],
            "high": [100.0, 99.0],
            "low": [95.0, 94.0],
            "close": [99.0, 98.5],
            "volume": [1000.0, 1500.0],
            "gap": [-0.04, -0.05],
            "close_location": [0.8, 0.9],
            "future_return": [-0.5, 0.8],
        })
        base, _ = build_candidate_pool(frame, start="2023-01-02", end="2023-01-02")
        changed = frame.copy()
        changed["future_return"] = [0.99, -0.99]
        after, _ = build_candidate_pool(changed, start="2023-01-02", end="2023-01-02")

        pd.testing.assert_frame_equal(base, after)
        self.assertNotIn("future_return", base.columns)


if __name__ == "__main__":
    unittest.main()
