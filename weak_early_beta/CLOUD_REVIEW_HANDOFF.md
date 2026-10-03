# Cloud 改修のレビューと残設定

> **2026-10-03 最終実100株比較プレビューv03完成。** 共有HTML辞書・遅延読込・資格付きbundle配信を実装。
> 原D5を凍結したまま表示D5/D6の取得基準を揃え、analytics初回HTMLは306,111 bytes。
> Python215件、gate179件、実データブラウザ140件、資格失効・異常応答10件、
> PC/スマホ・ライト/ダーク・full/freeの描画44件が成功。本番公開は本人の確認待ち。

対象は `research/weak-early-beta@0dc12cb5d8a6acd226a830d3e83ebc84e368986e`。
作業ブランチは `codex/cloud-analytics-d6-member-preferences`、レビュー先は
[draft PR #16](https://github.com/Ken5InvestmentLab/screening-bot/pull/16)。
main、検出条件、既存Discord通知処理、本番データを保護している。
**ユーザーの最終プレビュー確認と明示的な本番公開承認まではmerge・deployしない。**

## 実装範囲

- 研究HTMLをブラウザで確認し、2つの株数方式の比較、共通軸の累積確定損益、
  年別グラフ、資金・損失・集中度、数量をそろえた比較、条件の重なり、勝敗内訳を移植する。
  数値は現在の台帳と選択条件から再計算し、研究の固定実績を貼り付けない。
- 2022は表示・集計からだけ除外する。年、価格上限、D5/D6、株数方式を切り替えられる。
  過去再構成と実運用観測、2026が既知の過去期間であることを明記する。
- 入口は検出から1営業日後の始値。D5は「検出から5営業日後 終値」、
  D6は「検出から6営業日後 始値」。D5経済を凍結したまま、D6の実価格・状態・時刻・来歴と
  分割併合後の経済を独立して記録する。未知は空欄で、代替価格を使わない。
- 価格上限は検出日の検証済み名目実終値。初期値1,000円、プリセットは
  1,000/2,000/3,000/5,000円、制限なし、自由入力。検出モデルの直前観測行の
  実終値1,000円以下という条件は変更しない。上限を広げても未検出銘柄は復活しない。
- 無料版はD6実始値の検証済み取得を解禁条件とし、未解禁行を集計前に丸ごと除外する。
  HTML・属性・リンク・JSON・圧縮variants・CSV・価格境界・件数にも寄与させない。
  full/freeのキャッシュを分け、生台帳をanalyticsへ埋め込まない。
- 会員IDに紐づく設定API、既存Discord認証に追加するWhop有料資格確認、
  通知OFFを既定とするUI、配信台帳と無送信dry-runを用意した。端末保存は補助とする。
  新規検出、08:00 JSTの「今日は確定日」、実価格取得後の結果を個別に選べる。
  不明・失効・API障害時は保留し、重複を排除する。メール機能は追加しない。

非同期の集計切替中は両CSVと保存を無効化し、成功時に表示・履歴・CSVを一括反映する。
失敗時は直前の表示に戻す。空一覧の案内行は件数・取引CSVへ含めない。
年・株数方式は端末の表示設定、価格・D5/D6・通知は会員設定として分離する。

## 資料と価格照合

初回のLibrary正規取得はWindowsの`os.setxattr`非対応で失敗した。
その後、ユーザーが`task/inputs`へ配置したローカル原本を明示指示どおり使用した。
URLの直接取得やhelperの改造は行っていない。

| 入力 | bytes | SHA-256 |
|---|---:|---|
| 研究HTML | 4,915,183 | `e0e7952a2a6047062984bdb4f1b24abddf585862f75969ff99ac91947baf550c` |
| 保存一式JSON | 6,581,850 | `6e3c9b5e691fc38b92806b5ef879de19bcc090d314c8ceaeb5cace6b2ac10ab7` |
| JSONから復元した研究ZIP | 4,940,114 | `370e9c266319115b035808949b9fc5df3b2fe50f2f64b1dc9ce3f236714578d7` |
| 前日・当日価格比較ZIP | 157,679 | `481a688c76f6d86c3741b016de510ca2deb5f52a4c61ba4ccd91977ed55be37d` |

JSONの宣言サイズ・SHAを確認してgzip/base64を復元し、ZIPのパス・重複・暗号化・
symlink・展開量を検査した。CRCと全93ファイルのmanifest検証が成功した。
資料内のコードやモデルは実行・デシリアライズしていない。原本3ファイルは不変。

972モード行は254検出に対応し、研究253検出は967行と一致した。
未照合は`2026-09-30|4052`の5行で、実終値・D6を推測せず空欄にする。
253件の検出日実終値、506取引の入口/D5/D6日付とDecimal損益、872件の数量方式、
48集計組を独立に再計算した。2資料で全項目を照合できる取引は218検出、
残る35検出は価格比較資料の制限なし対照群から検証する。

| 検出日の実終値上限 | 検証済み検出数 |
|---|---:|
| 1,000円 | 218 |
| 2,000円 | 237 |
| 3,000円 | 247 |
| 5,000円 | 251 |
| 制限なし | 253 |

上表は履歴の価格母集団であり、成績集計の完了件数とは異なる。
既存の入口実行可能性ポリシーによる参考扱いの検出は履歴に残し、成績から除外する。
有料の制限なし履歴は未照合の最新検出も含む254件、無料版の上限は253件となる。

原`detections.csv`のSHAは
`7574c18d72948e8faa3b1e0e8d718690242750f5459e68a3f98d7e18b9a55909`。
バックフィルは別CSVと監査結果へ出力し、通常canonical upsertの保護を解除しない。
継続反映には対象IDと既存値を確認した専用価格証跡をレポート生成時に明示適用する。
詳細は[ENDPOINT_BACKFILL.md](ENDPOINT_BACKFILL.md)を参照。

### 検証範囲の限界

資料には元vendorバーと完全な企業行動表の実体がなく、SHA参照だけがある。
今回は固定研究資料の価格・日付・企業行動・計算の再検算であり、市場データの再取得や
別vendor照合ではない。共通218件も同じ上流資料に由来する。
証跡には研究資料由来と記録し、取込時刻を元vendorの取得時刻と偽らない。

凍結D5の調整価格参考値と研究の名目価格には46検出・164モード行で金額差がある。
原D5の価格・数量・円損益は変更せず、独立した表示専用sidecar
`state/reviewed_actual_d5.v1.json`から実100株D5経済を計算する。
履歴・CSV・資金・グラフ・年度/上限の集計は全て同じ変換を通し、D5/D6を
翌営業日実始値の100株・コスト0という同じ取得元本基準へ揃えた。
日付と企業行動を各出口まで検証し、証跡不足は未確認として比較対象から除く。
分割・併合を反映しても、単元未満株が市場始値で約定することを保証しない。

研究固定cohort（実終値1,000円以下）の2023–25年174件はD5約361,070円 / D6約430,770円、
2026年44件はD5 162,300円 / D6 205,000円を再現。既存の参考除外5件を反映した製品成績は
2023–25年171件で320,470円 / 379,670円、2026年42件で148,700円 / 191,300円。
7997・7601・3350・3103・6840の除外ID・理由・両出口の金額を独立照合資料に記録。
年度・6上限・D5/D6・数量方式の148照合、およびDecimal/資金/全曲線の36照合が成功した。

## 検証とプレビュー

最終版のPython回帰215件が114.857秒で成功した。
Node回帰30件、gate179件、型検査、Wranglerの無公開buildが成功した。
実データの全上限（1000/2000/3000/5000/制限なし/1234.56）×D5/D6で、
一覧・集計・CSV・会員設定保存/再読込と無料境界のブラウザ140件が成功した。
全253検出の入口・両出口・損益率CSV、履歴円損益、未確認行、履歴リンクの21照合が成功した。
401/403後の識別子破棄と503等のロールバック10件、PC/スマホ・ライト/ダーク・full/freeと
popupを含む描画44件、自己完結確認HTMLの2画面検査も成功した。
研究履歴967行は本番用通知adapterから除外され、現在の通知候補は0件。
原台帳SHAと生成16ページのrepo/public一致を最終照合した。

### 実測性能と生成アセット

16ページ、16,232 variants、4,062 JSON bundlesを再生成。各bundleは最大4条件・
実測最大131,963 bytes。初回analytics HTMLは306,111 bytes（free 306,455）、
履歴は1,818,232 bytes（free 1,812,685）。初期条件だけをinlineに置き、共通HTML辞書を
一度だけ収録する。非表示テーマ画像・画面外のフッター画像は遅延読込する。

Edge/localhost・HTTP圧縮なし・cold cacheの測定では、PC/スマホ4通常条件の
操作可能0.211–0.252秒、最大切替0.357秒。初回総転送はライト923,243 bytes、
ダーク1,804,142 bytes（既存ロゴ画像も含む）。10Mbps・80ms・CPU4倍の模擬PCは
操作可能1.459秒・最大切替0.488秒。1.6Mbps・150ms・CPU6倍の模擬スマホは
操作可能2.976秒、画像取得を含む安定化9.755秒、最大切替2.180秒。
実機、CDN/TLS、Whop通信、native/GPUメモリの測定ではない。

実100株比較へ修正したv03操作用ZIPは134,847,411 bytes、4,089 entries、CRC正常。
画面8枚を内蔵したv03確認HTMLは8,900,409 bytesでサーバー不要。
ZIPの操作にはローカルHTTPが必要。private sidecar・原台帳・資格情報は含めない。
bundle全体172,440,360 bytesは生成物なのでGit履歴へ毎回追加しない。
承認後のCloud専用tag deployは対象commitの台帳と固定価格証跡からHTMLとbundleを
一緒に再生成し、検証してから同期する。そのworkflow自体は未起動であり、ローカルで
同じbuilderを検証した。v02はD5/D6の経済基準が混在する旧確認資料であり、v03で置き換える。

Windows sandboxの一時フォルダで`WinError 5`が発生するため、Pythonテストと
子プロセスを使うブラウザ・ビルドは承認済みPC実行環境で検証する。
Python 3.14.7、NumPy 2.5.3、pandas 2.3.3、scikit-learn 1.9.1、XGBoost 3.4.1、
Node 22.13.1を使用。workflowのPython指定は3.12。モデル再学習は行っていない。

```powershell
python -B -m unittest tests.test_weak_early_beta tests.test_weak_early_beta_corporate_actions tests.test_weak_early_beta_trade_basis tests.test_weak_early_beta_model tests.test_weak_early_beta_endpoint_receipts tests.test_weak_early_beta_report_preferences tests.test_cloud_notification_adapter
python -B -m unittest tests.test_weak_early_beta_analytics tests.test_weak_early_beta_research_backfill tests.test_weak_early_beta_reviewed_overlay tests.test_weak_early_beta_research_presentation tests.test_weak_early_beta_actual_d5
python -B weak_early_beta/scripts/build_review_preview.py --output ../review-cloud
python -m http.server 8765 --bind 127.0.0.1 --directory ../review-cloud
```

別シェルで`weak-early-beta-gate`へ移動し`npm ci`、`npm run check`を実行する。
新規checkoutではbundleをGit管理していないため、checkの前に
`python -B weak_early_beta/scripts/build_review_preview.py --output reports` を実行する。
checkは同期・認証テスト・型検査・dry-run buildであり、公開しない。
previewはmetrics/HTML/補助アセットを別フォルダへ保存し、原台帳のSHA不変を確認する。

確認用 `Cloud_実100株比較_確認資料_v03.html` と `Cloud_実100株比較プレビュー_v03.zip` は
作業workspaceの `qa/delivery/actual-d5-v03/` に保存済み。親の指示により、v03のLibrary
出力uploadは試行していない。以前のv02の正規prepared uploadは
`Library prepare_uploads is not available` で停止した。別経路で権限拒否を回避しない。
ローカル操作用previewは `http://127.0.0.1:8772/weak_early_beta_analytics.html`。
静的localhost確認にはfull/freeの両方があり、本番資格認証の証明ではない。
PC終了の許可は取り消されており、終了・再起動・スリープは行わない。

## 残る本番セットアップ

[CLOUD_MEMBERSHIP_SETUP.md](../weak-early-beta-gate/CLOUD_MEMBERSHIP_SETUP.md)にまとめた。
D1とmigration、Discord IDとWhop会員の検証可能な紐付け、Whop資格確認用設定、
必要なWebhook設定、VAPID、プッシュ購読登録、候補取込・配信は本番で未設定・未実施。
今回のコードに実送信を有効化するスイッチはない。

会員・認証・通知はテスト用会員とローカルAPIで検証する。実Whopアカウントとの紐付けや
実プッシュ到達は未検証。既存認証を緩めず、新キー発行・権限拡張・契約は行わない。
GitHubのチェックが起動しない場合はローカル成功と区別し、
日次検出・本番deploy workflowを検証目的で起動しない。
