"""PRIVATE compiler/schedule input tests; no deployment or provider calls."""
import importlib.util
from datetime import date, timedelta
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cloud_canonical_compiler", ROOT / "weak-early-beta-gate/scripts/build-canonical-input.py")
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)

class CloudCanonicalFeedTests(unittest.TestCase):
    def row(self, **changes):
        return {"detection_id": "2026-10-02|9999|silence", "signal_date": "2026-10-02", "symbol": "9999",
            "source_scope": "FORWARD_CAUSAL", "signal_actual_close": 900,
            "signal_actual_close_observed_at": "2026-10-02T16:00:00+09:00", **changes}

    def test_future_reminders_are_prepared_without_reading_future_receipts(self):
        row = self.row(sixth_xtks_exit_open=901, sixth_xtks_exit_observed_at="2026-10-13T09:01:00+09:00",
            sixth_xtks_exit_source_sha256="b" * 64, fifth_xtks_exit_close=902,
            d5_price_observed_at="2026-10-09T15:31:00+09:00", price_basis_source_sha256="c" * 64)
        with patch.object(BUILD.ADAPTER, "signal_actual_close_verified", return_value=True), \
             patch.object(BUILD.ADAPTER, "sixth_endpoint_verified", return_value=True), \
             patch.object(BUILD.ADAPTER, "is_frozen_trade", return_value=True):
            manifest = BUILD.build_manifest(pd.DataFrame([row]), "a" * 64, pd.Timestamp("2026-10-02T17:00:00+09:00"))
        self.assertEqual(manifest["observed_at"], "2026-10-02T08:00:00.000Z")
        self.assertEqual([event["kind"] for event in manifest["events"]], ["new_detection", "reminder"])
        for event in manifest["events"]:
            self.assertEqual(event["signal_actual_close"], 900)
            for endpoint in event["endpoints"].values():
                self.assertEqual(endpoint["status"], "missing")
                self.assertIsNone(endpoint["actual_price"])

    def test_holiday_build_prepares_next_business_day_without_holiday_new_detection(self):
        manifest = BUILD.build_manifest(pd.DataFrame([self.row()]), "a" * 64, pd.Timestamp("2026-10-12T17:00:00+09:00"))
        self.assertEqual([event["kind"] for event in manifest["events"]], ["reminder"])
        self.assertEqual(manifest["events"][0]["endpoints"]["d6_open"]["date"], "2026-10-13")

    def test_expired_and_historical_signals_do_not_fill_private_feed(self):
        for frame in [pd.DataFrame([self.row()]), pd.DataFrame([self.row(source_scope="EXACT_CANONICAL_2023_2026")])]:
            self.assertEqual(BUILD.build_manifest(frame, "a" * 64, pd.Timestamp("2026-10-14T08:00:00+09:00"))["events"], [])

    def test_overlapping_modes_stay_one_new_and_one_reminder(self):
        frame = pd.DataFrame([self.row(), self.row(detection_id="2026-10-02|9999|dive")])
        manifest = BUILD.build_manifest(frame, "a" * 64, pd.Timestamp("2026-10-02T17:00:00+09:00"))
        self.assertEqual(len(manifest["events"]), 2)

    def test_calendar_matches_shared_business_days_for_every_covered_date(self):
        calendar = BUILD.build_calendar()
        self.assertEqual(calendar["source_sha256"], hashlib.sha256((ROOT / "weak_early_beta/bank_calendar.py").read_bytes()).hexdigest())
        closed = set(calendar["closed_dates"])
        day, end = date.fromisoformat(calendar["start_date"]), date.fromisoformat(calendar["end_date"])
        while day <= end:
            compiled = day.weekday() < 5 and day.isoformat() not in closed
            self.assertEqual(compiled, BUILD.is_bank_business_day(day), day.isoformat())
            day += timedelta(days=1)
        with self.assertRaises(ValueError):
            BUILD.build_calendar(2024, 2030)
        with self.assertRaises(ValueError):
            BUILD.build_calendar(2025, 2031)

if __name__ == "__main__":
    unittest.main()
