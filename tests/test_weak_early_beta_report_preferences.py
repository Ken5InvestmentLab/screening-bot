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
from weak_early_beta.report import _detection_rows, _page_shell, render_analytics_report, render_mode_report, render_report
from weak_early_beta.report_preferences import select_report_view, validate_price_cap
from weak_early_beta.trade_basis import LEGACY_PRICE_BASIS_VERSION


def actual_trade(symbol="9Z9Z", price=1000, *, complete=True, split=1):
    count = 7 if complete else 6
    actual = [price, price, price + 1, price + 2, price + 3, price + 4, (price + 5) / split][:count]
    factors = [split] * min(count, 6) + ([1] if complete else [])
    adjusted = [value / factor for value, factor in zip(actual, factors)]
    daily = normalize_daily(pd.DataFrame({
        "date": pd.bdate_range("2026-09-01", periods=count), "symbol": symbol,
        "open": adjusted, "high": [value + 1 for value in adjusted],
        "low": [value - 1 for value in adjusted], "close": adjusted,
        "volume": [10_000 * factor for factor in factors],
        "split_ratio": [0] * min(count, 6) + ([split if split != 1 else 0] if complete else []),
    }))
    selected = pd.DataFrame([{"date": pd.Timestamp("2026-09-01"), "symbol": symbol,
                              "selector": "volr20_low", "model_period": "2026-09"}])
    result = attach_forward_rows(selected, daily)
    result["company_name"] = "PRIVATE_IDENTITY_SENTINEL"
    result["fundamental_html"] = "PRIVATE_FUNDAMENTAL_SENTINEL"
    result["fundamental_discord_url"] = "https://example.test/PRIVATE_URL_SENTINEL"
    return result


def payload(output):
    data = json.loads(re.search(r'<script id="cloud-analytics-data" type="application/json">(.*?)</script>', output, re.S).group(1))
    if data.get("encoding") == "gzip-base64-json":
        data["variants"] = {key: json.loads(gzip.decompress(base64.b64decode(value["gzip"]))) for key, value in data["variants"].items()}
    return data


class ReportPreferenceTests(unittest.TestCase):
    generated = pd.Timestamp("2026-10-04", tz="Asia/Tokyo")

    def test_explicit_price_cap_validation_without_rounding(self):
        for value in (1, "1500", 1000.01, "0.01", "1500.00"):
            self.assertEqual(validate_price_cap(value), float(value))
        self.assertIsNone(validate_price_cap(None))
        for value in (True, 0, -1, "", float("inf"), float("nan"), 1.001, "0.001", "90071992547410"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_price_cap(value)

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
        self.assertEqual(view.iloc[0].display_d5_gross_return, .99)
        pd.testing.assert_frame_equal(source, original)

    def test_unverified_d6_economics_never_becomes_zero_or_a_d5_substitute(self):
        source = actual_trade(complete=False)
        self.assertTrue(pd.notna(source.iloc[0].gross_return))
        view = select_report_view(source, 1000, "d6_open")
        self.assertTrue(pd.isna(view.iloc[0].gross_return))
        self.assertTrue(pd.isna(view.iloc[0].one_hundred_shares_pl_yen))

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
        output = render_analytics_report(frame, pd.DataFrame(), self.generated)
        data = payload(output)
        self.assertEqual(data["priceBreakpoints"], [1000, 1500])
        for endpoint in ("d5_close", "d6_open"):
            for suffix, cap in (("1000", 1000), ("1500", 1500), ("all", None)):
                variant = data["variants"][f"{endpoint}:{suffix}"]
                view = select_report_view(frame, cap, endpoint)
                expected = json.loads(build_metrics(view, self.generated.tz_localize(None)).to_json(orient="records", double_precision=15))
                self.assertEqual(variant["metrics"], expected)
                monthly = json.loads(build_monthly_metrics(view, self.generated.tz_localize(None)).to_json(orient="records", double_precision=15))
                self.assertEqual(variant["monthlyMetrics"], monthly)
                totals = {row["selector_id"]: row for row in expected if row["period"] == "2026-2026"}
                for identity in (COMBINED_STACKED_ID, COMBINED_UNIQUE_ID):
                    self.assertIn(f"¥{totals[identity]['cash_pl_100_yen']:+,.0f}", variant["html"])
        # Entire analytics payload is an aggregate, with no raw trade records.
        self.assertNotIn("A001", output)
        self.assertNotIn("A002", output)
        self.assertNotIn("PRIVATE_IDENTITY_SENTINEL", output)
        self.assertNotIn('"entry_open"', output)

    def test_canonical_initial_view_excludes_unknown_prices_but_keeps_unlimited_reference(self):
        ledger = bootstrap_historical()
        output = render_analytics_report(ledger, pd.DataFrame(), self.generated)
        data = payload(output)
        self.assertEqual(data["variants"]["d5_close:empty"]["metrics"], [])
        totals = [r for r in data["variants"]["d5_close:all"]["metrics"] if r["period"] == "2023-2026" and r["selector_id"] == COMBINED_STACKED_ID]
        self.assertEqual(totals[0]["n"], 946)
        self.assertIn("2026年の過去再構成分も", output)

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


if __name__ == "__main__":
    unittest.main()
