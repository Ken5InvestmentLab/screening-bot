"""Cloud report population, receipt-gated identity and all-metric consistency."""

import json
import base64
import gzip
import re
import unittest
from unittest.mock import patch

import pandas as pd

from weak_early_beta.corporate_actions import normalize_daily
from weak_early_beta.config import COMBINED_STACKED_ID, COMBINED_UNIQUE_ID
from weak_early_beta.ledger import bootstrap_historical
from weak_early_beta.metrics import build_metrics, build_monthly_metrics
from weak_early_beta.model import attach_forward_rows
from weak_early_beta.report import MASKED_PENDING_NOTICE, _detection_rows, _page_shell, _variant_page, render_analytics_report, render_mode_report, render_report, _aggregate_variant_payload
from weak_early_beta.report_preferences import released_history, select_report_view, validate_price_cap
from weak_early_beta.trade_basis import LEGACY_PRICE_BASIS_VERSION


def actual_trade(symbol="9Z9Z", price=1000, *, complete=True, split=1, signal_date="2026-09-01"):
    count = 7 if complete else 6
    actual = [price, price, price + 1, price + 2, price + 3, price + 4, (price + 5) / split][:count]
    factors = [split] * min(count, 6) + ([1] if complete else [])
    adjusted = [value / factor for value, factor in zip(actual, factors)]
    daily = normalize_daily(pd.DataFrame({
        "date": pd.bdate_range(signal_date, periods=count), "symbol": symbol,
        "open": adjusted, "high": [value + 1 for value in adjusted],
        "low": [value - 1 for value in adjusted], "close": adjusted,
        "volume": [10_000 * factor for factor in factors],
        "split_ratio": [0] * min(count, 6) + ([split if split != 1 else 0] if complete else []),
    }))
    selected = pd.DataFrame([{"date": pd.Timestamp(signal_date), "symbol": symbol,
                              "selector": "volr20_low", "model_period": "2026-09"}])
    result = attach_forward_rows(selected, daily)
    result["company_name"] = "PRIVATE_IDENTITY_SENTINEL"
    result["fundamental_html"] = "PRIVATE_FUNDAMENTAL_SENTINEL"
    result["fundamental_discord_url"] = "https://example.test/PRIVATE_URL_SENTINEL"
    return result


def visible_prices(output):
    return sorted(set(float(value) for value in re.findall(r'data-signal-actual-close="([0-9.]+)"', output)))


def payload(output):
    data = json.loads(re.search(r'<script id="cloud-analytics-data" type="application/json">(.*?)</script>', output, re.S).group(1))
    if data.get("encoding") == "gzip-base64-json":
        data["variants"] = {key: json.loads(gzip.decompress(base64.b64decode(value["gzip"]))) for key, value in data["variants"].items()}
    for variant in data["variants"].values():
        variant["html"] = re.sub(r"<!--cloud-shared:([a-z0-9_-]+)-->", lambda match: data.get("sharedHtml", {})[match.group(1)], variant["html"])
    return data


