import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tvfree_screener.batch02.prospective_shadow_cli import (
    candidate_from_row,
    load_candidate_rows,
    load_freeze_manifest,
    read_daily_csv,
)


class ProspectiveShadowCliTests(unittest.TestCase):
    def _manifest(self, path: Path) -> dict:
        payload = {
            "experiment_id": "EXP-1",
            "model_freeze_id": "FREEZE-1",
            "frozen_at": "2026-09-14T00:00:00+09:00",
            "model_spec_sha256": "a" * 64,
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def test_manifest_sha_guard(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "freeze.json"
            self._manifest(path)
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            loaded = load_freeze_manifest(path, sha)
            self.assertEqual(loaded["model_freeze_id"], "FREEZE-1")
            with self.assertRaises(RuntimeError):
                load_freeze_manifest(path, "0" * 64)

    def test_candidate_cannot_override_freeze_identity(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "freeze.json"
            self._manifest(path)
            freeze = load_freeze_manifest(path)
            with self.assertRaises(ValueError):
                candidate_from_row({
                    "experiment_id": "OTHER",
                    "symbol": "1234",
                    "signal_date": "2026-09-14",
                    "bin_name": "AM_09_13",
                    "feature_cutoff": "2026-09-14T13:00:00+09:00",
                    "source_tag": "RAW_CAUSAL_INTRADAY",
                }, freeze)

    def test_csv_candidate_loader(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cand.csv"
            with path.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["symbol", "signal_date"])
                w.writeheader()
                w.writerow({"symbol": "1234", "signal_date": "2026-09-14"})
            rows = load_candidate_rows(path)
            self.assertEqual(rows[0]["symbol"], "1234")

    def test_daily_sessions_are_derived_without_fill(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "daily.csv"
            with path.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["symbol", "date", "open", "close"])
                w.writeheader()
                w.writerow({"symbol": "1234", "date": "2026-09-15", "open": "100", "close": "105"})
                w.writerow({"symbol": "1234", "date": "2026-09-16", "open": "106", "close": "107"})
            rows, sessions = read_daily_csv(path)
            self.assertEqual(sessions, ["2026-09-15", "2026-09-16"])
            self.assertEqual(rows[0]["open"], "100")


if __name__ == "__main__":
    unittest.main()
