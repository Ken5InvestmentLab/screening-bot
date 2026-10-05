import json
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from weak_early_beta.corporate_actions import (
    ACTION_SOURCE,
    PRICE_BASIS,
    VERSION,
    CorporateActionError,
    action_table,
    fetch_daily,
    normalize_daily,
    quarantine_repaired_volume_revisions,
    source_quality_audit,
    source_quality_receipt,
    validate_source_revision,
)


def daily(ratios=(0, 0, 2, 0), symbol="1234", start="2026-09-24"):
    prices = np.array([100.0, 102.0, 104.0, 106.0])[:len(ratios)]
    return pd.DataFrame({
        "symbol": [symbol] * len(ratios),
        "date": pd.bdate_range(start, periods=len(ratios)),
        "open": prices - 1,
        "high": prices + 2,
        "low": prices - 2,
        "close": prices,
        "volume": np.arange(len(ratios), dtype=float) * 100 + 20_000,
        "split_ratio": ratios,
    })


class CorporateActionTests(unittest.TestCase):
    def test_two_for_one_reconstructs_actual_units_and_event_day_uses_new_basis(self):
        raw = daily()
        result = normalize_daily(raw)
        np.testing.assert_allclose(result.split_factor, [2, 2, 1, 1])
        for column in ("open", "high", "low", "close"):
            np.testing.assert_allclose(result[column], raw[column])
            np.testing.assert_allclose(result[f"actual_{column}"], raw[column] * [2, 2, 1, 1])
        np.testing.assert_allclose(result.actual_volume, raw.volume / [2, 2, 1, 1])
        np.testing.assert_allclose(result.close * result.volume, result.actual_close * result.actual_volume)
        self.assertEqual(result.price_basis.unique().tolist(), [PRICE_BASIS])
        self.assertEqual(result.corporate_actions_version.unique().tolist(), [VERSION])
        self.assertEqual(result.basis_asof.unique().tolist(), [raw.date.max()])
        event = action_table(result).iloc[0]
        self.assertEqual(event.effective_date, raw.iloc[2].date)
        self.assertEqual(event.ratio, 2)
        self.assertEqual(event.source, ACTION_SOURCE)

    def test_reverse_split_and_multiple_actions_compose_in_date_order(self):
        result = normalize_daily(daily(ratios=(0, 2, 0.1, 0)))
        np.testing.assert_allclose(result.split_factor, [0.2, 0.1, 1, 1])
        np.testing.assert_allclose(result.actual_close, result.close * [0.2, 0.1, 1, 1])
        np.testing.assert_allclose(result.actual_volume, result.volume / [0.2, 0.1, 1, 1])
        self.assertEqual(action_table(result).ratio.tolist(), [2, 0.1])

    def test_first_session_event_does_not_rescale_event_day(self):
        result = normalize_daily(daily(ratios=(25, 0, 0, 0)))
        np.testing.assert_allclose(result.split_factor, [1, 1, 1, 1])
        np.testing.assert_allclose(result.actual_close, result.close)
        self.assertEqual(len(action_table(result)), 1)

    def test_action_without_a_price_row_is_preserved_without_fabricating_ohlcv(self):
        raw = daily(ratios=(0, 0, 0, 0))
        event_date = raw.date.max() + pd.Timedelta(days=1)
        raw["off_session_actions"] = ""
        raw.loc[3, "off_session_actions"] = json.dumps([{
            "effective_date": str(event_date.date()), "ratio": 0.1, "source": ACTION_SOURCE,
        }])
        result = normalize_daily(raw)
        self.assertEqual(len(result), 4)
        self.assertEqual(result.date.max(), raw.date.max())
        self.assertEqual(result.basis_asof.max(), event_date)
        np.testing.assert_allclose(result.actual_close, result.close * 0.1)
        self.assertEqual(action_table(result).iloc[0].effective_date, event_date)
        pd.testing.assert_frame_equal(result, normalize_daily(result))

    def test_off_session_action_before_or_between_price_rows_uses_declared_date(self):
        for event_date, factors in (("2026-09-23", [1, 1, 1, 1]), ("2026-09-26", [2, 2, 1, 1])):
            raw = daily(ratios=(0, 0, 0, 0))
            raw["off_session_actions"] = ""
            raw.loc[3, "off_session_actions"] = json.dumps([{
                "effective_date": event_date, "ratio": 2, "source": ACTION_SOURCE,
            }])
            with self.subTest(date=event_date):
                result = normalize_daily(raw)
                np.testing.assert_allclose(result.split_factor, factors)
                self.assertEqual(action_table(result).iloc[0].effective_date, pd.Timestamp(event_date))

    def test_duplicate_or_invalid_off_session_action_is_rejected(self):
        for event_date in ("2026-09-28", "bad-date"):
            raw = daily()
            raw["off_session_actions"] = ""
            raw.loc[3, "off_session_actions"] = json.dumps([{
                "effective_date": event_date, "ratio": 2, "source": ACTION_SOURCE,
            }])
            with self.subTest(date=event_date), self.assertRaises(CorporateActionError):
                normalize_daily(raw)

    def test_basis_is_per_ticker_and_dividends_are_not_split_factors(self):
        one = daily(ratios=(0, 0, 0, 0))
        one["dividends"] = [0, 5, 0, 0]
        one["adj_close"] = one.close * 0.8
        two = daily(ratios=(0, 0), symbol="5678", start="2026-09-28")
        result = normalize_daily(pd.concat([one, two], ignore_index=True))
        self.assertEqual(result[result.symbol.eq("1234")].basis_asof.unique().tolist(), [one.date.max()])
        self.assertEqual(result[result.symbol.eq("5678")].basis_asof.unique().tolist(), [two.date.max()])
        np.testing.assert_allclose(result.actual_close, result.close)
        self.assertTrue(action_table(result).empty)

    def test_normalization_is_idempotent_and_rejects_double_adjustment(self):
        first = normalize_daily(daily())
        second = normalize_daily(first)
        pd.testing.assert_frame_equal(first, second)
        modified = first.copy()
        modified["actual_close"] *= modified.split_factor
        with self.assertRaisesRegex(CorporateActionError, "already been adjusted"):
            normalize_daily(modified)

    def test_missing_action_metadata_does_not_assume_no_split(self):
        with self.assertRaisesRegex(CorporateActionError, "refresh-live"):
            normalize_daily(daily().drop(columns="split_ratio"))
        with self.assertRaisesRegex(CorporateActionError, "incomplete"):
            normalize_daily(normalize_daily(daily()).drop(columns="actual_volume"))

    def test_malformed_ratio_or_basis_is_rejected(self):
        for bad_ratio in (-2, float("nan"), float("inf"), "unknown"):
            raw = daily().astype({"split_ratio": "object"})
            raw.loc[2, "split_ratio"] = bad_ratio
            with self.subTest(ratio=bad_ratio), self.assertRaises(CorporateActionError):
                normalize_daily(raw)
        enriched = normalize_daily(daily())
        enriched.loc[0, "price_basis"] = "already_actual"
        with self.assertRaisesRegex(CorporateActionError, "double adjustment"):
            normalize_daily(enriched)
        enriched = normalize_daily(daily())
        enriched.loc[0, "split_factor"] = 3
        with self.assertRaisesRegex(CorporateActionError, "factor disagrees"):
            normalize_daily(enriched)

    def test_duplicate_and_future_row_are_rejected_and_bad_ohlc_is_audited(self):
        with self.assertRaisesRegex(CorporateActionError, "duplicate"):
            normalize_daily(pd.concat([daily(), daily().iloc[[0]]], ignore_index=True))
        raw = daily()
        raw.loc[0, "open"] = 999
        result = normalize_daily(raw)
        self.assertFalse(result.iloc[0].source_usable)
        self.assertEqual(result.iloc[0].source_issue, "inconsistent_ohlc")
        self.assertEqual(result.iloc[0].open, 999)
        self.assertEqual(result.source_usable.sum(), 3)
        self.assertEqual(len(action_table(result)), 1)
        self.assertEqual(len(source_quality_audit(result)), 1)
        pd.testing.assert_frame_equal(result, normalize_daily(result))
        with self.assertRaisesRegex(CorporateActionError, "after declared snapshot"):
            normalize_daily(daily(), basis_asof="2026-09-24")

    def test_close_outside_range_is_quarantined_without_relaxing_float_tolerance(self):
        raw = daily(ratios=(0, 0, 0, 0))
        raw.loc[0, "close"] = raw.loc[0, "high"] + 1
        raw.loc[1, "close"] = raw.loc[1, "high"] + 1e-8
        result = normalize_daily(raw)
        self.assertFalse(result.iloc[0].source_usable)
        self.assertTrue(result.iloc[1].source_usable)
        audit = source_quality_audit(result)
        self.assertEqual(audit.iloc[0].error_yen, 1)
        self.assertEqual(audit.iloc[0].date, raw.iloc[0].date)
        self.assertEqual(result.iloc[0].close, raw.iloc[0].close)
        receipt = source_quality_receipt(result)
        self.assertEqual(receipt["quarantinedRows"], 1)
        self.assertEqual(receipt["quarantinedSymbols"], ["1234"])
        json.dumps(receipt)
        changed = result.copy()
        changed.loc[0, "source_usable"] = True
        with self.assertRaisesRegex(CorporateActionError, "source_usable disagrees"):
            normalize_daily(changed)

    def test_overflowing_reconstruction_is_rejected(self):
        for ratio in (1e-310, 1e308):
            raw = daily(ratios=(0, 0, ratio, 0))
            with self.subTest(ratio=ratio), self.assertRaises(CorporateActionError):
                normalize_daily(raw)

    def test_unadjusted_split_gap_fails_without_guessing_a_price_correction(self):
        for ratio, pre_multiplier in ((2, 2), (0.1, 0.1)):
            raw = daily(ratios=(0, 0, ratio, 0))
            raw.loc[:1, ["open", "high", "low", "close"]] *= pre_multiplier
            with self.subTest(ratio=ratio), self.assertRaisesRegex(CorporateActionError, "split boundary"):
                normalize_daily(raw)

    def test_overadjusted_event_gap_is_also_rejected_when_no_repair_evidence_exists(self):
        raw = daily()
        raw.loc[:1, ["open", "high", "low", "close"]] /= 2
        with self.assertRaisesRegex(CorporateActionError, "split boundary"):
            normalize_daily(raw)

    def test_declared_new_split_explains_legacy_snapshot_rebase(self):
        old = daily(ratios=(0, 0)).drop(columns="split_ratio")
        now = daily()
        now.loc[:1, ["open", "high", "low", "close"]] = old[["open", "high", "low", "close"]].to_numpy() / 2
        now.loc[:1, "volume"] = old.volume.to_numpy() * 2
        # The post-event prices must continue the adjusted series rather than
        # accidentally introducing a genuine 100% rally in this fixture.
        now.loc[2:, ["open", "high", "low", "close"]] /= 2
        validate_source_revision(old, normalize_daily(now))

    def test_missing_new_action_rejects_historical_scale_revision(self):
        old = daily(ratios=(0, 0)).drop(columns="split_ratio")
        now = daily(ratios=(0, 0, 0, 0))
        now[["open", "high", "low", "close"]] /= 2
        now["volume"] *= 2
        with self.assertRaisesRegex(CorporateActionError, "unexplained historical"):
            validate_source_revision(old, normalize_daily(now))

    def test_legacy_download_basis_is_corpus_snapshot_not_stale_ticker_last_quote(self):
        stale = daily(ratios=(0, 0)).drop(columns="split_ratio")
        later = daily(ratios=(0, 0), symbol="5678", start="2026-09-29").drop(columns="split_ratio")
        previous = pd.concat([stale, later], ignore_index=True)
        raw = stale.copy()
        raw["split_ratio"] = 0
        raw["off_session_actions"] = ["", json.dumps([{
            "effective_date": "2026-09-28", "ratio": 0.1, "source": ACTION_SOURCE,
        }])]
        # The older whole-corpus snapshot already reflected this action despite
        # the stale ticker having no quotes on or after its action date.
        current = normalize_daily(raw, basis_asof=previous.date.max())
        validate_source_revision(previous, current)

    def test_verified_snapshot_and_completed_prices_do_not_change_after_later_split(self):
        old = normalize_daily(daily(ratios=(0, 0)))
        now = daily()
        now[["open", "high", "low", "close"]] /= 2
        now["volume"] *= 2
        current = normalize_daily(now)
        validate_source_revision(old, current)
        np.testing.assert_allclose(old.actual_close, current.iloc[:2].actual_close)
        np.testing.assert_allclose(old.actual_volume, current.iloc[:2].actual_volume)

    def test_legacy_invalid_bar_repaired_to_valid_is_not_used_as_revision_evidence(self):
        old = daily(ratios=(0, 0, 0, 0)).drop(columns="split_ratio")
        old.loc[0, "close"] = 1000
        current = normalize_daily(daily(ratios=(0, 0, 0, 0)))
        validate_source_revision(old, current)

    def test_legacy_marked_repair_requires_coherent_declared_multiplier_and_audit(self):
        raw = daily()
        raw["provider_repaired"] = [True, True, False, False]
        old = raw.drop(columns=["split_ratio", "provider_repaired"]).copy()
        old.loc[:1, ["open", "high", "low", "close"]] *= 2
        old.loc[:1, "volume"] /= 2
        current = normalize_daily(raw)
        receipt = validate_source_revision(old, current)
        self.assertEqual(receipt["previousBasis"], "legacy_unverified")
        self.assertEqual(receipt["acceptedRepairColumnValues"], 10)
        self.assertEqual(receipt["acceptedRepairs"][0]["differences"][0]["current"], 99)
        json.dumps(receipt)
        for missing_evidence in ("flag", "ratio", "coherent"):
            bad = raw.copy()
            if missing_evidence == "flag":
                bad["provider_repaired"] = False
            elif missing_evidence == "ratio":
                bad["split_ratio"] = 0
            else:
                bad.loc[0, "high"] *= 1.01
            with self.subTest(evidence=missing_evidence), self.assertRaisesRegex(CorporateActionError, "unexplained historical"):
                validate_source_revision(old, normalize_daily(bad))

    def _latest_zero_volume_placeholder(self):
        old = daily(ratios=(0, 0), start="2026-09-29")
        old["provider_repaired"] = [False, True]
        old.loc[1, ["open", "high", "low", "close"]] = 1000
        old.loc[1, "volume"] = 0
        extra = daily(ratios=(0, 0, 0), start="2026-09-29").iloc[[2]].copy()
        extra["provider_repaired"] = False
        current = pd.concat([old.copy(), extra], ignore_index=True)
        current.loc[1, "volume"] = 100
        current.loc[1, "provider_repaired"] = False
        return old, current

    def test_latest_repaired_zero_volume_can_settle_with_exact_prices_and_audit(self):
        old, current = self._latest_zero_volume_placeholder()
        receipt = validate_source_revision(normalize_daily(old), normalize_daily(current))
        self.assertEqual(receipt["acceptedRepairColumnValues"], 1)
        repair = receipt["acceptedRepairs"][0]
        self.assertEqual(repair["reason"], "latest_repaired_bar_settled_by_unrepaired_bar")
        self.assertEqual(repair["previousBasis"], "2026-09-30")
        self.assertEqual(repair["currentBasis"], "2026-10-01")
        self.assertEqual(repair["differences"][0]["previousExpected"], 0)
        self.assertEqual(repair["differences"][0]["current"], 100)
        self.assertEqual(repair["differences"][0]["previousActualOHLC"]["close"], 1000)
        json.dumps(receipt)
        # Once settled, the bar has the normal strict historical-volume contract.
        next_snapshot = current.copy()
        next_snapshot.loc[1, "volume"] = 200
        with self.assertRaisesRegex(CorporateActionError, "unexplained historical volume"):
            validate_source_revision(normalize_daily(current), normalize_daily(next_snapshot))

    def test_zero_volume_completion_requires_each_piece_of_source_evidence(self):
        for missing in ("old_repair", "raw_current", "later_basis", "positive_volume"):
            old, current = self._latest_zero_volume_placeholder()
            if missing == "old_repair":
                old.loc[1, "provider_repaired"] = False
            elif missing == "raw_current":
                current.loc[1, "provider_repaired"] = True
            elif missing == "later_basis":
                current = current.iloc[:2].copy()
            else:
                old.loc[1, "volume"] = 100
                current.loc[1, "volume"] = 0
            with self.subTest(missing=missing), self.assertRaisesRegex(CorporateActionError, "unexplained historical volume"):
                validate_source_revision(normalize_daily(old), normalize_daily(current))

    def test_latest_repaired_nonzero_volume_and_small_price_correction_can_settle(self):
        old, current = self._latest_zero_volume_placeholder()
        old.loc[1, "volume"] = 400
        current.loc[1, "volume"] = 500
        old.loc[1, "low"] = old.loc[1, "open"] = 990
        receipt = validate_source_revision(normalize_daily(old), normalize_daily(current))
        self.assertEqual(receipt["acceptedRepairs"][0]["differences"][0]["previousActualOHLC"]["open"], 990)
        self.assertEqual(receipt["acceptedRepairs"][0]["differences"][0]["currentActualOHLC"]["open"], 1000)
        current.loc[1, ["open", "high", "low", "close"]] = 1100
        with self.assertRaisesRegex(CorporateActionError, "unexplained historical open"):
            validate_source_revision(normalize_daily(old), normalize_daily(current))

    def test_unstable_older_repaired_volume_is_quarantined_with_original_values(self):
        old = daily(ratios=(0, 0, 0, 0))
        old["provider_repaired"] = [True, False, False, False]
        current = old.copy()
        current.loc[0, "volume"] *= 0.6
        previous = normalize_daily(old)
        with self.assertRaisesRegex(CorporateActionError, "unexplained historical volume"):
            validate_source_revision(previous, normalize_daily(current))
        reviewed = quarantine_repaired_volume_revisions(previous, normalize_daily(current))
        self.assertFalse(reviewed.iloc[0].source_usable)
        self.assertEqual(reviewed.iloc[0].source_issue, "unstable_historical_repaired_volume")
        self.assertEqual(reviewed.iloc[0].volume, current.iloc[0].volume)
        evidence = json.loads(reviewed.iloc[0].source_revision_evidence)
        self.assertEqual(evidence["previousActualVolume"], old.iloc[0].volume)
        self.assertEqual(evidence["currentActualVolume"], current.iloc[0].volume)
        self.assertEqual(validate_source_revision(previous, reviewed)["quarantinedComparisonRows"], 1)
        pd.testing.assert_frame_equal(reviewed, normalize_daily(reviewed))
        self.assertEqual(source_quality_receipt(reviewed)["issues"][0]["source_revision_evidence"], reviewed.iloc[0].source_revision_evidence)
        # Persist the first comparison as evidence across future acquisitions.
        next_snapshot = current.copy()
        next_snapshot.loc[0, "volume"] *= 0.8
        carried = quarantine_repaired_volume_revisions(reviewed, normalize_daily(next_snapshot))
        self.assertFalse(carried.iloc[0].source_usable)
        self.assertEqual(json.loads(carried.iloc[0].source_revision_evidence)["previousActualVolume"], old.iloc[0].volume)
        next_snapshot.loc[0, "provider_repaired"] = False
        released = quarantine_repaired_volume_revisions(reviewed, normalize_daily(next_snapshot))
        self.assertTrue(released.iloc[0].source_usable)
        next_snapshot.loc[0, "close"] += 1
        with self.assertRaisesRegex(CorporateActionError, "changed price/action evidence"):
            quarantine_repaired_volume_revisions(reviewed, normalize_daily(next_snapshot))

    def test_historical_repair_quarantine_cannot_mask_prices_flags_or_new_actions(self):
        for missing in ("old_repair", "current_repair", "same_price", "same_actions", "older_session"):
            old = daily(ratios=(0, 0, 0, 0))
            old["provider_repaired"] = [True, False, False, False]
            current = old.copy()
            current.loc[0, "volume"] *= 0.6
            if missing == "old_repair":
                old.loc[0, "provider_repaired"] = False
            elif missing == "current_repair":
                current.loc[0, "provider_repaired"] = False
            elif missing == "same_price":
                current.loc[0, "close"] += 1
            elif missing == "same_actions":
                current.loc[0, "split_ratio"] = 2
            else:
                old = old.iloc[:1]
            previous = normalize_daily(old)
            reviewed = quarantine_repaired_volume_revisions(previous, normalize_daily(current))
            with self.subTest(missing=missing), self.assertRaisesRegex(CorporateActionError, "unexplained historical"):
                validate_source_revision(previous, reviewed)

    def test_quarantine_evidence_is_checked_on_every_cache_read(self):
        old = daily(ratios=(0, 0, 0, 0))
        old["provider_repaired"] = [True, False, False, False]
        current = old.copy()
        current.loc[0, "volume"] *= 0.6
        reviewed = quarantine_repaired_volume_revisions(normalize_daily(old), normalize_daily(current))
        for changed in ("price", "volume", "basis", "actions", "flag", "evidence"):
            bad = reviewed.copy()
            evidence = json.loads(bad.iloc[0].source_revision_evidence)
            if changed == "price":
                evidence["previousActualOHLC"]["open"] += 1
            elif changed == "volume":
                evidence["currentActualVolume"] += 1
            elif changed == "basis":
                evidence["previousBasis"] = evidence["date"]
            elif changed == "actions":
                evidence["historicalActions"] = [{"effective_date": evidence["date"], "ratio": 2}]
            elif changed == "flag":
                evidence["previousProviderRepaired"] = False
            else:
                evidence["identity"] = "unknown"
            bad.loc[0, "source_revision_evidence"] = json.dumps(evidence)
            with self.subTest(changed=changed), self.assertRaisesRegex(CorporateActionError, "invalid repaired-volume revision evidence"):
                normalize_daily(bad)

    def test_repaired_zero_volume_on_older_session_still_requires_review(self):
        old, current = self._latest_zero_volume_placeholder()
        old = pd.concat([old, current.iloc[[2]]], ignore_index=True)
        extra = daily(ratios=(0, 0, 0, 0), start="2026-09-29").iloc[[3]].copy()
        extra["provider_repaired"] = False
        current = pd.concat([current, extra], ignore_index=True)
        with self.assertRaisesRegex(CorporateActionError, "unexplained historical volume"):
            validate_source_revision(normalize_daily(old), normalize_daily(current))

    def test_zero_volume_completion_cannot_accept_a_new_historical_action(self):
        old, current = self._latest_zero_volume_placeholder()
        current.loc[1, "split_ratio"] = 2
        # Keep all actual historical prices/volumes unchanged so only the
        # unrecorded historical action prevents accepting the placeholder.
        current.loc[0, ["open", "high", "low", "close"]] /= 2
        current.loc[0, "volume"] *= 2
        with self.assertRaisesRegex(CorporateActionError, "unexplained historical"):
            validate_source_revision(normalize_daily(old), normalize_daily(current))

    def test_provider_repair_flag_does_not_relax_verified_snapshot_comparison(self):
        raw = daily()
        old = normalize_daily(raw)
        raw[["open", "high", "low", "close"]] /= 2
        raw["volume"] *= 2
        raw["provider_repaired"] = True
        with self.assertRaisesRegex(CorporateActionError, "unexplained historical"):
            validate_source_revision(old, normalize_daily(raw))

    def test_repair_that_introduces_a_declared_split_sized_gap_is_quarantined(self):
        raw = daily()
        raw.loc[:1, ["open", "high", "low", "close"]] /= 2
        raw["provider_repaired"] = [True, True, False, False]
        result = normalize_daily(raw)
        self.assertFalse(result.source_usable.any())
        self.assertEqual(result.source_issue.unique().tolist(), ["ambiguous_provider_repair_basis"])
        self.assertEqual(len(action_table(result)), 1)
        pd.testing.assert_frame_equal(result, normalize_daily(result))

    def test_tiny_consolidation_repaired_volume_is_retained_but_not_assumed_adjusted(self):
        raw = daily(ratios=(0, 0, 1e-6, 0))
        raw["provider_repaired"] = [True, False, False, False]
        result = normalize_daily(raw)
        self.assertFalse(result.iloc[0].source_usable)
        self.assertTrue(result.iloc[1].source_usable)
        self.assertEqual(result.iloc[0].source_issue, "ambiguous_repaired_volume_basis")
        self.assertEqual(result.iloc[0].volume, raw.iloc[0].volume)
        pd.testing.assert_frame_equal(result, normalize_daily(result))

    def test_long_absence_after_tiny_consolidation_does_not_assume_same_security_identity(self):
        raw = daily(ratios=(0, 0, 0, 0))
        raw.loc[2:, "date"] += pd.Timedelta(days=400)
        raw["off_session_actions"] = ""
        raw.loc[3, "off_session_actions"] = json.dumps([{
            "effective_date": "2026-09-28", "ratio": 1e-6, "source": ACTION_SOURCE,
        }])
        result = normalize_daily(raw)
        self.assertFalse(result.source_usable.any())
        self.assertEqual(result.source_issue.unique().tolist(), ["ambiguous_security_identity_after_consolidation"])
        self.assertEqual(len(result), len(raw))
        self.assertEqual(len(action_table(result)), 1)
        pd.testing.assert_frame_equal(result, normalize_daily(result))

    def test_recorded_event_removal_or_revision_is_rejected(self):
        old = normalize_daily(daily())
        for ratio in (0, 3):
            now = daily()
            now.loc[2, "split_ratio"] = ratio
            with self.subTest(ratio=ratio), self.assertRaisesRegex(CorporateActionError, "removed/revised"):
                validate_source_revision(old, normalize_daily(now))

    @patch("yfinance.download")
    def test_fetch_requests_actions_repair_and_keeps_split_only_basis(self, download):
        raw = daily()
        source = raw.set_index("date").rename(columns={
            "open": "Open", "high": "High", "low": "Low", "close": "Close",
            "volume": "Volume", "split_ratio": "Stock Splits",
        }).drop(columns="symbol")
        source["Adj Close"] = source.Close * 0.9
        source["Dividends"] = [0, 3, 0, 0]
        source["Repaired?"] = [True, True, False, False]
        download.return_value = source
        result = fetch_daily(pd.DataFrame({"ticker": ["1234.T"]}), "5y")
        args = download.call_args.kwargs
        self.assertTrue(args["actions"])
        self.assertTrue(args["repair"])
        self.assertFalse(args["auto_adjust"])
        self.assertEqual(result.provider_repaired.tolist(), [True, True, False, False])
        np.testing.assert_allclose(result.close, raw.close)
        np.testing.assert_allclose(result.actual_close, raw.close * [2, 2, 1, 1])

    @patch("weak_early_beta.corporate_actions.time.sleep")
    @patch("yfinance.Ticker")
    @patch("yfinance.download")
    def test_fetch_multi_ticker_schema_and_missing_actions_fail(self, download, ticker, sleep):
        one = daily(ratios=(0, 0, 0, 0)).set_index("date").drop(columns="symbol")
        one = one.rename(columns={"split_ratio": "Stock Splits"})
        two = one.copy()
        download.return_value = pd.concat({"1234.T": one, "5678.T": two}, axis=1)
        result = fetch_daily(pd.DataFrame({"ticker": ["1234.T", "5678.T"]}), "5y")
        self.assertEqual(sorted(result.symbol.unique()), ["1234", "5678"])
        download.return_value = one.drop(columns="Stock Splits")
        ticker.return_value.history.return_value = download.return_value
        with self.assertRaisesRegex(CorporateActionError, "did not return split actions"):
            fetch_daily(pd.DataFrame({"ticker": ["1234.T"]}), "5y")
        self.assertEqual(ticker.return_value.history.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @patch("yfinance.Ticker")
    @patch("yfinance.download")
    def test_partial_batch_recovers_only_failed_ticker_with_repair_and_actions(self, download, ticker):
        one = daily().set_index("date").drop(columns="symbol").rename(columns={"split_ratio": "Stock Splits"})
        failed = one.drop(columns="Stock Splits") * np.nan
        download.return_value = pd.concat({"1234.T": one, "5678.T": failed}, axis=1)
        recovered = one.copy()
        recovered["Repaired?"] = [True, False, False, False]
        ticker.return_value.history.return_value = recovered
        result = fetch_daily(pd.DataFrame({"ticker": ["1234.T", "5678.T"]}), "5y")
        download.assert_called_once()
        ticker.assert_called_once_with("5678.T")
        args = ticker.return_value.history.call_args.kwargs
        self.assertTrue(args["actions"])
        self.assertTrue(args["repair"])
        self.assertFalse(args["auto_adjust"])
        self.assertFalse(args["raise_errors"])
        restored = result[result.symbol.eq("5678")]
        self.assertEqual(restored.provider_repaired.tolist(), [True, False, False, False])
        np.testing.assert_allclose(restored.actual_close, one.close * [2, 2, 1, 1])
        self.assertEqual(action_table(result).symbol.tolist(), ["1234", "5678"])

    @patch("yfinance.Ticker")
    @patch("yfinance.download")
    def test_missing_ticker_identity_in_partial_response_is_recovered_not_omitted(self, download, ticker):
        one = daily().set_index("date").drop(columns="symbol").rename(columns={"split_ratio": "Stock Splits"})
        download.return_value = pd.concat({"1234.T": one}, axis=1).swaplevel(axis=1)
        ticker.return_value.history.return_value = one
        result = fetch_daily(pd.DataFrame({"ticker": ["1234.T", "5678.T"]}), "5y")
        ticker.assert_called_once_with("5678.T")
        self.assertEqual(sorted(result.symbol.unique()), ["1234", "5678"])

    @patch("weak_early_beta.corporate_actions.time.sleep")
    @patch("yfinance.Ticker")
    @patch("yfinance.download")
    def test_empty_batch_can_recover_a_single_ticker_and_keeps_off_session_event(self, download, ticker, sleep):
        one = daily(ratios=(0, 0, 0, 0)).set_index("date").drop(columns="symbol").rename(columns={"split_ratio": "Stock Splits"})
        event_date = one.index.max() + pd.Timedelta(days=1)
        one.loc[event_date, :] = np.nan
        one.loc[event_date, "Stock Splits"] = 0.1
        download.return_value = pd.DataFrame()
        ticker.return_value.history.side_effect = [pd.DataFrame(), one]
        result = fetch_daily(pd.DataFrame({"ticker": ["1234.T"]}), "5y")
        self.assertEqual(download.call_count, 3)
        self.assertEqual(ticker.return_value.history.call_count, 2)
        self.assertEqual(len(result), 4)
        self.assertEqual(action_table(result).iloc[0].effective_date, event_date)

    @patch("weak_early_beta.corporate_actions.time.sleep")
    @patch("yfinance.Ticker")
    @patch("yfinance.download")
    def test_unknown_split_values_and_persistent_empty_history_fail_bounded(self, download, ticker, sleep):
        one = daily().set_index("date").drop(columns="symbol").rename(columns={"split_ratio": "Stock Splits"})
        for failed in (one * np.nan, one.assign(**{"Stock Splits": np.nan})):
            with self.subTest(columns=failed.columns.tolist()):
                download.return_value = pd.concat({"1234.T": one, "5678.T": failed}, axis=1)
                ticker.reset_mock()
                ticker.return_value.history.return_value = failed
                with self.assertRaisesRegex(CorporateActionError, "5678.T after 3 individual attempts"):
                    fetch_daily(pd.DataFrame({"ticker": ["1234.T", "5678.T"]}), "5y")
                self.assertEqual(ticker.return_value.history.call_count, 3)

    @patch("yfinance.Ticker")
    @patch("yfinance.download")
    def test_recovered_history_still_requires_source_revision_evidence(self, download, ticker):
        previous = normalize_daily(daily(ratios=(0, 0, 0, 0)))
        one = daily(ratios=(0, 0, 0, 0)).set_index("date").drop(columns="symbol").rename(columns={"split_ratio": "Stock Splits"})
        one[["open", "high", "low", "close"]] /= 2
        one["volume"] *= 2
        download.return_value = one.drop(columns="Stock Splits")
        ticker.return_value.history.return_value = one
        with self.assertRaisesRegex(CorporateActionError, "unexplained historical"):
            fetch_daily(pd.DataFrame({"ticker": ["1234.T"]}), "5y", previous=previous)

    @patch("yfinance.download")
    def test_fetch_retains_an_action_only_provider_row_in_journal(self, download):
        raw = daily(ratios=(0, 0, 0, 0)).set_index("date").drop(columns="symbol")
        raw = raw.rename(columns={"split_ratio": "Stock Splits"})
        event_date = raw.index.max() + pd.Timedelta(days=1)
        raw.loc[event_date, :] = float("nan")
        raw.loc[event_date, "volume"] = 0
        raw.loc[event_date, "Stock Splits"] = 0.1
        download.return_value = raw
        result = fetch_daily(pd.DataFrame({"ticker": ["1234.T"]}), "5y")
        self.assertEqual(len(result), 4)
        self.assertEqual(result.date.max(), raw.index[-2])
        self.assertEqual(result.basis_asof.max(), event_date)
        self.assertEqual(action_table(result).iloc[0].effective_date, event_date)
        np.testing.assert_allclose(result.actual_close, result.close * 0.1)


if __name__ == "__main__":
    unittest.main()
