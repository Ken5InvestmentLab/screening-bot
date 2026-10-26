"""Display prices cannot change scoring, economics, or morning time boundaries."""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from weak_early_beta.current_prices import quote_for, read_snapshot, refresh_from_cache, write_snapshot
from weak_early_beta.reminders import _payload
from tests.test_weak_early_beta_reminders import forward


class CurrentPricesTests(unittest.TestCase):
    def test_latest_actual_close_and_quarantine_do_not_fall_back_to_adjusted_or_older(self):
        daily = pd.DataFrame([
            {"symbol": "1234", "date": "2026-10-05", "close": 50, "actual_close": 100, "source_usable": True},
            {"symbol": "1234", "date": "2026-10-06", "close": 60, "actual_close": 120.5, "source_usable": True},
            {"symbol": "5678", "date": "2026-10-05", "close": 70, "actual_close": 70, "source_usable": True},
            {"symbol": "5678", "date": "2026-10-06", "close": 80, "actual_close": 80, "source_usable": False},
        ])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "prices.json"
            write_snapshot(daily, ["1234", "5678"], "a" * 64, path)
            prices = read_snapshot(path)
        self.assertEqual(quote_for(prices, "1234"), ("120.5円", "2026-10-06 終値"))
        self.assertEqual(quote_for(prices, "5678"), ("未取得", "2026-10-06 終値未確認"))
        self.assertEqual(quote_for(prices, "1234", before=date(2026, 10, 6)), ("未取得", ""))

    def test_cache_mismatch_never_publishes_display_prices(self):
        with tempfile.TemporaryDirectory() as folder:
            corpus = Path(folder) / "daily.csv"
            corpus.write_text("not a verified source")
            corpus.with_suffix(".source-quality.json").write_text(json.dumps({
                "identity": "CLOUD_SOURCE_QUALITY_V1", "daily_sha256": "a" * 64,
            }))
            target = Path(folder) / "prices.json"
            with self.assertRaisesRegex(ValueError, "matching source-quality"):
                refresh_from_cache(corpus, target)
            self.assertFalse(target.exists())

    def test_morning_embed_places_dated_latest_close_next_to_entry(self):
        group = forward("1234")
        before = group.copy(deep=True)
        payload = _payload(group, date(2026, 10, 7), "", 5, "終値",
                           {"1234": {"date": "2026-10-06", "close": 123.25}})
        fields = payload["embeds"][0]["fields"]
        self.assertEqual(fields[4], {"name": "現在株価（最新終値）", "value": "123.25円\n2026-10-06 終値", "inline": True})
        self.assertEqual(payload["components"][0]["components"][0]["label"], "チャートを見る")
        pd.testing.assert_frame_equal(group, before)

    def test_html_price_visible_in_company_summary_and_free_masks_stay_private(self):
        from weak_early_beta.ledger import bootstrap_historical
        from weak_early_beta.report import _detection_rows
        ledger = bootstrap_historical().iloc[:1].copy()
        ledger["fundamental_html"] = "事業概要\n表示位置を確認する分析本文"
        symbol = str(ledger.iloc[0]["symbol"])
        with patch("weak_early_beta.current_prices.read_snapshot", return_value={symbol: {"date": "2026-10-26", "close": 1234.5}}):
            output = _detection_rows(ledger)
            self.assertIn('class="current-quote"', output)
            self.assertIn("1,234.5円", output)
            self.assertIn("2026-10-26 終値", output)
            date_cell, company_cell = output.split('<div class="history-company">', 1)
            self.assertIn('class="actions history-date-actions"', date_cell)
            self.assertLess(date_cell.index('data-fundamental-toggle'), date_cell.index('>チャート</a>'))
            self.assertNotIn('class="actions', company_cell)
            self.assertEqual(output.count('<dialog class="fundamental-detail"'), 1)
            ledger["source_scope"] = "FORWARD_CAUSAL"
            ledger["sixth_xtks_exit_open"] = float("nan")
            ledger["sixth_price_observed_at"] = ""
            masked = _detection_rows(ledger, mask_pending=True)
            self.assertNotIn("1,234.5円", masked)


if __name__ == "__main__":
    unittest.main()
