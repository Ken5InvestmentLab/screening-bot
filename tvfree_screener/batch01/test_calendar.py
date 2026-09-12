from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from .session_calendar import SessionCalendar


class CalendarTests(unittest.TestCase):
    def test_frozen_xtks_calendar_matches_manifest_and_known_holidays(self) -> None:
        root = Path(__file__).resolve().parent / "reference"
        data_path = root / "xtks_sessions.csv"
        manifest = json.loads((root / "xtks_sessions.manifest.json").read_text(encoding="utf-8"))
        calendar = SessionCalendar.from_csv(data_path, expected_sha256=manifest["csv_sha256"])
        self.assertEqual(len(calendar.sessions), manifest["session_count"])
        self.assertEqual(calendar.sha256, hashlib.sha256(data_path.read_bytes()).hexdigest())
        self.assertEqual(calendar.sessions[0], pd.Timestamp("2022-01-04"))
        self.assertEqual(calendar.sessions[-1], pd.Timestamp("2026-12-30"))
        self.assertNotIn(pd.Timestamp("2024-01-08"), calendar.sessions)
        self.assertNotIn(pd.Timestamp("2026-09-22"), calendar.sessions)
        self.assertNotIn(pd.Timestamp("2026-12-31"), calendar.sessions)
        self.assertEqual(calendar.shift("2024-01-05", 1), pd.Timestamp("2024-01-09"))
        self.assertEqual(calendar.shift("2024-01-09", -1), pd.Timestamp("2024-01-05"))
        self.assertEqual(calendar.shift("2026-09-11", 5).weekday(), 4)

    def test_bad_hash_or_noncontiguous_index_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sessions.csv"
            path.write_text("date,session_index\n2024-01-04,0\n2024-01-05,2\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash"):
                SessionCalendar.from_csv(path, expected_sha256="0" * 64)
            with self.assertRaisesRegex(ValueError, "contiguous"):
                SessionCalendar.from_csv(path)


if __name__ == "__main__":
    unittest.main()
