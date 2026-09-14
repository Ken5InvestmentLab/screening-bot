from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from prospective_shadow_session_calendar_guard import validate_xtks_calendar


class SessionCalendarGuardTests(unittest.TestCase):
    def _write_fixture(self, root: Path, dates: list[str], *, count_override=None, sha_override=None):
        csv_path = root / "sessions.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["date", "session_index"])
            w.writeheader()
            for i, d in enumerate(dates):
                w.writerow({"date": d, "session_index": i})
        sha = hashlib.sha256(csv_path.read_bytes()).hexdigest()
        manifest = {
            "calendar_id": "XTKS",
            "generator": "test",
            "generator_version": "1",
            "session_count": len(dates) if count_override is None else count_override,
            "first_session": dates[0],
            "last_session": dates[-1],
            "csv_sha256": sha if sha_override is None else sha_override,
        }
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return csv_path, manifest_path

    def test_valid_calendar_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dates = ["2026-09-14","2026-09-15","2026-09-16","2026-09-17","2026-09-18","2026-09-24","2026-09-25"]
            csv_path, manifest_path = self._write_fixture(root, dates)
            sessions, out = validate_xtks_calendar(csv_path, manifest_path, ["2026-09-15"])
            self.assertTrue(out["calendar_valid"])
            self.assertEqual(sessions, dates)

    def test_sha_mismatch_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dates = ["2026-09-14","2026-09-15","2026-09-16","2026-09-17","2026-09-18","2026-09-24"]
            csv_path, manifest_path = self._write_fixture(root, dates, sha_override="0" * 64)
            _, out = validate_xtks_calendar(csv_path, manifest_path)
            self.assertFalse(out["calendar_valid"])
            self.assertIn("calendar_csv_sha256_mismatch", out["errors"])

    def test_manifest_count_mismatch_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dates = ["2026-09-14","2026-09-15","2026-09-16"]
            csv_path, manifest_path = self._write_fixture(root, dates, count_override=99)
            _, out = validate_xtks_calendar(csv_path, manifest_path)
            self.assertFalse(out["calendar_valid"])
            self.assertIn("session_count_mismatch", out["errors"])

    def test_missing_required_signal_date_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dates = ["2026-09-14","2026-09-15","2026-09-16","2026-09-17","2026-09-18","2026-09-24"]
            csv_path, manifest_path = self._write_fixture(root, dates)
            _, out = validate_xtks_calendar(csv_path, manifest_path, ["2026-09-22"])
            self.assertFalse(out["calendar_valid"])
            self.assertIn("required_signal_dates_missing", out["errors"])

    def test_insufficient_five_session_horizon_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dates = ["2026-09-14","2026-09-15","2026-09-16","2026-09-17","2026-09-18","2026-09-24"]
            csv_path, manifest_path = self._write_fixture(root, dates)
            _, out = validate_xtks_calendar(csv_path, manifest_path, ["2026-09-15"])
            self.assertFalse(out["calendar_valid"])
            self.assertIn("required_signal_dates_lack_5bd_horizon", out["errors"])

    def test_noncontiguous_index_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dates = ["2026-09-14","2026-09-15","2026-09-16","2026-09-17","2026-09-18","2026-09-24"]
            csv_path, manifest_path = self._write_fixture(root, dates)
            rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
            rows[2]["session_index"] = "9"
            with csv_path.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["date", "session_index"])
                w.writeheader()
                w.writerows(rows)
            manifest = json.loads(manifest_path.read_text())
            manifest["csv_sha256"] = hashlib.sha256(csv_path.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest))
            _, out = validate_xtks_calendar(csv_path, manifest_path)
            self.assertFalse(out["calendar_valid"])
            self.assertIn("session_indices_not_zero_based_contiguous", out["errors"])


if __name__ == "__main__":
    unittest.main()
