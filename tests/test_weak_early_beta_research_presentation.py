"""Research-layout migration uses selected public ledger aggregates, not constants."""

import json
import unittest

import pandas as pd

from tests.test_weak_early_beta_report_preferences import actual_trade, payload
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
        body = self.data["variants"]["d5_close:731.29"]["html"]
        for title in ("株数方式の比較", "累積確定損益", "必要資金・損失・集中度", "検出年別の損益", "株数増加だけの影響を確認", "検出条件の重なり", "重なり別の平均騰落率", "勝ち・負けと加重集計", "記録の範囲と来歴"):
            self.assertIn(title, body)
        for control in ("cloud-year-scope", "cloud-allocation", "cloud-research-reset", "cloud-price-preset", "cloud-exit-endpoint"):
            self.assertIn(f'id="{control}"', self.document)
        self.assertIn('data-cloud-allocation="unique"', body)
        self.assertIn('data-cloud-allocation="stacked"', body)
        self.assertIn("表示母集団 <strong>2検出 / 3条件一致", body)
        self.assertIn("結果が既知の過去期間", body)
        self.assertIn("100株・コスト0を共通基準", body)
        self.assertIn('weak_early_beta_latest.html#history', body)
        self.assertNotIn('weak_early_beta_latest.html#detections', body)
        self.assertIn("集計データを見る", body)
        # Analytics aggregates contain no raw identity even on full assets.
        serialized = json.dumps(self.data, ensure_ascii=False)
        for identity in ("R001", "R002", "R003", "PRIVATE_IDENTITY_SENTINEL", "PRIVATE_URL_SENTINEL"):
            self.assertNotIn(identity, serialized)
        pd.testing.assert_frame_equal(self.frame, self.original)

    def test_scope_specific_breakpoints_and_full_recalculation(self):
        self.assertEqual(self.data["page"], "analytics")
        self.assertEqual(self.data["scopes"]["2023"]["years"], [2023])
        self.assertEqual(self.data["scopes"]["2023"]["priceBreakpoints"], [222.22])
        self.assertNotIn("d5_close:2023:731.29", self.data["variants"])
        self.assertEqual(self.data["scopes"]["2023_2025"]["years"], [2023, 2024, 2025])
        variant = self.data["variants"]["d6_open:2024:all"]
        source = self.frame[pd.to_datetime(self.frame.signal_date).dt.year.eq(2024)]
        selected = select_report_view(source, None, "d6_open")
        expected = build_metrics(selected, self.generated.tz_localize(None))
        expected = expected[expected.selector_id.isin([COMBINED_STACKED_ID, COMBINED_UNIQUE_ID])]
        actual = pd.DataFrame(variant["metrics"])
        actual = actual[actual.selector_id.isin([COMBINED_STACKED_ID, COMBINED_UNIQUE_ID])]
        pd.testing.assert_frame_equal(actual.reset_index(drop=True), expected.reset_index(drop=True), check_dtype=False, atol=1e-9)
        calculated = build_analytics(selected)
        self.assertIn(f'{calculated["counts"]["completed_signals"]}件', variant["html"])
        self.assertIn("2024-02-01", variant["html"])
        self.assertNotIn("2023-02-01", variant["html"])

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
        self.assertEqual(scopes["all"]["priceBreakpoints"], [222.22])

    def test_scope_2022_is_never_exposed(self):
        source = self.frame.copy()
        source.loc[source.index[0], "signal_date"] = "2022-12-01"
        self.assertNotIn("2022", _scope_definitions(source))


if __name__ == "__main__":
    unittest.main()