class ReportPreferenceTests(unittest.TestCase):
    generated = pd.Timestamp("2026-10-04", tz="Asia/Tokyo")

    def test_purchase_cta_is_in_free_information_only(self):
        from weak_early_beta.report import render_guide
        for render in (render_report, render_analytics_report):
            free = render(actual_trade(), pd.DataFrame(), self.generated, mask_pending=True)
            full = render(actual_trade(), pd.DataFrame(), self.generated)
            self.assertIn('href="/purchase">有料プランを見る</a>', free)
            self.assertNotIn('href="/purchase">有料プランを見る</a>', full)
        self.assertIn('href="/purchase">有料プランを見る</a>', render_guide(self.generated, mask_pending=True))
        self.assertNotIn('href="/purchase">有料プランを見る</a>', render_guide(self.generated))

    def test_settings_copy_preserves_endpoint_choices_and_share_limits(self):
        from weak_early_beta.report import _settings_panel
        output = _settings_panel()
        self.assertIn('<span>確定日</span>', output)
        self.assertIn('<span>基準となる株数</span>', output)
        self.assertNotIn('基本の買付株数', output)
        self.assertIn('<option value="d5_close">5営業日後 終値</option><option value="d6_open" selected>6営業日後 始値</option>', output)
        self.assertIn('id="cloud-base-shares" type="number" min="100" max="1000000" step="100"', output)
        self.assertIn('基準となる株数×一致条件数', output)

    def test_explicit_price_cap_validation_without_rounding(self):
        for value in (1, "1500", 1000.01, "0.01", "1500.00"):
            self.assertEqual(validate_price_cap(value), float(value))
        self.assertIsNone(validate_price_cap(None))
        for value in (True, 0, -1, "", float("inf"), float("nan"), 1.001, "0.001", "90071992547410"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_price_cap(value)

    def test_compact_public_payload_has_no_precomputed_grid_or_unreleased_rows(self):
        frame = pd.concat([actual_trade("A001", 900), actual_trade("A002", 1500), actual_trade("Z999", 731.29, complete=False)], ignore_index=True)
        for free in (False, True):
            cache = {"bundle-assets": {}}
            output = _variant_page(frame, self.generated, "home", mask_pending=free, _variant_cache=cache)
            data = payload(output)
            self.assertEqual(data["version"], 2)
            self.assertEqual(data["variants"], {})
            self.assertLess(len(json.dumps(data).encode()), 2_000)
            self.assertEqual(cache["bundle-assets"], {})
            self.assertNotIn('"entry_open"', json.dumps(data))
            self.assertNotIn('"symbol"', json.dumps(data))
            self.assertNotIn('2023_2025', data["scopes"])
            if free:
                self.assertNotIn('data-symbol="Z999"', output)
                self.assertNotIn('731.29', output)
                self.assertIn(MASKED_PENDING_NOTICE, output)
                self.assertEqual(output.replace(MASKED_PENDING_NOTICE, ""), _variant_page(released_history(frame), self.generated, "home", mask_pending=True))

    def test_price_boundary_uses_verified_actual_close_not_adjusted_reference(self):
        below = actual_trade("A001", 999.99)
        equal = actual_trade("A002", 1000)
        above = actual_trade("A003", 1000.01)
        missing = actual_trade("A004", 50)
        missing["signal_actual_close_status"] = "missing"
        frame = pd.concat([below, equal, above, missing], ignore_index=True)
        frame["signal_close"] = 1  # Must never make the above/missing rows eligible.
        self.assertEqual(set(select_report_view(frame).symbol), {"A001", "A002"})
        self.assertEqual(len(select_report_view(frame, 1000.01)), 3)
        self.assertEqual(len(select_report_view(frame, None)), 4)

    def test_2022_exclusion_is_read_only_and_applies_to_every_endpoint(self):
        frame = actual_trade()
        older = frame.copy()
        older["signal_date"] = pd.Timestamp("2022-12-01")
        source = pd.concat([older, frame], ignore_index=True)
        original = source.copy(deep=True)
        for endpoint in ("d5_close", "d6_open"):
            view = select_report_view(source, None, endpoint)
            self.assertEqual(len(view), 1)
            self.assertEqual(pd.Timestamp(view.iloc[0].signal_date).year, 2026)
        pd.testing.assert_frame_equal(source, original)

    def test_d6_view_uses_independent_original_lot_and_preserves_d5(self):
        source = actual_trade(split=2)
        source["source_scope"] = "EXACT_CANONICAL_2023_2026"
        source["price_basis"] = LEGACY_PRICE_BASIS_VERSION
        source["entry_open"] = 17  # Simulate frozen canonical adjusted economics.
        source["gross_return"] = .99
        original = source.copy(deep=True)
        view = select_report_view(source, 1000, "d6_open")
        self.assertEqual(view.iloc[0].entry_open, 1000)
        self.assertEqual(view.iloc[0].entry_shares, 100)
        self.assertAlmostEqual(view.iloc[0].gross_return, .005)
        self.assertAlmostEqual(view.iloc[0].one_hundred_shares_pl_yen, 500)
        self.assertTrue(pd.isna(view.iloc[0].display_d5_gross_return))
        self.assertEqual(view.iloc[0].raw_d5_gross_return, .99)
        pd.testing.assert_frame_equal(source, original)

    def test_unverified_d6_economics_never_becomes_zero_or_a_d5_substitute(self):
        source = actual_trade(complete=False)
        self.assertTrue(pd.notna(source.iloc[0].gross_return))
        view = select_report_view(source, 1000, "d6_open")
        self.assertTrue(pd.isna(view.iloc[0].gross_return))
        self.assertTrue(pd.isna(view.iloc[0].one_hundred_shares_pl_yen))

    def test_d6_view_maps_selected_holding_actions_and_proceeds(self):
        for ratio in (2, .5):
            with self.subTest(ratio=ratio):
                source = actual_trade(split=ratio)
                original = source.copy(deep=True)
                view = select_report_view(source, 1000, "d6_open")
                row = view.iloc[0]
                self.assertEqual(row.exit_shares, 100 * ratio)
                self.assertAlmostEqual(row.exit_proceeds_yen, 100500)
                self.assertEqual(row.holding_action_factor, ratio)
                self.assertEqual(json.loads(row.applied_actions_json), [{"effective_date": "2026-09-09", "ratio": ratio}])
                self.assertEqual(original.iloc[0].exit_shares, 100)
                self.assertEqual(original.iloc[0].holding_action_factor, 1)
                pd.testing.assert_frame_equal(source, original)

    def test_d6_unverified_or_missing_holding_economics_never_reuses_d5(self):
        source = actual_trade(split=2)
        for missing in (False, True):
            with self.subTest(missing=missing):
                candidate = source.copy(deep=True)
                if missing:
                    candidate = candidate.drop(columns=["sixth_exit_shares", "sixth_exit_proceeds_yen", "sixth_holding_action_factor", "sixth_applied_actions_json"])
                else:
                    candidate["sixth_economics_status"] = "review_required"
                view = select_report_view(candidate, 1000, "d6_open")
                for column in ("exit_shares", "exit_proceeds_yen", "holding_action_factor"):
                    self.assertTrue(pd.isna(view.iloc[0][column]), column)
                self.assertEqual(view.iloc[0].applied_actions_json, "")
                self.assertTrue(pd.notna(source.iloc[0].exit_proceeds_yen))

    def test_free_all_pages_omit_d5_mature_identity_until_verified_d6(self):
        pending = actual_trade(complete=False)
        for renderer in (
            lambda: render_report(pending, pd.DataFrame(), self.generated, mask_pending=True),
            lambda: render_mode_report(pending, pd.DataFrame(), pd.DataFrame(), self.generated, "volr20_low", mask_pending=True),
            lambda: render_analytics_report(pending, pd.DataFrame(), self.generated, mask_pending=True),
        ):
            output = renderer()
            for secret in ("9Z9Z", "PRIVATE_IDENTITY_SENTINEL", "PRIVATE_FUNDAMENTAL_SENTINEL", "PRIVATE_URL_SENTINEL"):
                self.assertNotIn(secret, output)
                self.assertNotIn(secret, json.dumps(payload(output), ensure_ascii=False))
            self.assertNotIn('data-entry-open=', output)
            self.assertNotIn('data-d5-close=', output)
            self.assertNotIn('data-d6-open=', output)

    def test_free_population_excludes_all_pending_values_dates_and_thresholds(self):
        released = actual_trade("R001", 222.22, signal_date="2026-07-01")
        pending = actual_trade("Q9Z9", 876.54, complete=False)
        pending["one_hundred_shares_pl_yen"] = 12088.56
        pending["gross_return"] = pending["one_hundred_shares_pl_yen"] / pending["entry_cost_yen"]
        pending["company_name"] = "PENDING_PRIVATE_SENTINEL"
        mixed = pd.concat([released, pending], ignore_index=True)
        before = mixed.copy(deep=True)
        cache = {}
        renderers = (
            lambda data, free: render_report(data, pd.DataFrame(), self.generated, mask_pending=free, _variant_cache=cache),
            lambda data, free: render_analytics_report(data, pd.DataFrame(), self.generated, mask_pending=free, _variant_cache=cache),
            lambda data, free: render_mode_report(data, pd.DataFrame(), pd.DataFrame(), self.generated, "volr20_low", mask_pending=free, _variant_cache=cache),
        )
        for renderer in renderers:
            full_output = renderer(mixed, False)  # Full-first must not contaminate free.
            self.assertIn(876.54, visible_prices(full_output))
            output = renderer(mixed, True)
            data = payload(output)
            # Only the explicitly approved existence teaser may differ.
            # Counts, dates, thresholds, metrics, compressed data and CSV remain public-only.
            self.assertIn(MASKED_PENDING_NOTICE, output)
            self.assertEqual(output.replace(MASKED_PENDING_NOTICE, ""), renderer(released, True))
            self.assertEqual(visible_prices(output), [222.22])
            decoded = json.dumps(data, ensure_ascii=False)
            for secret in ("Q9Z9", "PENDING_PRIVATE_SENTINEL", "876.54", "12088.56", "12,089", "2026-09-01", "2026-09-02", "2026-09-08"):
                self.assertNotIn(secret, output)
                self.assertNotIn(secret, decoded)
            self.assertEqual(output.count('data-symbol="R001"'), 1)
            self.assertEqual(data["variants"], {})
        pd.testing.assert_frame_equal(mixed, before)

    def test_public_views_are_separated_by_source_generation_and_audience(self):
        first = actual_trade("R001", 222.22, signal_date="2026-07-01")
        second = actual_trade("R002", 333.33, signal_date="2026-07-01")
        cache = {}
        def render(frame, generated, free):
            return render_analytics_report(frame, pd.DataFrame(), generated, mask_pending=free, _variant_cache=cache)
        self.assertEqual(visible_prices(render(first, self.generated, True)), [222.22])
        self.assertEqual(visible_prices(render(second, self.generated, True)), [333.33])
        self.assertIn("2026-10-05", payload(render(second, self.generated + pd.Timedelta(days=1), True))["generated"])
        pending = actual_trade("Q9Z9", 876.54, complete=False)
        self.assertEqual(visible_prices(render(pending, self.generated, True)), [])
        self.assertEqual(visible_prices(render(pending, self.generated, False)), [876.54])

    def test_free_release_requires_all_overlapping_mode_receipts(self):
        first = actual_trade("R001", 222.22)
        overlap = first.copy()
        overlap["selector_id"] = "body_pct_low"
        overlap["sixth_xtks_exit_status"] = "pending"
        mixed = pd.concat([first, overlap], ignore_index=True)
        self.assertTrue(released_history(mixed).empty)
        output = render_mode_report(mixed, pd.DataFrame(), pd.DataFrame(), self.generated, "volr20_low", mask_pending=True)
        self.assertEqual(visible_prices(output), [])
        self.assertNotIn('data-symbol="R001"', output)

    def test_receipt_verified_d6_releases_identity_even_if_economics_unavailable(self):
        frame = actual_trade()
        frame["sixth_economics_status"] = "review_required"
        frame["sixth_gross_return"] = float("nan")
        output = render_report(frame, pd.DataFrame(), self.generated, mask_pending=True)
        self.assertIn('data-symbol="9Z9Z"', output)
        self.assertIn("PRIVATE_IDENTITY_SENTINEL", output)
        self.assertIn('data-d6-open="1005.0"', output)
        self.assertNotIn('data-d6-return=', output)

    def test_all_variant_metrics_and_charts_share_price_and_endpoint_population(self):
        first = actual_trade("A001", 1000)
        overlap = first.copy()
        overlap["selector_id"] = "body_pct_low"
        second = actual_trade("A002", 1500, complete=False)
        frame = pd.concat([first, overlap, second], ignore_index=True)
        # The Python aggregate oracle remains independently checked; the v2
        # shipped calculator is compared against it in the browser/math suite.
        default_html, serialized = _aggregate_variant_payload(frame, self.generated, "analytics")
        output = '<script id="cloud-analytics-data" type="application/json">' + serialized + '</script>'
        data = payload(output)
        self.assertEqual(data["priceBreakpoints"], [1000, 1500])
        for endpoint in ("d5_close", "d6_open"):
            for suffix, cap in (("1000", 1000), ("1500", 1500), ("all", None)):
                variant = data["variants"][f"{endpoint}:{suffix}"]
                view = select_report_view(frame, cap, endpoint)
                expected_frame = build_metrics(view, self.generated.tz_localize(None))
                expected_frame = expected_frame.loc[expected_frame.selector_id.isin([COMBINED_STACKED_ID, COMBINED_UNIQUE_ID])]
                expected = json.loads(expected_frame.to_json(orient="records", double_precision=15))
                self.assertEqual(variant["metrics"], expected)
                monthly_frame = build_monthly_metrics(view, self.generated.tz_localize(None))
                monthly_frame = monthly_frame.loc[monthly_frame.selector_id.isin([COMBINED_STACKED_ID, COMBINED_UNIQUE_ID])]
                monthly = json.loads(monthly_frame.to_json(orient="records", double_precision=15))
                self.assertEqual(variant["monthlyMetrics"], monthly)
                totals = {row["selector_id"]: row for row in expected if row["period"] == "2026-2026"}
                for identity in (COMBINED_STACKED_ID, COMBINED_UNIQUE_ID):
                    self.assertIn(f"¥{totals[identity]['cash_pl_100_yen']:+,.0f}", variant["html"])
        # Entire analytics payload is an aggregate, with no raw trade records.
        self.assertNotIn("A001", output)
        self.assertNotIn("A002", output)
        self.assertNotIn("PRIVATE_IDENTITY_SENTINEL", output)
        self.assertNotIn('"entry_open"', output)

    def test_canonical_without_actual_receipts_never_counts_legacy_reference_as_actual_d5(self):
        ledger = bootstrap_historical()
        output = render_analytics_report(ledger, pd.DataFrame(), self.generated)
        self.assertEqual(visible_prices(output), [])
        self.assertNotIn('data-d5-return=', output)
        self.assertNotIn('data-d5-proceeds=', output)
        self.assertIn("2026年の過去データも、結果が分かった期間の試算", output)

    def test_verified_history_has_only_twenty_initial_rows_without_javascript(self):
        frame = pd.concat([actual_trade(f"X{i:03d}") for i in range(25)], ignore_index=True)
        rows = _detection_rows(frame)
        opening_tags = re.findall(r'<tr\b[^>]*>', rows)
        self.assertEqual(len(opening_tags), 25)
        self.assertEqual(sum(" hidden>" not in tag for tag in opening_tags), 20)

    def test_oversize_report_fails_during_render_before_any_html_write(self):
        with patch("weak_early_beta.report.MAX_REPORT_BYTES", 1):
            with self.assertRaisesRegex(ValueError, "24 MiB asset budget"):
                _page_shell("test", "analytics", "test")


class PendingD6CoverageTests(unittest.TestCase):
    def test_missing_old_d6_schedule_is_derived_without_inventing_a_price(self):
        source = actual_trade(complete=False, signal_date="2026-09-01")
        source["sixth_xtks_exit_date"] = pd.NaT
        original = source.copy(deep=True)
        view = select_report_view(source, None, "d6_open")
        self.assertEqual(view.iloc[0]["fifth_xtks_exit_date"], pd.Timestamp("2026-09-09"))
        self.assertTrue(pd.isna(view.iloc[0]["gross_return"]))
        self.assertTrue(pd.isna(view.iloc[0]["fifth_xtks_exit_close"]))
        from weak_early_beta.metrics import coverage_years
        self.assertAlmostEqual(coverage_years(view, pd.Timestamp("2026-09-07")), 6 / 365.2425)
        pd.testing.assert_frame_equal(source, original)

    def test_mode_history_retains_global_match_count_on_an_isolated_copy(self):
        from weak_early_beta.config import SELECTOR_ORDER
        row = actual_trade()
        source = pd.concat([row.assign(selector_id=key) for key in SELECTOR_ORDER[:3]], ignore_index=True)
        original = source.copy(deep=True)
        output = render_mode_report(source, pd.DataFrame(), pd.DataFrame(), pd.Timestamp("2026-10-04", tz="Asia/Tokyo"), SELECTOR_ORDER[0])
        self.assertIn(f'data-selectors="{" ".join(SELECTOR_ORDER[:3])}"', output)
        self.assertEqual(output.count('data-date="'), 1)
        pd.testing.assert_frame_equal(source, original)

if __name__ == "__main__":
    unittest.main()
