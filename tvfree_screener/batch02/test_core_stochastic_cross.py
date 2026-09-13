from __future__ import annotations

import unittest

import pandas as pd

from tvfree_screener.batch02.core_stochastic_cross import build_candidate_pool, rank_candidates, select_candidates


class StochasticCrossTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sessions = pd.bdate_range("2024-01-01", periods=30)

    def signal_bars(self) -> pd.DataFrame:
        rows = [{"date": day, "symbol": "1000", "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.0, "volume": 1000} for day in self.sessions[:17]]
        # Keep the prior %K below (rather than numerically equal to) 20 so
        # floating-point representation does not determine the threshold test.
        rows[14].update({"close": 9.1})
        rows[15].update({"close": 9.3})
        rows[16].update({"high": 10.0, "close": 9.8})
        return pd.DataFrame(rows)

    def test_oversold_k_cross_above_d_is_detected(self) -> None:
        pool, counts = build_candidate_pool(self.signal_bars(), self.sessions, start=self.sessions[16], end=self.sessions[16])
        self.assertEqual(counts["candidate_rows"], 1)
        self.assertGreater(pool.iloc[0]["stoch_k"], pool.iloc[0]["stoch_d"])
        self.assertLessEqual(pool.iloc[0]["previous_stoch_k"], 20.0)

    def test_no_cross_or_close_below_midrange_is_rejected(self) -> None:
        bars = self.signal_bars()
        bars.loc[bars.index[-1], "close"] = 9.4
        pool, _ = build_candidate_pool(bars, self.sessions, start=self.sessions[16], end=self.sessions[16])
        self.assertTrue(pool.empty)

    def test_missing_official_session_breaks_stochastic_lookback(self) -> None:
        pool, counts = build_candidate_pool(self.signal_bars().drop(index=4), self.sessions, start=self.sessions[16], end=self.sessions[16])
        self.assertEqual(counts["candidate_rows"], 0)
        self.assertTrue(pool.empty)

    def test_top5_and_symbol_cooldown(self) -> None:
        rows = []
        for day in self.sessions[16:18]:
            for rank, symbol in enumerate(["1000", "1001", "1002", "1003", "1004", "1005"]):
                rows.append({"date": day, "symbol": symbol, "score": 6 - rank, "close_location": 0.7, "cross_strength": 6 - rank})
        selected = select_candidates(rank_candidates(pd.DataFrame(rows)), self.sessions)
        self.assertLessEqual(int(selected.groupby("date").size().max()), 5)
        day16 = selected.loc[selected["date"].eq(self.sessions[16]), "symbol"]
        day17 = selected.loc[selected["date"].eq(self.sessions[17]), "symbol"]
        self.assertEqual(len(day16), 5)
        # Five of the six symbols selected yesterday are cooled down today.
        self.assertEqual(len(day17), 1)
        self.assertIn("1000", day16.tolist())
        self.assertEqual(day17.tolist(), ["1005"])


if __name__ == "__main__":
    unittest.main()
