"""Local reviewed endpoints only; no cache, provider, runner or live services."""

import copy
import hashlib
import io
import json
import unittest
from unittest.mock import patch

import pandas as pd

from weak_early_beta import reviewed_repair_releases as releases
from weak_early_beta.corporate_actions import (
    ACTION_SOURCE, ACTUAL_COLUMNS, OHLC, REVISION_EVIDENCE, CorporateActionError,
    fetch_daily, normalize_daily, quarantine_repaired_volume_revisions, validate_source_revision,
)


def manifest():
    return json.loads(releases.MANIFEST_PATH.read_bytes())


def fixtures():
    reviewed = manifest()
    frames = []
    for endpoint in ("previous", "current"):
        raw = pd.DataFrame([
            {"symbol": "523A", "date": pd.Timestamp(spec["date"]),
             **spec[f"{endpoint}_actual"], "split_ratio": 0,
             "provider_repaired": endpoint == "previous",
             REVISION_EVIDENCE: json.dumps(spec["previous_quarantine_evidence"]) if endpoint == "previous" else ""}
            for spec in reviewed["rows"]
        ])
        frames.append(normalize_daily(raw, basis_asof=reviewed[f"{endpoint}_basis"]))
    frames[0].attrs["source_sha256"] = releases.PREVIOUS_SHA256
    return frames


def verify(previous, current):
    return releases.reviewed_repair_release_keys(
        previous, current, previous_source_sha256=releases.PREVIOUS_SHA256,
    )


