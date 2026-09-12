from __future__ import annotations

import unittest

import pandas as pd

from .audit_monster_canonical import _load_v18_functions, _periodized, _signal_diagnostics, _split_pool


class MonsterCanonicalAuditTests(unittest.TestCase):
    def test_v18_selector_functions_load_without_model_runtime(self) -> None:
        functions, _source_hash = _load_v18_functions()
        self.assertEqual(functions["RMAX"], 0.3040129098415149)
        self.assertTrue(callable(functions["select_v16"]))
        self.assertTrue(callable(functions["select_v17"]))

        dates = pd.date_range("2023-02-01", periods=3, freq="B")
        rows = pd.DataFrame({
            "date": [dates[0], dates[0], dates[1], dates[2]],
            "symbol": ["1111", "2222", "3333", "4444"],
            "med_ret5": [-0.01, 0.01, -0.01, -0.01],
            "volr20": [0.4, 0.1, 0.3, 0.2],
            "ret1": [0.02, -0.1, 0.01, 0.02],
            "tail_cdf": [0.9995, 0.9999, 0.9996, 0.9997],
            "tail_p": [0.0005, 0.0001, 0.0004, 0.0003],
            "range_pct": [0.1, 0.1, 0.1, 0.1],
        })
        sessions = pd.DatetimeIndex(pd.date_range("2023-02-01", periods=5, freq="B"))
        v16 = functions["select_v16"](rows, sessions)
        v17 = functions["select_v17"](rows, sessions)
        agreed = functions["consensus"](v16, v17)
        self.assertEqual(set(agreed["symbol"]), {"1111", "3333", "4444"})

    def test_full_candidate_pool_retains_unrankable_volr20_and_multiple_per_day(self) -> None:
        date = pd.Timestamp("2024-01-04")
        tail = pd.DataFrame({
            "date": [date, date, date],
            "symbol": ["1111", "2222", "3333"],
            "tail_cdf": [0.9992, 0.9994, 0.9996],
            "ret10": [0.1, 0.2, 0.7],
            "volr20": [0.5, float("nan"), 0.7],
            "market_median_ret5_lag1": [-0.01, 0.0, -0.01],
        })
        spec = {"spec_sha256": "frozen"}
        weak, pool, counts = _split_pool(tail, spec)
        self.assertEqual(len(weak), 3)
        self.assertEqual(set(pool["symbol"]), {"1111", "2222"})
        self.assertEqual(counts["candidate_pool_rows"], 2)
        self.assertEqual(counts["maximum_candidates_per_day"], 2)
        self.assertEqual(counts["candidate_missing_volr20_retained"], 1)
        self.assertEqual(pool.loc[pool["symbol"].eq("2222"), "volr20_rank_value"].iloc[0], float("inf"))

    def test_exit_past_split_cutoff_is_purged_without_dropping_row(self) -> None:
        rows = pd.DataFrame({
            "date": pd.to_datetime(["2023-12-25", "2023-12-28"]),
            "exit_date": pd.to_datetime(["2024-01-05", "2023-12-29"]),
            "label_resolved": [True, True],
            "label_status": ["RESOLVED", "RESOLVED"],
            "gross_return": [0.2, 0.1],
        })
        purged = _periodized(rows, 2023, "2023-12-29")
        self.assertEqual(len(purged), 2)
        self.assertEqual(purged.iloc[0]["label_status"], "PURGED_SPLIT_BOUNDARY")
        self.assertFalse(bool(purged.iloc[0]["label_resolved"]))
        self.assertTrue(bool(purged.iloc[1]["label_resolved"]))

    def test_signal_diagnostics_measure_symbol_and_period_concentration(self) -> None:
        rows = pd.DataFrame({
            "date": pd.to_datetime(["2023-01-02", "2023-01-03", "2023-01-04", "2023-02-01"]),
            "symbol": ["1111", "1111", "2222", "3333"],
            "gross_return": [0.20, -0.10, 0.10, 0.30],
            "label_resolved": [True, True, True, True],
        })
        result = _signal_diagnostics(rows)
        self.assertEqual(result["n"], 4)
        self.assertEqual(result["symbol_concentration"]["unique_symbols"], 3)
        self.assertAlmostEqual(result["symbol_concentration"]["most_frequent_symbol_signal_share"], 0.5)
        self.assertIn("2023-01", result["monthly"])
        self.assertIn("2023-W01", result["weekly"])


if __name__ == "__main__":
    unittest.main()
