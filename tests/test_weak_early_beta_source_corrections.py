"""Regression guards for the reviewed Oct 5 -> Oct 6 Cloud source transition.

The original cache had no 8377 action and mixed actual units on exactly three
sessions. Synthetic fixtures retain that defect without reading ignored caches,
changing canonical ledger rows, or permitting generic split-sized revisions.
"""

import copy
import hashlib
import json
import unittest
from unittest.mock import patch

import pandas as pd

from weak_early_beta.corporate_actions import (
    CorporateActionError,
    fetch_daily,
    normalize_daily,
    validate_source_revision,
)
from weak_early_beta.source_corrections import (
    CORRECTION_DATES,
    DEFAULT_MANIFEST,
    PREVIOUS_SHA256,
    PRIMARY_SOURCE_URLS,
    reviewed_comparison_overrides,
)


OLD_ACTUAL = {
    "2026-09-24": (860.5, 861.2999877929688, 831.5, 835.7999877929688, 7629000),
    "2026-09-25": (850, 881.5, 850, 881.5, 6986000),
    "2026-09-28": (882.0999755859375, 890, 877.5, 879.4000244140625, 4965000),
}
NEW_ACTUAL = {
    "2026-09-24": (8605, 8613, 8315, 8358, 762900),
    "2026-09-25": (8500, 8815, 8500, 8815, 698600),
    "2026-09-28": (8821, 8900, 8775, 8794, 496500),
}
COLUMNS = ("open", "high", "low", "close", "volume")


def raw_fixtures():
    dates = (
        "2026-09-17", "2026-09-18", *CORRECTION_DATES,
        "2026-09-29", "2026-10-05", "2026-10-06",
    )
    old_rows, new_rows = [], []
    for date in dates:
        pre_action = date < "2026-09-29"
        stable = (8500, 8600, 8400, 8500, 800000) if pre_action else (900, 910, 890, 900, 1000000)
        old_values = OLD_ACTUAL.get(date, stable)
        new_values = NEW_ACTUAL.get(date, stable)
        factor = 10 if pre_action else 1
        common = {"symbol": "8377", "date": pd.Timestamp(date), "provider_repaired": False}
        if date != "2026-10-06":
            old_rows.append({**common, **dict(zip(COLUMNS, old_values)), "split_ratio": 0.0})
        adjusted = [value / factor for value in new_values[:4]] + [new_values[4] * factor]
        new_rows.append({
            **common, **dict(zip(COLUMNS, adjusted)),
            "split_ratio": 10.0 if date == "2026-09-29" else 0.0,
        })
    return pd.DataFrame(old_rows), pd.DataFrame(new_rows)


def fixtures():
    old, new = raw_fixtures()
    previous = normalize_daily(old, basis_asof="2026-10-05")
    previous.attrs["source_sha256"] = PREVIOUS_SHA256
    return previous, normalize_daily(new, basis_asof="2026-10-06")


