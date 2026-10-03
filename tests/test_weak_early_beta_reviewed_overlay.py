"""A private report overlay never becomes an implicit ledger migration."""

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from tests import test_weak_early_beta_research_backfill as research_fixtures
from weak_early_beta.endpoint_receipts import ENDPOINT_COLUMNS, sixth_economics_verified
from weak_early_beta.reviewed_endpoint_overlay import (
    apply_reviewed_endpoint_overlay, build_reviewed_endpoint_overlay, load_reviewed_endpoint_overlay,
)
from weak_early_beta.research_price_receipts import build_research_receipts


class ReviewedOverlayTests(unittest.TestCase):
    def fixtures(self):
        fixture = research_fixtures.ResearchEndpointBackfillTests()
        original, _, _ = fixture.fixtures()
        reviewed = fixture.built()
        alternate = {"selector_id": "body_low", "detection_id": "2026-09-01|9999|body_low"}
        raw = pd.DataFrame([original, {**original, **alternate}])
        filled = pd.DataFrame([reviewed, {**reviewed, **alternate}])
        encoded, manifest = build_reviewed_endpoint_overlay(raw, filled, audit={
            "input_ledger_sha256": "a" * 64, "source_packages": [],
            "observed_at": "2026-10-01T16:15:00+09:00",
        })
        return raw, filled, encoded, manifest

    def test_deduplicated_receipts_preserve_raw_and_all_d5_values(self):
        raw, filled, encoded, manifest = self.fixtures()
        original = raw.copy(deep=True)
        self.assertEqual(manifest["signal_identities"], 1)
        self.assertEqual(manifest["mode_rows"], 2)
        revised, audit = apply_reviewed_endpoint_overlay(raw, json.loads(encoded))
        pd.testing.assert_frame_equal(raw, original)
        prior = [column for column in raw if column not in ENDPOINT_COLUMNS]
        pd.testing.assert_frame_equal(raw[prior], revised[prior])
        self.assertTrue(revised.apply(sixth_economics_verified, axis=1).all())
        self.assertEqual(audit["counts"], {"applied": 2})
        repeated, _ = apply_reviewed_endpoint_overlay(revised, json.loads(encoded))
        pd.testing.assert_frame_equal(revised, repeated)

    def test_future_and_unlisted_mode_rows_are_untouched(self):
        raw, _, encoded, _ = self.fixtures()
        future = raw.iloc[0].to_dict()
        future.update(signal_date="2026-09-30", symbol="4052", detection_id="2026-09-30|4052|volr20_low",
                      source_scope="FORWARD_CAUSAL")
        new_mode = {**raw.iloc[0].to_dict(), "selector_id": "unknown", "detection_id": "2026-09-01|9999|unknown"}
        expanded = pd.concat([raw, pd.DataFrame([future, new_mode])], ignore_index=True)
        revised, audit = apply_reviewed_endpoint_overlay(expanded, json.loads(encoded))
        pd.testing.assert_frame_equal(expanded.iloc[2:], revised.iloc[2:], check_dtype=False)
        self.assertEqual(audit["counts"]["unmatched_untouched"], 2)

    def test_changed_baseline_or_scope_fails_closed(self):
        raw, _, encoded, _ = self.fixtures()
        for field, value in (("entry_open", 100), ("gross_return", .1),
                             ("source_scope", "FORWARD_CAUSAL"), ("signal_close", 100)):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "baseline changed"):
                altered = raw.copy()
                altered.loc[0, field] = value
                apply_reviewed_endpoint_overlay(altered, json.loads(encoded))

    def test_quarantine_and_existing_valid_receipts_are_not_overwritten(self):
        raw, filled, encoded, _ = self.fixtures()
        quarantined = filled.copy()
        quarantined.loc[0, "sixth_xtks_exit_status"] = "quarantined"
        quarantined.loc[0, "sixth_xtks_exit_open"] = float("nan")
        quarantined.loc[0, "sixth_economics_status"] = "review_required"
        revised, audit = apply_reviewed_endpoint_overlay(quarantined, json.loads(encoded))
        pd.testing.assert_series_equal(quarantined.iloc[0], revised.iloc[0])
        self.assertEqual(audit["counts"]["review_untouched"], 1)
        verified, _ = apply_reviewed_endpoint_overlay(raw, json.loads(encoded))
        original_receipt = verified.loc[0, "sixth_xtks_exit_provenance_json"]
        again, _ = apply_reviewed_endpoint_overlay(verified, json.loads(encoded))
        self.assertEqual(again.loc[0, "sixth_xtks_exit_provenance_json"], original_receipt)

    def test_pinned_sha_and_invalid_endpoint_receipt_fail_closed(self):
        raw, _, encoded, manifest = self.fixtures()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private.json"
            path.write_bytes(encoded)
            overlay = load_reviewed_endpoint_overlay(path, expected_sha256=manifest["sha256"])
            self.assertEqual(len(overlay["records"]), 1)
            path.write_bytes(encoded + b" ")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                load_reviewed_endpoint_overlay(path, expected_sha256=manifest["sha256"])
        tampered = json.loads(encoded)
        tampered["records"]["2026-09-01|9999"]["receipts"]["sixth_xtks_exit_open"] = 120
        with self.assertRaisesRegex(ValueError, "invalid reviewed endpoint"):
            apply_reviewed_endpoint_overlay(raw, tampered)

    def test_valid_but_conflicting_entry_economics_fail_closed(self):
        raw, _, encoded, _ = self.fixtures()
        fixture = research_fixtures.ResearchEndpointBackfillTests()
        original, quote, trade = fixture.fixtures()
        trade.update(entry_price=90, entry_cost_yen=9000, gross_return=2000/9000, price_pl_yen=2000)
        different = build_research_receipts(original, quote, trade, price_index=0, trade_index=0,
                                            peer_close=100, observed_at="2026-10-01T16:15:00+09:00")
        for column, value in different.items():
            raw.at[0, column] = value
        self.assertTrue(sixth_economics_verified(raw.iloc[0]))
        with self.assertRaisesRegex(ValueError, "conflicting reviewed D6 economics"):
            apply_reviewed_endpoint_overlay(raw, json.loads(encoded))


if __name__ == "__main__":
    unittest.main()
