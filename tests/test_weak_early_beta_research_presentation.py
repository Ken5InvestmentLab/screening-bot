"""Research-layout migration uses selected public ledger aggregates, not constants."""

import json
import unittest

import pandas as pd

from tests.test_weak_early_beta_report_preferences import actual_trade, payload, visible_prices
from weak_early_beta.analytics import build_analytics
from weak_early_beta.config import COMBINED_STACKED_ID, COMBINED_UNIQUE_ID
from weak_early_beta.metrics import build_metrics
from weak_early_beta.report import render_analytics_report, _render_analytics_body, _scope_definitions
from weak_early_beta.report_preferences import select_report_view


class ResearchPresentationTests(unittest.TestCase):
    generated = pd.Timestamp("2026-10-04", tz="Asia/Tokyo")

    @classmethod
    def setUpClass(cls):
        first = actual_trade("R001", 222.22, signal_date="2023-02-01")
        second = actual_trade("R002", 731.29, signal_date="2024-02-01")
        overlap = second.copy()
        overlap["selector_id"] = "volr20_mid"
        # Use a real supported selector; duplicate matches represent two lots.
        from weak_early_beta.config import SELECTOR_ORDER
        overlap["selector_id"] = next(key for key in SELECTOR_ORDER if key != "volr20_low")
        current = actual_trade("R003", 1212.34, signal_date="2026-09-01")
        cls.frame = pd.concat([first, second, overlap, current], ignore_index=True)
        cls.original = cls.frame.copy(deep=True)
        cls.document = render_analytics_report(cls.frame, pd.DataFrame(), cls.generated)
        cls.data = payload(cls.document)

    def test_reference_visual_sections_and_controls_are_real_aggregates(self):
        selected = select_report_view(self.frame, 1000, "d5_close")
        body = _render_analytics_body(selected, pd.DataFrame(), self.generated)
        for title in ("株数方式の比較", "累積確定損益", "必要資金・損失・集中度", "検出年別の損益", "検出条件の重なり"):
            self.assertIn(title, body)
        for control in ("cloud-year-scope", "cloud-allocation", "cloud-research-reset", "cloud-price-preset", "cloud-exit-endpoint", "cloud-base-shares", "cloud-cost-percent"):
            self.assertIn(f'id="{control}"', self.document)
        self.assertNotIn('id="history"', self.document)
        self.assertIn('<template id="cloud-scenario-rows">', self.document)
        self.assertNotIn('class="history-expand"', self.document)
        self.assertNotIn('<circle class="research-point"', body)
        self.assertNotIn("記録の範囲と来歴", body)
        self.assertNotIn("2022年", body)
        self.assertIn("2026年の過去データも、結果が分かった期間の試算", body)
        self.assertEqual(self.data["variants"], {})
        serialized = json.dumps(self.data, ensure_ascii=False)
        for identity in ("R001", "R002", "R003", "PRIVATE_IDENTITY_SENTINEL", "PRIVATE_URL_SENTINEL"):
            self.assertNotIn(identity, serialized)
        pd.testing.assert_frame_equal(self.frame, self.original)

    def test_individual_years_are_public_choices_without_combined_year_or_variant_grid(self):
        self.assertEqual(self.data["page"], "analytics")
        self.assertEqual(self.data["scopes"]["2023"]["years"], [2023])
        self.assertEqual(self.data["scopes"]["2024"]["years"], [2024])
        self.assertNotIn("2023_2025", self.data["scopes"])
        self.assertEqual(self.data["variants"], {})
        self.assertEqual(visible_prices(self.document), [222.22, 731.29, 1212.34])

    def test_unreleased_year_and_price_do_not_change_free_scope_or_content(self):
        pending = actual_trade("S9Z9", 876.54, signal_date="2025-02-13", complete=False)
        public = self.frame.iloc[:1].copy()
        cache = {}
        # Full render first exercises audience/source cache isolation.
        render_analytics_report(pd.concat([public, pending]), pd.DataFrame(), self.generated, _variant_cache=cache)
        baseline = render_analytics_report(public, pd.DataFrame(), self.generated, mask_pending=True, _variant_cache=cache)
        candidate = render_analytics_report(pd.concat([public, pending]), pd.DataFrame(), self.generated, mask_pending=True, _variant_cache=cache)
        self.assertEqual(candidate, baseline)
        scopes = payload(candidate)["scopes"]
        self.assertNotIn("2025", scopes)
        self.assertEqual(visible_prices(candidate), [222.22])

    def test_scope_2022_is_never_exposed(self):
        source = self.frame.copy()
        source.loc[source.index[0], "signal_date"] = "2022-12-01"
        self.assertNotIn("2022", _scope_definitions(source))


if __name__ == "__main__":
    unittest.main()
