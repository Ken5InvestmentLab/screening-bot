# 本人通知・canonical供給・朝スケジューラの追加レビュー

> この文書はd176652時点の記録。以下の「承認待ち」「null stub」「workflow未接続」は解消済み。今回の直接承認・接続実装・335件検証・残件は `CLOUD_CANONICAL_CONNECTION_REVIEW.md` を正とする。本番反映と本人OS到着は未実施。

`CLOUD_PERSONAL_NOTIFY_REVIEW.md` の候補に、通知供給と朝処理の隔離実装を追加した。本番反映・実通知・OS到着は未実施。画面だけの先行公開には使わない。

## 実装と有効化状態

- `build-notification-events.py` の任意future-reminderモードと `build-canonical-input.py` が、現時点のcanonical forward観測から当日新検出と将来D5/D6のリマインドを準備する。将来の確認日を観測cutoffとして使わず、未来に取得された価格を取り込まない。歴史的再構築、終了済み候補、重複モードを除外する。
- compilerの既定出力はrepo外の `qa/private-notification-input/`。ASSETSへの出力は拒否する。実台帳payloadを追跡対象のコードへ自動コピーするhookは追加していない。
- `cloud-canonical-feed.ts` が入力全体のversion/revision/cutoff/重複/価格/営業日/確定日を検証し、既存 `cloud_notification_events` だけに20件ずつ保存する。同一signal/kindのkeyと初回available_atを維持し、設定・購読・送信receipt・スキーマは変更しない。
- `cloud-push-scheduler.ts` と `index.ts.scheduled` が本人固定・managed-role方式・明示scheduler flag・既存Bot資格を必要とする朝処理を実装した。UTC `0 23 * * *` は翌日08:00 JST。実到着が08時台を過ぎた場合、前日遅延、休日、年末年始、カレンダー範囲外では送信しない。根拠は [Cloudflare cron仕様](https://developers.cloudflare.com/workers/configuration/cron-triggers/) と既存 `evaluateNotification`。
- 共有bank calendarと同じ2025〜2030年のカレンダーをコードに固定した。範囲外は保留。全対象日で元Pythonの営業日判定と一致する試験を実施。
- runnerは通知kind/JST日/本人/端末のカーソルを分離し、対象日の候補のみ巡回する。schedulerは最大50ページで処理を制限し、件数と状態だけをログへ返す。provider acceptedはOS到着とは扱わない。unknown/preparing等の自動再送はしない。
- 新検出の起動時刻は未指定。`CLOUD_PUSH_NEW_DETECTION_CRON` に運用者が明示した別cron以外は受け付けず、既存17時GHAから勝手に時刻を選ばない。
- **現在はwranglerのcron未設定、mode OFF、scheduler未有効。追跡する `CANONICAL_MANIFEST` はnull。** 個別データ送信の回答待ちのため、本番の供給経路とデプロイhookは接続していない。仮にscheduler flagだけをONにしてもnull入力で保留し、送信しない。

## 自動レビューの拒否と保留

公開workflowにcompilerを接続する変更は、自動承認レビューが拒否した。理由は「非公開台帳由来のcanonical入力をWorkerデプロイへ組み込む永続経路を追加し、Cloudflareへの機微データ送信を可能にしますが、その具体的なpayloadと宛先を明示したユーザー承認は確認できません」。該当変更は未適用。別のshellやhookで迂回していない。

本人への確認を提示済みで未回答。対象payloadは銘柄ID・検出日・検証済み価格・D5/D6日・観測時刻・証跡ハッシュ、宛先は既存 `tentei-kyokuchi-cloud` の非公開Workerコードと、そのWorker内部からの既存 `tentei-cloud-settings`。会員情報・Cookie・秘密鍵・購読endpointを含めず、本人固定1端末に限定する。現段階の確認はコード接続と隔離試験だけ。一般配信、新認証資格、新アクセス権の拡大は含めない。

## 最終検証

- `npm run check`: Node 329件成功、TypeScript、production/preview dry-run成功。リモート操作なし。
- scheduler 36試験を上記に含む。実SQLiteでcanonical import→08JST巡回→指定1名のfresh role→暗号化された合成providerへ一回送信→重複抑止まで確認。公開RFC鍵と合成identity/subscriptionのみ使用し、鍵生成・実providerを使わない。
- Python 3.12.13、numpy2.5.3/pandas2.3.3と既存scorer workflowの依存で、全β/Cloud関連240試験が成功。旧UI期待値2件を承認済み文言・重複削除に合わせて更新した。
- GHAと同じレポート再生成スクリプトもPython3.12で隔離QA出力へ成功。972行の台帳SHA不変、通知0、デプロイなし。**実GHA環境での実行ではない**。
- UI本体は前候補から変更なし。全指示を反映したfull/free 16 HTML、1440/390幅の隔離Edge 14検査成功を維持。実本人Edgeは未操作。
- 元checkoutのed77cfd/clean、state/価格成果物の不変、main・本番・公開workflowの未変更を確認。

## 公開認証経路の読取

GitHub接続で対象HEAD `0dc12cb5d8a6acd226a830d3e83ebc84e368986e` の公開workflowを読取成功。file SHA `5791ca04425606d3a1aa67131fbc3959ca6d30ca`。既存 `secrets.CLOUDFLARE_ACCOUNT_ID` / `secrets.CLOUDFLARE_API_TOKEN` の参照、非空チェック、最新対象HEADとtag SHAの一致チェックを確認。秘密値・本番Cookieは読んでいない。Push Secretの設置を行うworkflowではない。実際の資格有効性・今回のGHA成功は確認していない。workflow runの読取toolはINVALID_ARGUMENTで結果を取得できなかった。

## ローカルCodexへの最小手動工程

1. この候補と残件をレビューする。未回答canonicalデータ範囲と未指定の新検出起動時刻を解決する。base OFF verifierをすり抜けず、本人限定の有効化設定・検証を整える。
2. Cloudflare操作可能な環境で現Worker/Secret名/既存VAPID有無を確認。承認済み範囲で必要な鍵・VAPID Secretだけを安全に設置する。既存Discord OAuth/SESSION_SECRETを維持。初回手動テストはBot資格もWhop資格も不要。
3. **ユーザーPCの既存Edgeを使う**。正規computer-use/browser toolから既存ログインを利用し、通知許可・通知ON・登録を確認する。本番Cookieの取り出し・コピー・別プロセスへの再利用をしない。購読originを正確に許可し、本人のserver-derived会員ID/指定端末ID/RUN_IDを固定する。
4. 全レビュー後、対象HEADのみへ通知込みで反映し、既存cloud-deploy workflowで公開する。0001〜0003はpendingだけで再適用しない。cronは承認済み本人設定だけ。キー/資格/endpointをログやチャットへ出さない。
5. 指定Edgeの「この端末へテスト通知」を一回操作。provider受理とWindows実表示を別記録にする。unknown/preparingは再送しない。バックグラウンド時だけ、既存Bot資格と固定本人IDを安全に用意し、08JSTの実行/receiptを監視する。他会員へ送らない。

本人のSecret/鍵/公開/実送信承認は受領済み（parentが確認したitem `01a106c2-7dd1-75ed-839b-b11443fb8a2e`）。同じ一般承認を再度求める必要はない。今回の個別確認は自動レビューが要求したcanonical payload接続範囲のみ。
