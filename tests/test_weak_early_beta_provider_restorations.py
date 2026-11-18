"""Small synthetic histories and retained packets only; no live source access."""

import copy
import hashlib
import json
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stderr
from io import BytesIO, StringIO
from pathlib import Path
from types import MappingProxyType
from unittest.mock import patch

import pandas as pd

from weak_early_beta import reviewed_provider_restorations as reviewed
from weak_early_beta.acquisition import AcquisitionArchive
from weak_early_beta.corporate_actions import (
    ACTUAL_COLUMNS, BASIS_COLUMNS, OHLC, CorporateActionError,
    fetch_daily, normalize_daily, validate_source_revision,
)


def fixtures():
    raw = pd.DataFrame({
        "symbol": ["3624", "3624"],
        "date": pd.to_datetime(["2026-10-30", "2026-11-02"]),
        "open": [32., 33.], "high": [34., 34.],
        "low": [28., 28.], "close": [31., 31.],
        "volume": [1000., 1917200.], "split_ratio": 0.,
        "provider_repaired": False, "off_session_actions": "",
    })
    old = normalize_daily(raw, basis_asof="2026-11-02")
    old.attrs["source_sha256"] = reviewed.SEED_SHA256
    raw.loc[1, "high"] = 33.
    latest = raw.iloc[[0]].copy()
    latest["date"] = pd.Timestamp("2026-11-04")
    raw = pd.concat([raw, latest], ignore_index=True)
    raw.attrs = {"synthetic": {"unchanged": True}}
    return old, raw


def restore(old, raw, basis="2026-11-04", archive=None):
    return reviewed.restore_reviewed_provider_values(
        old, raw, basis_asof=pd.Timestamp(basis), archive=archive,
    )


def persist(frame, audits):
    """Use an actual serialized CSV digest and JSON-roundtripped quality data."""
    content = frame.to_csv(index=False, date_format="%Y-%m-%d", lineterminator="\n").encode()
    digest = hashlib.sha256(content).hexdigest()
    quality = json.loads(json.dumps({
        "identity": "CLOUD_SOURCE_QUALITY_V1", "daily_sha256": digest,
        "source_revision": {"reviewedProviderRestorations": audits},
    }))
    previous = pd.read_csv(BytesIO(content), parse_dates=["date"], dtype={"symbol": str})
    previous.attrs = {
        "source_sha256": digest,
        reviewed.PRIOR_AUDIT_ATTR: {
            "dailySha256": quality["daily_sha256"],
            "restorations": quality["source_revision"]["reviewedProviderRestorations"],
        },
    }
    return previous, quality


class NoNetwork(unittest.TestCase):
    def setUp(self):
        guard = patch("socket.socket.connect", side_effect=AssertionError("network is forbidden"))
        guard.start()
        self.addCleanup(guard.stop)


