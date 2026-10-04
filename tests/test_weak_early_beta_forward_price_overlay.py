import unittest
from unittest.mock import patch

import pandas as pd

from weak_early_beta.ledger import DEFAULT_LEDGER, read_ledger
from weak_early_beta.forward_price_overlay import apply_reviewed_forward_close
from weak_early_beta.endpoint_receipts import SIGNAL_ACTUAL_COLUMNS, signal_actual_close_verified
from weak_early_beta.report_preferences import select_report_view


class ForwardPriceOverlayTests(unittest.TestCase):
    def setUp(self):
        source = read_ledger(DEFAULT_LEDGER)
        self.frame = source.loc[source.symbol.eq("4052") & source.signal_date.eq(pd.Timestamp("2026-09-30"))].copy()

    def test_provider_snapshot_supplies_signal_day_not_previous_day(self):
        result = apply_reviewed_forward_close(self.frame)
        self.assertEqual(len(result), 5)
        self.assertTrue(result.signal_actual_close.eq(1149).all())
        self.assertTrue(result.apply(signal_actual_close_verified, axis=1).all())
        self.assertTrue(select_report_view(result, 1000).empty)
        self.assertEqual(len(select_report_view(result, 1149)), 5)

    def test_view_only_preserves_every_canonical_and_d6_column(self):
        before = self.frame.copy(deep=True)
        result = apply_reviewed_forward_close(self.frame)
        protected = [column for column in before if column not in SIGNAL_ACTUAL_COLUMNS]
        pd.testing.assert_frame_equal(before[protected], result[protected])
        pd.testing.assert_frame_equal(before, self.frame)

    def test_replay_is_idempotent(self):
        first = apply_reviewed_forward_close(self.frame)
        pd.testing.assert_frame_equal(first, apply_reviewed_forward_close(first))

    def test_canonical_and_other_sessions_are_not_backfilled_by_forward_snapshot(self):
        for column, value in [("source_scope", "EXACT_CANONICAL_2023_2026"), ("signal_date", pd.Timestamp("2026-09-29")), ("symbol", "9999")]:
            frame = self.frame.copy()
            frame[column] = value
            pd.testing.assert_frame_equal(frame, apply_reviewed_forward_close(frame))

    def test_changed_source_pin_fails_closed(self):
        with patch("weak_early_beta.forward_price_overlay.CSV_SHA", "0" * 64):
            with self.assertRaisesRegex(ValueError, "snapshot changed"):
                apply_reviewed_forward_close(self.frame)

    def test_invalid_claimed_verified_record_is_not_silently_overwritten(self):
        self.frame["signal_actual_close_status"] = "verified"
        with self.assertRaisesRegex(ValueError, "invalid existing"):
            apply_reviewed_forward_close(self.frame)
