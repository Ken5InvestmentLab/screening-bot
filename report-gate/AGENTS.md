# Discord認証ゲート

- 認証の正は `src/index.ts`。Cloud側の `weak-early-beta-gate/src/shared-report-gate.ts` は `npm run sync-shared` による生成物なので直接編集しない。
- HTML要求ではトークン更新もセッションCookie書込みも行わない。更新が必要なら銘柄を含まない待機ページを返し、外部 `/auth/guard.js` がブラウザのWeb Lock下で `/auth/check` を実行してから再読込する。
- 更新済みトークンは、その後の権限確認が403や一時障害503になっても暗号化HttpOnly Cookieへ保存する。遅い権限確認だけの応答で更新前のトークンを上書きしない。
- 最初の401や `invalid_grant` でCookieを消さない。ブラウザの最新Cookieで再確認してから再OAuthへ進む。`invalid_client`、汎用400/401/403、429、通信障害は認証失効と区別する。ログアウトの明示操作はCookieを削除する。
- 永続的なトークン保存先は暗号化Cookieのみ。同時要求の共有キャッシュはハッシュキー・短期・件数上限を維持し、OAuth応答本文やトークンをログへ出さない。ロール制限と定期確認を外さない。
- Cloudだけは無料HTMLにも `data-auth-free` と認証ガードを付ける。成功した再確認でのみ有料表示へ再読込し、401・403・503では無料表示を保持する。新規の有料HTMLは直前に新規照会済みなので初回pageshowの重複照会を省き、復元・再表示・定期確認は残す。Cloudのみ承認済みのREPORT_ROLE_LOOKUPフックでCloudRoleAuthorityへ照会を集約する。正常確認のpaid/freeは確認開始から固定90秒だけ共有し、アクセスで延長しない。新規HTML/dataの期限切れ・照会失敗はunavailableとして有料提供を拒否し、ロールなしの確認と区別する。開いている画面はスコアリングレポートと同じく503・通信例外で保持し、確認済みの403で無料表示へ切り替える。90秒期限で既存画面を強制非表示にしない。
- 正常なトークン更新はCloudもデータなしの `data-auth-recovery` 待機画面にし、資格取得失敗と表示しない。再試行は有効なRetry-Afterを優先し、指定なし・通信例外では2秒から最大60秒のbackoffを使う。非表示タブでは定期・再試行を止め、Web Lock取得後と401再確認前にも可視性・待機期限を再検査する。表示復帰・onlineイベントもprovider待機期限を破らない。
- 無料表示を保持する原則の例外として、`data-auth-unavailable` の画面は `/auth/check` が403かつ `reason: "role_required"` を返した場合だけ一度再読込し、資格確認失敗の表示から通常の無料表示へ戻す。通常の無料画面、継続503、別の403理由、不正JSONでは再読込しない。
- Discord HTTP APIはOAuth交換・更新・ロール照会とも公式形式の `DiscordBot (https://github.com/Ken5InvestmentLab/screening-bot, 1.0)` User-Agentを送る。429の待機秒数は有効なRetry-Afterヘッダーを優先し、なければ数値JSON `retry_after` のみ読む。応答本文やトークンはログに出さない。
- Workers/workerdの認証付きfetchで転送を防ぐ場合は `redirect: "manual"` を使い、3xxを成功として採用しない。`redirect: "error"` はworkerdが通信前にTypeErrorを返すため使わず、HTTPオプションの変更はNodeのfetchモックだけでなく隔離workerdでも検証する。
- Cloudの `REPORT_LOGIN_REQUIRED=true` は初回HTMLアクセスを購入案内なしの既存Discord OAuthへ進める。認証済みの無料会員は無料HTMLへ戻す。無料表示からの401は最新Cookieで3回確認後だけ再認証へ進み、ロール不足403や一時障害503で購入案内・再認証ループにしない。
- 新規照会の429はトークン・guildのダイジェスト単位で待機期限だけを保持し、期限中に再照会しない。成功結果のキャッシュは作らず、期限後の有料判定・剥奪判定は必ず再照会する。Cloud `/auth/check` は待機秒数をRetry-Afterへ渡し、ブラウザも可視化・定期イベントで早期再試行しない。診断はHTTP理由・秒数・許可リストに限定したscope・JSON/other区分のみとし、応答本文は出さない。
- `npm test` は `tests/report_gate_auth.test.cjs` の実Worker・ブラウザガード回帰テスト。各ゲートの `npm run check` は、このテスト・型検査・公開しないdry-runビルドを含む。
