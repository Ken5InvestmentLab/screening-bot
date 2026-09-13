from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import eval_core_failed_breakdown_reclaim as mod


class FailedBreakdownReclaimContractTests(unittest.TestCase):
    def test_candidate_predicate_is_strict_on_all_three_conditions(self):
        df = pd.DataFrame(
            {
                "low": [89.0, 90.0, 89.0, 89.0],
                "prev_daily_low": [90.0, 90.0, 90.0, 90.0],
                "close": [91.0, 91.0, 90.0, 91.0],
                "open": [90.5, 90.5, 89.0, 91.0],
            }
        )
        got = mod.failed_breakdown_reclaim_mask(df).tolist()
        self.assertEqual(got, [True, False, False, False])

    def test_primary_gate_boundaries_match_frozen_spec(self):
        base = {
            "n": 20,
            "mean": 0.001,
            "median": 0.0,
            "win": 0.5001,
            "top3_removed": 0.001,
            "gross_le10": 0.10,
        }
        self.assertTrue(mod.frozen_gate(base, 20)["all_pass"])

        for key, bad in [
            ("mean", 0.0),
            ("win", 0.5),
            ("top3_removed", 0.0),
        ]:
            q = dict(base)
            q[key] = bad
            self.assertFalse(mod.frozen_gate(q, 20)["all_pass"], key)

        q = dict(base)
        q["median"] = -1e-12
        self.assertFalse(mod.frozen_gate(q, 20)["all_pass"])

        q = dict(base)
        q["gross_le10"] = 0.1000001
        self.assertFalse(mod.frozen_gate(q, 20)["all_pass"])

    def test_locked_confirmation_requires_both_preconfirmation_blocks(self):
        passed = {"frozen_gate": {"all_pass": True}}
        failed = {"frozen_gate": {"all_pass": False}}
        self.assertTrue(mod.preconfirmation_blocks_pass(passed, passed))
        self.assertFalse(mod.preconfirmation_blocks_pass(passed, failed))
        self.assertFalse(mod.preconfirmation_blocks_pass(failed, passed))
        self.assertFalse(mod.preconfirmation_blocks_pass(failed, failed))

    def test_canonical_endpoint_is_next_open_to_signal_plus_five_close(self):
        dates = [
            "2025-01-06",
            "2025-01-07",
            "2025-01-08",
            "2025-01-09",
            "2025-01-10",
            "2025-01-14",
            "2025-01-15",
        ]
        candidates = pd.DataFrame(
            {
                "symbol": ["1234"],
                "date": [dates[0]],
                "session": ["AM"],
                "session_time": [pd.Timestamp("2025-01-06 09:00")],
                "open": [100.0],
                "high": [102.0],
                "low": [98.0],
                "close": [101.0],
                "volume": [10000.0],
                "prev_daily_low": [99.0],
                "prev_daily_close": [100.0],
                "prev_daily_volume": [50000.0],
            }
        )
        daily = pd.DataFrame(
            {
                "symbol": ["1234"] * len(dates),
                "date": dates,
                "daily_open": [100, 110, 120, 130, 140, 150, 160],
                "daily_low": [90] * len(dates),
                "daily_close": [105, 115, 125, 135, 145, 165, 170],
                "daily_volume": [50000] * len(dates),
            }
        )
        out = mod.attach_canonical_label(candidates, dates, daily)
        row = out.iloc[0]
        self.assertEqual(row["entry_date"], dates[1])
        self.assertEqual(row["exit_date"], dates[5])
        self.assertEqual(float(row["entry_open"]), 110.0)
        self.assertEqual(float(row["exit_close"]), 165.0)
        self.assertAlmostEqual(float(row["canonical_ret5bd_gross"]), 0.5, places=12)
        self.assertEqual(row["endpoint_status"], "RESOLVED")


if __name__ == "__main__":
    unittest.main()
