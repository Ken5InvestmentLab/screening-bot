import unittest

from generate_mega_validation_report import (
    discord_embed_impact_class,
    markdown_text_html,
    normalize_cached_fundamental_html,
    normalize_tradingview_title,
)
from weak_early_beta.report import _fundamental_html
from weak_early_beta.impact import normalize_report_material_impact


class ReportFundamentalHtmlTest(unittest.TestCase):
    def test_disclosure_markdown_link_with_parenthesized_time_becomes_anchor(self):
        source = (
            "[2026-06-29 定款 2026/06/29(13:17)]"
            "(https://finance-frontend-pc-dist.west.edge.storage-yahoo.jp/"
            "disclosure/20260629/20260625576479.pdf)"
        )

        html = markdown_text_html(source)

        self.assertIn('<a href="https://finance-frontend-pc-dist.west.edge.storage-yahoo.jp/', html)
        self.assertIn(">2026-06-29 定款 2026/06/29(13:17)</a>", html)
        self.assertNotIn("](", html)

    def test_disclosure_markdown_link_allows_nested_brackets_in_label(self):
        source = (
            "[2026-05-08 2026年3月期決算短信[日本基準](連結)]"
            "(https://f.irbank.net/pdf/20260508/140120260508548421.pdf)"
        )

        html = markdown_text_html(source)

        self.assertIn('<a href="https://f.irbank.net/pdf/20260508/140120260508548421.pdf"', html)
        self.assertIn(">2026-05-08 2026年3月期決算短信[日本基準](連結)</a>", html)
        self.assertNotIn("](https://", html)
        self.assertNotIn("](<a href=", html)

    def test_cached_literal_markdown_link_is_normalized(self):
        cached = (
            '<div class="discord-message"><article class="discord-embed">'
            "<dl><div><dt>開示リンク</dt><dd>"
            "[2026-06-29 開示](https://example.com/disclosure.pdf)"
            "</dd></div></dl></article></div>"
        )

        html = normalize_cached_fundamental_html(cached)

        self.assertIn('<a href="https://example.com/disclosure.pdf"', html)
        self.assertNotIn("](", html)

    def test_cached_mixed_impact_class_is_normalized_to_watch(self):
        cached = (
            '<div class="discord-message"><article class="discord-embed impact-mixed">'
            "<dl><div><dt>材料インパクト</dt><dd>混在/要確認</dd></div></dl>"
            "</article></div>"
        )

        html = normalize_cached_fundamental_html(cached)

        self.assertIn('class="discord-embed impact-watch"', html)
        self.assertNotIn("impact-mixed", html)

    def test_cached_truncated_markdown_url_does_not_create_nested_anchor(self):
        cached = (
            '<div class="discord-message"><article class="discord-embed">'
            "<dl><div><dt>開示リンク</dt><dd>"
            "・[2026-05-14 決算短信〔IFRS〕(連結)](https://finance-f…"
            "</dd></div></dl></article></div>"
        )

        html = normalize_cached_fundamental_html(cached)

        self.assertIn("2026-05-14 決算短信〔IFRS〕(連結)", html)
        self.assertNotIn("](<a href=", html)
        self.assertNotIn('href="https://finance-f…"', html)

    def test_watch_impact_keywords_keep_watch_class(self):
        embed = {"fields": [{"name": "材料インパクト", "value": "混在/要確認：確認が必要"}]}

        self.assertEqual(discord_embed_impact_class(embed), " impact-watch")

    def test_historical_fundamental_impact_uses_premium_label_and_color_priority(self):
        value = (
            "材料インパクト\nネガティブ材料: 減収と営業損失の拡大が続く。\n\n"
            "足元材料\n決算では売上高と営業利益が前年を下回りました。"
        )

        rendered = _fundamental_html(value, "テスト社", "1234", "2024-01-01")

        self.assertIn('class="discord-embed impact-negative"', rendered)
        self.assertIn("ネガティブ材料：減収と営業損失の拡大が続く。", rendered)
        self.assertNotIn("ネガティブ材料:", rendered)

    def test_historical_mixed_impact_gets_watch_color_before_negative_words(self):
        value = (
            "材料インパクト\n混在・慎重：増収だが営業損失が残る。\n\n"
            "足元材料\n売上高は増加しました。"
        )

        rendered = _fundamental_html(value, "テスト社", "1234", "2024-01-01")

        self.assertIn('class="discord-embed impact-watch"', rendered)
        self.assertIn("混在/要確認：増収だが営業損失が残る。", rendered)

    def test_legacy_mixed_impact_is_normalized_without_rewriting_stored_copy(self):
        original = "売上が増えた一方、赤字が続いた。"
        value = f"材料インパクト\n{original}\n\n足元材料\n同じ時点の開示要約。"

        rendered = _fundamental_html(value, "テスト社", "1234", "2024-01-01")

        self.assertIn('class="discord-embed impact-watch"', rendered)
        self.assertIn(f"混在/要確認：{original}", rendered)
        self.assertLessEqual(len(f"混在/要確認：{original}".split("：", 1)[1]), 90)

    def test_legacy_clear_positive_and_negative_impacts_get_matching_colors(self):
        positive = _fundamental_html(
            "材料インパクト\n売上高と営業利益が前年を上回り、黒字転換した。",
            "テスト社", "1234", "2024-01-01",
        )
        negative = _fundamental_html(
            "材料インパクト\n減収と営業損失が続き、通期予想も下方修正した。",
            "テスト社", "5678", "2024-01-01",
        )

        self.assertIn('class="discord-embed impact-positive"', positive)
        self.assertIn('ポジティブ材料：', positive)
        self.assertIn('class="discord-embed impact-negative"', negative)
        self.assertIn('ネガティブ材料：', negative)

    def test_impact_normalization_persists_field_and_top_level_without_new_facts(self):
        source = {
            "signalDate": "2024-01-01",
            "symbolCode": "1234",
            "materialImpact": "売上が増えた一方、赤字が続いた。",
            "fields": [
                {"name": "材料インパクト", "value": "売上が増えた一方、赤字が続いた。"},
                {"name": "事業概要", "value": "既存の事業説明。"},
            ],
        }

        normalized, audit = normalize_report_material_impact(source)

        impact = normalized["fields"][0]["value"]
        self.assertEqual(impact, "混在/要確認：売上が増えた一方、赤字が続いた。")
        self.assertEqual(normalized["materialImpact"], impact)
        self.assertEqual(normalized["fields"][1]["value"], "既存の事業説明。")
        self.assertEqual(source["fields"][0]["value"], "売上が増えた一方、赤字が続いた。")
        self.assertEqual(audit["normalized_value"], impact)

    def test_fundamental_modal_markup_and_interaction_use_native_dialog(self):
        from pathlib import Path

        interactions = (
            Path("reports/weak-early-beta-interactions.js").read_text(encoding="utf-8")
        )
        report_source = Path("weak_early_beta/report.py").read_text(encoding="utf-8")

        self.assertIn('<dialog class="fundamental-detail"', report_source)
        self.assertIn("showModal()", interactions)
        self.assertIn("dialog.fundamental-detail::backdrop", report_source)
        self.assertNotIn("max-width:620px){.fundamental-detail{width:calc(100% + 32px)", report_source)

    def test_tradingview_title_removes_duplicate_symbol_code(self):
        title = "ルネサンス (2378) (2378) | TradingView チャート"

        self.assertEqual(
            normalize_tradingview_title(title),
            "ルネサンス (2378) | TradingView チャート",
        )

    def test_tradingview_title_repairs_garbled_chart_label(self):
        title = "ルネサンス (2378) | TradingView ????"

        self.assertEqual(
            normalize_tradingview_title(title),
            "ルネサンス (2378) | TradingView チャート",
        )


if __name__ == "__main__":
    unittest.main()
