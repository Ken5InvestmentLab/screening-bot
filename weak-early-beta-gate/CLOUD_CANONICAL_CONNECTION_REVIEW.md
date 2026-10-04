# 本人通知候補：canonical接続の最終レビュー

既存の通知候補へ、承認された非公開canonical入力の生成と公開workflowへの接続を追加した。コードと隔離検証は完了。本番公開、Secret設置、キー生成、実送信、本人OS到着は未実施。新画面だけの先行公開には使わない。

## 今回の具体的承認

本人がこの会話で「このデータ範囲・既存Worker/D1への接続コードと隔離テストを承認」と回答した。以前の自動承認レビューによる保留は、この直接承認後の再試行で解消し、patchが適用された。下記の限定範囲で実装・検証した。

- 入力：銘柄ID、検出日、検証済み価格、D5/D6日、観測時刻、証跡ハッシュ。
- 宛先：既存 `tentei-kyokuchi-cloud` の非公開Workerコードから、既存binding `CLOUD_DB` の `tentei-cloud-settings` 通知イベント表。
- 会員情報、Cookie、秘密値、購読endpointはこの入力に含まない。ASSETS/publicへコピーしない。
- 本人固定1端末だけを対象にする。新しいログイン、権限、一般配信API、他会員列挙は追加しない。

## 実装と結果

`build-canonical-input.py` を両既存Cloud公開workflowに接続した。公開対象を再生成する時点で、現在の観測cutoffを使い、検出と将来D5/D6リマインドを非公開TSモジュールへ生成する。今回のローカル生成は1イベント、送信0件。未来の価格や過去再構成データは追加しない。

`verify-canonical-input.mjs` をcheck/deployへ接続した。現在の台帳・共有銀行営業日カレンダーのSHA、version、cutoff形式を確認する。台帳やカレンダー変更後の古い入力、旧null stubは公開前に停止する。Workerのimporterはさらに全イベントの価格・cutoff・営業日・重複を検証してから既存D1へ書く。初回available_atと送信receiptを維持する。

`npm run check` 成功：Node **335件**、TypeScript、production/preview dry-run。新規5件は古い台帳・カレンダー・null入力等の拒否を検証した。scheduler **37件**には今回生成した実manifestの隔離SQLite importと、合成本人identity＋公開RFC鍵を使った08JST→fresh role→暗号化fixture push→重複抑止が含まれる。実providerは呼んでいない。

Python **3.12.13** canonical関連5件を今回再実行して成功。前段の関連240件と、GHAと同じHTML再生成スクリプトの3.12実行は成功済み。**実GHA runは未検証**。前段UIのfull/free16 HTML、隔離Edge1440/390幅14件、Worker/D1 smoke14件も成功済み。今回UIを変更していない。

## 公開前に残る作業

現在のwranglerは通知OFF、scheduler無効、cron未設定を維持している。現在のOFF verifierを回避してこの候補だけを公開してはならない。本人固定の登録・送信設定と、その設定を検証する公開gateを揃えてから、最新 `research/weak-early-beta` HEADだけを専用公開workflowへ渡す必要がある。

本人が選んだ会員判定は `whop_managed_discord_role`。Whopの購入・月額終了に連動する既存Discordロールを送信直前に取得し、剥奪・取得失敗なら停止する。直接Whop決済API資格や新Whopログインは不要。OAuthを使う本人の手動テストにはBot資格も不要。バックグラウンド処理には既存Bot資格と固定本人Discord IDが必要。

リマインドは `0 23 * * *` UTC、08JST、共有銀行営業日だけ。09JST以降や前日遅延は送らない。新検出の起動頻度・時刻は本人の指定がなく未設定。レポート生成時刻から勝手に推定しない。

正規の操作ツールが使える元のローカルCodexで、**ユーザーPCの既存Edgeセッションを使用する**。既存ログインを維持し、通知許可、通知ON、本人端末登録、正確なprovider origin許可、固定本人/端末/RUN_IDを安全に設定する。Cookie・endpointを抽出して別プロセスへ再利用しない。既存VAPID・Secret名を確認し、本人が承認済みの必要なキー/Secretだけを設定する。0001–0003をpending表示だけで再適用しない。Previewへ本番D1を接続しない。

登録後、本人Edgeから「この端末へテスト通知」を1回操作する。provider受理とWindowsの実表示を別々に記録する。unknown/preparingは自動再送しない。他会員には送らない。

## この実行環境の制約

利用可能なツールを再確認したが、本人Edgeを操作するbrowser/node_repl/skyツール、Cloudflare接続ツール、週間使用量取得ツールがない。ローカルWranglerは未認証。既存GitHub公開workflowのaccount/token参照は前段で読めたが、実Secret有効性や実GHAの成功は未確認。広いキー/Secret/公開/実送信の本人承認は既にあるため、同じ承認を再質問する必要はない。ここでの残件は操作能力・実端末状態と具体的設定の検証である。

元checkoutは `ed77cfd2b77d97443abc94575426842156e85c7e` のcleanを維持。main、他Worker、本番D1、既存Discord認証は変更していない。PC電源操作は行っていない。週間残量を推測していない。
