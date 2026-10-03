"""Actual D6 receipts, canonical migration and independent freeze contracts."""

import json
import hashlib
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import pandas as pd

from weak_early_beta import model
from weak_early_beta.cli import command_backfill_endpoints, parser
from weak_early_beta.corporate_actions import action_table, normalize_daily
from weak_early_beta.endpoint_receipts import (
    ENDPOINT_COLUMNS, SIXTH_ECONOMIC_COLUMNS, build_endpoint_receipts,
    signal_actual_close_verified, sixth_economics_verified, sixth_endpoint_verified,
    source_digest,
)
from weak_early_beta.ledger import backfill_verified_endpoints, merge_detections, read_ledger, write_ledger
from weak_early_beta.trade_basis import ECONOMIC_COLUMNS, LEGACY_PRICE_BASIS_VERSION


class IndependentEndpointTests(unittest.TestCase):
    @staticmethod
    def daily(ratio=1.0, *, count=7):
        actual = [100, 100, 101, 103, 105, 110, 110 / ratio][:count]
        factors = [ratio] * min(count, 6) + ([1] if count == 7 else [])
        adjusted = [price / factor for price, factor in zip(actual, factors)]
        return normalize_daily(pd.DataFrame({
            "date": pd.bdate_range("2026-09-01", periods=count), "symbol": "9999",
            "open": adjusted, "high": [price + 1 for price in adjusted],
            "low": [price - 1 for price in adjusted], "close": adjusted,
            "volume": [10_000 * factor for factor in factors],
            "split_ratio": [0] * min(count, 6) + ([ratio if ratio != 1 else 0] if count == 7 else []),
        }))

    @staticmethod
    def selected():
        return pd.DataFrame([{"date": pd.Timestamp("2026-09-01"), "symbol": "9999",
                              "selector": "volr20_low", "model_period": "2026-09"}])

    def attached(self, raw=None):
        return model.attach_forward_rows(self.selected(), self.daily() if raw is None else raw)

    def legacy(self):
        frame = self.attached().drop(columns=ENDPOINT_COLUMNS)
        frame["source_scope"] = "EXACT_CANONICAL_2023_2026"
        frame["price_basis"] = LEGACY_PRICE_BASIS_VERSION
        frame["signal_close"] = 12.5  # Deliberately a vendor-adjusted reference.
        frame["entry_open"] = 12.5
        return frame

    def test_calendar_meaning_is_detection_plus_one_five_and_six(self):
        row = self.attached().iloc[0]
        self.assertEqual(row.entry_date, pd.Timestamp("2026-09-02"))
        self.assertEqual(row.fifth_xtks_exit_date, pd.Timestamp("2026-09-08"))
        self.assertEqual(row.sixth_xtks_exit_date, pd.Timestamp("2026-09-09"))

    def test_year_end_holidays_do_not_count_as_sessions(self):
        selected = self.selected()
        selected["date"] = pd.Timestamp("2025-12-24")
        raw = self.daily(count=1)[["date", "symbol", "open", "high", "low", "close", "volume", "split_ratio"]]
        raw["date"] = pd.Timestamp("2025-12-24")
        row = model.attach_forward_rows(selected, normalize_daily(raw)).iloc[0]
        self.assertEqual(row.entry_date, pd.Timestamp("2025-12-25"))
        self.assertEqual(row.fifth_xtks_exit_date, pd.Timestamp("2026-01-05"))
        self.assertEqual(row.sixth_xtks_exit_date, pd.Timestamp("2026-01-06"))

    def test_d5_freeze_does_not_prevent_d6_capture_and_split_economics(self):
        original = self.attached(self.daily(count=6))
        self.assertEqual(original.iloc[0].status, "mature")
        self.assertFalse(sixth_endpoint_verified(original.iloc[0]))
        refreshed = model.refresh_forward_endpoints(original, self.daily(ratio=2))
        row = refreshed.iloc[0]
        pd.testing.assert_series_equal(row[ECONOMIC_COLUMNS], original.iloc[0][ECONOMIC_COLUMNS], check_names=False)
        self.assertTrue(sixth_endpoint_verified(row))
        self.assertTrue(sixth_economics_verified(row))
        self.assertEqual(row.sixth_xtks_exit_open, 55)
        self.assertEqual(row.sixth_exit_shares, 200)
        self.assertEqual(row.sixth_one_hundred_shares_pl_yen, 1000)
        self.assertAlmostEqual(row.sixth_gross_return, .1)

    def test_d6_consolidation_uses_original_lot(self):
        row = self.attached(self.daily(ratio=.1)).iloc[0]
        self.assertEqual(row.sixth_xtks_exit_open, 1100)
        self.assertEqual(row.sixth_exit_shares, 10)
        self.assertAlmostEqual(row.sixth_gross_return, .1)
        self.assertEqual(row.sixth_one_hundred_shares_pl_yen, 1000)

    def test_fractional_liquidation_keeps_price_but_not_invented_economics(self):
        row = self.attached(self.daily(ratio=.003)).iloc[0]
        self.assertTrue(sixth_endpoint_verified(row))
        self.assertEqual(row.sixth_economics_status, "review_required")
        self.assertTrue(pd.isna(row.sixth_gross_return))
        self.assertTrue(pd.isna(row.sixth_one_hundred_shares_pl_yen))

    def test_missing_d6_is_blank_not_d5_close_or_zero(self):
        row = self.attached(self.daily(count=6)).iloc[0]
        self.assertEqual(row.sixth_xtks_exit_status, "pending")
        self.assertTrue(pd.isna(row.sixth_xtks_exit_open))
        self.assertFalse(sixth_endpoint_verified(row))

    def test_quarantine_never_unlocks(self):
        raw = self.daily()[["date", "symbol", "open", "high", "low", "close", "volume", "split_ratio"]]
        raw.loc[6, "close"] = 999
        row = self.attached(normalize_daily(raw)).iloc[0]
        self.assertEqual(row.sixth_xtks_exit_status, "quarantined")
        self.assertTrue(pd.isna(row.sixth_xtks_exit_open))
        self.assertFalse(sixth_endpoint_verified(row))

    def test_missing_entry_does_not_stop_actual_d6_price_receipt(self):
        raw = self.daily()
        raw = raw[raw.date.ne(pd.Timestamp("2026-09-02"))]
        row = self.attached(raw).iloc[0]
        self.assertTrue(sixth_endpoint_verified(row))
        self.assertEqual(row.sixth_economics_status, "pending")
        self.assertTrue(pd.isna(row.sixth_gross_return))

    def test_morning_eight_is_not_an_observed_result(self):
        raw = self.daily()
        base = self.legacy().iloc[0].to_dict()
        receipt = build_endpoint_receipts(base, raw.set_index(["symbol", "date"]), action_table(raw),
                                         digest=source_digest(raw), observed_at="2026-09-09T08:00:00+09:00")
        self.assertEqual(receipt["sixth_xtks_exit_status"], "pending")
        self.assertTrue(pd.isna(receipt["sixth_xtks_exit_open"]))
        self.assertFalse(sixth_endpoint_verified({**base, **receipt}))

    def test_no_signal_close_alias_and_receipt_has_price_lineage(self):
        original = self.legacy()
        filled, _ = backfill_verified_endpoints(original, self.daily(ratio=2), source_sha256="a" * 64,
                                                observed_at="2026-10-01T16:15:00+09:00", identities=original.detection_id)
        row = filled.iloc[0]
        self.assertEqual(row.signal_close, 12.5)
        self.assertEqual(row.signal_actual_close, 100)
        self.assertEqual(row.entry_open, 12.5)
        self.assertEqual(row.sixth_entry_open, 100)
        self.assertTrue(signal_actual_close_verified(row))
        provenance = json.loads(row.signal_actual_close_provenance_json)
        self.assertEqual(provenance["adjusted_price"], 50)
        self.assertEqual(provenance["split_factor"], 2)
        self.assertEqual(provenance["source_sha256"], "a" * 64)

    def test_canonical_normal_upsert_and_refresh_cannot_backfill(self):
        original = self.legacy()
        incoming = self.attached()
        merged = merge_detections(original, incoming)
        refreshed = model.refresh_forward_endpoints(original, self.daily())
        for frame in (merged, refreshed):
            self.assertTrue(pd.isna(frame.iloc[0].sixth_xtks_exit_open))
            self.assertEqual(frame.iloc[0].signal_close, 12.5)
            self.assertEqual(frame.iloc[0].entry_open, 12.5)

    def test_explicit_backfill_is_idempotent_and_only_changes_endpoint_columns(self):
        original = self.legacy()
        filled, receipt = backfill_verified_endpoints(original, self.daily(), source_sha256="a" * 64,
                                                      observed_at="2026-10-01T16:15:00+09:00", identities=original.detection_id)
        repeated, second = backfill_verified_endpoints(filled, self.daily(), source_sha256="b" * 64,
                                                       observed_at="2026-10-02T16:15:00+09:00", identities=original.detection_id)
        pd.testing.assert_frame_equal(filled[original.columns], original)
        pd.testing.assert_frame_equal(filled, repeated)
        self.assertEqual(receipt["changed_count"], 1)
        self.assertEqual(second["changed_count"], 0)
        self.assertFalse(receipt["d5_economics_modified"])

    def test_explicit_backfill_rejects_unknown_identity_and_missing_hash(self):
        original = self.legacy()
        for digest, identities in (("", original.detection_id), ("a" * 64, ["unknown"]), ("a" * 64, [])):
            with self.subTest(digest=digest, identities=list(identities)), self.assertRaises(ValueError):
                backfill_verified_endpoints(original, self.daily(), source_sha256=digest,
                                            observed_at="2026-10-01T16:15:00+09:00", identities=identities)

    def test_replay_preserves_verified_d6_and_close_receipts(self):
        original = self.attached()
        missing = self.attached(self.daily(count=1))
        replay = merge_detections(original, missing)
        pd.testing.assert_series_equal(original.iloc[0][ENDPOINT_COLUMNS], replay.iloc[0][ENDPOINT_COLUMNS], check_names=False)
        refreshed = model.refresh_forward_endpoints(original, self.daily(count=1))
        pd.testing.assert_frame_equal(original, refreshed)

    def test_malformed_or_unverified_receipts_do_not_unlock(self):
        original = self.attached().iloc[0].to_dict()
        for column, value in (("sixth_xtks_exit_status", "pending"), ("sixth_xtks_exit_open", 0),
                              ("sixth_xtks_exit_open", float("inf")), ("sixth_xtks_exit_source_sha256", ""),
                              ("sixth_xtks_exit_provenance_json", "{}"), ("sixth_xtks_exit_observed_at", "2026-09-09T08:00:00+09:00"),
                              ("symbol", "8888")):
            with self.subTest(column=column, value=value):
                self.assertFalse(sixth_endpoint_verified({**original, column: value}))

    def test_corrupt_frozen_d6_economics_require_review(self):
        frame = self.attached()
        frame.loc[0, "sixth_exit_shares"] = 200
        self.assertFalse(sixth_economics_verified(frame.iloc[0]))
        with self.assertRaisesRegex(ValueError, "corrupt verified sixth economics"):
            model.refresh_forward_endpoints(frame, self.daily())

    def test_price_receipt_with_wrong_schedule_or_reconstruction_is_rejected(self):
        row = self.attached().iloc[0].to_dict()
        evidence = json.loads(row["sixth_xtks_exit_provenance_json"])
        for field, value in (("split_factor", 2), ("basis_asof", "2026-09-08"),
                             ("source_price_basis", "unknown"), ("session", "2026-09-08")):
            with self.subTest(field=field):
                altered = {**row, "sixth_xtks_exit_provenance_json": json.dumps({**evidence, field: value})}
                self.assertFalse(sixth_endpoint_verified(altered))
        altered = {**row, "signal_date": pd.Timestamp("2026-08-31")}
        self.assertFalse(sixth_endpoint_verified(altered))

    def test_future_observation_and_wrong_entry_session_cannot_verify(self):
        row = self.attached().iloc[0].to_dict()
        self.assertFalse(sixth_endpoint_verified({**row, "sixth_xtks_exit_observed_at": "2099-01-01T10:00:00+09:00"}))
        self.assertFalse(signal_actual_close_verified({**row, "signal_actual_close_observed_at": "2099-01-01T16:00:00+09:00"}))
        self.assertFalse(sixth_economics_verified({**row, "sixth_entry_date": row["signal_date"]}))
        self.assertFalse(sixth_economics_verified({**row, "sixth_economics_observed_at": "2099-01-01T16:00:00+09:00"}))
        self.assertFalse(sixth_economics_verified({**row, "sixth_price_basis_date": "2099-01-01"}))

    def test_source_basis_after_claimed_observation_is_rejected(self):
        raw = self.daily()[["date", "symbol", "open", "high", "low", "close", "volume", "split_ratio"]]
        raw = normalize_daily(raw, basis_asof="2026-10-02")
        legacy = self.legacy()
        with self.assertRaisesRegex(ValueError, "invalid new endpoint receipt"):
            backfill_verified_endpoints(legacy, raw, source_sha256="a" * 64,
                                        observed_at="2026-10-01T16:15:00+09:00", identities=legacy.detection_id)

    def test_changed_d5_action_prefix_cannot_become_verified_d6_economics(self):
        from tests.test_weak_early_beta_model import SplitAwareModelTests
        raw = SplitAwareModelTests.daily()
        original = model.attach_forward_rows(self.selected(), raw)
        original.loc[0, "sixth_economics_status"] = "pending"
        # The provider loses a recorded D5 split while keeping actual entry=100.
        revised_raw = raw[["date", "symbol", "split_ratio"]].copy()
        revised_raw["split_ratio"] = 0
        for field in ("open", "high", "low", "close", "volume"):
            revised_raw[field] = raw[f"actual_{field}"]
        revised_raw = normalize_daily(revised_raw)
        refreshed = model.refresh_forward_endpoints(original, revised_raw)
        row = refreshed.iloc[0]
        self.assertFalse(sixth_endpoint_verified(row))
        self.assertEqual(row.sixth_economics_status, "review_required")
        self.assertEqual(row.sixth_economics_issue, "d6_holding_action_revision")
        self.assertTrue(pd.isna(row.sixth_gross_return))
        pd.testing.assert_series_equal(row[ECONOMIC_COLUMNS], original.iloc[0][ECONOMIC_COLUMNS], check_names=False)
        incoming = model.attach_forward_rows(self.selected(), revised_raw)
        merged = merge_detections(original, incoming)
        self.assertFalse(sixth_endpoint_verified(merged.iloc[0]))
        self.assertEqual(merged.iloc[0].sixth_economics_status, "review_required")

    def test_d5_observation_is_newly_recorded_but_never_invented_for_old_freeze(self):
        entered = self.attached(self.daily(count=3))
        self.assertEqual(entered.iloc[0].d5_price_observed_at, "")
        mature = model.refresh_forward_endpoints(entered, self.daily())
        self.assertIsNotNone(pd.Timestamp(mature.iloc[0].d5_price_observed_at).tzinfo)
        old = mature.copy()
        old.loc[0, "d5_price_observed_at"] = ""
        refreshed = model.refresh_forward_endpoints(old, self.daily())
        replay = merge_detections(old, self.attached())
        self.assertEqual(refreshed.iloc[0].d5_price_observed_at, "")
        self.assertEqual(replay.iloc[0].d5_price_observed_at, "")

    def test_replay_cannot_pair_frozen_d6_price_with_revised_economics(self):
        original = self.attached()
        original.loc[0, "sixth_economics_status"] = "pending"
        revised = self.attached()
        revised.loc[0, "sixth_xtks_exit_open"] = 120
        evidence = json.loads(revised.loc[0, "sixth_xtks_exit_provenance_json"])
        evidence.update({"actual_price": 120, "adjusted_price": 120})
        revised.loc[0, "sixth_xtks_exit_provenance_json"] = json.dumps(evidence)
        revised.loc[0, "sixth_exit_proceeds_yen"] = 12000
        revised.loc[0, "sixth_gross_return"] = .2
        revised.loc[0, "sixth_one_hundred_shares_pl_yen"] = 2000
        merged = merge_detections(original, revised)
        self.assertFalse(sixth_endpoint_verified(merged.iloc[0]))
        self.assertTrue(pd.isna(merged.iloc[0].sixth_gross_return))

    def pending_d6_with_captured_open(self, raw=None):
        frozen = self.attached(self.daily(count=6))
        partial = self.daily() if raw is None else raw
        partial = partial[partial.date.ne(frozen.iloc[0].entry_date)]
        first = model.refresh_forward_endpoints(frozen, partial)
        self.assertTrue(sixth_endpoint_verified(first.iloc[0]))
        self.assertEqual(first.iloc[0].sixth_economics_status, "pending")
        return frozen, first

    def test_two_stage_d6_price_and_new_split_cannot_mix(self):
        frozen, first = self.pending_d6_with_captured_open()
        self.assertEqual(first.iloc[0].sixth_xtks_exit_open, 110)
        second = model.refresh_forward_endpoints(first, self.daily(ratio=2))
        row = second.iloc[0]
        self.assertFalse(sixth_endpoint_verified(row))
        self.assertFalse(sixth_economics_verified(row))
        self.assertEqual(row.sixth_xtks_exit_status, "quarantined")
        self.assertEqual(row.sixth_economics_status, "review_required")
        self.assertTrue(pd.isna(row.sixth_xtks_exit_open))
        self.assertTrue(pd.isna(row.sixth_one_hundred_shares_pl_yen))
        self.assertTrue(pd.isna(row.sixth_gross_return))
        pd.testing.assert_series_equal(row[ECONOMIC_COLUMNS], frozen.iloc[0][ECONOMIC_COLUMNS], check_names=False)
        audit = json.loads(row.sixth_xtks_exit_provenance_json)["quarantine"]
        self.assertEqual(audit["saved_price_receipt"]["sixth_xtks_exit_open"], 110)
        self.assertEqual(audit["conflicting_price_receipt"]["sixth_xtks_exit_open"], 55)
        self.assertNotEqual(audit["saved_price_receipt"]["sixth_xtks_exit_source_sha256"],
                            audit["conflicting_price_receipt"]["sixth_xtks_exit_source_sha256"])
        coherent = self.attached(self.daily(ratio=2)).iloc[0]
        self.assertTrue(sixth_economics_verified(coherent))
        self.assertEqual(coherent.sixth_one_hundred_shares_pl_yen, 1000)
        self.assertAlmostEqual(coherent.sixth_gross_return, .1)

    def test_two_stage_unchanged_split_snapshot_completes_with_one_source_bundle(self):
        _, first = self.pending_d6_with_captured_open(self.daily(ratio=2))
        filled = model.refresh_forward_endpoints(first, self.daily(ratio=2)).iloc[0]
        self.assertTrue(sixth_economics_verified(filled))
        self.assertEqual(filled.sixth_one_hundred_shares_pl_yen, 1000)
        evidence = json.loads(filled.sixth_economics_provenance_json)
        self.assertNotEqual(filled.sixth_xtks_exit_source_sha256, filled.sixth_price_basis_source_sha256)
        self.assertEqual(evidence["exit_receipt"]["sixth_xtks_exit_source_sha256"], filled.sixth_price_basis_source_sha256)
        self.assertEqual(evidence["exit_receipt"]["sixth_xtks_exit_open"], 55)
        self.assertEqual(evidence["entry"]["actual_open"], 100)
        self.assertEqual(evidence["holding_actions"], [{"effective_date": "2026-09-09", "ratio": 2.0}])

    def test_unchanged_d6_price_with_changed_d6_actions_is_quarantined(self):
        raw = self.daily()[["date", "symbol", "open", "high", "low", "close", "volume", "split_ratio"]].copy()
        for field in ("open", "high", "low", "close"):
            raw.loc[6, field] /= 2
        _, first = self.pending_d6_with_captured_open(normalize_daily(raw))
        self.assertEqual(first.iloc[0].sixth_xtks_exit_open, 55)
        second = model.refresh_forward_endpoints(first, self.daily(ratio=2)).iloc[0]
        self.assertEqual(second.sixth_economics_issue, "d6_holding_action_revision")
        self.assertFalse(sixth_endpoint_verified(second))

    def test_missing_current_d6_quote_cannot_complete_saved_price_with_new_actions(self):
        _, first = self.pending_d6_with_captured_open()
        second = model.refresh_forward_endpoints(first, self.daily(count=6)).iloc[0]
        self.assertTrue(sixth_endpoint_verified(second))
        self.assertEqual(second.sixth_economics_status, "pending")
        self.assertTrue(pd.isna(second.sixth_gross_return))

    def test_new_off_session_d6_action_revokes_release_even_without_new_quote(self):
        _, first = self.pending_d6_with_captured_open()
        raw = self.daily(ratio=2).iloc[:6][["date", "symbol", "open", "high", "low", "close", "volume", "split_ratio"]].copy()
        raw["off_session_actions"] = ""
        raw.loc[5, "off_session_actions"] = json.dumps([
            {"effective_date": "2026-09-09", "ratio": 2, "source": "Yahoo Finance Stock Splits"},
        ])
        second = model.refresh_forward_endpoints(first, normalize_daily(raw)).iloc[0]
        self.assertFalse(sixth_endpoint_verified(second))
        self.assertEqual(second.sixth_economics_issue, "d6_holding_action_revision")

    def test_quarantine_survives_refresh_merge_csv_and_generic_backfill(self):
        _, first = self.pending_d6_with_captured_open()
        quarantined = model.refresh_forward_endpoints(first, self.daily(ratio=2))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quarantined.csv"
            write_ledger(quarantined, path)
            restored = read_ledger(path)
        for candidate in (
            model.refresh_forward_endpoints(restored, self.daily()),
            model.refresh_forward_endpoints(restored, self.daily(ratio=2)),
            merge_detections(restored, self.attached()),
            merge_detections(self.attached(), restored),
            backfill_verified_endpoints(restored, self.daily(ratio=2), source_sha256="a" * 64,
                                        observed_at="2026-10-01T16:15:00+09:00", identities=restored.detection_id)[0],
        ):
            self.assertFalse(sixth_endpoint_verified(candidate.iloc[0]))
            self.assertFalse(sixth_economics_verified(candidate.iloc[0]))
            self.assertEqual(candidate.iloc[0].sixth_xtks_exit_provenance_json, restored.iloc[0].sixth_xtks_exit_provenance_json)

    def test_completed_d6_also_revokes_release_on_a_contradictory_source(self):
        complete = self.attached()
        self.assertTrue(sixth_economics_verified(complete.iloc[0]))
        for revised in (model.refresh_forward_endpoints(complete, self.daily(ratio=2)),
                        merge_detections(complete, self.attached(self.daily(ratio=2)))):
            self.assertFalse(sixth_endpoint_verified(revised.iloc[0]))
            self.assertFalse(sixth_economics_verified(revised.iloc[0]))
            audit = json.loads(revised.iloc[0].sixth_xtks_exit_provenance_json)["quarantine"]
            self.assertEqual(audit["saved_economics"]["sixth_one_hundred_shares_pl_yen"], 1000)
            pd.testing.assert_series_equal(revised.iloc[0][ECONOMIC_COLUMNS], complete.iloc[0][ECONOMIC_COLUMNS], check_names=False)

    def test_later_post_d6_split_changes_source_hash_without_changing_held_units(self):
        raw = self.daily()[["date", "symbol", "open", "high", "low", "close", "volume", "split_ratio"]].copy()
        for field in ("open", "high", "low", "close"):
            raw[field] /= 2
        raw["volume"] *= 2
        raw.loc[7] = {"date": pd.Timestamp("2026-09-10"), "symbol": "9999", "open": 55,
                      "high": 56, "low": 54, "close": 55, "volume": 10_000, "split_ratio": 2}
        later = normalize_daily(raw)
        _, first = self.pending_d6_with_captured_open()
        filled = model.refresh_forward_endpoints(first, later).iloc[0]
        self.assertTrue(sixth_economics_verified(filled))
        self.assertEqual(filled.sixth_xtks_exit_open, 110)
        self.assertEqual(filled.sixth_exit_shares, 100)
        self.assertEqual(filled.sixth_one_hundred_shares_pl_yen, 1000)
        complete = self.attached()
        retained = model.refresh_forward_endpoints(complete, later)
        pd.testing.assert_series_equal(retained.iloc[0][ENDPOINT_COLUMNS], complete.iloc[0][ENDPOINT_COLUMNS], check_names=False)

    def test_economics_validator_rejects_mixed_or_missing_source_bundle(self):
        row = self.attached().iloc[0].to_dict()
        self.assertFalse(sixth_economics_verified({**row, "sixth_economics_provenance_json": ""}))
        bundle = json.loads(row["sixth_economics_provenance_json"])
        bundle["exit_receipt"]["sixth_xtks_exit_source_sha256"] = "a" * 64
        self.assertFalse(sixth_economics_verified({**row, "sixth_economics_provenance_json": json.dumps(bundle)}))

    def test_csv_roundtrip_preserves_receipts_and_timestamp_precision(self):
        original = self.attached()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            write_ledger(original, path)
            restored = read_ledger(path)
        self.assertTrue(signal_actual_close_verified(restored.iloc[0]))
        self.assertTrue(sixth_endpoint_verified(restored.iloc[0]))
        self.assertTrue(sixth_economics_verified(restored.iloc[0]))
        self.assertEqual(original.iloc[0].sixth_xtks_exit_observed_at, restored.iloc[0].sixth_xtks_exit_observed_at)

    def cli_fixture(self, directory):
        folder = Path(directory)
        ledger = folder / "input.csv"
        daily = folder / "verified.csv"
        identities = folder / "identities.json"
        self.legacy().to_csv(ledger, index=False)
        self.daily().to_csv(daily, index=False)
        identities.write_text(json.dumps(self.legacy().detection_id.tolist()), encoding="utf-8")
        return parser().parse_args([
            "backfill-endpoints", "--ledger", str(ledger), "--daily-corpus", str(daily),
            "--source-sha256", hashlib.sha256(daily.read_bytes()).hexdigest(),
            "--identities", str(identities), "--observed-at", "2026-10-01T16:15:00+09:00",
            "--output", str(folder / "output.csv"), "--audit", str(folder / "audit.json"),
        ])

    def test_cli_writes_only_explicit_new_outputs_and_audits_all_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.cli_fixture(directory)
            before = {name: Path(getattr(args, name)).read_bytes() for name in ("ledger", "daily_corpus", "identities")}
            with redirect_stdout(StringIO()):
                command_backfill_endpoints(args)
            for name, contents in before.items():
                self.assertEqual(Path(getattr(args, name)).read_bytes(), contents)
            audit = json.loads(Path(args.audit).read_text(encoding="utf-8"))
            self.assertEqual(audit["changed_count"], 1)
            self.assertEqual(audit["notifications_sent"], 0)
            self.assertEqual(audit["output_ledger_sha256"], hashlib.sha256(Path(args.output).read_bytes()).hexdigest())
            self.assertTrue(sixth_economics_verified(read_ledger(Path(args.output)).iloc[0]))
            with self.assertRaisesRegex(ValueError, "already exists"):
                command_backfill_endpoints(args)

    def test_cli_rejects_bad_hash_inplace_write_future_time_and_production_output(self):
        for scenario in ("hash", "inplace", "future", "production", "identities"):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                args = self.cli_fixture(directory)
                if scenario == "hash":
                    args.source_sha256 = "a" * 64
                elif scenario == "inplace":
                    args.output = args.ledger
                elif scenario == "future":
                    args.observed_at = "2099-01-01T16:15:00+09:00"
                elif scenario == "production":
                    args.output = "weak_early_beta/state/test_backfill_forbidden.csv"
                else:
                    Path(args.identities).write_text('{"ids": []}', encoding="utf-8")
                with self.assertRaises(ValueError):
                    command_backfill_endpoints(args)
                self.assertFalse(Path(args.audit).exists())


if __name__ == "__main__":
    unittest.main()