class ReviewedRepairReleaseTests(unittest.TestCase):
    def test_exact_pinned_transition_is_atomic_audited_and_does_not_mutate_inputs(self):
        previous, current = fixtures()
        originals = [copy.deepcopy(frame) for frame in (previous, current)]
        keys, audit = verify(previous, current)
        self.assertEqual(keys, {("523A", pd.Timestamp(date)) for date in releases.RELEASE_DATES})
        self.assertEqual(audit[0]["manifestSha256"], hashlib.sha256(releases.MANIFEST_PATH.read_bytes()).hexdigest())
        self.assertEqual(audit[0]["previousSourceSha256"], releases.PREVIOUS_SHA256)
        reviewed = manifest()
        self.assertEqual(audit[0]["primarySourceURLs"], reviewed["primary_sources"])
        self.assertEqual(audit[0]["corroboratingSources"], reviewed["corroborating_sources"])
        for spec in reviewed["rows"]:
            date = spec["date"]
            self.assertEqual(audit[0]["originalQuarantineEvidence"][date], spec["previous_quarantine_evidence"])
            self.assertEqual(audit[0]["oldActualValues"][date], spec["previous_actual"])
            self.assertEqual(audit[0]["newActualValues"][date], spec["current_actual"])
        result = quarantine_repaired_volume_revisions(previous, current)
        pd.testing.assert_frame_equal(result, current)
        self.assertEqual(result.attrs["reviewedRepairReleases"], audit)
        receipt = validate_source_revision(previous, result)
        self.assertEqual(receipt["quarantinedComparisonRows"], 4)
        self.assertEqual(receipt["sourceCorrectionAudit"], [])
        self.assertEqual(receipt["acceptedRepairs"], [])
        for actual, original in zip((previous, current), originals):
            pd.testing.assert_frame_equal(actual, original)
            self.assertEqual(actual.attrs, original.attrs)

    def test_unrelated_hash_never_reads_manifest_and_keeps_original_carried_failure(self):
        previous, current = fixtures()
        previous.attrs["source_sha256"] = "0" * 64
        with patch.object(type(releases.MANIFEST_PATH), "read_bytes", side_effect=AssertionError("not consulted")) as read:
            self.assertEqual(releases.reviewed_repair_release_keys(previous, current, previous_source_sha256="0" * 64), (set(), []))
            with self.assertRaisesRegex(CorporateActionError, "changed price/action evidence"):
                quarantine_repaired_volume_revisions(previous, current)
            read.assert_not_called()

    def test_each_old_new_actual_and_raw_ohlcv_on_every_date_must_match_exactly(self):
        # Sub-tolerance changes are intentional: this is an exact fingerprint.
        for endpoint in (0, 1):
            for position in range(4):
                for field in (*OHLC, "volume", *ACTUAL_COLUMNS):
                    previous, current = fixtures()
                    frame = (previous, current)[endpoint]
                    frame[field] = frame[field].astype(float)
                    frame.loc[position, field] += 1e-7
                    with self.subTest(endpoint=endpoint, position=position, field=field):
                        with self.assertRaises(CorporateActionError):
                            verify(previous, current)
                        # Normalization must not erase a near-exact mismatch.
                        with self.assertRaises(CorporateActionError):
                            quarantine_repaired_volume_revisions(previous, current)

    def test_missing_duplicate_or_changed_date_on_either_endpoint_fails_closed(self):
        for endpoint in (0, 1):
            for position in range(4):
                for change in ("missing", "duplicate", "date", "symbol"):
                    frames = fixtures()
                    frame = frames[endpoint]
                    if change == "missing":
                        frames[endpoint] = frame.drop(index=position)
                    elif change == "duplicate":
                        frames[endpoint] = pd.concat([frame, frame.iloc[[position]]], ignore_index=True)
                    elif change == "date":
                        frame.loc[position, "date"] += pd.Timedelta(days=10)
                    else:
                        frame.loc[position, "symbol"] = "524A"
                    with self.subTest(endpoint=endpoint, position=position, change=change), self.assertRaises(CorporateActionError):
                        verify(*frames)

    def test_target_metadata_flags_issue_and_evidence_are_exact(self):
        changes = {
            "split_factor": 1.0000000000001, "split_ratio": 1e-13,
            "price_basis": "unknown", "corporate_actions_source": "other",
            "corporate_actions_version": "other", "provider_repaired": None,
            "source_usable": None, "source_issue": "other", REVISION_EVIDENCE: "{}",
        }
        for endpoint in (0, 1):
            for position in range(4):
                for field, value in changes.items():
                    frames = fixtures()
                    frame = frames[endpoint]
                    if field in ("provider_repaired", "source_usable"):
                        value = not bool(frame.loc[position, field])
                    frame[field] = frame[field].astype(object)
                    frame.loc[position, field] = value
                    with self.subTest(endpoint=endpoint, position=position, field=field), self.assertRaises(CorporateActionError):
                        verify(*frames)
        previous, current = fixtures()
        previous.loc[0, "split_factor"] += 1e-13
        with self.assertRaises(CorporateActionError):
            quarantine_repaired_volume_revisions(previous, current)

    def test_every_original_evidence_field_is_verified_including_extra_fields(self):
        for field in (*manifest()["rows"][0]["previous_quarantine_evidence"], "extra"):
            previous, current = fixtures()
            evidence = json.loads(previous.loc[3, REVISION_EVIDENCE])
            if field == "previousActualOHLC":
                evidence[field]["open"] += 1e-7
            elif field == "previousProviderRepaired":
                evidence[field] = 1  # bool/number equality must not authorize it
            elif field == "historicalActions":
                evidence[field] = [{"effective_date": "2026-04-01", "ratio": 2}]
            else:
                evidence[field] = "changed"
            previous.loc[3, REVISION_EVIDENCE] = json.dumps(evidence)
            with self.subTest(field=field), self.assertRaises(CorporateActionError):
                verify(previous, current)

    def test_null_metadata_cannot_be_hidden_by_nullable_dtype_or_normalization(self):
        for endpoint in (0, 1):
            for field in ("price_basis", "corporate_actions_source", "corporate_actions_version"):
                frames = fixtures()
                frames[endpoint][field] = frames[endpoint][field].astype("string")
                frames[endpoint].loc[0, field] = pd.NA
                with self.subTest(endpoint=endpoint, field=field):
                    with self.assertRaises(CorporateActionError):
                        verify(*frames)
                    with self.assertRaises(CorporateActionError):
                        quarantine_repaired_volume_revisions(*frames, previous_source_sha256=releases.PREVIOUS_SHA256)

    def test_missing_required_metadata_and_missing_evidence_fail_closed(self):
        for endpoint in (0, 1):
            for field in ("basis_asof", "split_factor", "split_ratio", "provider_repaired", "source_usable",
                          "source_issue", "off_session_actions", "price_basis", "corporate_actions_source",
                          "corporate_actions_version", *ACTUAL_COLUMNS):
                frames = fixtures()
                frames[endpoint] = frames[endpoint].drop(columns=field)
                with self.subTest(endpoint=endpoint, field=field), self.assertRaises(CorporateActionError):
                    verify(*frames)
        previous, current = fixtures()
        with self.assertRaises(CorporateActionError):
            verify(previous.drop(columns=REVISION_EVIDENCE), current)
        for bad_previous in (previous.iloc[:0], previous.drop(columns="corporate_actions_version")):
            with self.assertRaises(CorporateActionError):
                quarantine_repaired_volume_revisions(bad_previous, current, previous_source_sha256=releases.PREVIOUS_SHA256)

    def test_complete_symbol_basis_and_actions_outside_target_rows_are_checked(self):
        for endpoint in (0, 1):
            for change in ("all_basis", "extra_basis", "extra_metadata", "priced_action", "off_session_action"):
                frames = fixtures()
                frame = frames[endpoint]
                extra = frame.iloc[[0]].copy()
                extra["date"] = pd.Timestamp("2026-09-01")
                extra[REVISION_EVIDENCE] = ""
                if change == "all_basis":
                    frame["basis_asof"] += pd.Timedelta(days=1)
                elif change == "extra_basis":
                    extra["basis_asof"] += pd.Timedelta(days=1)
                elif change == "extra_metadata":
                    extra["corporate_actions_version"] = "other"
                elif change == "priced_action":
                    extra["split_ratio"] = 2
                else:
                    extra["off_session_actions"] = json.dumps([{
                        "effective_date": "2026-04-01", "ratio": 2, "source": ACTION_SOURCE,
                    }])
                frames[endpoint] = pd.concat([frame, extra], ignore_index=True)
                with self.subTest(endpoint=endpoint, change=change), self.assertRaises(CorporateActionError):
                    verify(*frames)

    def test_entire_manifest_bytes_are_pinned_and_read_failures_are_closed(self):
        frames = fixtures()
        contents = releases.MANIFEST_PATH.read_bytes()
        self.assertEqual(hashlib.sha256(contents).hexdigest(), releases.MANIFEST_SHA256)
        for tampered in (contents + b"\n", contents.replace(b"523A", b"524A"), b"not-json"):
            with self.subTest(tampered=tampered[:20]), patch.object(type(releases.MANIFEST_PATH), "read_bytes", return_value=tampered):
                with self.assertRaisesRegex(CorporateActionError, "manifest SHA-256"):
                    verify(*frames)
        with patch.object(type(releases.MANIFEST_PATH), "read_bytes", side_effect=OSError("missing")):
            with self.assertRaises(CorporateActionError):
                verify(*frames)

    def test_manifest_shape_is_validated_in_addition_to_hash(self):
        frames = fixtures()
        for change in ("root", "extra", "version", "basis", "dates", "rows", "values", "evidence", "sources", "corroboration"):
            reviewed = manifest()
            if change == "root":
                reviewed = []
            elif change == "extra":
                reviewed["extra"] = True
            elif change == "version":
                reviewed["manifest_version"] = True
            elif change == "basis":
                reviewed["current_basis"] = "2026-10-28"
            elif change == "dates":
                reviewed["rows"][-1]["date"] = "2026-08-22"
            elif change == "rows":
                reviewed["rows"].pop()
            elif change == "values":
                reviewed["rows"][0]["current_actual"]["open"] = True
            elif change == "evidence":
                reviewed["rows"][0]["previous_quarantine_evidence"].pop("historicalActions")
            elif change == "sources":
                reviewed["primary_sources"] = []
            else:
                reviewed["corroborating_sources"][0]["rows_verified"] = 3
            contents = json.dumps(reviewed).encode()
            # Deliberately supply a matching test digest to exercise shape checks
            # separately; production has neither a manifest nor a digest argument.
            with self.subTest(change=change), patch.object(type(releases.MANIFEST_PATH), "read_bytes", return_value=contents), patch.object(
                releases, "MANIFEST_SHA256", hashlib.sha256(contents).hexdigest(),
            ), self.assertRaises(CorporateActionError):
                verify(*frames)

    def test_cache_csv_reread_works_with_original_evidence_and_empty_new_evidence(self):
        previous, current = fixtures()
        restored = [pd.read_csv(io.StringIO(f.to_csv(index=False)), parse_dates=["date"], dtype={"symbol": str}) for f in (previous, current)]
        result = quarantine_repaired_volume_revisions(*restored, previous_source_sha256=releases.PREVIOUS_SHA256)
        pd.testing.assert_frame_equal(result, normalize_daily(current))
        validate_source_revision(restored[0], result)
        audit = result.attrs["reviewedRepairReleases"][0]
        self.assertEqual(audit["originalQuarantineEvidence"]["2026-08-21"], manifest()["rows"][3]["previous_quarantine_evidence"])
        pd.testing.assert_frame_equal(result, normalize_daily(pd.read_csv(
            io.StringIO(result.to_csv(index=False)), parse_dates=["date"], dtype={"symbol": str},
        )))

    def test_unmarked_unrelated_price_and_action_revisions_still_throw(self):
        previous, current = fixtures()
        extra = current.iloc[[0]].copy()
        extra["symbol"] = "9999"
        old_extra = extra.copy()
        old_extra["basis_asof"] = pd.Timestamp("2026-10-26")
        for change in ("price", "action"):
            now = extra.copy()
            if change == "price":
                now[list(OHLC)] *= 2
                now[list(ACTUAL_COLUMNS[:4])] *= 2
            else:
                old_extra["split_ratio"] = 2  # action on its sole priced session
            old = pd.concat([previous, old_extra], ignore_index=True)
            new = pd.concat([current, now], ignore_index=True)
            result = quarantine_repaired_volume_revisions(old, new, previous_source_sha256=releases.PREVIOUS_SHA256)
            with self.subTest(change=change), self.assertRaises(CorporateActionError):
                validate_source_revision(old, result)

    @patch("yfinance.download")
    def test_mocked_fetch_captures_hash_and_retains_audit_when_normalization_drops_attrs(self, download):
        previous, current = fixtures()
        original = copy.deepcopy(previous)
        # Synthetic final session supplies fetch_daily's provider basis; the four
        # reviewed observations themselves come only from the local manifest.
        raw = current[["symbol", "date", *OHLC, "volume", "split_ratio", "provider_repaired"]].copy()
        extra = raw.iloc[[0]].copy()
        extra["date"] = pd.Timestamp("2026-10-27")
        raw = pd.concat([raw, extra], ignore_index=True)
        download.return_value = raw.set_index("date").drop(columns="symbol").rename(columns={
            "split_ratio": "Stock Splits", "provider_repaired": "Repaired?",
        })

        def without_attrs(*args, **kwargs):
            frame = normalize_daily(*args, **kwargs)
            frame.attrs.clear()
            return frame

        with patch("weak_early_beta.corporate_actions.normalize_daily", side_effect=without_attrs):
            result = fetch_daily(pd.DataFrame({"ticker": ["523A.T"]}), "5y", previous=previous)
        download.assert_called_once()
        receipt = result.attrs["source_revision_receipt"]
        self.assertEqual(receipt["reviewedRepairReleases"], result.attrs["reviewedRepairReleases"])
        self.assertEqual(receipt["reviewedRepairReleases"][0]["previousSourceSha256"], releases.PREVIOUS_SHA256)
        self.assertEqual(receipt["quarantinedComparisonRows"], 4)
        self.assertEqual(receipt["sourceCorrectionAudit"], [])
        self.assertTrue(result.source_usable.all())
        self.assertFalse(result.provider_repaired.any())
        self.assertTrue(result.source_issue.eq("").all())
        self.assertTrue(result[REVISION_EVIDENCE].eq("").all())
        pd.testing.assert_frame_equal(result.loc[:3, current.columns].reset_index(drop=True), current)
        pd.testing.assert_frame_equal(previous, original)
        self.assertEqual(previous.attrs, original.attrs)


if __name__ == "__main__":
    unittest.main()
