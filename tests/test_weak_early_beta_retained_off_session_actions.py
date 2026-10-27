"""Synthetic provider frames and mocked acquisition only; no live cache access."""

import copy
import json
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from weak_early_beta import reviewed_off_session_actions as retained
from weak_early_beta.corporate_actions import (
    ACTUAL_COLUMNS, BASIS_COLUMNS, OHLC, CorporateActionError, action_table,
    fetch_daily, normalize_daily, source_quality_receipt, validate_source_revision,
)


def fixtures():
    dates = pd.bdate_range("2021-10-26", periods=450).append(pd.bdate_range(end="2026-10-26", periods=239))
    old_raw = pd.DataFrame({"symbol": "8303", "date": dates, "open": 100., "high": 101.,
                            "low": 99., "close": 100., "volume": 10000., "split_ratio": 0.,
                            "provider_repaired": False, "off_session_actions": ""})
    old_raw.loc[688, "off_session_actions"] = json.dumps([retained.EVENT])
    old = normalize_daily(old_raw)
    old.attrs["source_sha256"] = retained.SEED_SHA256
    raw = old_raw.copy()
    raw["date"] = dates[1:].append(pd.DatetimeIndex(["2026-10-27"]))
    raw["off_session_actions"] = ""
    return old, raw


def carry(old, raw):
    return retained.retain_reviewed_off_session_actions(old, raw, basis_asof=raw.date.max())


