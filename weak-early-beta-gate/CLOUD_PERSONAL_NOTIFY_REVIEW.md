# 本人1端末通知候補のレビュー記録（2026-10-04）

この候補は実装・隔離検証の成果であり、通知完成・本番反映・Windows到着確認は未完了。画面だけの先行公開には使わない。

## 基準と承認

- 対象は `Ken5InvestmentLab/screening-bot` の `research/weak-early-beta` と Worker `tentei-kyokuchi-cloud`。main・他Workerは変更しない。
- 元候補は `ed77cfd2b77d97443abc94575426842156e85c7e`（tree `a5807bb4e89c34213c68a3df7e5a6be6bcc93ec1`）。最新の対象ブランチはGitHub接続で `0dc12cb5d8a6acd226a830d3e83ebc84e368986e` と確認した。
- 書き込み競合を避け、元の `task/screening-bot` を変更せず `task-2/screening-bot` に独立cloneを作り、`codex/cloud-personal-notify-completion` で作業した。既存Codexプロセスは停止していない。プロセス一覧だけでは他作業の停止状態を断定できない。
- 本人はコード・隔離テストを承認し、その後「Secret設置、鍵生成、本番公開、実送信もやってくれていい」と明示した。指定端末はユーザーPCの既存Edgeセッション。
- 本人がWhop購入時のDiscordロール付与と月額終了時の剥奪を説明し、「既存Whop管理ロールを基準にする」と選択した。従来の会員ロール代替禁止は、この明示選択の範囲で更新される。Whop照会失敗からの自動フォールバックではない。
- 既存Discord OAuth、許可guild/role、SESSION_SECRET、無料/有料公開範囲は維持。共有認証モジュールは `report-gate/src/index.ts` と同一SHA-256。

## 今回の実装

`CLOUD_PUSH_MEMBERSHIP_POLICY=whop_managed_discord_role` を明示設定した場合、通知ON保存・端末登録・送信には新鮮なDiscordロール取得を必要とする。新しいWhopログイン・決済API資格・Discord-to-WhopリンクDBは必要ない。通知OFFの設定保存はWhop非依存のまま。

`cloud-push-dispatch.ts` のバックグラウンド経路は固定した本人Discord ID、ハッシュ会員ID、端末IDのみを扱う。既存Bot資格で指定guildの本人をGETし、IDの一致・ロールを確認する。送信直前にも再取得し、剥奪・429・通信失敗は送信を止める。会員一覧取得やロール変更は行わない。この経路はHTTP/cron/queueに接続していない。

`cloud-push-runner.ts` は20件単位でcanonical候補を巡回する内部バッチ。本人・端末専用のカーソル名前空間を使用し、一般会員配信モードは持たない。送信予約を原子的に保存し、preparing/unknown/accepted等を自動再送しない。旧日の新検出候補も送らない。08 JSTのリマインド判定は既存 `evaluateNotification` を使う。

`POST /api/cloud/notifications/personal-test` を追加した。本人の既存OAuthセッション、fresh role、通知ON、固定した登録端末、運用者が指定した16〜64文字のテストIDがそろった時だけ、固定のテスト文を1回送る。ブラウザからrecipient/event/messageを受け取らない。canonicalの銘柄データは作らない。最初の端末テストにはBot SecretもWhop Secretも不要。

端末登録UIに「この端末へテスト通知」を追加した。サーバーで指定した端末と現在のブラウザ購読が一致した時だけ表示する。プロバイダー受理・不明・重複を区別し、Windows到着を確認する文言を表示する。読み込み時に登録・許可要求・送信をしない。

`build-notification-events.py` にPRIVATE SQL計画の生成を追加した。forward canonical観測だけを利用し、共有bank calendarで休日を除外する。SQLは実行せず、同一signal/kindは台帳revisionが変わっても同じsource keyとし、available_atを維持する。設定・購読・送信receiptを書き換えない。

直接Whop API用の `nested_v1` adapterも隔離試験済みだが、選択したロール方式では使用しない。実Whop schema/responseをライブ確認したとは扱わず、WHOP_RESPONSE_SCHEMA/WHOP_API_KEYの新設は不要。

## 画面変更

