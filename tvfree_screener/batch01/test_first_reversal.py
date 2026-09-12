from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from .first_reversal import (
    FAMILY,
    FIRST_REVERSAL_SPEC_SHA256,
    build_first_reversal_candidate_pool,
)


class FirstReversalPoolTests(unittest.TestCase):
    def test_pool_uses_lagged_market_gate_and_keeps_all_prefilter_rows(self) -> None:
        dates = pd.bdate_range("2023-01-02", periods=80)
        rows = []
        for symbol, start, reverse in (("1111", 100.0, True), ("2222", 200.0, False), ("3333", 300.0, False)):
            close = [start] * 70
            for _ in range(9):
                close.append(close[-1] * 0.99)
            if reverse:
                close.append(close[-1] * 1.02)
            else:
                close.append(close[-1] * 0.99)
            for idx, (day, value) in enumerate(zip(dates, close, strict=True)):
                rows.append({
                    "date": day,
                    "symbol": symbol,
                    "open": value / 1.001,
                    "high": value * 1.01,
                    "low": value * 0.99,
                    "close": value,
                    "volume": 10000.0,
                })
        pool = build_first_reversal_candidate_pool(
            pd.DataFrame(rows), sessions=dates,
        )
        today = pool.loc[pool.date.eq(dates[-1])]
        self.assertEqual(today.symbol.tolist(), ["1111"])
        self.assertLessEqual(float(today.iloc[0].market_median_ret5_lag1), -0.01)
        self.assertEqual(today.iloc[0].family, FAMILY)
        self.assertEqual(today.iloc[0].spec_hash, FIRST_REVERSAL_SPEC_SHA256)
        self.assertEqual(len(pool.loc[pool.date.eq(dates[-1])]), 1)
        self.assertFalse(any(c.lower().startswith(("target", "future_", "label_")) for c in pool.columns))


if __name__ == "__main__":
    unittest.main()
