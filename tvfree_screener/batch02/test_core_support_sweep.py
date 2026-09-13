from __future__ import annotations

import unittest

import pandas as pd

from tvfree_screener.batch02.core_support_sweep import build_candidate_pool, rank_candidates, select_candidates


class SupportSweepTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sessions = pd.bdate_range("2024-01-01", periods=12)

    def test_undercut_then_reclaim_with_strong_close_is_detected(self) -> None:
        rows = []
        for i, day in enumerate(self.sessions[:7]):
            low = 10.0 if i < 6 else 9.8
            close = 10.4 if i < 6 else 10.4
            high = 10.5
            rows.append({"date": day, "symbol": "1000", "open": 10.1, "high": high, "low": low, "close": close, "volume": 1000})
        pool, counts = build_candidate_pool(pd.DataFrame(rows), self.sessions, start=self.sessions[6], end=self.sessions[6])
        self.assertEqual(counts["candidate_rows"], 1)
        self.assertEqual(pool.iloc[0]["prior5_low"], 10.0)

    def test_no_undercut_or_weak_close_is_rejected(self) -> None:
        rows = []
        for i, day in enumerate(self.sessions[:7]):
            low, close = (10.0, 10.4) if i < 6 else (10.01, 10.2)
            rows.append({"date": day, "symbol": "1000", "open": 10.1, "high": 10.5, "low": low, "close": close, "volume": 1000})
        pool, _ = build_candidate_pool(pd.DataFrame(rows), self.sessions, start=self.sessions[6], end=self.sessions[6])
        self.assertTrue(pool.empty)

    def test_missing_official_session_breaks_support_window(self) -> None:
        rows = []
        for i, day in enumerate(self.sessions[:7]):
            if i == 4:
                continue
            low, close = (10.0, 10.4) if i < 6 else (9.8, 10.4)
            rows.append({"date": day, "symbol": "1000", "open": 10.1, "high": 10.5, "low": low, "close": close, "volume": 1000})
        pool, counts = build_candidate_pool(pd.DataFrame(rows), self.sessions, start=self.sessions[6], end=self.sessions[6])
        self.assertEqual(counts["rows_with_complete_prior5_sessions"], 0)
        self.assertTrue(pool.empty)

    def test_max_five_names_and_previous_session_symbol_cooldown(self) -> None:
        rows = []
        for sym in ["1000", "1001", "1002", "1003", "1004", "1005"]:
            for i, day in enumerate(self.sessions[:8]):
                low, close = (10.0, 10.4) if i < 6 else ((9.8, 10.4) if i == 6 else (9.7, 10.4))
                rows.append({"date": day, "symbol": sym, "open": 10.1, "high": 10.5, "low": low, "close": close, "volume": 1000})
        pool, _ = build_candidate_pool(pd.DataFrame(rows), self.sessions, start=self.sessions[6], end=self.sessions[7])
        selected = select_candidates(rank_candidates(pool), self.sessions)
        self.assertTrue((selected.groupby("date").size() <= 5).all())
        day6 = selected.loc[selected["date"].eq(self.sessions[6]), "symbol"].tolist()
        day7 = selected.loc[selected["date"].eq(self.sessions[7]), "symbol"].tolist()
        self.assertIn("1000", day6)
        self.assertNotIn("1000", day7)


if __name__ == "__main__":
    unittest.main()