class RestorationTests(NoNetwork):
    def setUp(self):
        super().setUp()
        verifier = patch.object(reviewed, "verify_seed_archive")
        self.verifier = verifier.start()
        self.addCleanup(verifier.stop)

    def rolling(self):
        old, raw = fixtures()
        result, audits = restore(old, raw)
        previous, quality = persist(normalize_daily(result, basis_asof="2026-11-04"), audits)
        following = raw.copy()
        following.loc[2, "date"] = pd.Timestamp("2026-11-05")
        return previous, following, quality

    def test_exact_raw_restoration_one_cell_and_normalized_feature_input(self):
        old, raw = fixtures()
        originals = [copy.deepcopy(frame) for frame in (old, raw)]
        # Nonunique DataFrame labels must not broaden the edit.
        raw.index = [7, 7, 9]
        originals[1] = copy.deepcopy(raw)
        result, audits = restore(old, raw)
        expected = raw.copy()
        expected.iloc[1, expected.columns.get_loc("high")] = 34.
        pd.testing.assert_frame_equal(result, expected)
        self.assertEqual(int(result.ne(raw).to_numpy().sum()), 1)
        normalized = normalize_daily(result, basis_asof="2026-11-04")
        target = normalized.loc[normalized.date.eq(reviewed.SESSION)].iloc[0]
        self.assertEqual((target.high, target.actual_high), (34., 34.))
        self.assertFalse(normalized.provider_repaired.any())
        self.assertTrue(normalized.source_usable.all())
        self.assertEqual(validate_source_revision(old, normalized)["acceptedRepairColumnValues"], 0)
        audit = audits[0]
        self.assertEqual(audit["observedOHLCV"], [33, 33, 28, 31, 1917200])
        self.assertEqual(audit["restoredOHLCV"], [33, 34, 28, 31, 1917200])
        self.assertEqual(audit["changedCellCount"], 1)
        self.assertNotEqual(audit["targetBeforeSha256"], audit["targetAfterSha256"])
        self.assertEqual(audit["catalogSha256"], reviewed.CATALOG_SHA256)
        self.assertEqual(audit["receiptInventorySha256"], reviewed.CATALOG["receiptInventorySha256"])
        self.assertEqual(audit["previousSourceSha256"], reviewed.SEED_SHA256)
        self.assertEqual(audit["officialPDFPage"], 132)
        self.verifier.assert_called_once_with(None)
        for frame, original in zip((old, raw), originals):
            pd.testing.assert_frame_equal(frame, original)
            self.assertEqual(frame.attrs, original.attrs)
        result.iloc[0, result.columns.get_loc("high")] = 999
        self.assertEqual(raw.iloc[0].high, 34.)

    def test_seed_contract_has_no_numeric_tolerance(self):
        cases = [
            (0, "basis_asof", pd.Timestamp("2026-11-01")),
            (0, "price_basis", "other"),
            (0, "corporate_actions_version", "other"),
            (0, "corporate_actions_source", "other"),
            (0, "source_usable", False),
            (0, "source_issue", "unreviewed"),
            (0, "split_factor", 1.000000000001),
            (0, "high", 34.000000001),
            (0, "actual_high", 34.000000001),
            (0, "actual_volume", 1917200.000001),
            (1, "open", 33.000000001),
            (1, "low", 28.000000001),
            (1, "close", 31.000000001),
            (1, "volume", 1917200.000001),
            (1, "high", 33.000000001),
            (1, "high", 35.),
        ]
        for endpoint, field, value in cases:
            frames = fixtures()
            frames[endpoint].loc[1, field] = value
            with self.subTest(endpoint=endpoint, field=field, value=value):
                with self.assertRaises(CorporateActionError):
                    restore(*frames)
        old, raw = fixtures()
        with self.assertRaises(CorporateActionError):
            restore(old, raw, basis="2026-11-05")

    def test_complete_metadata_flags_journals_duplicates_and_missing_rows(self):
        raw_required = ("split_ratio", "provider_repaired", "off_session_actions")
        for field in (*ACTUAL_COLUMNS, *BASIS_COLUMNS):
            old, raw = fixtures()
            with self.subTest(missing_previous=field), self.assertRaises(CorporateActionError):
                restore(old.drop(columns=field), raw)
        for field in raw_required:
            old, raw = fixtures()
            with self.subTest(missing_current=field), self.assertRaises(CorporateActionError):
                restore(old, raw.drop(columns=field))
        for endpoint in (0, 1):
            for field, value in (
                ("provider_repaired", True), ("split_ratio", 2.),
                ("split_ratio", None),
                ("off_session_actions", '[{"effective_date":"2026-10-29","ratio":2,"source":"Yahoo Finance Stock Splits"}]'),
                ("off_session_actions", "[]"),
            ):
                frames = fixtures()
                # Check the entire history, including a nontarget session.
                frames[endpoint].loc[0, field] = value
                with self.subTest(endpoint=endpoint, field=field, value=value):
                    with self.assertRaises(CorporateActionError):
                        restore(*frames)
            frames = fixtures()
            frames[endpoint].loc[1, "source_revision_evidence"] = '{"unreviewed":true}'
            with self.subTest(endpoint=endpoint, field="source_revision_evidence"):
                with self.assertRaises(CorporateActionError):
                    restore(*frames)
            for change in ("duplicate", "missing", "symbol_missing"):
                frames = list(fixtures())
                if change == "duplicate":
                    attrs = copy.deepcopy(frames[endpoint].attrs)
                    frames[endpoint] = pd.concat([frames[endpoint], frames[endpoint].iloc[[1]]], ignore_index=True)
                    frames[endpoint].attrs = attrs
                elif change == "missing":
                    frames[endpoint] = frames[endpoint].drop(index=1)
                else:
                    frames[endpoint]["symbol"] = "9999"
                with self.subTest(endpoint=endpoint, change=change):
                    with self.assertRaises(CorporateActionError):
                        restore(*frames)

    def test_unrelated_invalid_ohlc_retains_ordinary_quarantine(self):
        _, raw = fixtures()
        # The older session is inconsistent independently of the reviewed quote.
        raw.loc[0, "high"] = 27.
        previous_raw = raw.iloc[:2].copy()
        previous_raw.loc[1, "high"] = 34.
        old = normalize_daily(previous_raw, basis_asof="2026-11-02")
        old.attrs["source_sha256"] = reviewed.SEED_SHA256
        unrelated_session = pd.Timestamp("2026-10-30")
        old_unrelated = old.loc[old.date.eq(unrelated_session)]
        self.assertFalse(bool(old_unrelated.source_usable.item()))
        self.assertEqual(old_unrelated.source_issue.item(), "inconsistent_ohlc")
        originals = [copy.deepcopy(frame) for frame in (old, raw)]

        # Ordinary revision validation still rejects the uncorrected target,
        # even when an unrelated session is already quarantined.
        with self.assertRaisesRegex(CorporateActionError, "unexplained historical high"):
            validate_source_revision(old, normalize_daily(raw, basis_asof="2026-11-04"))

        result, audits = restore(old, raw)
        expected = raw.copy()
        expected.loc[1, "high"] = 34.
        pd.testing.assert_frame_equal(result, expected)
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits[0]["changedCellCount"], 1)
        normalized = normalize_daily(result, basis_asof="2026-11-04")
        target = normalized.loc[normalized.date.eq(reviewed.SESSION)].iloc[0]
        self.assertEqual((target.high, target.actual_high), (34., 34.))
        self.assertTrue(bool(target.source_usable))
        self.assertEqual(target.source_issue, "")

        unrelated = normalized.loc[normalized.date.eq(unrelated_session)]
        unchanged_columns = [
            "symbol", "date", *reviewed.FIELDS, *ACTUAL_COLUMNS,
            "source_usable", "source_issue",
        ]
        pd.testing.assert_frame_equal(
            unrelated[unchanged_columns].reset_index(drop=True),
            old_unrelated[unchanged_columns].reset_index(drop=True),
        )
        self.assertEqual(
            unrelated[list(reviewed.FIELDS)].iloc[0].tolist(),
            [32., 27., 28., 31., 1000.],
        )
        self.assertFalse(bool(unrelated.source_usable.item()))
        self.assertEqual(unrelated.source_issue.item(), "inconsistent_ohlc")
        # No restoration exemption is passed to the ordinary validator; the
        # unchanged invalid session relies on its preexisting quarantine.
        receipt = validate_source_revision(old, normalized)
        self.assertEqual(receipt["acceptedRepairColumnValues"], 0)
        for frame, original in zip((old, raw), originals):
            pd.testing.assert_frame_equal(frame, original)
            self.assertEqual(frame.attrs, original.attrs)

    def test_unrelated_revision_evidence_and_actual_values_do_not_authorize_edits(self):
        old, raw = fixtures()
        old.loc[0, "actual_high"] = 35.
        for frame in (old, raw):
            frame["source_revision_evidence"] = ""
            frame.loc[0, "source_revision_evidence"] = '{"unreviewed":true}'
        originals = [copy.deepcopy(frame) for frame in (old, raw)]
        result, audits = restore(old, raw)
        expected = raw.copy()
        expected.loc[1, "high"] = 34.
        pd.testing.assert_frame_equal(result, expected)
        self.assertEqual(len(audits), 1)
        for frame, original in zip((old, raw), originals):
            pd.testing.assert_frame_equal(frame, original)
            self.assertEqual(frame.attrs, original.attrs)

    def test_unknown_hashes_do_not_restore_and_ordinary_gate_stays_strict(self):
        for digest in (None, "", "0" * 64, "not-a-sha"):
            old, raw = fixtures()
            old.attrs["source_sha256"] = digest
            result, audits = restore(old, raw)
            self.assertIs(result, raw)
            self.assertEqual(audits, [])
            with self.assertRaisesRegex(CorporateActionError, "unexplained historical high"):
                validate_source_revision(old, normalize_daily(result, basis_asof="2026-11-04"))
        old, raw = fixtures()
        with self.assertRaisesRegex(CorporateActionError, "unexplained historical high"):
            validate_source_revision(old, normalize_daily(raw, basis_asof="2026-11-04"))

    def test_unrelated_revision_is_not_authorized_by_restoration(self):
        old, raw = fixtures()
        other_old, other_raw = fixtures()
        other_old["symbol"] = other_raw["symbol"] = "9999"
        other_raw.loc[1, "high"] = 50.
        previous = pd.concat([old, other_old], ignore_index=True)
        previous.attrs = copy.deepcopy(old.attrs)
        current = pd.concat([raw, other_raw], ignore_index=True)
        result, audits = restore(previous, current)
        self.assertEqual(len(audits), 1)
        self.assertEqual(result.loc[result.symbol.eq("9999") & result.date.eq(reviewed.SESSION), "high"].item(), 50.)
        with self.assertRaisesRegex(CorporateActionError, "unexplained historical high revision for 9999"):
            validate_source_revision(previous, normalize_daily(result, basis_asof="2026-11-04"))

    def test_descendant_csv_quality_lineage_and_advancing_basis(self):
        previous, raw, quality = self.rolling()
        self.assertEqual(previous.attrs["source_sha256"], quality["daily_sha256"])
        self.verifier.reset_mock()
        result, audits = restore(previous, raw, basis="2026-11-05")
        self.verifier.assert_not_called()
        self.assertEqual(audits[0]["previousSourceSha256"], quality["daily_sha256"])
        self.assertEqual(audits[0]["previousBasis"], "2026-11-04")
        self.assertEqual(audits[0]["currentBasis"], "2026-11-05")
        normalized = normalize_daily(result, basis_asof="2026-11-05")
        validate_source_revision(previous, normalized)
        next_previous, _ = persist(normalized, audits)
        result, next_audits = restore(next_previous, raw, basis="2026-11-05")
        self.assertEqual(result.loc[result.date.eq(reviewed.SESSION), "high"].item(), 34.)
        self.assertEqual(next_audits[0]["previousBasis"], "2026-11-05")

    def test_tampered_lineage_fixed_proofs_and_third_values_fail_closed(self):
        changes = {
            "catalogSha256": "0" * 64,
            "seedSourceSha256": "0" * 64,
            "seedPreviousBasis": "2026-11-01",
            "seedCurrentBasis": "2026-11-05",
            "officialPDFURL": "https://example.invalid/",
            "officialPDFSha256": "0" * 64,
            "officialPDFPage": 131,
            "targetPacketSha256": "0" * 64,
            "receiptInventorySha256": "0" * 64,
            "targetBeforeSha256": "0" * 64,
            "targetAfterSha256": "0" * 64,
            "expectedPreviousOHLCV": [33, 33, 28, 31, 1917200],
            "restoredOHLCV": [33, 35, 28, 31, 1917200],
            "observedHigh": 35,
            "previousSourceSha256": None,
            "previousBasis": "2026-11-03",
            "currentBasis": "2026-11-05",
            "changedCellCount": 0,
            "applicationCorrection": 1,
            "providerRepaired": 0,
        }
        for field, value in changes.items():
            previous, raw, _ = self.rolling()
            previous.attrs[reviewed.PRIOR_AUDIT_ATTR]["restorations"][0][field] = value
            with self.subTest(field=field), self.assertRaises(CorporateActionError):
                restore(previous, raw, basis="2026-11-05")
        previous, raw, _ = self.rolling()
        previous.attrs[reviewed.PRIOR_AUDIT_ATTR]["dailySha256"] = "0" * 64
        with self.assertRaises(CorporateActionError):
            restore(previous, raw, basis="2026-11-05")
        previous, raw, _ = self.rolling()
        raw.loc[1, "high"] = 35.
        with self.assertRaises(CorporateActionError):
            restore(previous, raw, basis="2026-11-05")
        previous, raw, _ = self.rolling()
        previous.loc[1, ["high", "actual_high"]] = 33.
        with self.assertRaises(CorporateActionError):
            restore(previous, raw, basis="2026-11-05")
        previous, raw, _ = self.rolling()
        with self.assertRaises(CorporateActionError):
            restore(previous, raw, basis="2026-11-03")

    def test_provider_correct_value_is_noop_and_preserves_lineage(self):
        old, raw = fixtures()
        raw.loc[1, "high"] = 34.
        result, audits = restore(old, raw)
        self.assertIs(result, raw)
        self.assertEqual(audits[0]["changedCellCount"], 0)
        self.assertEqual(audits[0]["targetBeforeSha256"], audits[0]["targetAfterSha256"])
        previous, _ = persist(normalize_daily(result, basis_asof="2026-11-04"), audits)
        result, audits = restore(previous, raw, basis="2026-11-04")
        self.assertIs(result, raw)
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits[0]["changedCellCount"], 0)
        next_previous, _ = persist(normalize_daily(result, basis_asof="2026-11-04"), audits)
        raw.loc[1, "high"] = 33.
        result, audits = restore(next_previous, raw, basis="2026-11-04")
        self.assertEqual(result.loc[1, "high"], 34.)
        self.assertEqual(audits[0]["changedCellCount"], 1)

    def test_expired_session_outside_both_rolling_histories_is_noop(self):
        previous, raw, _ = self.rolling()
        previous = previous.loc[previous.date.gt(reviewed.SESSION)].copy()
        raw = raw.loc[raw.date.gt(reviewed.SESSION)].copy()
        result, audits = restore(previous, raw, basis="2026-11-05")
        self.assertIs(result, raw)
        self.assertEqual(audits, [])

    def test_fetch_normalizes_restored_input_then_attaches_application_audit(self):
        old, raw = fixtures()
        provider = raw.set_index("date")[[*OHLC, "volume", "split_ratio"]].rename(columns={
            **{field: field.title() for field in (*OHLC, "volume")},
            "split_ratio": "Stock Splits",
        })
        normalized_inputs = []

        def observe(frame, **kwargs):
            normalized_inputs.append(frame.copy())
            return normalize_daily(frame, **kwargs)

        with patch("yfinance.download", return_value=provider), \
             patch("weak_early_beta.corporate_actions.normalize_daily", side_effect=observe), \
             patch("weak_early_beta.reviewed_repair_releases.reviewed_repair_release_keys",
                   return_value=(set(), [])):
            result = fetch_daily(pd.DataFrame({"ticker": ["3624.T"]}), "5y", previous=old)
        # This is the normalized corpus subsequently supplied to feature work.
        first = normalized_inputs[0]
        self.assertEqual(first.loc[first.date.eq(reviewed.SESSION), "high"].item(), 34.)
        target = result.loc[result.date.eq(reviewed.SESSION)].iloc[0]
        self.assertEqual((target.high, target.actual_high), (34., 34.))
        self.assertFalse(target.provider_repaired)
        receipt = result.attrs["source_revision_receipt"]
        self.assertEqual(receipt["sourceCorrectionAudit"], [])
        self.assertEqual(receipt["reviewedProviderRestorations"][0]["changedCellCount"], 1)

    def test_cli_only_attaches_small_matching_quality_wrapper(self):
        from weak_early_beta import model
        from weak_early_beta.cli import _write_daily_cache, command_daily

        class Captured(Exception):
            pass

        for kind in ("matching", "wrong_hash", "wrong_identity", "absent"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                previous, _, quality = self.rolling()
                path = Path(temporary) / "daily.csv"
                _write_daily_cache(previous, path)
                digest = model.sha256(path)
                quality["daily_sha256"] = digest
                quality["issues"] = ["never attach this large audit"] * 100
                if kind == "wrong_hash":
                    quality["daily_sha256"] = "0" * 64
                elif kind == "wrong_identity":
                    quality["identity"] = "other"
                if kind != "absent":
                    path.with_suffix(".source-quality.json").write_text(json.dumps(quality), encoding="utf-8")

                def capture(universe, period, *, previous, archive):
                    expected = {"source_sha256": digest}
                    if kind == "matching":
                        expected[reviewed.PRIOR_AUDIT_ATTR] = {
                            "dailySha256": digest,
                            "restorations": quality["source_revision"]["reviewedProviderRestorations"],
                        }
                    self.assertEqual(previous.attrs, expected)
                    self.assertEqual(archive.context["previousSourceSha256"], digest)
                    raise Captured

                args = Namespace(
                    refresh_live=True, as_of="2026-11-05", period="5y",
                    ledger=str(Path(temporary) / "ledger.csv"), daily_corpus=str(path),
                )
                with patch("weak_early_beta.restrictions.fetch_jpx_restricted_symbols", return_value=[]), \
                     patch("weak_early_beta.cli._load_or_bootstrap", return_value=pd.DataFrame()), \
                     patch.object(model.base, "jpx_universe", return_value=pd.DataFrame({"code": ["3624"]})), \
                     patch("weak_early_beta.corporate_actions.fetch_daily", side_effect=capture), \
                     patch("weak_early_beta.cli._write_daily_cache") as write, redirect_stderr(StringIO()):
                    with self.assertRaises(Captured):
                        command_daily(args)
                    write.assert_not_called()


class HistoricalInvalidBarTests(NoNetwork):
    @staticmethod
    def histories(*, carried=False):
        # Synthetic surrounding history; the invalid Nov 18 row is copied
        # exactly from the retained vendor/source-quality readback, including
        # its close's low bit. No official Nov 18 quote is asserted here.
        dates = pd.bdate_range("2026-06-01", "2026-11-19")
        raw = pd.concat([pd.DataFrame({
            "symbol": symbol, "date": dates, "open": 100., "high": 103.,
            "low": 98., "close": 101., "volume": 1000000.,
            "split_ratio": 0., "provider_repaired": False, "off_session_actions": "",
        }) for symbol in ("3624", "9999")], ignore_index=True)
        reviewed_key = raw.symbol.eq("3624") & raw.date.eq(reviewed.SESSION)
        raw.loc[reviewed_key, list(reviewed.FIELDS)] = reviewed.CATALOG["previousOHLCV"]
        invalid_key = raw.symbol.eq("3624") & raw.date.eq(pd.Timestamp("2026-11-18"))
        raw.loc[invalid_key, list(reviewed.FIELDS)] = [
            78., 107., 73., float.fromhex("0x1.b800000000001p+6"), 12506100.,
        ]
        raw.loc[invalid_key, "provider_repaired"] = True
        basis = "2026-11-18" if carried else "2026-11-17"
        old = normalize_daily(raw.loc[raw.date.le(basis)], basis_asof=basis)
        previous, _ = persist(old, [reviewed._audit("a" * 64, "2026-11-16", basis, 33)])
        raw.loc[reviewed_key, "high"] = 33.
        return previous, raw

    def test_next_day_first_and_carried_quote_remain_quarantined_without_raw_edits(self):
        from weak_early_beta.new_a.features import compute_features

        for carried in (False, True):
            with self.subTest(carried=carried):
                previous, raw = self.histories(carried=carried)
                original_old, original_raw = copy.deepcopy(previous), copy.deepcopy(raw)
                if carried:
                    saved = previous.loc[previous.symbol.eq("3624") & previous.date.eq("2026-11-18")].iloc[0]
                    self.assertEqual(float(saved.close).hex(), "0x1.b800000000000p+6")
                result, audits = restore(previous, raw, basis="2026-11-19")
                expected = raw.copy()
                key = expected.symbol.eq("3624") & expected.date.eq(reviewed.SESSION)
                expected.loc[key, "high"] = 34.
                pd.testing.assert_frame_equal(result, expected)
                self.assertEqual(int(result.ne(raw).to_numpy().sum()), 1)
                normalized = normalize_daily(result, basis_asof="2026-11-19")
                receipt = validate_source_revision(previous, normalized)
                self.assertEqual(receipt["acceptedRepairColumnValues"], 0)
                self.assertEqual(len(audits), 1)
                bad = normalized.loc[normalized.symbol.eq("3624") & normalized.date.eq("2026-11-18")].iloc[0]
                self.assertEqual(float(bad.close).hex(), "0x1.b800000000001p+6")
                self.assertTrue(bad.provider_repaired)
                self.assertFalse(bad.source_usable)
                self.assertEqual(bad.source_issue, "inconsistent_ohlc")
                self.assertEqual(normalized.duplicated(["symbol", "date"]).sum(), 0)
                features = {symbol: compute_features(group) for symbol, group in normalized.groupby("symbol")}
                self.assertFalse(features["3624"].loc["2026-11-19", "eligible_common"])
                self.assertFalse(features["3624"].loc["2026-11-19", "candidate"])
                self.assertTrue(features["9999"].loc["2026-11-19", "eligible_common"])
                baseline = normalize_daily(raw.loc[raw.symbol.eq("9999")], basis_asof="2026-11-19")
                pd.testing.assert_frame_equal(features["9999"], compute_features(baseline))
                for frame, original in ((previous, original_old), (raw, original_raw)):
                    pd.testing.assert_frame_equal(frame, original)
                    self.assertEqual(frame.attrs, original.attrs)

    def test_exact_endpoints_flags_actions_and_previous_quality_are_required(self):
        mutations = [
            ("close", 110.00000000000003), ("open", 78.000000001), ("high", 110.00000000000001),
            ("low", 72.), ("volume", 12506101.), ("date", pd.Timestamp("2026-11-17")),
            ("provider_repaired", "unknown"), ("split_ratio", 2.),
            ("off_session_actions", "[]"),
        ]
        for endpoint in (0, 1):
            cases = mutations + ([("source_usable", True), ("source_issue", "other"),
                                    ("actual_close", 110.00000000000001)] if endpoint == 0 else [("close", 110.)])
            for field, value in cases:
                previous, raw = self.histories(carried=True)
                frame = (previous, raw)[endpoint]
                key = frame.symbol.eq("3624") & frame.date.eq("2026-11-18")
                if isinstance(value, str):
                    frame[field] = frame[field].astype(object)
                frame.loc[key, field] = value
                with self.subTest(endpoint=endpoint, field=field), self.assertRaises(CorporateActionError):
                    restore(previous, raw, basis="2026-11-19")
        previous, raw = self.histories()
        # Another flagged, otherwise valid row is still unreviewed.
        raw.loc[raw.symbol.eq("3624") & raw.date.eq("2026-11-19"), "provider_repaired"] = True
        with self.assertRaises(CorporateActionError):
            restore(previous, raw, basis="2026-11-19")

    def test_same_day_duplicate_and_lost_lineage_do_not_gain_permission(self):
        previous, raw = self.histories()
        with self.assertRaises(CorporateActionError):
            restore(previous, raw.loc[raw.date.le("2026-11-18")], basis="2026-11-18")
        for endpoint in (0, 1):
            frames = list(self.histories(carried=True))
            frame = frames[endpoint]
            duplicate = frame.loc[frame.symbol.eq("3624") & frame.date.eq("2026-11-18")]
            frames[endpoint] = pd.concat([frame, duplicate], ignore_index=True)
            frames[endpoint].attrs = copy.deepcopy(frame.attrs)
            with self.subTest(endpoint=endpoint), self.assertRaises(CorporateActionError):
                restore(*frames, basis="2026-11-19")
        previous, raw = self.histories()
        previous.attrs[reviewed.PRIOR_AUDIT_ATTR]["dailySha256"] = "0" * 64
        with self.assertRaises(CorporateActionError):
            restore(previous, raw, basis="2026-11-19")

    def test_fresh_fetch_uses_normal_quality_and_revision_pipeline(self):
        previous, raw = self.histories()
        provider = raw.loc[raw.symbol.eq("3624")].set_index("date")[[*OHLC, "volume", "split_ratio", "provider_repaired"]].rename(columns={
            **{field: field.title() for field in (*OHLC, "volume")},
            "split_ratio": "Stock Splits", "provider_repaired": "Repaired?",
        })
        with patch("yfinance.download", return_value=provider), \
             patch("weak_early_beta.reviewed_repair_releases.reviewed_repair_release_keys", return_value=(set(), [])):
            result = fetch_daily(pd.DataFrame({"ticker": ["3624.T"]}), "5y", previous=previous)
        bad = result.loc[result.date.eq("2026-11-18")].iloc[0]
        self.assertFalse(bad.source_usable)
        self.assertTrue(bad.provider_repaired)
        self.assertEqual(bad.source_issue, "inconsistent_ohlc")
        audit = result.attrs["source_revision_receipt"]["reviewedProviderRestorations"]
        self.assertEqual(audit, [reviewed._audit(previous.attrs["source_sha256"], "2026-11-17", "2026-11-19", 33)])


class ArchiveVerificationTests(NoNetwork):
    def with_inventory_root(self, archive, catalog):
        inventory = sorted([
            [path.name, hashlib.sha256(path.read_bytes()).hexdigest()]
            for path in archive.directory.glob("*.json")
            if path.name != "manifest.json"
        ])
        return MappingProxyType({
            **catalog,
            "receiptInventorySha256": hashlib.sha256(
                json.dumps(inventory, separators=(",", ":")).encode()
            ).hexdigest(),
        })

    def make_archive(self, root, *, known_provider_errors=False):
        archive = AcquisitionArchive(root / "synthetic", {
            "date": "2026-11-04", "period": "5y", "tickers": ["3624.T"],
            "previousSourceSha256": reviewed.SEED_SHA256,
        })
        for number in range(1, 48):
            request = {
                "kind": "batch", "tickers": ["3624.T"] if number == 11 else ["9999.T"],
                "kwargs": {"repair": True, "syntheticSequence": number},
            }
            archive.request(request, lambda: pd.DataFrame({"tiny": [1]}), {})
        if known_provider_errors:
            # Synthetic receipts model the three retained inner repair errors.
            # Finish constructing the fixture before pinning its inventory.
            for number, ticker, start, end in (
                (22, "5537.T", "2025-10-07", "2025-10-23"),
                (32, "7075.T", "2024-11-06", "2024-12-06"),
                (39, "8303.T", "2024-11-06", "2025-11-20"),
            ):
                receipt = next(archive.directory.glob(f"{number:05d}-*.json"))
                saved = json.loads(receipt.read_text(encoding="utf-8"))
                saved["providerErrors"] = {
                    ticker: f"possibly delisted; no price data found (1h {start} -> {end})",
                }
                receipt.write_text(json.dumps(saved), encoding="utf-8")
        target = next(archive.directory.glob("00011-*.pkl"))
        catalog = MappingProxyType({
            **reviewed.CATALOG, "targetPacket": target.name,
            "targetPacketSha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        })
        return archive, self.with_inventory_root(archive, catalog)

    def save_manifest(self, archive):
        archive.manifest_path.write_text(json.dumps(archive.manifest), encoding="utf-8")

    def test_production_catalog_is_fixed_and_seed_requires_archive_object(self):
        self.assertEqual(reviewed.CATALOG["requests"], 47)
        self.assertEqual(reviewed.CATALOG["targetPacket"], "00011-ae8f5b4225001403bfb5.pkl")
        self.assertEqual(
            reviewed.CATALOG["receiptInventorySha256"],
            "97c4bbb40e8c5a21f1143899c72e27950c94ee3018b8aa888dbf311e243ac055",
        )
        self.assertEqual(
            reviewed.CATALOG_SHA256,
            hashlib.sha256(json.dumps(
                dict(reviewed.CATALOG), sort_keys=True, separators=(",", ":"),
            ).encode()).hexdigest(),
        )
        with self.assertRaises(TypeError):
            reviewed.CATALOG["requests"] = 1
        with self.assertRaises(TypeError):
            reviewed.CATALOG["receiptInventorySha256"] = "0" * 64
        with self.assertRaises(CorporateActionError):
            reviewed.verify_seed_archive(None)
        old, raw = fixtures()
        with self.assertRaises(CorporateActionError):
            restore(old, raw)

    def test_all_47_packets_are_hashed_and_archive_bytes_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive, catalog = self.make_archive(Path(temporary))
            before = {path.name: path.read_bytes() for path in archive.directory.iterdir()}
            with patch.object(reviewed, "CATALOG", catalog), \
                 patch.object(reviewed, "_file_sha256", wraps=reviewed._file_sha256) as hashes:
                reviewed.verify_seed_archive(archive)
            self.assertEqual(hashes.call_count, 47)
            self.assertEqual(before, {path.name: path.read_bytes() for path in archive.directory.iterdir()})
            # No packet can escape verification merely because it is unrelated.
            with patch.object(reviewed, "CATALOG", catalog):
                for packet in sorted(archive.directory.glob("*.pkl")):
                    content = packet.read_bytes()
                    packet.write_bytes(content + b"corrupt")
                    with self.subTest(packet=packet.name), self.assertRaises(CorporateActionError):
                        reviewed.verify_seed_archive(archive)
                    packet.write_bytes(content)
                reviewed.verify_seed_archive(archive)

    def test_every_receipt_raw_byte_is_pinned_before_packet_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive, catalog = self.make_archive(Path(temporary))
            with patch.object(reviewed, "CATALOG", catalog):
                for receipt in sorted(archive.directory.glob("*.json")):
                    if receipt.name == "manifest.json":
                        continue
                    original = receipt.read_bytes()
                    # Valid JSON with identical parsed content still differs.
                    receipt.write_bytes(original + b"\n")
                    with self.subTest(receipt=receipt.name), \
                         patch.object(reviewed, "_file_sha256") as hashes:
                        with self.assertRaisesRegex(
                            CorporateActionError, "receipt inventory SHA-256 differs",
                        ):
                            reviewed.verify_seed_archive(archive)
                        hashes.assert_not_called()
                    receipt.write_bytes(original)
                reviewed.verify_seed_archive(archive)

    def test_known_provider_errors_are_accepted_and_preserved_only_at_pinned_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive, catalog = self.make_archive(Path(temporary), known_provider_errors=True)
            before = {path.name: path.read_bytes() for path in archive.directory.iterdir()}
            with patch.object(reviewed, "CATALOG", catalog):
                reviewed.verify_seed_archive(archive)
                self.assertEqual(
                    before, {path.name: path.read_bytes() for path in archive.directory.iterdir()},
                )
                for number in (22, 32, 39):
                    receipt = next(archive.directory.glob(f"{number:05d}-*.json"))
                    original = receipt.read_bytes()
                    for change in ("text", "key", "remove_entry", "remove_field"):
                        saved = json.loads(original)
                        errors = saved["providerErrors"]
                        ticker = next(iter(errors))
                        if change == "text":
                            errors[ticker] += " changed"
                        elif change == "key":
                            errors["9999.T"] = errors.pop(ticker)
                        elif change == "remove_entry":
                            del errors[ticker]
                        else:
                            del saved["providerErrors"]
                        receipt.write_text(json.dumps(saved), encoding="utf-8")
                        with self.subTest(number=number, change=change), \
                             patch.object(reviewed, "_file_sha256") as hashes:
                            with self.assertRaisesRegex(
                                CorporateActionError, "receipt inventory SHA-256 differs",
                            ):
                                reviewed.verify_seed_archive(archive)
                            hashes.assert_not_called()
                        receipt.write_bytes(original)
                reviewed.verify_seed_archive(archive)
            self.assertEqual(
                before, {path.name: path.read_bytes() for path in archive.directory.iterdir()},
            )

    def test_top_level_error_is_rejected_even_with_recomputed_test_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive, catalog = self.make_archive(Path(temporary), known_provider_errors=True)
            receipt = next(archive.directory.glob("00022-*.json"))
            saved = json.loads(receipt.read_text(encoding="utf-8"))
            saved["error"] = "top-level request failed"
            receipt.write_text(json.dumps(saved), encoding="utf-8")
            with patch.object(reviewed, "CATALOG", catalog), self.assertRaisesRegex(
                CorporateActionError, "receipt inventory SHA-256 differs",
            ):
                reviewed.verify_seed_archive(archive)
            catalog = self.with_inventory_root(archive, catalog)
            before = {path.name: path.read_bytes() for path in archive.directory.iterdir()}
            with patch.object(reviewed, "CATALOG", catalog), self.assertRaisesRegex(
                CorporateActionError, "archive contains a request error",
            ):
                reviewed.verify_seed_archive(archive)
            self.assertEqual(
                before, {path.name: path.read_bytes() for path in archive.directory.iterdir()},
            )

    def test_provider_errors_must_be_objects_even_with_matching_test_root(self):
        for invalid in (None, False, "", [], ["retained error"]):
            with self.subTest(providerErrors=invalid), tempfile.TemporaryDirectory() as temporary:
                archive, catalog = self.make_archive(Path(temporary))
                receipt = next(archive.directory.glob("00022-*.json"))
                saved = json.loads(receipt.read_text(encoding="utf-8"))
                saved["providerErrors"] = invalid
                receipt.write_text(json.dumps(saved), encoding="utf-8")
                catalog = self.with_inventory_root(archive, catalog)
                with patch.object(reviewed, "CATALOG", catalog), self.assertRaisesRegex(
                    CorporateActionError, "archive providerErrors must be an object",
                ):
                    reviewed.verify_seed_archive(archive)

    def test_target_hash_is_pinned_separately_from_self_consistent_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive, catalog = self.make_archive(Path(temporary))
            wrong = MappingProxyType({**catalog, "targetPacketSha256": "0" * 64})
            with patch.object(reviewed, "CATALOG", wrong), self.assertRaises(CorporateActionError):
                reviewed.verify_seed_archive(archive)
            target = archive.directory / catalog["targetPacket"]
            target.write_bytes(b"replacement")
            receipt = target.with_suffix(".json")
            saved = json.loads(receipt.read_text(encoding="utf-8"))
            saved["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
            receipt.write_text(json.dumps(saved), encoding="utf-8")
            with patch.object(reviewed, "CATALOG", catalog), self.assertRaisesRegex(
                CorporateActionError, "receipt inventory SHA-256 differs",
            ):
                reviewed.verify_seed_archive(archive)
            # A matching synthetic root must not bypass the separate target pin.
            catalog = self.with_inventory_root(archive, catalog)
            with patch.object(reviewed, "CATALOG", catalog), self.assertRaisesRegex(
                CorporateActionError, "reviewed target packet differs",
            ):
                reviewed.verify_seed_archive(archive)

    def test_wrong_context_inventory_errors_and_target_request_fail_closed(self):
        for change in (
            "date", "previous_sha", "count", "missing_receipt", "missing_packet",
            "extra_packet", "duplicate_sequence", "receipt_error", "provider_error",
            "receipt_sha", "request_key", "target_kind", "target_ticker", "target_repair",
        ):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                archive, catalog = self.make_archive(Path(temporary))
                target = archive.directory / catalog["targetPacket"]
                receipt = target.with_suffix(".json")
                if change in ("date", "previous_sha"):
                    key = "date" if change == "date" else "previousSourceSha256"
                    archive.context[key] = "2026-11-05" if change == "date" else "0" * 64
                    archive.manifest["context"] = archive.context
                    self.save_manifest(archive)
                elif change == "count":
                    archive.manifest["requests"] = 46
                    self.save_manifest(archive)
                elif change == "missing_receipt":
                    receipt.unlink()
                elif change == "missing_packet":
                    target.unlink()
                elif change == "extra_packet":
                    (archive.directory / "extra.pkl").write_bytes(b"extra")
                elif change == "duplicate_sequence":
                    other = next(archive.directory.glob("00012-*.json"))
                    other.rename(other.with_name("00011-" + other.name[6:]))
                else:
                    saved = json.loads(receipt.read_text(encoding="utf-8"))
                    if change == "receipt_error":
                        saved["error"] = "retained error"
                    elif change == "provider_error":
                        saved["providerErrors"] = {"3624.T": "retained error"}
                    elif change == "receipt_sha":
                        saved["sha256"] = "0" * 64
                    else:
                        if change == "request_key":
                            saved["request"]["kwargs"]["extra"] = True
                        elif change == "target_kind":
                            saved["request"]["kind"] = "history"
                        elif change == "target_ticker":
                            saved["request"]["tickers"] = ["9999.T"]
                        elif change == "target_repair":
                            saved["request"]["kwargs"]["repair"] = False
                        if change != "request_key":
                            # Keep the filename/request binding valid so the
                            # target-specific request contract is exercised.
                            key = hashlib.sha256(json.dumps(saved["request"], sort_keys=True).encode()).hexdigest()[:20]
                            replacement = target.with_name(f"00011-{key}.pkl")
                            target.rename(replacement)
                            receipt.rename(replacement.with_suffix(".json"))
                            receipt = replacement.with_suffix(".json")
                            catalog = MappingProxyType({**catalog, "targetPacket": replacement.name})
                    receipt.write_text(json.dumps(saved), encoding="utf-8")
                if change != "provider_error":
                    # Exercise the independent guards after the inventory gate.
                    # A newly added provider error instead fails the fixed root.
                    catalog = self.with_inventory_root(archive, catalog)
                with patch.object(reviewed, "CATALOG", catalog), self.assertRaises(CorporateActionError):
                    reviewed.verify_seed_archive(archive)




class RetainedNovemberQuotesTests(unittest.TestCase):
    def setUp(self):
        self.official = pd.DataFrame({
            "symbol": ["6918", "7886"], "date": pd.to_datetime(["2026-11-06"] * 2),
            "open": [2900., 500.], "high": [2953., 509.], "low": [2804., 464.],
            "close": [2951., 509.], "volume": [74600., 7000.], "split_ratio": 0.,
            "provider_repaired": False, "off_session_actions": "",
        })
        self.previous = normalize_daily(self.official, basis_asof="2026-11-06")
        self.previous.attrs["source_sha256"] = reviewed.NOVEMBER_SEED_SHA
        self.raw = self.official.copy()
        self.raw.loc[0, "open"] = 2804.
        self.raw.loc[1, "low"] = 480.
        self.archive = AcquisitionArchive.__new__(AcquisitionArchive)
        self.archive.replay = True
        self.archive.context = {"date": "2026-11-09", "previousSourceSha256": reviewed.NOVEMBER_SEED_SHA}
        self.archive.manifest = {"requests": 47}
        self.archive.sequence = 47
        self.archive.directory = Path("test-only")
        self.archive.manifest_path = self.archive.directory / "manifest.json"

    def restore(self):
        return reviewed.restore_reviewed_november_quotes(
            self.previous, self.raw, basis_asof="2026-11-09", archive=self.archive,
        )

    def test_only_reviewed_cells_change_and_normalize(self):
        with patch.object(reviewed, "_verify_november_archive"):
            result, audits = self.restore()
        pd.testing.assert_frame_equal(result, self.official)
        self.assertEqual(self.raw.loc[0, "open"], 2804.)
        self.assertEqual(self.raw.loc[1, "low"], 480.)
        self.assertEqual([audit["changedCellCount"] for audit in audits.values()], [1, 1])
        normalized = normalize_daily(result, basis_asof="2026-11-09")
        self.assertEqual(normalized.loc[0, "actual_open"], 2900.)
        self.assertEqual(normalized.loc[1, "actual_low"], 464.)
        validate_source_revision(self.previous, normalized)

    def test_fails_closed_on_unreviewed_endpoint_or_archive(self):
        with patch.object(reviewed, "_file_sha256", return_value="different"):
            with self.assertRaisesRegex(CorporateActionError, "retained archive differs"):
                self.restore()
        self.raw.loc[1, "high"] = 510.
        with patch.object(reviewed, "_verify_november_archive"):
            with self.assertRaisesRegex(CorporateActionError, "7886 restoration: OHLCV differs"):
                self.restore()
        self.assertEqual(self.raw.loc[0, "open"], 2804.)

    def test_repeat_and_normal_value_require_verified_lineage(self):
        with patch.object(reviewed, "_verify_november_archive"):
            result, seed_audits = self.restore()
        previous = normalize_daily(result, basis_asof="2026-11-09")
        source_sha = "a" * 64
        previous.attrs.update({
            "source_sha256": source_sha,
            reviewed.NOVEMBER_AUDIT_ATTR: {"dailySha256": source_sha, "restorations": seed_audits},
        })
        for _ in range(2):
            corrected, audits = reviewed.restore_reviewed_november_quotes(
                previous, self.raw, basis_asof="2026-11-09", archive=None,
            )
            pd.testing.assert_frame_equal(corrected, self.official)
            previous.attrs[reviewed.NOVEMBER_AUDIT_ATTR]["restorations"] = audits
        normal, audits = reviewed.restore_reviewed_november_quotes(
            previous, self.official, basis_asof="2026-11-10", archive=None,
        )
        pd.testing.assert_frame_equal(normal, self.official)
        self.assertTrue(all(audit["changedCellCount"] == 0 for audit in audits.values()))
        previous.attrs[reviewed.NOVEMBER_AUDIT_ATTR]["dailySha256"] = "b" * 64
        with self.assertRaisesRegex(CorporateActionError, "source-quality lineage differs"):
            reviewed.restore_reviewed_november_quotes(previous, self.raw, basis_asof="2026-11-10", archive=None)

    def test_live_seed_acquisition_has_no_override(self):
        self.archive.replay = False
        result, audits = self.restore()
        self.assertIs(result, self.raw)
        self.assertEqual(audits, {})



if __name__ == "__main__":
    unittest.main()
