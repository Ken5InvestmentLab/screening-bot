# Cloud D1 公開準備 — 2026-10-04

このD1作業後の通知OFF統合候補・最新テスト・公開と64bee25dへの復旧手順は [CLOUD_NOTIFY_OFF_RELEASE.md](CLOUD_NOTIFY_OFF_RELEASE.md) を参照。以下の準備HEAD e081eabはD1作業時点の記録。

## 本番公開の状態

**D1接続・スキーマは承認後に本番適用済み。準備コードは本番未公開。** 2026-10-04 19:16 JST時点。既存Cloudサイトを接続変更後もEdgeの既存ログイン状態から再読み込みし、従来レポートが表示されることを確認した。CloudflareはD1接続追加だけの新バージョン `64bee25d` を作成し、Deployment Historyで100%へのデプロイを確認した。直前の版 `499ebb26` は履歴に残っている。

D1 `tentei-cloud-settings` に0001〜0003のSQLを順次適用し、9テーブル・2つの明示インデックスを確認。全9テーブルのデータ件数は0。ユーザーが承認した `tentei-kyokuchi-cloud` への `CLOUD_DB` 接続だけを追加した。プレビュー側はNo connected bindings。マージ、push、`cloud-deploy-*`タグ、準備コードの公開、通知送信、新しいキー生成、承認範囲外の権限変更は行っていない。

## 適用前の空DB・復旧確認と適用後の検証

