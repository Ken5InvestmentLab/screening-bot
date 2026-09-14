import unittest
import pandas as pd
from ohlcv_supplement import build_missing_inventory

class MissingInventoryTests(unittest.TestCase):
    def test_exact_expected_minus_observed_only(self):
        expected = pd.DataFrame([
            {"symbol":"7203.T","timestamp":"2025-08-01T05:00:00Z","timeframe":"1h","decision_ts":"2025-08-01T06:00:00Z"},
            {"symbol":"6758","timestamp":"2025-08-01T05:00:00Z","timeframe":"1h","decision_ts":"2025-08-01T06:00:00Z"},
        ])
        observed = pd.DataFrame([
            {"symbol":"7203","timestamp":"2025-08-01T05:00:00Z","timeframe":"1H"},
            {"symbol":"9999","timestamp":"2025-08-01T05:00:00Z","timeframe":"1h"},
        ])
        inv, receipt = build_missing_inventory(expected, observed)
        self.assertEqual(inv["symbol"].tolist(), ["6758"])
        self.assertEqual(receipt["expected_n"], 2)
        self.assertEqual(receipt["observed_expected_n"], 1)
        self.assertEqual(receipt["missing_n"], 1)
        self.assertEqual(receipt["unexpected_observed_n"], 1)
        self.assertFalse(receipt["performance_opened"])
        self.assertFalse(receipt["outcome_informed"])
        self.assertEqual(len(receipt["receipt_sha256"]), 64)

    def test_duplicate_observed_pair_fails_closed(self):
        expected = pd.DataFrame([{"symbol":"7203","timestamp":"2025-08-01T05:00:00Z","timeframe":"1h","decision_ts":"2025-08-01T06:00:00Z"}])
        observed = pd.DataFrame([
            {"symbol":"7203","timestamp":"2025-08-01T05:00:00Z","timeframe":"1h"},
            {"symbol":"7203.T","timestamp":"2025-08-01T05:00:00Z","timeframe":"1H"},
        ])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_missing_inventory(expected, observed)

if __name__ == "__main__":
    unittest.main()
