from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from missing_inventory_runner import run_missing_inventory


class MissingInventoryRunnerTests(unittest.TestCase):
    def test_runner_binds_exact_inputs_and_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "expected.csv"
            observed = root / "observed.csv"
            out = root / "out"
            pd.DataFrame([
                {"symbol": "7203.T", "timestamp": "2026-01-05T00:00:00Z", "timeframe": "1H", "decision_ts": "2026-01-05T01:00:00Z"},
                {"symbol": "6758.T", "timestamp": "2026-01-05T00:00:00Z", "timeframe": "1H", "decision_ts": "2026-01-05T01:00:00Z"},
            ]).to_csv(expected, index=False)
            pd.DataFrame([
                {"symbol": "7203", "timestamp": "2026-01-05T00:00:00Z", "timeframe": "1h"},
            ]).to_csv(observed, index=False)

            bundle = run_missing_inventory(expected, observed, out)
            self.assertEqual(bundle["contract"], "CORE24_REAL_MISSING_INVENTORY_V1")
            self.assertFalse(bundle["outcome_informed"])
            self.assertFalse(bundle["performance_opened"])
            self.assertEqual(bundle["builder_receipt"]["expected_n"], 2)
            self.assertEqual(bundle["builder_receipt"]["observed_expected_n"], 1)
            self.assertEqual(bundle["builder_receipt"]["missing_n"], 1)

            inv = pd.read_csv(out / "missing_inventory.csv")
            self.assertEqual(len(inv), 1)
            self.assertEqual(str(inv.iloc[0]["symbol"]), "6758")

            for key, path in (("expected_input", expected), ("observed_input", observed), ("missing_inventory_output", out / "missing_inventory.csv")):
                self.assertEqual(bundle[key]["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

            receipt = json.loads((out / "missing_inventory_receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["bundle_sha256"], bundle["bundle_sha256"])

    def test_runner_fails_closed_on_duplicate_observed_key(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "expected.csv"
            observed = root / "observed.csv"
            pd.DataFrame([
                {"symbol": "7203", "timestamp": "2026-01-05T00:00:00Z", "timeframe": "1h", "decision_ts": "2026-01-05T01:00:00Z"},
            ]).to_csv(expected, index=False)
            pd.DataFrame([
                {"symbol": "7203", "timestamp": "2026-01-05T00:00:00Z", "timeframe": "1h"},
                {"symbol": "7203.T", "timestamp": "2026-01-05T00:00:00Z", "timeframe": "1H"},
            ]).to_csv(observed, index=False)
            with self.assertRaises(ValueError):
                run_missing_inventory(expected, observed, root / "out")


if __name__ == "__main__":
    unittest.main()
