from __future__ import annotations

import unittest

import pandas as pd

from tvfree_screener.batch02.core_cmf_flow_acceleration import (
    build_candidate_pool,
    rank_candidates,
    select_candidates,
)


class CmfFlowAccelerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sessions = pd.bdate_range("2024-01-01", periods=30)

    def panel(self) -> pd.DataFrame:
        rows = []
        for index, date in enumerate(self.sessions[:25]):
            for symbol, close_location in (("1000", 0.9 if index >= 15 else 0.5), ("1001", 0.5), ("1002", 0.1 if index >= 15 else 0.8)):
                close = 9.0 + 2.0 * close_location
                open_ = 10.0 if close_location <= 0.5 else 10.7
                rows.append({"date": date, "symbol": symbol, "open": open_, "high": 11.0, "low": 9.0, "close": close, "volume": 1000.0})
        return pd.DataFrame(rows)

    def test_positive_and_accelerating_cmf_is_detected(self) -> None:
        pool, counts = build_candidate_pool(self.panel(), self.sessions, start=self.sessions[20], end=self.sessions[20])
        self.assertEqual(counts["candidate_rows"], 1)
        self.assertEqual(pool["symbol"].tolist(), ["1000"])
        self.assertGreater(pool.iloc[0]["cmf5"], 0)
        self.assertGreater(pool.iloc[0]["cmf5"], pool.iloc[0]["cmf20"])

    def test_nonpositive_or_decelerating_flow_is_rejected(self) -> None:
        panel = self.panel()
        pool, _ = build_candidate_pool(panel, self.sessions, start=self.sessions[20], end=self.sessions[20])
        self.assertNotIn("1001", pool["symbol"].tolist())
        self.assertNotIn("1002", pool["symbol"].tolist())

    def test_missing_official_session_breaks_twenty_session_cmf_window(self) -> None:
        panel = self.panel().loc[lambda x: ~x["date"].eq(self.sessions[10])].copy()
        pool, counts = build_candidate_pool(panel, self.sessions, start=self.sessions[24], end=self.sessions[24])
        self.assertEqual(counts["complete_consecutive_flow_rows"], 0)
        self.assertTrue(pool.empty)

    def test_top5_allows_multiple_names_and_cools_selected_names_for_next_xtks_session(self) -> None:
        rows = []
        symbols = ["1000", "1001", "1002", "1003", "1004", "1005"]
        for day in self.sessions[20:22]:
            for rank, symbol in enumerate(symbols):
                rows.append({"date": day, "symbol": symbol, "cmf5": 0.9 - rank * 0.05, "cmf20": 0.1, "cmf_delta": 0.8 - rank * 0.05})
        selected = select_candidates(rank_candidates(pd.DataFrame(rows)), self.sessions)
        first = selected.loc[selected["date"].eq(self.sessions[20]), "symbol"].tolist()
        second = selected.loc[selected["date"].eq(self.sessions[21]), "symbol"].tolist()
        self.assertEqual(len(first), 5)
        self.assertEqual(first, symbols[:5])
        self.assertEqual(second, ["1005"])


if __name__ == "__main__":
    unittest.main()
