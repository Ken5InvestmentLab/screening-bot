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

## 株式分割・併合と価格上限

日次取得はCloud専用の `corporate_actions.py` を通し、Yahooの日足と分割・併合イベントを一緒に取得します。Yahooの価格・出来高は既に分割調整されているため、同じ倍率を重ねて適用しません。イベント日と比率、価格基準日を保存して、各営業日当時の株価・出来高を復元します。相対的なテクニカル指標には連続した調整系列を使い、価格・出来高の絶対条件には当時の値を使います。後日の分割で過去の価格条件を変更しません。

売買停止後など、価格がない日に記録されたイベントも別のジャーナルへ保存します。架空の日足は追加しません。始値・終値が高値・安値の範囲外にある不整合バーは、元の値と理由を保存して `source_usable=false` にします。指標計算時だけそのバーのOHLCVを欠損として扱い、日付の位置を保つために行を削除しません。不正な購入・決済価格から成績を確定させず、日次receiptへ隔離件数と詳細を残します。

提供元の修復が分割相当の段差を作った系列、極端な併合後に修復された出来高の基準が不明なバー、極端な併合と長期の価格欠落を挟み同じコードで再開した系列も、倍率を推測せず隔離します。旧キャッシュからの初回移行に限り、提供元の修復済み表示・4価格の同一倍率・既知分割比率・出来高の逆倍率が一致する修復を監査記録付きで受け入れます。検証済みキャッシュ同士の比較はこの例外を使いません。詳細な品質・移行監査は日足キャッシュ隣の `.source-quality.json` に保存し、日次receiptにそのパスとSHA-256を残します。

日次の検出・Discord銘柄通知は、東証プライム・スタンダード・グロースの内国株式を株価上限なしで候補にします。出来高、20円の価格下限、価格品質、Tail判定、既存5モードの選抜条件、JPXの整理銘柄除外は維持します。対象銘柄すべてを通知するのではなく、この条件で選ばれた銘柄を通知します。

学習は元のV7研究と同じく、銘柄ごとの前の観測日の実株価が1,000円以下の行で行います。予測候補だけを広げ、学習行・日別順位ラベル・Tail CDFの基準は変えません。高価格銘柄が既存モードで選ばれると、低価格銘柄の選抜結果も変わる場合があります。既存の検出台帳や過去の成績を再計算・再通知せず、変更後の日次検出から適用します。レポートの表示上限の初期値は1,000円のままで、「上限なし」を選ぶと保存済みの高価格銘柄も表示します。上限なしの検出成績を過去まで評価する場合は、保存済みの上限付きTail候補を流用せず、別の研究として再検証します。

新規取引は当時の購入価格と取得100株を保存し、購入日の翌日以降から決済日までの分割・併合を保有株数へ反映します。購入日当日のイベントは購入価格に反映済みとして二重適用しません。検証済みの確定取引は、後日の分割で価格・騰落率・円損益・必要資金を書き換えません。端株の換金処理が必要な場合は、換金価格や丸めを推測せず停止します。

購入予定日は検出翌営業日、決済予定日は検出5営業日後とし、既存の日本営業日カレンダーで固定します。全銘柄の日足が欠けた日を営業日から飛ばしません。購入済みの価格・日付が保存済み記録と変わる場合は確認を要求するエラーとします。日足キャッシュは、一時ファイルの書き込みが完了してから置換し、書き込み失敗で前回の価格・イベント証跡を壊しません。

従来の確定済みcanonical履歴は、調整済み株価基準の参考値として保存し、今回の変更だけで当時100株の実額へ書き換えません。旧形式の日足キャッシュにはイベントの証跡がないため、採点には `daily --refresh-live` による取得が必要です。既知イベントの未調整段差、イベントの削除・変更、説明できない過去価格の変更は、公開レポートを更新する前にエラーにします。GASや既存スコアリングレポートの取得処理は変更しません。

検証コマンド:

```powershell
python -B -m unittest tests.test_weak_early_beta tests.test_weak_early_beta_corporate_actions tests.test_weak_early_beta_trade_basis tests.test_weak_early_beta_model
```

## 実行コマンド

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

Windowsの専用ランナーは `scripts/windows/weak-early-beta-fundamental-runner.mjs` です。例設定を複製して実行します。ランナーは `gpt-5.6-luna` / `xhigh` を固定し、claimの16:15 JSTを基準に開示時点と7フィールドを検証します。検証済み分析はベータ専用stateの `completed` に保存し、receiptを介してHTMLへ埋め込みます。ファンダ分析のDiscord通知とwebhook設定は不要です。HTMLへの取り込みが成功するまでclaimを保持し、中断時は同じ分析を再利用します。

## 定時運用

- Codex予定タスク `Cloud 日次スコアリング`（ID `cloud-2`）を平日17:00 JSTに実行します。
- ランナーは当日の日足が揃うまで最大3回・5分間隔で有限再試行し、揃わなければ通知前に停止します。
- 毎回JPX公式の監理・整理銘柄一覧を取得し、シグナル日以前に「上場廃止の決定・整理銘柄指定」となった銘柄は新規エントリー対象から除外します。監理銘柄だけの銘柄は一律除外しません。除外行は `state/excluded_detections.csv` に監査保存します。
- Codex予定タスク `Cloud 5営業日目リマインダー`（ID `cloud-5`）を平日7:30 JSTに実行します。
- 両ランナーとも日本の銀行休業日（祝日・振替休日・12月31日〜1月3日）をコード側で判定し、休業日は何も変更しません。
- 日次ランナーは `scripts/windows/weak-early-beta-daily-runner.mjs`、朝のリマインダーは `scripts/windows/weak-early-beta-exit-reminder-runner.mjs` です。新規検出がある日だけ銘柄Embedと集計Embedを送り、0件の日は公開向け通知を送りません。起動・検出終了・エラー停止はadmin用システムログチャンネルに記録し、17:30 JSTの独立した監視タスクが定時起動の記録を確認します。ファンダ分析はHTMLへ反映し、Discordへ通知しません。
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

基本株数は100株が初期値で、100株単位で変更できます。売買コストは初期値0%、指定率を買付金額と売却金額の両方に適用し、画面・グラフ・CSVを同じ条件で再計算します。単純年率はこのコストを含み、複利・税金は含みません。検出日終値の上限は保存済みの検出を絞る条件で、検出されなかった銘柄を増やしません。

過去の銘柄名はJPXの2026年8月版「東証上場銘柄一覧」から、canonical trade rowsに登場する104銘柄だけを `state/company_names_202608.csv` へ固定しています。元ExcelのSHA256は `FFF94DD14057C8BFA36A3FBABD8E228BBED63751C7ECD10C1A8281F5385FCB78`、固定CSVのSHA256は `B496BA65F862B0BFD453500BFE9DD172A039D996C4B38CC7BC9D41AF4314FC45` です。

## 運用境界

- 検出履歴とモード別ページへの入口は `reports/weak_early_beta_latest.html`、合算成績と資産推移は `reports/weak_early_beta_analytics.html`、各モードは `reports/weak_early_beta_<mode>.html` に生成します。各ページの無料版は `_free.html` です。
- `weak-early-beta-gate/` は現行report-gateの認証実装をコード再利用しますが、別Worker・別公開URL・別assetsです。
- 既存の本番workflow、Stable、Sniper、Mega、TradingView、watchlist、Spreadsheetは読み書きしません。
- 定時起動は研究branchを対象にしたCodex予定タスクから専用Windowsランナーを呼びます。GitHub Actionsのscheduleや既存GASは変更しません。