- ナビの「検出履歴」を「ダッシュボード」に変更。実際の検出履歴とファンダメンタル機能は維持。
- 試算件数・運用開始日等の画面上の動的注記を削除し、「実際の運用実績ではありません」はガイドに維持。
- ガイドの重複した検出履歴・ファンダ分析説明を削除し、ダッシュボード/アナリティクス/5モードへ実在するリンクを追加。
- 買い方は同じ株数を先、一致条件数に応じた株数を後に表示。保存済み株数と例示が連動する。保存識別子と計算は維持。
- ガイドだけの現在設定summaryを削除。他ページと設定画面は維持。
- full/freeの16 HTMLを再生成。972台帳行、追跡対象state/価格成果432ファイルのSHAは生成前後で不変。

## 検証結果と限界

- `npm run check`: Node 293件成功、TypeScript成功、本番・preview dry-run成功。リモート操作なし。
- `test_cloud_notification_adapter.py`: Python/実SQLite 13件成功。source/kind重複、revision更新、205件のページ巡回、別端末・dry-runカーソル分離、遅い更新の抑止を確認。
- レポート設定・通知候補の関連Python試験も成功。Pythonはローカル3.14.7。GHAの3.12は今回まだ実行していない。
- 実ローカルWorker/隔離D1 14項目成功。本人別保存・匿名/偽装/cross-origin拒否・Discord公開範囲・OFF保存を確認。本番DBを使用しない。
- 既存Edgeバイナリの専用headlessプロファイルで1440/390幅14項目成功、page error 0、実push操作0。これは指定された個人Edgeプロファイルの試験ではない。
- QAログ・画像・ローカルD1は `task-2/qa/notification-completion-20261004/` に分離し、Workerアセットに含めない。

## 残作業と必要な接続

1. Cloudflareを操作できる実行環境へ引き継ぐ。今回 `wrangler whoami` で認証なし、Cloudflare CLI環境資格もなし。GitHub接続は対象HEADの確認に成功したが、Cloudflare Secret設置やブラウザ操作能力はない。
2. 本番Workerの現設定・Secret名・稼働versionを再確認する。引き継ぎ時の本番は `64bee25d` 100%、CLOUD_DB接続と0001〜0003はConsole適用済み。d1_migrationsがない/pendingだけで再適用しない。今回本番へ読み書きしていない。
3. 初回到着テストの最小構成は既存OAuth資格＋CLOUD_VAPID_PRIVATE_KEY。既存VAPID有無を確認し、なければ承認済みの鍵を生成してSecret保存する。公開鍵、HTTPS subject、本人のserver-derivedハッシュ会員ID、personal_test mode、registration flagを設定する。資格・cookie・private key・購読endpointをチャット/ログへ出さない。
4. ユーザーPCの既存Edgeで通知許可と本人opt-inを確認し、購読providerの正確なoriginだけを許可する。ホスト/endpointを推測せず、wildcardを使用しない。登録後に本人端末のsubscription IDと一回用RUN_IDを固定する。他会員は登録・送信対象にしない。
5. 現在のwrangler.jsonc/verify-releaseは通知OFFを強制する。本人専用の承認済み設定と検証を整備してから最新対象HEADへレビュー反映し、既存 `cloud-deploy-*` 専用workflowで公開する。現状の候補をそのままdeployすると通知は有効にならない。画面だけの公開をしない。
6. 指定Edgeからテスト通知を1回実行し、provider acceptedとWindowsの実表示を別々に記録する。unknown/preparingは自動再送しない。再試験はreceiptを削除せず、本人に到着状態を確認して新しいRUN_IDを使用する。
7. 通常の新検出/08 JST定期通知は未完成。canonical SQLの安全なD1 import、本人用background runnerの呼び出し、休日付きscheduler、監視をまだ本番へ接続していない。既存daily GHAのscheduleはdefault branchでのみ動くため、researchのworkflowだけで朝実行できると仮定しない。mainを変更せずに実現する接続を用意する。バックグラウンド時だけ既存Bot資格をCLOUD_DISCORD_BOT_TOKENに安全に設置し、固定した本人IDを設定する。

既存Bot token自体の権限はCloudへコピーしても狭くならない。実装は本人1名のGETしか使わないが、資格の扱いは既存Bot資格と同じ機密扱いにする。新しいBot権限付与や一般配信を追加する必要はない。

本人の承認は上記対象について受領済みで、同じ操作を再承認待ちにしない。実端末の許可状態と到着状態は未確認。キー生成・Secret設置・本番公開・実通知は今回未実施。週間残量の取得ツールはなく、推測していない。
