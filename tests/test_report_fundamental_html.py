import unittest

from generate_mega_validation_report import (
    discord_embed_impact_class,
    markdown_text_html,
    normalize_cached_fundamental_html,
    normalize_tradingview_title,
)


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