class RetainedOffSessionActionTests(unittest.TestCase):
    def test_seed_retains_journal_only_preserves_inputs_and_quarantine(self):
        old, raw = fixtures()
        originals = [copy.deepcopy(frame) for frame in (old, raw)]
        result, audit = carry(old, raw)
        pd.testing.assert_frame_equal(result.drop(columns="off_session_actions"), raw.drop(columns="off_session_actions"))
        self.assertEqual(json.loads(result.iloc[-1].off_session_actions), [retained.EVENT])
        self.assertEqual(result.off_session_actions.ne("").sum(), 1)
        normalized = normalize_daily(result)
        self.assertFalse(normalized.source_usable.any())
        self.assertTrue(normalized.source_issue.eq(retained.ISSUE).all())
        self.assertEqual(action_table(normalized).ratio.tolist(), [5e-8])
        receipt = validate_source_revision(old, normalized)
        self.assertEqual(receipt["comparedRows"], 0)
        self.assertEqual(receipt["quarantinedComparisonRows"], 688)
        self.assertEqual(source_quality_receipt(normalized)["quarantinedRows"], len(normalized))
        self.assertEqual(audit[0]["seedSourceSha256"], retained.SEED_SHA256)
        self.assertEqual(audit[0]["previousSourceSha256"], retained.SEED_SHA256)
        self.assertEqual(audit[0]["providerEvent"]["effective_date"], "2023-09-28")
        self.assertEqual(audit[0]["legalEffectiveDate"], "2023-10-02")
        self.assertIs(audit[0]["noPriceEdits"], True)
        self.assertEqual(audit[0]["rawOHLCVBeforeSha256"], audit[0]["rawOHLCVAfterSha256"])
        for frame, original in zip((old, raw), originals):
            pd.testing.assert_frame_equal(frame, original)
            self.assertEqual(frame.attrs, original.attrs)

    def test_unknown_hash_or_absent_lineage_never_carries(self):
        for sha in (None, "", "0" * 64, "not-a-sha"):
            old, raw = fixtures()
            old.attrs["source_sha256"] = sha
            with self.subTest(sha=sha), self.assertRaises(CorporateActionError):
                carry(old, raw)

    def test_retained_identity_cannot_enter_live_scoring(self):
        from weak_early_beta import model

        result, _ = carry(*fixtures())
        features = normalize_daily(result)
        # Even otherwise-complete features cannot make this identity eligible.
        for field in model.base.FEATURES:
            features[field] = 1.
        self.assertTrue(model.eligible_live_rows(features).empty)

    def test_old_quarantine_metadata_and_regular_actions_are_required(self):
        for field in (*ACTUAL_COLUMNS, *BASIS_COLUMNS):
            old, raw = fixtures()
            if field == "off_session_actions":
                with self.assertRaises(CorporateActionError):
                    result, _ = carry(old.drop(columns=field), raw)
                    validate_source_revision(old.drop(columns=field), normalize_daily(result))
                continue
            with self.subTest(missing=field), self.assertRaises(CorporateActionError):
                carry(old.drop(columns=field), raw)
        for field, value in (("source_usable", True), ("source_issue", "inconsistent_ohlc"),
                             ("price_basis", "other"), ("corporate_actions_version", "other"),
                             ("corporate_actions_source", "other"), ("split_ratio", 2.),
                             ("basis_asof", pd.Timestamp("2026-10-25"))):
            old, raw = fixtures()
            old.loc[0, field] = value
            with self.subTest(field=field), self.assertRaises(CorporateActionError):
                carry(old, raw)

    def test_conflicting_journals_dates_ratios_sources_and_priced_date_reject(self):
        for endpoint in (0, 1):
            for event in ({**retained.EVENT, "effective_date": "2023-10-02"},
                          {**retained.EVENT, "ratio": 5e-7},
                          {**retained.EVENT, "source": "other"},
                          {**retained.EVENT, "extra": "unreviewed"}):
                frames = fixtures()
                frames[endpoint].loc[688, "off_session_actions"] = json.dumps([event])
                # Extra provider keys are left to the existing ordinary parser.
                if endpoint == 1 and "extra" in event:
                    continue
                with self.subTest(endpoint=endpoint, event=event), self.assertRaises(CorporateActionError):
                    carry(*frames)
        for endpoint in (0, 1):
            for change in ("priced_date", "no_bracket", "regular_action", "duplicate_event"):
                frames = fixtures()
                frame = frames[endpoint]
                if change == "priced_date":
                    frame.loc[449, "date"] = pd.Timestamp("2023-09-28")
                elif change == "no_bracket":
                    frame["date"] = pd.bdate_range("2024-01-01", periods=len(frame))
                elif change == "regular_action":
                    frame.loc[0, "split_ratio"] = 2.
                else:
                    frame.loc[0, "off_session_actions"] = json.dumps([retained.EVENT])
                    frame.loc[688, "off_session_actions"] = json.dumps([retained.EVENT])
                with self.subTest(endpoint=endpoint, change=change), self.assertRaises(CorporateActionError):
                    carry(*frames)

    def test_seed_bounds_and_missing_old_metadata_cannot_authorize(self):
        old, raw = fixtures()
        old = old.iloc[1:].copy()
        with self.assertRaises(CorporateActionError):
            carry(old, raw)
        old, raw = fixtures()
        old.loc[0, "price_basis"] = None
        with self.assertRaises(CorporateActionError):
            carry(old, raw)

    def test_provider_declared_event_uses_ordinary_validation_without_duplicate(self):
        old, raw = fixtures()
        old.attrs.clear()
        raw.loc[688, "off_session_actions"] = json.dumps([retained.EVENT])
        result, audit = carry(old, raw)
        self.assertEqual(audit, [])
        self.assertIs(result, raw)
        self.assertEqual(len(action_table(normalize_daily(result))), 1)
        validate_source_revision(old, normalize_daily(result))

    @staticmethod
    def rolling():
        old, raw = fixtures()
        result, audit = carry(old, raw)
        previous = normalize_daily(result)
        previous.attrs = {"source_sha256": "1" * 64, retained.PRIOR_AUDIT_ATTR: {
            "dailySha256": "1" * 64, "actions": audit,
        }}
        next_raw = raw.copy()
        next_raw["date"] = pd.DatetimeIndex(raw.date.iloc[1:]).append(pd.DatetimeIndex(["2026-10-28"]))
        return previous, next_raw

    def test_next_daily_carries_only_matching_quality_audit(self):
        previous, raw = self.rolling()
        result, audit = carry(previous, raw)
        self.assertEqual(audit[0]["previousSourceSha256"], "1" * 64)
        self.assertEqual(audit[0]["seedSourceSha256"], retained.SEED_SHA256)
        self.assertEqual(audit[0]["previousBounds"]["lastDate"], "2026-10-27")
        self.assertEqual(audit[0]["currentBounds"]["lastDate"], "2026-10-28")
        validate_source_revision(previous, normalize_daily(result))

    def test_lineage_survives_missing_declared_then_missing_provider_event(self):
        previous, raw = self.rolling()
        raw.loc[688, "off_session_actions"] = json.dumps([retained.EVENT])
        declared, audit = carry(previous, raw)
        pd.testing.assert_frame_equal(declared, raw)
        self.assertEqual(audit[0]["actionStatus"], "provider-declared")
        previous = normalize_daily(declared)
        validate_source_revision(normalize_daily(carry(*fixtures())[0]), previous)
        previous.attrs = {"source_sha256": "2" * 64, retained.PRIOR_AUDIT_ATTR: {
            "dailySha256": "2" * 64, "actions": audit,
        }}
        raw["date"] = pd.DatetimeIndex(raw.date.iloc[1:]).append(pd.DatetimeIndex(["2026-10-29"]))
        raw["off_session_actions"] = ""
        result, audit = carry(previous, raw)
        self.assertEqual(audit[0]["actionStatus"], "retained")
        self.assertEqual(len(action_table(normalize_daily(result))), 1)
        validate_source_revision(previous, normalize_daily(result))

    def test_stale_or_tampered_lineage_fails_closed(self):
        changes = {"catalogSha256": "0" * 64, "seedSourceSha256": "0" * 64,
                   "providerEvent": {**retained.EVENT, "ratio": 5e-7}, "legalEffectiveDate": "2023-09-28",
                   "originalJournal": [], "currentBounds": retained.SEED_BOUNDS,
                   "seedBounds": {}, "primarySourceURLs": [], "noPriceEdits": 1,
                   "previousSourceSha256": None, "previousBounds": {},
                   "actionStatus": "other",
                   "rawOHLCVBeforeSha256": "0" * 64, "rawOHLCVAfterSha256": "0" * 64}
        for field, value in changes.items():
            old, raw = self.rolling()
            old.attrs[retained.PRIOR_AUDIT_ATTR]["actions"][0][field] = value
            with self.subTest(field=field), self.assertRaises(CorporateActionError):
                carry(old, raw)
        old, raw = self.rolling()
        old.attrs[retained.PRIOR_AUDIT_ATTR]["dailySha256"] = "2" * 64
        with self.assertRaises(CorporateActionError):
            carry(old, raw)

    def test_verified_lineage_survives_fractional_csv_roundtrip(self):
        from weak_early_beta import model
        from weak_early_beta.cli import _write_daily_cache

        old, raw = fixtures()
        for field in (*OHLC, "volume"):
            raw[field] += 0.123456789012345
        first, audit = carry(old, raw)
        first = normalize_daily(first)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.csv"
            _write_daily_cache(first, path)
            previous = pd.read_csv(path, parse_dates=["date"], dtype={"symbol": str})
            digest = model.sha256(path)
            previous.attrs = {"source_sha256": digest, retained.PRIOR_AUDIT_ATTR: {
                "dailySha256": digest, "actions": audit,
            }}
            raw["date"] = pd.DatetimeIndex(raw.date.iloc[1:]).append(pd.DatetimeIndex(["2026-10-28"]))
            result, next_audit = carry(previous, raw)
            self.assertEqual(next_audit[0]["previousSourceSha256"], digest)
            validate_source_revision(previous, normalize_daily(result))

    def test_other_symbols_missing_actions_still_fail_ordinary_gate(self):
        old, raw = fixtures()
        old["symbol"] = raw["symbol"] = "9999"
        result, audit = carry(old, raw)
        self.assertIs(result, raw)
        self.assertEqual(audit, [])
        with self.assertRaisesRegex(CorporateActionError, "removed/revised"):
            validate_source_revision(old, normalize_daily(raw))

    def test_mocked_fetch_retains_before_first_normalization_and_audits(self):
        old, raw = fixtures()
        provider = raw.set_index("date")[[*OHLC, "volume", "split_ratio"]].rename(columns={
            **{key: key.title() for key in (*OHLC, "volume")}, "split_ratio": "Stock Splits",
        })
        with patch("yfinance.download", return_value=provider), \
             patch("weak_early_beta.reviewed_repair_releases.reviewed_repair_release_keys", return_value=(set(), [])):
            result = fetch_daily(pd.DataFrame({"ticker": ["8303.T"]}), "5y", previous=old)
        self.assertFalse(result.source_usable.any())
        self.assertEqual(len(result.attrs["source_revision_receipt"]["retainedOffSessionActions"]), 1)
        pd.testing.assert_frame_equal(result[[*OHLC, "volume", "split_ratio"]], raw[[*OHLC, "volume", "split_ratio"]])
        old.attrs.clear()
        with patch("yfinance.download", return_value=provider), self.assertRaises(CorporateActionError):
            fetch_daily(pd.DataFrame({"ticker": ["8303.T"]}), "5y", previous=old)

    def test_cli_attaches_only_small_matching_quality_lineage(self):
        from weak_early_beta import model
        from weak_early_beta.cli import _write_daily_cache, command_daily

        class VendorReached(Exception):
            pass

        for quality_kind in ("matching", "wrong_hash", "wrong_identity", "absent"):
            with self.subTest(quality=quality_kind), tempfile.TemporaryDirectory() as temporary:
                previous, _ = self.rolling()
                expected_audit = previous.attrs[retained.PRIOR_AUDIT_ATTR]["actions"]
                path = Path(temporary) / "daily.csv"
                _write_daily_cache(previous, path)
                digest = model.sha256(path)
                if quality_kind != "absent":
                    quality = {"identity": "CLOUD_SOURCE_QUALITY_V1", "daily_sha256": digest,
                               "issues": ["do not copy into attrs"] * 100,
                               "source_revision": {"retainedOffSessionActions": expected_audit,
                                                   "quarantinedComparisons": ["also do not copy"]}}
                    if quality_kind == "wrong_hash":
                        quality["daily_sha256"] = "0" * 64
                    elif quality_kind == "wrong_identity":
                        quality["identity"] = "other"
                    path.with_suffix(".source-quality.json").write_text(json.dumps(quality), encoding="utf-8")

                def capture(universe, period, *, previous):
                    expected = {"source_sha256": digest}
                    if quality_kind == "matching":
                        expected[retained.PRIOR_AUDIT_ATTR] = {"dailySha256": digest, "actions": expected_audit}
                    self.assertEqual(previous.attrs, expected)
                    raise VendorReached

                args = Namespace(refresh_live=True, as_of="2026-10-28", period="5y",
                                 ledger=str(Path(temporary) / "ledger.csv"), daily_corpus=str(path))
                with patch("weak_early_beta.restrictions.fetch_jpx_restricted_symbols", return_value=[]), \
                     patch("weak_early_beta.cli._load_or_bootstrap", return_value=pd.DataFrame()), \
                     patch.object(model.base, "jpx_universe", return_value=pd.DataFrame({"code": ["8303"]})), \
                     patch("weak_early_beta.corporate_actions.fetch_daily", side_effect=capture), \
                     patch("weak_early_beta.cli._write_daily_cache") as write, redirect_stderr(StringIO()):
                    with self.assertRaises(VendorReached):
                        command_daily(args)
                    write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
