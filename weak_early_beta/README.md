# 天底極致 -Cloud-

現行の Stable / Sniper / Mega / Discord / HTML を変更せず、復元済み `WEAK_EARLY_EXACT_V1` の5条件を並走させる独立ベータです。

## 採用した5条件

| 内部ID（固定） | 表示名 | 特徴 |
|---|---|---|
| `volr20_low` | Silence | 20日平均に対して出来高が静かな候補 |
| `body_pct_low` | Dive | 符号付き実体比が低く、陰線側へ沈んだ候補 |
| `mean_rank_volr20_body_pct` | Shadow | 出来高沈静と陰線沈み込みの平均順位 |
| `dual_top1_agreement` | Fusion | 上の2条件が同じ銘柄をTop1に選んだ日だけ |
| `dual_top1_agreement_g3_no_acute_selloff` | Balance | 2条件一致に市場1日中央値リターン `>= -1%` を追加 |

表示名だけを変更し、内部ID・gate・rank・tie-break・因果タイミングは変更していません。

## データフロー

```text
引け後のJPX日足
  -> 月初前に成熟したlabelだけでV7を学習（30,000行以上）
  -> causal Tail CDF >= 0.999
  -> med_ret5 <= 0 AND ret10 <= 0.5735294117647058
  -> 5条件で選択
  -> JPXで上場廃止決定・整理銘柄指定済みの銘柄を除外
  -> append-safe ledger
  -> 専用Premium Worker claim（日次は新規検出分、Luna xhigh）
  -> ファンダ分析receiptをledgerへ反映
  -> 分析込みHTMLを再生成・Cloudflareへ反映
  -> 最後に専用Discordへ検出Embedを通知
```

同じ日・銘柄が複数条件へ該当した場合、ledgerは条件ごとに1行を保持し、Discordは銘柄単位で1通知へまとめます。

## コマンド

```powershell
py -m weak_early_beta.cli bootstrap
py -m weak_early_beta.cli report
py -m weak_early_beta.cli daily --refresh-live --dry-run-notify
py -m weak_early_beta.cli daily --refresh-live --notify
py -m weak_early_beta.cli notify
py -m weak_early_beta.cli notify-day --date 2026-09-24 --dry-run
py -m weak_early_beta.cli refresh-restrictions --as-of 2026-09-20
py -m weak_early_beta.cli is-business-day --date 2026-09-24
py -m weak_early_beta.cli remind-exits --date 2026-09-24 --dry-run
py -m weak_early_beta.cli prepare-fundamentals
py -m weak_early_beta.cli export-fundamentals
py -m weak_early_beta.cli import-fundamentals --receipts path/to/receipts.json
```

通知を実送信する場合は `WEAK_EARLY_BETA_SIGNAL_WEBHOOK_URL`、レポートリンクには `WEAK_EARLY_BETA_REPORT_URL` を使います。専用Botがチャンネル履歴を読める場合だけ `WEAK_EARLY_BETA_DISCORD_BOT_TOKEN` を設定します。現行Bot tokenはベータへ流用しません。通常の日次運用では `state/fundamental_queue.json` の新規検出分を処理します。過去銘柄のファンダ分析も、対象期間と上限を固定した専用バッチとして後から追加できます。

Windowsの専用ランナーは `scripts/windows/weak-early-beta-fundamental-runner.mjs` です。例設定を複製し、`WEAK_EARLY_BETA_FUNDAMENTAL_WEBHOOK_URL` をGit管理外の `.env` に設定して実行します。ランナーは `gpt-5.6-luna` / `xhigh` を固定し、現行Premium Workerのvalidatorでdry-run通過後に専用チャンネルへ投稿します。

## 定時運用

- Codex予定タスク `Cloud 日次スコアリング`（ID `cloud-2`）を平日16:15 JSTに実行します。16:00直後のデータ未到着を避けつつ早めに動かす設定です。
- ランナーは当日の日足が揃うまで最大3回・5分間隔で有限再試行し、揃わなければ通知前に停止します。
- 毎回JPX公式の監理・整理銘柄一覧を取得し、シグナル日以前に「上場廃止の決定・整理銘柄指定」となった銘柄は新規エントリー対象から除外します。監理銘柄だけの銘柄は一律除外しません。除外行は `state/excluded_detections.csv` に監査保存します。
- Codex予定タスク `Cloud 5営業日目リマインダー`（ID `cloud-5`）を平日7:30 JSTに実行します。
- 両ランナーとも日本の銀行休業日（祝日・振替休日・12月31日〜1月3日）をコード側で判定し、休業日は何も変更しません。
- 日次ランナーは `scripts/windows/weak-early-beta-daily-runner.mjs`、朝のリマインダーは `scripts/windows/weak-early-beta-exit-reminder-runner.mjs` です。日次の最後に、検出ありなら銘柄Embedとアナリティクス更新完了Embed、検出なしならゼロ件Embedと更新完了Embedを送ります。予定タスク自体は `gpt-5.6-luna` / minimal、ファンダ分析だけは専用ランナーが `gpt-5.6-luna` / xhigh に固定します。
- PCとCodexのローカル実行環境、インターネット接続が利用できることが前提です。GitHub cronや既存GAS、本番workflowは使用しません。

## 成績表示

- 年別・月別・全期間の `確定取引数 / 平均 / 中央値 / 勝率 / +10 / +20 / -10 / -20 / 最大上昇 / 最大下落 / Top3除外平均`
- 100株ずつ売買した損益
- 100株損益額による年別・全期間順位
- 同時保有に必要だった必要資金（目安）と資金増加率
- 5モードを合わせた統合成績（1モードにつき100株の「モード別積上げ」と、同日・同銘柄を100株にする「銘柄均等」を併記）
- 同時保有を賄う参考必要元金に対する単純年率
- 未確定件数
- トータルと5モードを分けた専用ページ
- 必要資金（目安）へ決済日の100株損益を加算した資産推移グラフ
- 証券コード・銘柄名・シグナル日範囲・モードによる検出履歴検索
- 検出履歴と月別成績の20件ずつ追加表示、端末ごとのダークモード保存、独立した見方・使い方ページ

延べ投入額は表示しません。単純年率は複利・売買コスト・税金を含みません。

過去の銘柄名はJPXの2026年8月版「東証上場銘柄一覧」から、canonical trade rowsに登場する104銘柄だけを `state/company_names_202608.csv` へ固定しています。元ExcelのSHA256は `FFF94DD14057C8BFA36A3FBABD8E228BBED63751C7ECD10C1A8281F5385FCB78`、固定CSVのSHA256は `B496BA65F862B0BFD453500BFE9DD172A039D996C4B38CC7BC9D41AF4314FC45` です。

## 運用境界

- 検出履歴とモード別ページへの入口は `reports/weak_early_beta_latest.html`、合算成績と資産推移は `reports/weak_early_beta_analytics.html`、各モードは `reports/weak_early_beta_<mode>.html` に生成します。各ページの無料版は `_free.html` です。
- `weak-early-beta-gate/` は現行report-gateの認証実装をコード再利用しますが、別Worker・別公開URL・別assetsです。
- 既存の本番workflow、Stable、Sniper、Mega、TradingView、watchlist、Spreadsheetは読み書きしません。
- 定時起動は研究branchを対象にしたCodex予定タスクから専用Windowsランナーを呼びます。GitHub Actionsのscheduleや既存GASは変更しません。
