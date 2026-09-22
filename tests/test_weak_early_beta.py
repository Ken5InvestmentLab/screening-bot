import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from weak_early_beta.config import (
    COMBINED_STACKED_ID,
    COMBINED_UNIQUE_ID,
    SELECTOR_ORDER,
    selector_info,
)
from weak_early_beta.bank_calendar import fifth_session_from_entry, is_bank_business_day
from weak_early_beta.fundamental import export_receipts, prepare_claim
from weak_early_beta.ledger import bootstrap_historical, build_fundamental_queue, merge_detections
from weak_early_beta.metrics import build_metrics, build_monthly_metrics
from weak_early_beta.notify import EMBED_COLORS, _message, notify_daily_completion
from weak_early_beta.report import (
    ANALYTICS_PAGE_NAME,
    MODE_PAGE_NAMES,
    render_analytics_report,
    render_guide,
    render_mode_report,
    render_report,
    write_report,
)
from weak_early_beta.reminders import notify_exit_reminders
from weak_early_beta.restrictions import parse_jpx_restricted_symbols, quarantine_restricted_detections


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
        incoming.loc[:, "company_name"] = ""
        merged = merge_detections(old, incoming)
        self.assertEqual(merged.iloc[0]["signal_discord_url"], "https://discord.example/message")
        self.assertEqual(merged.iloc[0]["company_name"], old.iloc[0]["company_name"])

    def test_signal_notification_is_user_facing_embed(self):
        group = self.ledger.head(5).copy()
        group.loc[:, "signal_date"] = pd.Timestamp("2026-09-14")
        group.loc[:, "symbol"] = "7709"
        group.loc[:, "company_name"] = "クボテック"
        group.loc[:, "signal_close"] = 76
        group.loc[:, "signal_volume"] = 2_405_500
        group.loc[:, "selector_id"] = SELECTOR_ORDER
        group.loc[:, "selector_name"] = [selector_info(value).display_name for value in SELECTOR_ORDER]
        payload = _message(group, "https://example.test/")
        self.assertEqual(payload["content"], "")
        self.assertEqual(len(payload["embeds"]), 1)
        embed = payload["embeds"][0]
        self.assertEqual(embed["title"], "7709 クボテック")
        self.assertEqual(embed["url"], "https://jp.tradingview.com/chart/?symbol=TSE%3A7709")
        self.assertEqual(embed["color"], EMBED_COLORS[5])
        fields = {field["name"]: field["value"] for field in embed["fields"]}
        self.assertEqual(fields["検出時点の終値"], "76円")
        self.assertEqual(fields["当日の出来高"], "2,405,500株")
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("Weak+Early ベータ検出", serialized)
        self.assertNotIn("売買評価", serialized)
        self.assertNotIn("WEAK_EARLY_BETA:", serialized)

    def test_daily_completion_notifies_zero_detection_and_analytics(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = Path(temp) / "daily.json"
            payloads = notify_daily_completion(
                self.ledger,
                "2026-09-24",
                "https://example.test/",
                state_path=state_path,
                dry_run=True,
            )
        self.assertEqual(len(payloads), 2)
        self.assertEqual(payloads[0]["embeds"][0]["title"], "本日の検出銘柄はありません")
        self.assertEqual(
            payloads[1]["embeds"][0]["url"],
            "https://example.test/weak_early_beta_analytics.html",
        )

    def test_jpx_delisting_gate_is_causal_and_keeps_an_audit_row(self):
        document = """<table><tr><th>指定年月日</th><th>銘柄名</th><th>コード</th><th>市場</th><th>解除</th><th>内容</th></tr>
        <tr><td>2026/04/22</td><td>クボテック（株）</td><td>7709</td><td>スタンダード</td><td>-</td><td>上場廃止の決定・整理銘柄指定</td></tr>
        <tr><td>2026/10/01</td><td>未来指定社</td><td>9999</td><td>スタンダード</td><td>-</td><td>上場廃止の決定・整理銘柄指定</td></tr></table>""".encode("utf-8")
        restrictions = parse_jpx_restricted_symbols(document, "2026-09-14")
        self.assertEqual([row["code"] for row in restrictions], ["7709"])
        forward = self.ledger.head(2).copy()
        forward.loc[:, "source_scope"] = "FORWARD_CAUSAL"
        forward.loc[:, "symbol"] = "7709"
        forward.loc[forward.index[0], "signal_date"] = pd.Timestamp("2026-04-21")
        forward.loc[forward.index[1], "signal_date"] = pd.Timestamp("2026-09-14")
        with tempfile.TemporaryDirectory() as temp:
            active, excluded = quarantine_restricted_detections(
                forward,
                restrictions,
                Path(temp) / "excluded.csv",
            )
        self.assertEqual(len(active), 1)
        self.assertEqual(pd.Timestamp(active.iloc[0]["signal_date"]), pd.Timestamp("2026-04-21"))
        self.assertEqual(len(excluded), 1)
        self.assertEqual(excluded.iloc[0]["restriction_designation_date"], "2026-04-22")

    def test_bank_calendar_and_fifth_session_reminder(self):
        self.assertFalse(is_bank_business_day(date(2026, 9, 21)))
        self.assertFalse(is_bank_business_day(date(2026, 9, 22)))
        self.assertFalse(is_bank_business_day(date(2026, 9, 23)))
        self.assertEqual(fifth_session_from_entry(date(2026, 9, 15)), date(2026, 9, 24))
        forward = self.ledger.head(5).copy()
        forward.loc[:, "source_scope"] = "FORWARD_CAUSAL"
        forward.loc[:, "signal_date"] = pd.Timestamp("2026-09-14")
        forward.loc[:, "entry_date"] = "2026-09-15"
        forward.loc[:, "entry_open"] = 80
        forward.loc[:, "symbol"] = "7709"
        forward.loc[:, "company_name"] = "クボテック"
        forward.loc[:, "selector_id"] = SELECTOR_ORDER
        forward["exit_reminded_at"] = pd.Series("", index=forward.index, dtype="object")
        updated, payloads = notify_exit_reminders(
            forward,
            date(2026, 9, 24),
            report_url="https://example.test/",
            dry_run=True,
        )
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0]["embeds"][0]["title"], "5営業日目の確認：7709 クボテック")
        self.assertTrue(updated["exit_reminded_at"].fillna("").eq("").all())

    def test_report_has_no_extended_investment_metric(self):
        metrics = build_metrics(self.ledger, pd.Timestamp("2026-09-11"))
        monthly = build_monthly_metrics(self.ledger, pd.Timestamp("2026-09-11"))
        output = render_report(
            self.ledger.head(20),
            metrics,
            pd.Timestamp("2026-09-19", tz="Asia/Tokyo"),
            monthly_metrics=monthly,
        )
        self.assertIn("100株損益", output)
        self.assertIn("天底極致 -Cloud- ダッシュボード", output)
        self.assertIn('<a class="brand" href="./weak_early_beta_latest.html"', output)
        self.assertNotIn("Cloud全体の成績", output)
        self.assertNotIn("トータルの資産推移", output)
        self.assertEqual(output.count('role="img"'), 0)
        self.assertIn("./weak_early_beta_shadow.html", output)
        self.assertIn("./weak-early-beta-interactions.js", output)
        self.assertIn("./weak-early-beta-theme-init.js", output)
        self.assertIn('aria-label="Discord"', output)
        self.assertIn('aria-label="ココナラ"', output)
        self.assertIn('aria-label="X"', output)
        for asset_name in (
            "discord-light.png",
            "discord-dark.png",
            "coconala-light.png",
            "coconala-dark.png",
            "x-light.png",
            "x-dark.png",
        ):
            self.assertIn(f'report-assets/{asset_name}', output)
        self.assertNotIn("確定n", output)
        self.assertNotIn("確定ユニット", output)
        self.assertNotIn(">n<", output)
        self.assertIn("天底極致 -Cloud-", output)
        self.assertIn(">アナリティクス</a>", output)
        self.assertIn("cloud-logo-light.png", output)
        self.assertIn("cloud-logo-dark.png", output)
        for old_label in ("現行", "Stable", "Sniper", "Mega", "Weak+Early"):
            self.assertNotIn(old_label, output)
        self.assertNotIn("延べ投入額</th>", output)

    def test_mode_pages_have_separate_metrics_chart_and_searchable_history(self):
        metrics = build_metrics(self.ledger, pd.Timestamp("2026-09-11"))
        monthly = build_monthly_metrics(self.ledger, pd.Timestamp("2026-09-11"))
        output = render_mode_report(
            self.ledger,
            metrics,
            monthly,
            pd.Timestamp("2026-09-19", tz="Asia/Tokyo"),
            "mean_rank_volr20_body_pct",
        )
        self.assertIn("Shadow の資産推移", output)
        self.assertEqual(output.count('role="img"'), 1)
        self.assertIn('data-search="', output)
        self.assertIn('data-date="', output)
        self.assertIn("証券コード・銘柄名で検索", output)
        self.assertIn('id="history-date-from"', output)
        self.assertIn('id="history-date-to"', output)
        self.assertIn('id="history-load-more"', output)
        self.assertIn("最新20件を表示中", output)
        self.assertNotIn("<details class=\"history-details\"", output)
        self.assertIn("https://jp.tradingview.com/chart/", output)
        self.assertNotIn('id="selector-filter"', output)

    def test_write_report_creates_all_mode_pages_and_free_shells(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_report(
                self.ledger,
                report_path=root / "weak_early_beta_latest.html",
                metrics_path=root / "metrics.csv",
                monthly_metrics_path=root / "monthly.csv",
            )
            for filename in MODE_PAGE_NAMES.values():
                self.assertTrue((root / filename).exists(), filename)
                self.assertTrue((root / filename.replace(".html", "_free.html")).exists(), filename)
            self.assertTrue((root / "weak_early_beta_guide.html").exists())
            self.assertTrue((root / "weak_early_beta_guide_free.html").exists())
            self.assertTrue((root / ANALYTICS_PAGE_NAME).exists())
            self.assertTrue((root / ANALYTICS_PAGE_NAME.replace(".html", "_free.html")).exists())

    def test_analytics_is_separate_and_uses_actual_period(self):
        metrics = build_metrics(self.ledger, pd.Timestamp("2026-09-11"))
        monthly = build_monthly_metrics(self.ledger, pd.Timestamp("2026-09-11"))
        output = render_analytics_report(
            self.ledger,
            metrics,
            pd.Timestamp("2026-09-19", tz="Asia/Tokyo"),
            monthly_metrics=monthly,
        )
        dates = pd.to_datetime(self.ledger["signal_date"])
        expected = f"{dates.min():%Y-%m-%d}<br>〜{dates.max():%Y-%m-%d}"
        self.assertIn(expected, output)
        self.assertIn("トータルの資産推移", output)
        self.assertIn("資金増加率", output)
        self.assertIn("単純年率", output)
        self.assertIn("3モード該当なら合計300株", output)
        self.assertIn("Cloud全体の成績 — モード別積み上げ", output)
        self.assertIn("Cloud全体の成績 — 銘柄均等", output)
        self.assertNotIn('id="history"', output)

    def test_free_report_masks_pending_identity_until_fifth_close(self):
        pending = self.ledger.head(1).copy()
        pending.loc[:, "source_scope"] = "FORWARD_CAUSAL"
        pending.loc[:, "status"] = "entered"
        pending.loc[:, "symbol"] = "9999"
        pending.loc[:, "company_name"] = "未確定テスト社"
        pending.loc[:, "gross_return"] = float("nan")
        pending.loc[:, "one_hundred_shares_pl_yen"] = float("nan")
        metrics = build_metrics(pending, pd.Timestamp("2026-09-20"))
        monthly = build_monthly_metrics(pending, pd.Timestamp("2026-09-20"))
        output = render_report(
            pending,
            metrics,
            pd.Timestamp("2026-09-20", tz="Asia/Tokyo"),
            monthly_metrics=monthly,
            mask_pending=True,
        )
        self.assertNotIn("9999", output)
        self.assertNotIn("未確定テスト社", output)
        self.assertIn("5営業日終値確定まで会員限定", output)
        self.assertIn('href="/purchase"', output)

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
            reports_path = root / "reports.json"
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
            reports_path.write_text(json.dumps({"reports": [{
                "alertId": identity,
                "fields": [{"name": "材料インパクト", "value": "様子見：テスト"}],
            }]}, ensure_ascii=False), encoding="utf-8")
            receipts = export_receipts(state_path, receipt_path, reports_path)
            self.assertEqual(receipts[0]["signal_date"], "2026-09-18")
            self.assertEqual(receipts[0]["symbol"], "1234")
            self.assertIn("材料インパクト", receipts[0]["html"])

    def test_embedded_fundamental_text_is_html_escaped(self):
        ledger = self.ledger.head(1).copy()
        ledger.loc[:, "fundamental_html"] = '<img src=x onerror="alert(1)">'
        metrics = build_metrics(self.ledger, pd.Timestamp("2026-09-11"))
        output = render_report(ledger, metrics, pd.Timestamp("2026-09-19", tz="Asia/Tokyo"))
        self.assertNotIn('<img src=x onerror="alert(1)">', output)
        self.assertIn("&lt;img src=x", output)

    def test_embedded_fundamental_links_and_impact_are_rendered(self):
        ledger = self.ledger.head(1).copy()
        ledger.loc[:, "fundamental_html"] = (
            "材料インパクト\nポジティブ材料：受注を確認\n\n"
            "開示リンク\n[会社資料](https://example.com/disclosure)"
        )
        metrics = build_metrics(self.ledger, pd.Timestamp("2026-09-11"))
        output = render_report(ledger, metrics, pd.Timestamp("2026-09-19", tz="Asia/Tokyo"))
        self.assertIn("impact-positive", output)
        self.assertIn('href="https://example.com/disclosure"', output)
        self.assertIn('target="_blank" rel="noopener noreferrer"', output)

    def test_guide_uses_beginner_friendly_copy_without_future_only_limit(self):
        output = render_guide(pd.Timestamp("2026-09-20", tz="Asia/Tokyo"))
        self.assertIn("モードは、銘柄を選ぶ「見方の違い」です", output)
        self.assertIn("資料名を押すと根拠となる開示資料を確認できます", output)
        self.assertNotIn("未来の新規検出だけを対象に", output)


if __name__ == "__main__":
    unittest.main()
