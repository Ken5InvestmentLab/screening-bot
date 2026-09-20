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
  -> append-safe ledger
  -> 専用Discordへ検出通知
  -> 専用Premium Worker claim（未来分のみ）
  -> ファンダ分析receiptをledgerへ反映
  -> 別HTMLを再生成
```

同じ日・銘柄が複数条件へ該当した場合、ledgerは条件ごとに1行を保持し、Discordは銘柄単位で1通知へまとめます。

## コマンド

```powershell
py -m weak_early_beta.cli bootstrap
py -m weak_early_beta.cli report
py -m weak_early_beta.cli daily --refresh-live --dry-run-notify
py -m weak_early_beta.cli daily --refresh-live --notify
py -m weak_early_beta.cli prepare-fundamentals
py -m weak_early_beta.cli export-fundamentals
py -m weak_early_beta.cli import-fundamentals --receipts path/to/receipts.json
```

通知を実送信する場合は `WEAK_EARLY_BETA_SIGNAL_WEBHOOK_URL`、レポートリンクには `WEAK_EARLY_BETA_REPORT_URL` を使います。専用Botがチャンネル履歴を読める場合だけ `WEAK_EARLY_BETA_DISCORD_BOT_TOKEN` を設定します。現行Bot tokenはベータへ流用しません。ファンダ分析は `state/fundamental_queue.json` の未来分claimだけを対象にし、過去分を一括生成しません。

Windowsの専用ランナーは `scripts/windows/weak-early-beta-fundamental-runner.mjs` です。例設定を複製し、`WEAK_EARLY_BETA_FUNDAMENTAL_WEBHOOK_URL` をGit管理外の `.env` に設定して実行します。ランナーは `gpt-5.6-luna` / `xhigh` を固定し、現行Premium Workerのvalidatorでdry-run通過後に専用チャンネルへ投稿します。

## 成績表示

- 年別・月別・全期間の `確定取引数 / 平均 / 中央値 / 勝率 / +10 / +20 / -10 / -20 / 最大上昇 / 最大下落 / Top3除外平均`
- 100株ずつ売買した損益
- 100株損益額による年別・全期間順位
- 同時保有に必要だった参考元金と元金増加率
- 5モードを合わせた統合成績（1モードにつき100株の「モード別積上げ」と、同日・同銘柄を100株にする「銘柄均等」を併記）
- 同時保有を賄う参考必要元金に対する単純年率
- 未確定件数
- トータルと5モードを分けた専用ページ
- 参考元金へ決済日の100株損益を加算した資産推移グラフ
- 証券コードまたは銘柄名による検出履歴検索

延べ投入額は表示しません。単純年率は複利・売買コスト・税金を含みません。

過去の銘柄名はJPXの2026年8月版「東証上場銘柄一覧」から、canonical trade rowsに登場する104銘柄だけを `state/company_names_202608.csv` へ固定しています。元ExcelのSHA256は `FFF94DD14057C8BFA36A3FBABD8E228BBED63751C7ECD10C1A8281F5385FCB78`、固定CSVのSHA256は `B496BA65F862B0BFD453500BFE9DD172A039D996C4B38CC7BC9D41AF4314FC45` です。

## 運用境界

- トータルは `reports/weak_early_beta_latest.html`、モード別は `reports/weak_early_beta_<mode>.html` を生成します。
- `weak-early-beta-gate/` は現行report-gateの認証実装をコード再利用しますが、別Worker・別公開URL・別assetsです。
- 既存の本番workflow、Stable、Sniper、Mega、TradingView、watchlist、Spreadsheetは読み書きしません。
- GitHub Actionsのscheduleはdefault branchに置かれた後だけ有効です。研究branch上では手動実行で検証します。
