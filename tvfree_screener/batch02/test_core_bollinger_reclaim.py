from __future__ import annotations

import unittest

import pandas as pd

from tvfree_screener.batch02.core_bollinger_reclaim import build_candidate_pool, rank_candidates, select_candidates


class BollingerReclaimTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sessions = pd.bdate_range("2024-01-01", periods=30)

    def bars(self, signal_low: float, signal_close: float, signal_high: float = 10.5) -> pd.DataFrame:
        rows = [{"date": day, "symbol": "1000", "open": 10.0, "high": 10.2, "low": 9.8, "close": 10.0, "volume": 1000} for day in self.sessions[:21]]
        rows[-1] = {"date": self.sessions[20], "symbol": "1000", "open": 10.0, "high": signal_high, "low": signal_low, "close": signal_close, "volume": 1000}
        return pd.DataFrame(rows)

    def test_lower_band_excursion_then_close_reclaim_detected(self) -> None:
        pool, counts = build_candidate_pool(self.bars(9.7, 10.3), self.sessions, start=self.sessions[20], end=self.sessions[20])
        self.assertEqual(counts["candidate_rows"], 1)
        self.assertAlmostEqual(pool.iloc[0]["prior_lower_band"], 10.0)

    def test_no_excursion_close_below_band_and_weak_close_are_rejected(self) -> None:
        for low, close in ((10.0, 10.3), (9.7, 9.9), (9.7, 10.0)):
            pool, _ = build_candidate_pool(self.bars(low, close), self.sessions, start=self.sessions[20], end=self.sessions[20])
            self.assertTrue(pool.empty)

    def test_missing_official_session_breaks_twenty_session_band_history(self) -> None:
        bars = self.bars(9.7, 10.3).drop(index=5)
        pool, counts = build_candidate_pool(bars, self.sessions, start=self.sessions[20], end=self.sessions[20])
        self.assertEqual(counts["rows_with_complete_prior20_sessions"], 0)
        self.assertTrue(pool.empty)

    def test_multiple_names_daily_cap_and_cooldown(self) -> None:
        rows = []
        for symbol in ["1000", "1001", "1002", "1003", "1004", "1005"]:
            for i, day in enumerate(self.sessions[:22]):
                low, close = (9.7, 10.3) if i >= 20 else (9.8, 10.0)
                rows.append({"date": day, "symbol": symbol, "open": 10.0, "high": 10.5, "low": low, "close": close, "volume": 1000})
        pool, _ = build_candidate_pool(pd.DataFrame(rows), self.sessions, start=self.sessions[20], end=self.sessions[21])
        selected = select_candidates(rank_candidates(pool), self.sessions)
        self.assertTrue((selected.groupby("date").size() <= 5).all())
        day20 = selected.loc[selected["date"].eq(self.sessions[20]), "symbol"].tolist()
        day21 = selected.loc[selected["date"].eq(self.sessions[21]), "symbol"].tolist()
        self.assertIn("1000", day20)
        self.assertNotIn("1000", day21)


if __name__ == "__main__":
    unittest.main()
