"""Pinned nominal-research receipts without invented adjusted market bars."""

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from weak_early_beta.endpoint_receipts import (
    ENDPOINT_COLUMNS, signal_actual_close_verified, sixth_endpoint_verified, sixth_economics_verified,
)
from weak_early_beta.ledger import LEDGER_COLUMNS, read_ledger, write_ledger, merge_detections
from weak_early_beta.research_endpoint_backfill import reconcile_and_backfill, verified_zip
from weak_early_beta.research_price_receipts import (
    KIND, PRICE_INPUT_SHA256, build_research_receipts, verify_research_trade,
)
from weak_early_beta.trade_basis import LEGACY_PRICE_BASIS_VERSION


class ResearchEndpointBackfillTests(unittest.TestCase):
    def fixtures(self):
        quote = {"signal_date": "2026-09-01", "symbol": "9999", "signal_close": 100.0,
                 "previous_date": "2026-08-31", "previous_close": 99.0,
                 "signal_usable": True, "previous_usable": True, "between_actions": []}
        trade = {"rule": "OPEN6", "signal_date": "2026-09-01", "signal_year": "2026", "symbol": "9999",
                 "entry_date": "2026-09-02", "scheduled_exit_date": "2026-09-09", "exit_date": "2026-09-09",
                 "entry_price": 100.0, "entry_shares": 100, "entry_cost_yen": 10000.0,
                 "exit_price": 110.0, "exit_shares": 100.0, "exit_proceeds_yen": 11000.0,
                 "gross_return": .1, "price_pl_yen": 1000.0, "applied_actions": [],
                 "status": "resolved", "reason": "sixth_open_control", "holding_sessions": 6}
        row = {**dict.fromkeys(LEDGER_COLUMNS, ""), "signal_date": "2026-09-01", "symbol": "9999",
               "detection_id": "2026-09-01|9999|volr20_low", "selector_id": "volr20_low",
               "source_scope": "EXACT_CANONICAL_2023_2026", "status": "mature", "signal_close": 12.5,
               "price_basis": LEGACY_PRICE_BASIS_VERSION, "entry_open": 12.5,
               "fifth_xtks_exit_close": 13.0, "gross_return": .04, "one_hundred_shares_pl_yen": 50.0}
        return row, quote, trade

    def built(self):
        row, quote, trade = self.fixtures()
        receipt = build_research_receipts(row, quote, trade, price_index=0, trade_index=0,
                                          peer_close=100.0, observed_at="2026-10-01T16:15:00+09:00")
        return {**row, **receipt}

    def test_nominal_receipt_has_original_record_and_no_fake_adjustment(self):
        row = self.built()
        self.assertTrue(signal_actual_close_verified(row))
        self.assertTrue(sixth_endpoint_verified(row))
        self.assertTrue(sixth_economics_verified(row))
        self.assertEqual(row["signal_close"], 12.5)
        self.assertEqual(row["signal_actual_close"], 100)
        self.assertEqual(row["entry_open"], 12.5)
        self.assertEqual(row["sixth_entry_open"], 100)
        for field in ("signal_actual_close_provenance_json", "sixth_xtks_exit_provenance_json"):
            evidence = json.loads(row[field])
            self.assertEqual(evidence["provenance_kind"], KIND)
            self.assertFalse(evidence["raw_market_refetched"])
            self.assertNotIn("adjusted_price", evidence)
            self.assertNotIn("split_factor", evidence)
        economic = json.loads(row["sixth_economics_provenance_json"])
        self.assertNotIn("adjusted_open", economic["entry"])
        self.assertEqual(economic["source_sha256"], PRICE_INPUT_SHA256)

    def test_research_record_source_and_peer_tampering_fail_closed(self):
        row = self.built()
        for key, value in (("source_package_sha256", "a" * 64), ("source_sha256", "b" * 64),
                           ("peer_nominal_close", 99), ("raw_market_refetched", True),
                           ("source_record_path", "prices/123"), ("research_record_sha256", "c" * 64)):
            with self.subTest(key=key):
                evidence = json.loads(row["signal_actual_close_provenance_json"])
                evidence[key] = value
                altered = {**row, "signal_actual_close_provenance_json": json.dumps(evidence)}
                self.assertFalse(signal_actual_close_verified(altered))
        evidence = json.loads(row["sixth_xtks_exit_provenance_json"])
        evidence["research_record"]["exit_price"] = 120
        self.assertFalse(sixth_endpoint_verified({**row, "sixth_xtks_exit_provenance_json": json.dumps(evidence)}))

    def test_identity_missing_quote_and_calendar_mismatch_are_rejected(self):
        row, quote, trade = self.fixtures()
        for bad_row, bad_quote, bad_trade in (
            ({**row, "symbol": "8888"}, quote, trade),
            (row, {**quote, "signal_usable": False}, trade),
            (row, quote, {**trade, "exit_date": "2026-09-08"}),
            (row, quote, {**trade, "entry_date": "2026-09-01"}),
        ):
            with self.assertRaises(ValueError):
                build_research_receipts(bad_row, bad_quote, bad_trade, price_index=0, trade_index=0,
                                         peer_close=100, observed_at="2026-10-01T16:15:00+09:00")

    def test_record_arithmetic_and_action_receipts_are_independently_recomputed(self):
        _, _, trade = self.fixtures()
        for changes in ({"price_pl_yen": 12000}, {"exit_shares": 200},
                        {"applied_actions": [{"effective_date": "2026-09-09", "ratio": 2}]},
                        {"applied_actions": [{"effective_date": "2026-09-02", "ratio": 2}]}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                verify_research_trade({**trade, **changes})
        split = {**trade, "exit_price": 55.0, "exit_shares": 200,
                 "applied_actions": [{"effective_date": "2026-09-09", "ratio": 2.0}]}
        self.assertEqual(verify_research_trade(split)["one_hundred_shares_pl_yen"], 1000)
        consolidation = {**trade, "exit_price": 1100.0, "exit_shares": 10,
                         "applied_actions": [{"effective_date": "2026-09-09", "ratio": .1}]}
        self.assertEqual(verify_research_trade(consolidation)["one_hundred_shares_pl_yen"], 1000)

    def test_csv_roundtrip_preserves_both_receipt_types(self):
        original, quote, trade = self.fixtures()
        # Actual 7138 research quote exposed the old %.12g cancellation error.
        trade.update(entry_price=1590.0, entry_cost_yen=159000.0,
                     exit_price=1591.0000610351562, exit_proceeds_yen=159100.00610351562,
                     price_pl_yen=100.006103515625,
                     gross_return=100.006103515625 / 159000.0)
        receipts = build_research_receipts(original, quote, trade, price_index=0, trade_index=0,
                                           peer_close=100.0, observed_at="2026-10-01T16:15:00+09:00")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            write_ledger(pd.DataFrame([{**original, **receipts}]), path)
            row = read_ledger(path).iloc[0]
        self.assertTrue(signal_actual_close_verified(row))
        self.assertTrue(sixth_endpoint_verified(row))
        self.assertTrue(sixth_economics_verified(row))
        self.assertAlmostEqual(row.sixth_one_hundred_shares_pl_yen, 100.006103515625, places=10)
        self.assertEqual(row.entry_open, 12.5)

    def test_mode_reconciliation_changes_only_new_columns_and_is_idempotent(self):
        row, quote, trade = self.fixtures()
        missing = {**row, "signal_date": "2026-09-30", "symbol": "4052",
                   "detection_id": "2026-09-30|4052|volr20_low", "source_scope": "FORWARD_CAUSAL"}
        frame = pd.DataFrame([row, missing])
        original = frame.copy(deep=True)
        compact = {"mode_rows": [row, missing], "signal_prices": {"2026-09-01|9999": 100}}
        validated = {"quotes": {"2026-09-01|9999": (0, quote)},
                     "trades": {"BASE5": {"2026-09-01|9999": (0, trade)}, "OPEN6": {"2026-09-01|9999": (0, trade)}},
                     "peer_counts": {"BASE5": 1, "OPEN6": 1}, "metric_checks": 48}
        with patch("weak_early_beta.research_endpoint_backfill.validate_research_inputs", return_value=validated):
            filled, audit, coverage = reconcile_and_backfill(frame, {}, compact, {}, observed_at="2026-10-01T16:15:00+09:00")
            repeated, second, _ = reconcile_and_backfill(filled, {}, compact, {}, observed_at="2026-10-02T16:15:00+09:00")
        pd.testing.assert_frame_equal(frame, original)
        old = [column for column in original if column not in ENDPOINT_COLUMNS]
        pd.testing.assert_frame_equal(filled[old], original[old])
        pd.testing.assert_frame_equal(filled, repeated)
        self.assertEqual(audit["changed_rows"], 1)
        self.assertEqual(second["changed_rows"], 0)
        self.assertEqual(audit["ledger_only_identities"], ["2026-09-30|4052"])
        self.assertEqual(coverage.coverage.tolist(), ["verified_research_receipts", "missing_research_price"])
        pd.testing.assert_series_equal(merge_detections(original, filled).iloc[0], original.iloc[0], check_names=False)

    def test_zip_outer_checksum_and_inner_manifest_are_both_required(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("data.json", b"{}")
                archive.writestr("manifest.json", json.dumps({"data.json": {"bytes": 2, "sha256": "a" * 64}}))
            with self.assertRaisesRegex(ValueError, "package SHA"):
                verified_zip(path, "b" * 64, "manifest.json")
            with self.assertRaisesRegex(ValueError, "member checksum"):
                verified_zip(path, hashlib.sha256(path.read_bytes()).hexdigest(), "manifest.json")


if __name__ == "__main__":
    unittest.main()
