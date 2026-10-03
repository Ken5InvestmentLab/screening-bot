"""Local-only candidate/calendar and durable-schema contract tests."""
import importlib.util
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cloud_notification_adapter",
    ROOT / "weak-early-beta-gate/scripts/build-notification-events.py")
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)


class CloudNotificationAdapterTests(unittest.TestCase):
    def row(self, **changes):
        return {"detection_id": "2026-12-28|9999|silence", "signal_date": "2026-12-28",
                "symbol": "9999", "source_scope": "FORWARD_CAUSAL", **changes}

    def test_year_boundary_and_bank_holidays_come_from_shared_calendar(self):
        events = ADAPTER.build_events(pd.DataFrame([self.row()]), "a" * 64,
            pd.Timestamp("2027-01-07T08:00:00+09:00"))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["kind"], "reminder")
        self.assertEqual(events[0]["endpoints"]["d5_close"]["date"], "2027-01-06")
        self.assertEqual(events[0]["endpoints"]["d6_open"]["date"], "2027-01-07")
        self.assertIsNone(events[0]["endpoints"]["d6_open"]["actual_price"])

    def test_conflicting_ledger_endpoint_date_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "endpoint date mismatch"):
            ADAPTER.build_events(pd.DataFrame([self.row(sixth_xtks_exit_date="2027-01-08")]),
                "a" * 64, pd.Timestamp("2027-01-08T10:00:00+09:00"))

    def test_reconstructions_and_2022_never_become_new_notifications(self):
        for row in [self.row(source_scope="EXACT_CANONICAL_2023_2026"), self.row(signal_date="2022-12-28")]:
            self.assertEqual(ADAPTER.build_events(pd.DataFrame([row]), "a" * 64,
                pd.Timestamp("2026-12-28T17:00:00+09:00")), [])

    def test_missing_d5_acquisition_is_not_synthesized_from_updated_at(self):
        event = ADAPTER.build_events(pd.DataFrame([self.row(updated_at="2027-01-07T17:00:00+09:00")]),
            "a" * 64, pd.Timestamp("2027-01-07T17:00:00+09:00"))[0]
        self.assertEqual(event["endpoints"]["d5_close"]["status"], "missing")
        self.assertIsNone(event["endpoints"]["d5_close"]["fetched_at"])

    def test_naive_time_or_missing_ledger_digest_rejected(self):
        for digest, as_of in [("a" * 64, pd.Timestamp("2026-12-28")), ("", pd.Timestamp("2026-12-28T17:00:00+09:00"))]:
            with self.assertRaises(ValueError):
                ADAPTER.build_events(pd.DataFrame(), digest, as_of)

    def test_overlapping_selectors_emit_one_stock_notification(self):
        rows = [self.row(), self.row(detection_id="2026-12-28|9999|dive")]
        events = ADAPTER.build_events(pd.DataFrame(rows), "a" * 64, pd.Timestamp("2026-12-28T17:00:00+09:00"))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["signal_id"], "2026-12-28|9999")

    def test_conflicting_verified_overlap_is_rejected(self):
        rows = [self.row(signal_actual_close=900, signal_actual_close_observed_at="2026-12-28T16:00:00+09:00"),
                self.row(detection_id="2026-12-28|9999|dive", signal_actual_close=901,
                         signal_actual_close_observed_at="2026-12-28T16:00:00+09:00")]
        # The ledger verifier has its own receipt tests; here exercise aggregation
        # after two observations have passed that boundary independently.
        with patch.object(ADAPTER, "signal_actual_close_verified", return_value=True):
            with self.assertRaisesRegex(ValueError, "conflicting overlapping"):
                ADAPTER.build_events(pd.DataFrame(rows), "a" * 64, pd.Timestamp("2026-12-28T17:00:00+09:00"))

    def test_d1_schema_is_idempotent_and_receipts_deduplicate(self):
        db = sqlite3.connect(":memory:")
        schema = (ROOT / "weak-early-beta-gate/migrations/0001_cloud_preferences.sql").read_text(encoding="utf-8")
        db.executescript(schema)
        db.executescript(schema)
        db.execute("INSERT INTO cloud_member_preferences VALUES (?, ?, ?)", ("memberA", '{}', "2026-10-04"))
        self.assertEqual(db.execute("SELECT preferences_json FROM cloud_member_preferences WHERE member_id = ?", ("memberA",)).fetchone()[0], "{}")
        values = ("memberA", "event1", "dry_run_eligible", "verified", "now", "now", 1)
        db.execute("INSERT INTO cloud_notification_deliveries VALUES (?, ?, ?, ?, ?, ?, ?)", values)
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute("INSERT INTO cloud_notification_deliveries VALUES (?, ?, ?, ?, ?, ?, ?)", values)
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute("INSERT INTO cloud_member_preferences VALUES (?, ?, ?)", ("memberB", '{broken', "now"))
        db.close()


if __name__ == "__main__":
    unittest.main()