- 適用直前の `sqlite_master` はCloudflare内部テーブル `_cf_KV` のみ。アプリケーションテーブル・index・view・triggerは存在しなかった。
- D1 Consoleの `/bookmark` で適用前の復旧地点 `00000001-00000000-000050fa-e5bdcf181e5345c755c3104a1f35ded6` を取得し、Time Travel画面の復旧windowと `/restore <bookmark>` の手順を確認。復旧操作自体は実行していない。無料プランの復旧期間は7日であり、長期保存用exportではない。[Cloudflare公式Time Travel](https://developers.cloudflare.com/d1/reference/time-travel/)
- 既存キーのままEdgeの認証済みD1 Consoleを使い、SQLコメントと改行をConsole入力形式に合わせただけで、0001→0002→0003を適用。各応答はsuccess。元のmigrationファイルは変更していない。
- 本番の `sqlite_master` を画面から読み取り、未変更migrationを実行したローカルSQLiteの定義と照合。9テーブルと2インデックスの定義が一致した。件数確認は読取のみ、全9テーブル0件。テスト用の会員・購読・通知データは本番へ挿入していない。
- 適用後のOverview集計はNumber of Tablesが0のままだった。Consoleの実DB照会では9テーブルが返り、一覧スクリーンショットも保存した。集計表示の更新は未確認であり、テーブル確認には実DB照会結果を採用する。
- WorkerのProduction接続は `CLOUD_DB` → 対象DB ID、Previews BaseはNo connected bindingsを確認。
- 保存後のDiscordギルド/許可ロールと全既存変数は同じ。3つのDiscord/Session Secret名は同じでValue encryptedのまま。秘密値は開いたり書き換えたりしていない。通知設定・cron・queue consumerを追加していない。
- 既存サイトを再読み込みし、トップH1・検出履歴・モード別ページ・最終更新 `2026-10-02 18:04:49 JST` の従来表示を確認。ユーザー別保存機能の本番テストは、準備コード未公開のため未実施。
- 復旧が必要になった場合は現状を保全して、Workerを直前版 `499ebb26` へ戻すかCLOUD_DB接続を外し、必要な場合だけ保存したbookmarkへDBを復旧する。復旧はデータを上書きするので、現在の依頼では実行しない。
- Console適用はWranglerの `d1_migrations` を登録しない。手作業で登録履歴を捏造せず、今後CLIを使用する際に0001〜0003がpending扱いになる点を明記する。追加型SQLの再適用はローカルで既存設定を保持することを確認済み。
- 入力段階で改行が拒否されたため1行形式へ調整した。また、9つのUNIONによる件数確認はD1のcompound SELECT制限で拒否され、単一SELECTのjson_objectへ調整して成功した。いずれも未解決エラーではなく、スキーマ適用・データ保持には影響していない。

## 確認した引き継ぎとコード

- リポジトリ：`Ken5InvestmentLab/screening-bot`。
- 対象ブランチ：`research/weak-early-beta`。リモートHEADは `0dc12cb5d8a6acd226a830d3e83ebc84e368986e`。
- 作業チェックアウト：`codex/cloud-analytics-d6-member-preferences`、HEAD `e081eabe65243942079c35775e81f358e40e6f8d`。引き継ぎ `../../qa/push-prep/FINAL_HANDOFF.md` と一致。準備コードは対象ブランチへ未マージ。
- リモート `main` の確認時HEAD：`0bf62d8ad64d6db995e7ac2b892ed003fa1b2ff6`。mainの変更・切替は行っていない。
- 既存Discord OAuthと許可ロールによるフルHTML・auth/check・遅延bundle保護を維持。設定キーはセッションのDiscord IDをサーバーでハッシュ化して決定する。通知OFFでの設定保存はWhop追加認証を要求しない。
- 通知登録と配信は独立した支払確認を要求し、未確認・エラー時は送信しない。今回も有効化していない。

## Edgeで確認・作成したCloudflare資源

Browser UseでD1作成画面、D1一覧、対象WorkerのOverview・Deployments・Settingsを実際に読み取った。最初のD1一覧は「You have no D1 Databases.」で、同名DBが存在しないことを確認してから作成した。

| 項目 | 値・状態 |
|---|---|
| Worker | `tentei-kyokuchi-cloud` |
| D1名 | `tentei-cloud-settings` |
| D1 ID | `e0cdb3a7-b682-4db8-96ac-f2afcc9c23cb` |
| 所在地指定 | 標準の自動配置。location hint・jurisdictionは指定していない |
| 作成時の利用状況 | DB数0/10、無料枠のhard limit表示。アップグレードや支払操作なし |
| 実装のbinding名 | `CLOUD_DB` |
| 本番の接続 | Productionに `CLOUD_DB` → `tentei-cloud-settings` を追加済み。Previews BaseはNo connected bindings |
| 本番Secret名 | `DISCORD_CLIENT_ID`、`DISCORD_CLIENT_SECRET`、`SESSION_SECRET`。すべてValue encrypted、値は開いていない |
| Discordギルド | `1479418833352785944`。ローカル設定と一致 |
| Discord許可ロール | `1487089073385373828`。ローカル設定と一致 |
| その他の本番変数 | `DISCORD_API_BASE`、`ACCESS_PURCHASE_URL`、`REPORT_ASSET_PATH`、`SESSION_TTL_SECONDS`がローカル設定と一致 |
| 通知・支払用設定 | このWorkerの設定一覧にはWHOP/CLOUD_PUSH/CLOUD_VAPID名がない |
| cron / queue consumer | 設定なし |
| 旧版候補 | Version Historyに `eb6dffe5` 等あり。復旧操作は未実施 |

## 今回の変更

1. `wrangler.jsonc` に上記のD1を指す `CLOUD_DB` と `migrations_dir: migrations` を追加した。ローカル準備コードは未デプロイ。接続設定だけは今回承認されたDashboard操作で本番へ追加済み。Discord変数・認証実装・通知フラグは変更していない。
2. ワークスペースルート `../../AGENTS.md` を作成し、本書への導線と資源・権限・通知範囲の運用規則を記録した。リポジトリルートAGENTSにもCloud固有の運用規則を追加した。
3. QA記録を `../../qa/release-prep-20261004/` に保存した。以前の引き継ぎ・レビューZIP・証跡を上書きしていない。
4. 承認後、Edgeの本番D1接続フォームで `CLOUD_DB` → `tentei-cloud-settings` を保存。PREVIEWSのUse production valueはOFF、プレビューDB未選択を維持。保存後のPreviews BaseにもDB接続がないことを確認した。

## 実装が要求するテーブルと設定手順

スキーマの正は `migrations/0001_cloud_preferences.sql`、`0002_notification_scan_progress.sql`、`0003_push_device_metadata.sql`。既存の追加型SQLをそのまま使い、推測による列・認証データ・会員リンクは追加しない。

| Migration | アプリケーションテーブル |
|---|---|
| 0001 | `cloud_member_links`、`cloud_member_preferences`、`cloud_push_subscriptions`、`cloud_notification_events`、`cloud_notification_deliveries`、`cloud_whop_webhook_receipts` |
| 0002 | `cloud_notification_scan_progress` |
| 0003 | `cloud_push_subscription_metadata`、`cloud_push_dispatch_receipts` |

新規DBへのスキーマ適用と、このWorkerへのDB読書きアクセス追加は、空DB・復旧地点確認の後に実施済み。接続追加に伴う本番バージョンは `64bee25d`。準備コード公開は別の本番反映レビューで行う。今後もプレビュー/remote devで本番DBを使わず、ローカルD1または別途承認された独立DBを使う。

既存の許可済み認証が使えるCLIの場合は、このサブプロジェクトで実行する：

```powershell
# ローカル専用の検証。リモートDBには接続しない。
node node_modules/wrangler/bin/wrangler.js d1 migrations apply CLOUD_DB --local --persist-to ../../qa/release-prep-20261004/local-d1

# 以下は承認後だけ。既存の適切な認証がない場合、新規キーを無断で作らない。
node node_modules/wrangler/bin/wrangler.js d1 migrations list CLOUD_DB --remote
node node_modules/wrangler/bin/wrangler.js d1 migrations apply CLOUD_DB --remote
```

既存CLI認証は引き継ぎ時点で未接続。今回、CLIのログインや認証権限追加は行っていない。新規キーなしでEdgeのD1 Consoleから正規SQLを適用した。各SQLのSHA256と本番スキーマ照合結果を `d1-production-verification.json` に記録。Wranglerのmigration管理表を手作業で捏造していない。将来CLIから同じ追加型migrationが再適用されてもデータを保持することはローカルで確認済み。

コマンドとmigration管理の仕様は [Cloudflare公式D1 migrations](https://developers.cloudflare.com/d1/reference/migrations/) と [Wrangler commands](https://developers.cloudflare.com/d1/wrangler-commands/) を参照。

## 今回のテスト結果

- `npm run check`：**240 passed / 0 failed**。Discord認証・ロール・ログアウト・期限切れ・provider error・フル/無料bundle・ユーザー別設定・通知OFF・単一端末送信制限等のテスト、TypeScript、Wrangler dry-runが成功。dry-runで正しいWorker名と `env.CLOUD_DB (tentei-cloud-settings)` を確認。
- Wranglerの隔離ローカルD1に0001–0003を実適用：すべて成功。再実行は「No migrations to apply」。リモートDB操作なし。
- ローカルD1実ファイルの確認：9アプリケーションテーブルと3つのmigration管理記録が一致。SQL再適用による保存済み設定保持、重複endpoint拒否、重複dispatch予約拒否、不正dispatch状態拒否を確認。
- Edgeで既存公開ページを再読み込み：既存セッションから従来レポートを表示。最終更新表示は `2026-10-02 18:04:49 JST`。今回の準備版の動作検証ではない。
- 前回引き継ぎのPython109件・Edgeのstub29件は既存証跡として保持。今回の新規テスト件数には加算していない。
- 今回は実OS通知許可、実購読、実送信、他会員への送信をしていない。保存の本番・別端末round tripと通知の実到着は未検証。今回追加した本番照合スクリプトは成功、9テーブル・2インデックス一致、全9件数0。

## 残作業と必要な確認

1. D1スキーマ適用と `CLOUD_DB` 本番接続は完了。プレビューから本番DBを共有しない方針を維持する。復旧bookmarkの有効期間とConsole適用のmigration管理差異に注意する。
2. 準備ブランチ全体の差分レビュー、対象 `research/weak-early-beta` への反映判断、本番前のアクセス保護確認、復旧先の記録。本番公開は最新対象ブランチHEADだけを指す `cloud-deploy-*` タグのワークフローを使う。mainにマージしない。
3. 公開後、本人の既存Discordセッションで通知OFFのユーザー別保存・再読込・同じDiscord IDの別端末共有を確認する。他人の設定が読めないことも検証する。
4. 通知用Whop確認には、実APIの正確なversion/response/query/read scope、既存の検証済みDiscord↔Whopリンク、支払期間・返金・失効・ロール剥奪連携の確認が必要。現在のfixture adapterと公式ドキュメントの形式が異なるため、推測で置換せず、実レスポンスの秘密・個人情報を除いた構造を検証する。レポート表示や通知OFF設定の公開を、この未検証のWhop条件へ変更しない。
5. VAPID公開/秘密鍵、HTTPS subject、端末固有のpush provider origin許可リストが未設定。既存の適切な鍵があるか確認し、新規生成・本番Secret設置・追加読取権限が必要なら操作内容を示して別途承認を得る。
6. 本人の端末/OS/ブラウザ、既存許可状態、対象の1購読を確定し、明示的なopt-inの後に本人だけへラベル付きテストを行う。端末endpointや認証値をチャットへ貼らない。provider受理と本人のOS到着確認を別々に記録する。
7. 一般配信には現在未接続のbackground identity確認、canonical event連携、08JST/休日スケジューラ、schema/webhook/reconciliation、監視・再送運用の実装と承認が必要。現在の内部dispatch helperには公開送信APIやcronがなく、キー設定だけでは通知を送れない。

## 証跡

`../../qa/release-prep-20261004/` 内：既存のローカルQAに加えて、`d1-preapply-empty.txt`、`d1-preapply-bookmark.txt/jpg`、`d1-production-0001/0002/0003.txt`、`d1-production-schema.json`、`d1-production-counts.json`、`d1-production-verification.json`、`verify-production-schema.py`、`worker-production-settings-after.txt`、`worker-preview-bindings-after.txt`、`worker-cloud-db-connected.jpg`、`worker-deployment-after.txt`、`worker-deployment-history-after.txt`、`live-site-after-summary.txt`、`d1-production-nine-tables.jpg`、`live-site-after.jpg`。秘密値・ユーザー実購読値は記録していない。以前の証跡は上書きしていない。
