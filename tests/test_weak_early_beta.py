import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from weak_early_beta.config import (
    COMBINED_STACKED_ID,
    COMBINED_UNIQUE_ID,
    SELECTOR_ORDER,
    selector_info,
)
from weak_early_beta.bank_calendar import fifth_session_from_entry, is_bank_business_day
from weak_early_beta.fundamental import export_receipts, prepare_claim
from weak_early_beta.historical_fundamentals import (
    FIELD_ORDER,
    build_manifest as build_historical_manifest,
    import_historical_reports,
    validate_historical_report,
)
from weak_early_beta.ledger import bootstrap_historical, build_fundamental_queue, merge_detections
from weak_early_beta.metrics import build_metrics, build_monthly_metrics
from weak_early_beta.notify import EMBED_COLORS, GUILD_ID, SUMMARY_CHANNEL_ID, _discord_url, _message, daily_summary_payload, notify_daily_completion
from weak_early_beta.report import (
    ANALYTICS_PAGE_NAME,
    MODE_PAGE_NAMES,
    _payoff_structure,
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
        self.assertEqual(fields["該当モード"], "Silence / Dive / Shadow / Fusion / Balance")
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("Weak+Early ベータ検出", serialized)
        self.assertNotIn("売買評価", serialized)
        self.assertNotIn("WEAK_EARLY_BETA:", serialized)

    def test_daily_summary_counts_overlapping_modes_and_links(self):
        group = self.ledger.head(5).copy()
        group.loc[:, "source_scope"] = "FORWARD_CAUSAL"
        group.loc[:, "signal_date"] = pd.Timestamp("2026-09-24")
        group.loc[:, "symbol"] = "7709"
        group.loc[:, "selector_id"] = SELECTOR_ORDER
        payload = daily_summary_payload(group, "2026-09-24", "https://example.test/")
        fields = {field["name"]: field["value"] for field in payload["embeds"][0]["fields"]}
        self.assertEqual(fields["重複を除いた検出銘柄"], "1件")
        self.assertEqual(fields["モード別内訳"], "**1件**｜Silence・Dive・Shadow・Fusion・Balance")
        self.assertIn("weak_early_beta_latest.html", fields["検出銘柄一覧"])
        self.assertNotIn("weak_early_beta_analytics.html", json.dumps(payload, ensure_ascii=False))

        second = group.head(2).copy()
        second.loc[:, "symbol"] = "1234"
        mixed = daily_summary_payload(pd.concat([group, second]), "2026-09-24", "https://example.test/")
        mixed_fields = {field["name"]: field["value"] for field in mixed["embeds"][0]["fields"]}
        self.assertEqual(mixed_fields["重複を除いた検出銘柄"], "2件")
        self.assertEqual(
            mixed_fields["モード別内訳"],
            "**2件**｜Silence・Dive\n**1件**｜Shadow・Fusion・Balance",
        )

    def test_daily_completion_sends_one_zero_count_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = Path(temp) / "daily.json"
            payloads = notify_daily_completion(
                self.ledger,
                "2026-09-24",
                "https://example.test/",
                state_path=state_path,
                dry_run=True,
            )
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0]["content"], "")
        self.assertEqual(
            payloads[0]["embeds"][0]["url"],
            "https://example.test/weak_early_beta_latest.html",
        )
        fields = {field["name"]: field["value"] for field in payloads[0]["embeds"][0]["fields"]}
        self.assertEqual(fields["重複を除いた検出銘柄"], "0件")
        self.assertEqual(fields["モード別内訳"], "全モード0件")

    def test_daily_summary_receipt_prevents_a_second_post(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = Path(temp) / "daily.json"
            response = {"channel_id": SUMMARY_CHANNEL_ID, "id": "123"}
            with patch("weak_early_beta.notify._post_bot", return_value=response) as post:
                first = notify_daily_completion(
                    self.ledger, "2026-09-24", "https://example.test/",
                    state_path=state_path, bot_token="test-token",
                )
                second = notify_daily_completion(
                    self.ledger, "2026-09-24", "https://example.test/",
                    state_path=state_path, bot_token="test-token",
                )
            self.assertEqual(len(first), 1)
            self.assertEqual(second, [])
            post.assert_called_once()
            self.assertEqual(post.call_args.args[0], SUMMARY_CHANNEL_ID)
            self.assertEqual(
                json.loads(state_path.read_text(encoding="utf-8"))["days"]["2026-09-24"]["summary_url"],
                f"https://discord.com/channels/{GUILD_ID}/{SUMMARY_CHANNEL_ID}/123",
            )
            self.assertEqual(_discord_url(response), f"https://discord.com/channels/{GUILD_ID}/{SUMMARY_CHANNEL_ID}/123")

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

    def test_analytics_is_separate_and_uses_generated_day_for_period_end(self):
        metrics = build_metrics(self.ledger, pd.Timestamp("2026-09-11"))
        monthly = build_monthly_metrics(self.ledger, pd.Timestamp("2026-09-11"))
        output = render_analytics_report(
            self.ledger,
            metrics,
            pd.Timestamp("2026-09-19", tz="Asia/Tokyo"),
            monthly_metrics=monthly,
        )
        dates = pd.to_datetime(self.ledger["signal_date"])
        expected = f"{dates.min():%Y-%m-%d}<br>〜2026-09-19"
        self.assertIn(expected, output)
        self.assertIn(f"最終検出: {dates.max():%Y-%m-%d}", output)
        self.assertIn("トータルの資産推移", output)
        self.assertIn('<section class="panel" id="annual-pl">', output)
        self.assertIn('<section class="panel" id="payoff-structure">', output)
        self.assertIn("50.88%", output)
        self.assertIn("+24.2%", output)
        self.assertIn("-12.6%", output)
        self.assertIn("1.92倍", output)
        self.assertIn("2026年（9月3日検出分まで）", output)
        self.assertNotIn("YTD", output)
        self.assertIn("資金増加率", output)
        self.assertIn("単純年率", output)
        self.assertIn("3モード該当なら合計300株", output)
        self.assertIn("Cloud全体の成績 — モード別積み上げ", output)
        self.assertIn("Cloud全体の成績 — 銘柄均等", output)
        self.assertNotIn("<th>配分方式</th>", output)
        self.assertIn('<div class="nav-links" aria-label="ページ移動">', output)
        self.assertNotIn('id="history"', output)

    def test_annual_pl_chart_uses_stacked_metrics_and_handles_losses(self):
        metrics = build_metrics(self.ledger, pd.Timestamp("2026-09-19"))
        year_mask = metrics["selector_id"].eq(COMBINED_STACKED_ID) & metrics["period"].eq("2026")
        metrics.loc[year_mask, "cash_pl_100_yen"] = -123_456
        output = render_analytics_report(
            self.ledger, metrics, pd.Timestamp("2026-09-19", tz="Asia/Tokyo")
        )
        chart = output.split('id="annual-pl">', 1)[1].split('</section>', 1)[0]
        self.assertIn('aria-label="2026年（9月3日検出分まで）の100株損益 ¥-123,456"', chart)
        self.assertIn('class="annual-pl-bar negative"', chart)
        self.assertIn("確定取引数", chart)
        self.assertEqual(chart.count('class="annual-pl-row"'), 4)
        self.assertIn("¥+370,003", chart)
        self.assertNotIn("¥+90,307", chart)

    def test_payoff_structure_uses_current_completed_trades(self):
        frame = pd.DataFrame({"gross_return": [0.2, -0.1, 0.0, float("nan")]})
        chart = _payoff_structure(frame)
        self.assertIn("33.33%", chart)
        self.assertIn("+20.0%", chart)
        self.assertIn("-10.0%", chart)
        self.assertIn("2.00倍", chart)
        self.assertIn("勝ち 1件・負け 1件・引き分け 1件", chart)
        self.assertIn('width:42.00%', chart)
        self.assertIn('width:21.00%', chart)

    def test_detection_history_starts_with_only_twenty_rows_visible_in_html(self):
        metrics = build_metrics(self.ledger, pd.Timestamp("2026-09-19"))
        output = render_report(self.ledger, metrics, pd.Timestamp("2026-09-19", tz="Asia/Tokyo"))
        history = output.split('<table id="detection-table">', 1)[1].split('</table>', 1)[0]
        self.assertEqual(history.count('data-date="'), len(self.ledger.drop_duplicates(["signal_date", "symbol"])))
        self.assertEqual(history.count('data-search="'), history.count('data-date="'))
        self.assertEqual(history.count(' hidden>'), max(history.count('data-date="') - 20, 0))
        self.assertIn('data-label="100株損益"', history)

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
            self.assertEqual(claim["alerts"][0]["receivedAt"], "2026-09-18T16:15:00+09:00")
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

    def _historical_report(self, signal_date="2023-01-04", symbol="3133"):
        values = {
            "材料インパクト": "様子見：一次資料に示された業績推移は横ばい。",
            "事業概要": "テスト用の事業概要。",
            "足元材料": "2023年1月3日公表の決算資料を確認。",
            "ファンダ要点": "売上と利益の推移を事業構造と合わせて見る。",
            "注意点": "顧客構成と継続性が開示からは限定的。",
            "開示リンク": "[2023-01-03 決算短信(15:00)](https://example.com/filing.pdf)",
            "Sources": "[IR](https://example.com/ir)\n[TDnet一覧](https://example.com/tdnet)",
        }
        return {
            "signalDate": signal_date,
            "symbolCode": symbol,
            "symbolName": "テスト社",
            "analysisCutoff": f"{signal_date}T16:15:00+09:00",
            "fields": [{"name": name, "value": values[name]} for name in FIELD_ORDER],
            "sourceChecks": [
                {"role": "official_ir", "url": "https://example.com/ir"},
                {"role": "irbank_or_tdnet", "url": "https://example.com/tdnet"},
            ],
            "disclosures": [{
                "title": "決算短信",
                "publishedAt": "2023-01-03T15:00:00+09:00",
                "url": "https://example.com/filing.pdf",
                "contentReviewed": True,
            }],
        }

    def test_historical_manifest_is_per_date_symbol_and_outside_forward_queue(self):
        sample = self.ledger[
            self.ledger["signal_date"].dt.strftime("%Y-%m-%d").eq("2023-01-04")
            & self.ledger["symbol"].eq("3133")
        ]
        manifest = build_historical_manifest(
            sample,
            generated_at="2026-09-23T16:00:00+09:00",
        )
        self.assertEqual(manifest["total_identities"], 1)
        record = manifest["records"][0]
        self.assertEqual(record["identity"], "2023-01-04|3133")
        self.assertEqual(record["analysis_cutoff"], "2023-01-04T16:15:00+09:00")
        self.assertEqual(record["status"], "pending")
        self.assertTrue(manifest["records"][0]["selector_names"])

    def test_historical_report_rejects_disclosures_published_after_cutoff(self):
        report = self._historical_report()
        report["disclosures"][0]["publishedAt"] = "2023-01-04T16:16:00+09:00"
        with self.assertRaisesRegex(ValueError, "post-detection disclosure"):
            validate_historical_report(report)

    def test_historical_import_sets_html_without_creating_or_clearing_discord_receipts(self):
        ledger = self.ledger[
            self.ledger["signal_date"].dt.strftime("%Y-%m-%d").eq("2023-01-04")
            & self.ledger["symbol"].eq("3133")
        ].copy()
        ledger.loc[:, "fundamental_discord_url"] = "https://discord.example/existing"
        updated, accepted = import_historical_reports(ledger, [self._historical_report()])
        self.assertEqual(len(accepted), 1)
        self.assertTrue(updated["fundamental_status"].eq("complete_historical").all())
        self.assertTrue(updated["fundamental_html"].str.contains("開示リンク").all())
        self.assertTrue(updated["fundamental_discord_url"].eq("https://discord.example/existing").all())
        manifest = build_historical_manifest(updated, accepted)
        self.assertEqual(manifest["status_counts"], {"complete": 1})

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
