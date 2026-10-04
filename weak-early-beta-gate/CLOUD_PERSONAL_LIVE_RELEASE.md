# 本人1端末の手動通知公開

この構成は既存Whop管理Discordロールを毎回取得する `personal_test` の手動送信専用。main・既存OAuth/許可guild/role/無料公開範囲・既存D1スキーマを変更しない。スケジューラーとpreviewのpushはOFF、previewのD1は空配列のまま。

## 運用値

本番Dashboardに本人Discord IDの `SHA256("cloud-member:" + ID)` から得る `CLOUD_PUSH_TEST_MEMBER_ID`、登録後の本人端末 `CLOUD_PUSH_TEST_SUBSCRIPTION_ID`、一回用の `CLOUD_PUSH_TEST_RUN_ID`、本人端末で観測した完全一致HTTPS originだけの `CLOUD_PUSH_ALLOWED_ORIGINS` を設定する。これらをGitへ入れない。公開鍵・HTTPS subjectはwranglerのvars、`CLOUD_VAPID_PRIVATE_KEY` は本番Secret。既存OAuth/session Secretは維持する。新Whop/Bot資格や権限変更は手動テストに不要。

Wranglerの `keep_vars: true` によりDashboardの固定値を再deployで維持する。Secretsはコード/アセット/ログへ保存しない。previewへ本番Secretをコピーしない。

## 初回端末登録

固定本人のfresh roleと公開鍵がある場合だけ、明示ボタンから通知許可・ブラウザ内購読準備を行える。originが未承認ならoriginだけを画面へ表示し、endpoint/key materialを送信・D1保存しない。ブラウザ内準備は同じ明示ボタン操作で再利用する。運用者が完全一致originを本番に設定した後、登録を再実行して本人のD1行とmetadataを保存する。登録は通知設定を自動ONにしない。

本人が通知ONを保存し、登録IDを本番の固定端末値に設定した後、本人Edgeの「この端末へテスト通知」を1回実行する。送信直前にもfresh role・通知ON・本人/端末一致を確認する。unknown/preparing/acceptedの予約は削除・自動再送しない。provider acceptedはOS実到着と区別して記録する。

手動テストHTTP内のDiscord照会は、予約後・送信前のfresh照会1回に限定する。入口の署名済み未期限切れセッション確認は本人行の選択にだけ使い、送信を許可しない。ロールキャッシュや429猶予では送らず、最終照会失敗もheld receiptとして保存する。通常のレポート認証は既存処理のまま。

## 公開と復旧

`npm run check`、最新research HEADとの祖先・差分確認、運用値と既存3認証Secretの存在確認を完了してから、fast-forwardで `research/weak-early-beta` を更新し、そのHEADに `cloud-deploy-*` タグを作成する。専用workflowは同じ台帳からHTMLとprivate canonical moduleを生成し、台帳/カレンダー検証後にdeployする。SQL 0001–0003は適用済みなので再実行しない。

DashboardのDeployments/Version Historyで `64bee25d` に100% rollbackできる。WorkerのrollbackはD1を巻き戻さない。設定/購読/receiptを削除せず、通知を止める場合は `CLOUD_PUSH_MODE=disabled` とregistration/schedulerをOFFにする。

通常の新検出起動頻度・時刻は別途指定が必要。08 JST schedulerの有効化と既存Bot資格設置も、手動テストの成立とは別の運用作業として扱う。