class ReviewedSourceCorrectionTests(unittest.TestCase):
    def test_matches_and_never_mutates_either_input(self):
        previous, current = fixtures()
        before_previous, before_current = previous.copy(deep=True), current.copy(deep=True)
        receipt = validate_source_revision(previous, current)
        pd.testing.assert_frame_equal(previous, before_previous)
        pd.testing.assert_frame_equal(current, before_current)
        self.assertEqual(previous.attrs, before_previous.attrs)
        self.assertEqual(current.attrs, before_current.attrs)
        self.assertEqual(receipt["acceptedRepairColumnValues"], 0)
        self.assertEqual(receipt["comparedRows"], len(previous))
        self.assertEqual(len(receipt["sourceCorrectionAudit"]), 1)
        audit = receipt["sourceCorrectionAudit"][0]
        self.assertEqual(audit["previousSourceSha256"], PREVIOUS_SHA256)
        self.assertEqual(audit["manifestSha256"], hashlib.sha256(DEFAULT_MANIFEST.read_bytes()).hexdigest())
        self.assertEqual(audit["dates"], list(CORRECTION_DATES))
        self.assertEqual(audit["symbol"], "8377")
        self.assertEqual(audit["primarySourceURLs"], list(PRIMARY_SOURCE_URLS))
        for date in CORRECTION_DATES:
            self.assertEqual(audit["oldActualValues"][date], dict(zip(COLUMNS, OLD_ACTUAL[date])))
            self.assertEqual(audit["newActualValues"][date], dict(zip(COLUMNS, NEW_ACTUAL[date])))
        json.dumps(receipt, allow_nan=False)
        # The old cache remains an internally consistent, uncorrected snapshot.
        pd.testing.assert_frame_equal(previous, normalize_daily(previous))
        pd.testing.assert_frame_equal(current, normalize_daily(current))

    def test_wrong_hash_cannot_bypass_ordinary_validation(self):
        previous, current = fixtures()
        previous.attrs["source_sha256"] = "0" * 64
        overrides, audit = reviewed_comparison_overrides(
            previous, current, previous_source_sha256=previous.attrs["source_sha256"],
        )
        self.assertEqual((overrides, audit), ({}, []))
        with self.assertRaisesRegex(CorporateActionError, "unexplained historical"):
            validate_source_revision(previous, current)
        receipt = validate_source_revision(previous, previous)
        self.assertEqual(receipt["sourceCorrectionAudit"], [])

    def test_wrong_new_price_endpoint_raises_inside_generic_price_tolerance(self):
        previous, _ = fixtures()
        _, raw = raw_fixtures()
        raw.loc[raw.date.eq(pd.Timestamp("2026-09-24")), "open"] += 0.0002
        current = normalize_daily(raw, basis_asof="2026-10-06")
        with self.assertRaisesRegex(CorporateActionError, "current 2026-09-24 open endpoint"):
            validate_source_revision(previous, current)

    def test_current_volume_fingerprint_is_exact(self):
        previous, _ = fixtures()
        _, raw = raw_fixtures()
        raw.loc[raw.date.eq(pd.Timestamp("2026-09-24")), "volume"] += 1
        current = normalize_daily(raw, basis_asof="2026-10-06")
        with self.assertRaisesRegex(CorporateActionError, "current 2026-09-24 volume endpoint"):
            validate_source_revision(previous, current)

    def test_wrong_old_endpoint_raises_inside_generic_price_tolerance(self):
        raw, _ = raw_fixtures()
        raw.loc[raw.date.eq(pd.Timestamp("2026-09-24")), "open"] += 0.002
        previous = normalize_daily(raw, basis_asof="2026-10-05")
        previous.attrs["source_sha256"] = PREVIOUS_SHA256
        _, current = fixtures()
        with self.assertRaisesRegex(CorporateActionError, "previous 2026-09-24 open endpoint"):
            validate_source_revision(previous, current)

    def test_old_action_present_raises(self):
        raw, _ = raw_fixtures()
        raw.loc[raw.date.eq(pd.Timestamp("2026-09-29")), "split_ratio"] = 10.0
        previous = normalize_daily(raw, basis_asof="2026-10-05")
        previous.attrs["source_sha256"] = PREVIOUS_SHA256
        _, current = fixtures()
        with self.assertRaisesRegex(CorporateActionError, "previous complete action journal"):
            validate_source_revision(previous, current)

    def test_wrong_new_journal_raises(self):
        previous, _ = fixtures()
        _, raw = raw_fixtures()
        raw.loc[raw.date.eq(pd.Timestamp("2026-09-29")), "split_ratio"] = 2.0
        current = normalize_daily(raw, basis_asof="2026-10-06")
        with self.assertRaisesRegex(CorporateActionError, "current complete action journal"):
            validate_source_revision(previous, current)

    def test_additional_new_journal_event_raises(self):
        previous, _ = fixtures()
        _, raw = raw_fixtures()
        raw.loc[raw.date.eq(pd.Timestamp("2026-10-05")), "split_ratio"] = 2.0
        current = normalize_daily(raw, basis_asof="2026-10-06")
        with self.assertRaisesRegex(CorporateActionError, "current complete action journal"):
            validate_source_revision(previous, current)

    def test_wrong_current_basis_raises(self):
        previous, _ = fixtures()
        _, raw = raw_fixtures()
        current = normalize_daily(raw, basis_asof="2026-10-07")
        with self.assertRaisesRegex(CorporateActionError, "current basis/symbol"):
            validate_source_revision(previous, current)

    def test_provider_flags_and_source_usability_are_required(self):
        for endpoint, field in (
            ("previous", "provider_repaired"),
            ("current", "provider_repaired"),
            ("previous", "source_usable"),
            ("current", "source_usable"),
        ):
            old, new = raw_fixtures()
            raw = old if endpoint == "previous" else new
            mask = raw.date.eq(pd.Timestamp("2026-09-24"))
            if field == "provider_repaired":
                raw.loc[mask, field] = True
            else:
                raw.loc[mask, "open"] = raw.loc[mask, "high"] + 1
            previous = normalize_daily(old, basis_asof="2026-10-05")
            previous.attrs["source_sha256"] = PREVIOUS_SHA256
            current = normalize_daily(new, basis_asof="2026-10-06")
            with self.subTest(endpoint=endpoint, field=field):
                with self.assertRaisesRegex(CorporateActionError, f"{endpoint} 2026-09-24 {field}"):
                    validate_source_revision(previous, current)

    def test_unrelated_symbol_revision_remains_fail_closed(self):
        old, new = raw_fixtures()
        other_old = old.copy()
        other_old["symbol"] = "1234"
        other_old[list(COLUMNS)] = [100, 101, 99, 100, 1000]
        other_new = new.copy()
        other_new["symbol"] = "1234"
        other_new["split_ratio"] = 0.0
        other_new[list(COLUMNS)] = [200, 202, 198, 200, 1000]
        previous = normalize_daily(pd.concat([old, other_old]), basis_asof="2026-10-05")
        previous.attrs["source_sha256"] = PREVIOUS_SHA256
        current = normalize_daily(pd.concat([new, other_new]), basis_asof="2026-10-06")
        with self.assertRaisesRegex(CorporateActionError, "unexplained historical open revision for 1234"):
            validate_source_revision(previous, current)

    def test_other_8377_session_still_uses_ordinary_validation(self):
        previous, _ = fixtures()
        _, raw = raw_fixtures()
        mask = raw.date.eq(pd.Timestamp("2026-09-18"))
        raw.loc[mask, ["open", "high", "low", "close"]] *= 1.1
        current = normalize_daily(raw, basis_asof="2026-10-06")
        with self.assertRaisesRegex(CorporateActionError, "unexplained historical open revision for 8377 2026-09-18"):
            validate_source_revision(previous, current)

    def test_declared_manifest_transition_version_and_sources_are_required(self):
        previous, current = fixtures()
        manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        for field, value in (
            ("current_basis", "2026-10-07"),
            ("symbol", "1234"),
            ("manifest_version", 2),
            ("primary_sources", []),
        ):
            bad = copy.deepcopy(manifest)
            bad[field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(CorporateActionError, "reviewed source correction mismatch"):
                    validate_source_revision(previous, current, source_corrections_manifest=bad)
        for field in ("manifest_version", "primary_sources"):
            bad = copy.deepcopy(manifest)
            del bad[field]
            with self.subTest(missing=field):
                with self.assertRaisesRegex(CorporateActionError, "manifest fields"):
                    validate_source_revision(previous, current, source_corrections_manifest=bad)
        # An unrelated old SHA never activates even a mismatched transition.
        same = current.copy(deep=True)
        same.attrs["source_sha256"] = "0" * 64
        receipt = validate_source_revision(same, current, source_corrections_manifest=bad)
        self.assertEqual(receipt["sourceCorrectionAudit"], [])

    def test_explicit_manifest_has_an_auditable_canonical_hash(self):
        previous, current = fixtures()
        manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        original = copy.deepcopy(manifest)
        receipt = validate_source_revision(previous, current, source_corrections_manifest=manifest)
        expected = hashlib.sha256(json.dumps(
            manifest, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")).hexdigest()
        self.assertEqual(receipt["sourceCorrectionAudit"][0]["manifestSha256"], expected)
        self.assertEqual(manifest, original)

    def test_hash_is_preserved_before_normalization_discards_attrs(self):
        previous, current = fixtures()
        real_normalize = normalize_daily

        def without_attrs(*args, **kwargs):
            result = real_normalize(*args, **kwargs)
            result.attrs.clear()
            return result

        with patch("weak_early_beta.corporate_actions.normalize_daily", side_effect=without_attrs):
            receipt = validate_source_revision(previous, current)
        self.assertEqual(receipt["sourceCorrectionAudit"][0]["previousSourceSha256"], PREVIOUS_SHA256)

    @patch("yfinance.download")
    def test_fetch_passes_previous_full_file_hash_and_returns_original_new_basis(self, download):
        previous, expected_current = fixtures()
        original_previous = previous.copy(deep=True)
        _, raw = raw_fixtures()
        download.return_value = raw.set_index("date").drop(columns="symbol").rename(
            columns={"split_ratio": "Stock Splits", "provider_repaired": "Repaired?"},
        )
        result = fetch_daily(pd.DataFrame({"ticker": ["8377.T"]}), "5y", previous=previous)
        audit = result.attrs["source_revision_receipt"]["sourceCorrectionAudit"]
        self.assertEqual(audit[0]["previousSourceSha256"], PREVIOUS_SHA256)
        pd.testing.assert_frame_equal(previous, original_previous)
        for column in (*COLUMNS, *(f"actual_{name}" for name in COLUMNS), "split_factor"):
            pd.testing.assert_series_equal(result[column], expected_current[column])
        self.assertEqual(result.basis_asof.unique().tolist(), [pd.Timestamp("2026-10-06")])


if __name__ == "__main__":
    unittest.main()
