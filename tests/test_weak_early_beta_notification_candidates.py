"""Private candidate adapter: same reviewed prices, no result producer or sends."""
import hashlib
import importlib.util
from pathlib import Path
import unittest

import pandas as pd

from weak_early_beta.ledger import DEFAULT_LEDGER, read_ledger
from weak_early_beta.endpoint_receipts import SIGNAL_ACTUAL_COLUMNS, signal_actual_close_verified
from weak_early_beta import model
from tests import test_weak_early_beta_endpoint_receipts as endpoint_fixture

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("notification_adapter", ROOT / "weak-early-beta-gate/scripts/build-notification-events.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class NotificationCandidateTests(unittest.TestCase):
    def test_reviewed_4052_price_matches_report_without_rewriting_source(self):
        digest = hashlib.sha256(DEFAULT_LEDGER.read_bytes()).hexdigest()
        ledger = read_ledger(DEFAULT_LEDGER)
        original = ledger.copy(deep=True)
        events = adapter.build_events(ledger, digest, pd.Timestamp("2026-10-08T08:00:00+09:00"))
        target = [e for e in events if e["signal_id"] == "2026-09-30|4052"]
        self.assertEqual(len(target), 1)
        self.assertEqual(target[0]["kind"], "reminder")
        self.assertEqual(target[0]["signal_actual_close"], 1149)
        self.assertEqual(target[0]["signal_price_status"], "verified")
        self.assertEqual(target[0]["source_ledger_revision"], digest)
        self.assertEqual(target[0]["endpoints"]["d6_open"]["status"], "missing")
        pd.testing.assert_frame_equal(ledger, original)
        self.assertEqual(hashlib.sha256(DEFAULT_LEDGER.read_bytes()).hexdigest(), digest)

    def test_later_receipt_does_not_create_retrospective_price_availability(self):
        events = adapter.build_events(read_ledger(DEFAULT_LEDGER), "a" * 64,
                                      pd.Timestamp("2026-09-30T17:00:00+09:00"))
        target = [e for e in events if e["signal_id"] == "2026-09-30|4052"]
        self.assertEqual(len(target), 1)
        self.assertEqual(target[0]["kind"], "new_detection")
        self.assertIsNone(target[0]["signal_actual_close"])
        self.assertEqual(target[0]["signal_price_status"], "missing")

    def test_results_are_never_candidates_even_when_observed_today(self):
        fixture = endpoint_fixture.IndependentEndpointTests()
        ledger = fixture.attached()
        ledger["d5_price_observed_at"] = "2026-09-09T16:00:00+09:00"
        ledger["price_basis_source_sha256"] = "a" * 64
        ledger["sixth_xtks_exit_observed_at"] = "2026-09-09T16:00:00+09:00"
        events = adapter.build_events(ledger, "b" * 64, pd.Timestamp("2026-09-09T17:00:00+09:00"))
        self.assertEqual([e["kind"] for e in events], ["reminder"])

    def test_future_model_capture_and_frozen_refresh_keep_signal_receipt(self):
        fixture = endpoint_fixture.IndependentEndpointTests()
        raw = fixture.daily(count=6)
        attached = fixture.attached(raw)
        self.assertTrue(signal_actual_close_verified(attached.iloc[0]))
        original = attached.drop(columns=SIGNAL_ACTUAL_COLUMNS)
        refreshed = model.refresh_forward_endpoints(original, fixture.daily())
        self.assertTrue(signal_actual_close_verified(refreshed.iloc[0]))
        self.assertEqual(refreshed.iloc[0].signal_actual_close, 100)
        self.assertEqual(refreshed.iloc[0].one_hundred_shares_pl_yen, attached.iloc[0].one_hundred_shares_pl_yen)
