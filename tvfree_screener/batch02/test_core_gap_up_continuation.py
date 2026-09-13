from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from tvfree_screener.batch02.core_gap_up_continuation import build_candidate_pool, rank_candidates, select_candidates


class GapUpContinuationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sessions = pd.bdate_range("2024-01-01", periods=30)

    def panel(self) -> pd.DataFrame:
        rows = []
        for symbol, overrides in (
            ("1000", {}),
            ("1001", {"gap": -0.01}),
            ("1002", {"volr20_prevavg": 1.2}),
            ("1003", {"close_location": 0.6}),
            ("1004", {"body_pct": -0.1}),
            ("1005", {"gap": np.nan}),
        ):
            row = {"date": self.sessions[20], "symbol": symbol, "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.8, "volume": 1000, "gap": 0.02, "volr20_prevavg": 2.0, "close_location": 0.9, "body_pct": 0.2}
            row.update(overrides)
            rows.append(row)
        return pd.DataFrame(rows)

    def test_strong_positive_gap_volume_and_close_detected(self) -> None:
        pool, counts = build_candidate_pool(self.panel(), self.sessions, start=self.sessions[20], end=self.sessions[20])
        self.assertEqual(counts["candidate_rows"], 1)
        self.assertEqual(pool.iloc[0]["symbol"], "1000")

    def test_each_frozen_event_gate_rejects_weak_rows(self) -> None:
        pool, _ = build_candidate_pool(self.panel(), self.sessions, start=self.sessions[20], end=self.sessions[20])
        self.assertEqual(pool["symbol"].tolist(), ["1000"])

    def test_equal_weight_percentile_ranks_are_deterministic(self) -> None:
        pool = pd.DataFrame([
            {"date": self.sessions[20], "symbol": "1000", "gap": 0.03, "volr20_prevavg": 3.0, "close_location": 0.9},
            {"date": self.sessions[20], "symbol": "1001", "gap": 0.02, "volr20_prevavg": 2.0, "close_location": 0.8},
        ])
        ranked = rank_candidates(pool)
        self.assertEqual(ranked.iloc[0]["symbol"], "1000")
        self.assertEqual(ranked.iloc[0]["score"], 1.0)
        self.assertEqual(ranked.iloc[1]["score"], 0.5)

    def test_top5_multiple_names_and_next_session_cooldown(self) -> None:
        rows = []
        symbols = ["1000", "1001", "1002", "1003", "1004", "1005"]
        for day in self.sessions[20:22]:
            for rank, symbol in enumerate(symbols):
                rows.append({"date": day, "symbol": symbol, "gap": 0.04 - rank * 0.002, "volr20_prevavg": 4.0 - rank * 0.2, "close_location": 0.95 - rank * 0.03})
        selected = select_candidates(rank_candidates(pd.DataFrame(rows)), self.sessions)
        day20 = selected.loc[selected["date"].eq(self.sessions[20]), "symbol"].tolist()
        day21 = selected.loc[selected["date"].eq(self.sessions[21]), "symbol"].tolist()
        self.assertEqual(len(day20), 5)
        self.assertEqual(day20, ["1000", "1001", "1002", "1003", "1004"])
        self.assertEqual(day21, ["1005"])


if __name__ == "__main__":
    unittest.main()
