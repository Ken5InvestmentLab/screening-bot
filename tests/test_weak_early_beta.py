import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from weak_early_beta.config import (
    COMBINED_STACKED_ID,
    COMBINED_UNIQUE_ID,
    SELECTOR_ORDER,
    selector_info,
)
from weak_early_beta.fundamental import export_receipts, prepare_claim
from weak_early_beta.ledger import bootstrap_historical, build_fundamental_queue, merge_detections
from weak_early_beta.metrics import build_metrics, build_monthly_metrics
from weak_early_beta.report import render_report


class WeakEarlyBetaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = bootstrap_historical()

    def test_bootstrap_exact_counts_and_unique_identities(self):
        self.assertEqual(len(self.ledger), 967)
        self.assertFalse(self.ledger["detection_id"].duplicated().any())
        self.assertEqual(set(self.ledger["selector_id"]), set(SELECTOR_ORDER))
        self.assertTrue(self.ledger["gross_return"].notna().all())

    def test_names_explain_features_and_internal_ids_stay_fixed(self):
        self.assertEqual(selector_info("mean_rank_volr20_body_pct").display_name, "Shadow")
        self.assertEqual(selector_info("body_pct_low").display_name, "Dive")
        self.assertEqual(selector_info("volr20_low").display_name, "Silence")
        self.assertEqual(selector_info("dual_top1_agreement").display_name, "Fusion")
        self.assertEqual(
            selector_info("dual_top1_agreement_g3_no_acute_selloff").display_name,
            "Balance",
        )

    def test_bootstrap_resolves_company_names_without_nan(self):
        names = self.ledger["company_name"].fillna("").astype(str).str.strip()
        self.assertTrue(names.ne("").all())
        self.assertFalse(names.str.lower().eq("nan").any())

    def test_metrics_include_user_facing_fields(self):
        metrics = build_metrics(self.ledger, pd.Timestamp("2026-09-11"))
        total = metrics[metrics["period"].eq("2023-2026")]
        self.assertEqual(len(total), 7)
        for column in (
            "mean_pct", "median_pct", "win_pct", "plus10_pct", "plus20_pct",
            "minus10_pct", "minus20_pct", "cash_pl_100_yen", "simple_annualized_pct",
        ):
            self.assertTrue(total[column].notna().all(), column)
        combined = total[total["selector_id"].eq(COMBINED_UNIQUE_ID)].iloc[0]
        unique_trades = self.ledger.drop_duplicates(["signal_date", "symbol"])
        self.assertEqual(combined["n"], len(unique_trades))
        stacked = total[total["selector_id"].eq(COMBINED_STACKED_ID)].iloc[0]
        self.assertEqual(stacked["n"], len(self.ledger))

    def test_historical_rows_do_not_enter_fundamental_queue(self):
        self.assertEqual(build_fundamental_queue(self.ledger), [])

    def test_merge_preserves_notification_receipts(self):
        old = self.ledger.head(1).copy()
        old.loc[:, "notified_at"] = "2026-09-19T17:00:00+09:00"
        old.loc[:, "signal_discord_url"] = "https://discord.example/message"
        incoming = old.copy()
        incoming.loc[:, "notified_at"] = ""
        incoming.loc[:, "signal_discord_url"] = ""
        merged = merge_detections(old, incoming)
        self.assertEqual(merged.iloc[0]["signal_discord_url"], "https://discord.example/message")

    def test_report_has_no_extended_investment_metric(self):
        metrics = build_metrics(self.ledger, pd.Timestamp("2026-09-11"))
        monthly = build_monthly_metrics(self.ledger, pd.Timestamp("2026-09-11"))
        output = render_report(
            self.ledger.head(20),
            metrics,
            pd.Timestamp("2026-09-19", tz="Asia/Tokyo"),
            monthly_metrics=monthly,
        )
        self.assertIn("勝率", output)
        self.assertIn("平均", output)
        self.assertIn("100株損益", output)
        self.assertIn("参考元金", output)
        self.assertIn("元金増加率", output)
        self.assertIn("順位", output)
        self.assertIn("Cloud 全体の成績", output)
        self.assertIn("モード別積上げ", output)
        self.assertIn("銘柄均等", output)
        self.assertIn("単純年率", output)
        self.assertIn("月別の詳しい成績を見る", output)
        self.assertIn("確定取引数", output)
        self.assertNotIn("確定n", output)
        self.assertNotIn("確定ユニット", output)
        self.assertNotIn(">n<", output)
        self.assertIn("天底極致 -Cloud-", output)
        for old_label in ("現行", "Stable", "Sniper", "Mega", "Weak+Early"):
            self.assertNotIn(old_label, output)
        self.assertNotIn("延べ投入額</th>", output)

    def test_monthly_metrics_keep_year_month_labels(self):
        monthly = build_monthly_metrics(self.ledger, pd.Timestamp("2026-09-11"))
        self.assertFalse(monthly.empty)
        self.assertTrue(monthly["period"].astype(str).str.fullmatch(r"\d{4}-\d{2}").all())
        self.assertTrue(set(SELECTOR_ORDER).issubset(set(monthly["selector_id"])))

    def test_fundamental_claim_and_receipt_stay_in_beta_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ledger_path = root / "detections.csv"
            queue_path = root / "queue.json"
            state_path = root / "beta-state.json"
            claim_path = root / "claim.json"
            receipt_path = root / "receipts.json"
            forward = self.ledger.head(1).copy()
            forward.loc[:, "source_scope"] = "FORWARD_CAUSAL"
            forward.loc[:, "fundamental_status"] = "queued"
            forward.loc[:, "signal_date"] = pd.Timestamp("2026-09-18")
            forward.loc[:, "symbol"] = "1234"
            forward.to_csv(ledger_path, index=False)
            queue = [{
                "signal_date": "2026-09-18",
                "symbol": "1234",
                "company_name": "テスト社",
                "selector_names": ["出来高沈静リバウンド"],
            }]
            queue_path.write_text(json.dumps(queue, ensure_ascii=False), encoding="utf-8")
            claim = prepare_claim(queue_path, ledger_path, state_path, claim_path)
            self.assertEqual(claim["claimedCount"], 1)
            identity = "weak-early-beta:2026-09-18:1234"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertIn(identity, state["claims"])
            state["posted"][identity] = {
                "discordMessageUrl": "https://discord.com/channels/g/c/m"
            }
            state["claims"] = {}
            state_path.write_text(json.dumps(state), encoding="utf-8")
            receipts = export_receipts(state_path, receipt_path)
            self.assertEqual(receipts[0]["signal_date"], "2026-09-18")
            self.assertEqual(receipts[0]["symbol"], "1234")

    def test_embedded_fundamental_text_is_html_escaped(self):
        ledger = self.ledger.head(1).copy()
        ledger.loc[:, "fundamental_html"] = '<img src=x onerror="alert(1)">'
        metrics = build_metrics(self.ledger, pd.Timestamp("2026-09-11"))
        output = render_report(ledger, metrics, pd.Timestamp("2026-09-19", tz="Asia/Tokyo"))
        self.assertNotIn('<img src=x onerror="alert(1)">', output)
        self.assertIn("&lt;img src=x", output)


if __name__ == "__main__":
    unittest.main()
