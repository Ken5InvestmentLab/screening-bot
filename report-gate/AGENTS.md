# Discord認証ゲート

- 認証の正は `src/index.ts`。Cloud側の `weak-early-beta-gate/src/shared-report-gate.ts` は `npm run sync-shared` による生成物なので直接編集しない。
- HTML要求ではトークン更新もセッションCookie書込みも行わない。更新が必要なら銘柄を含まない待機ページを返し、外部 `/auth/guard.js` がブラウザのWeb Lock下で `/auth/check` を実行してから再読込する。
- 更新済みトークンは、その後の権限確認が403や一時障害503になっても暗号化HttpOnly Cookieへ保存する。遅い権限確認だけの応答で更新前のトークンを上書きしない。
- 最初の401や `invalid_grant` でCookieを消さない。ブラウザの最新Cookieで再確認してから再OAuthへ進む。`invalid_client`、汎用400/401/403、429、通信障害は認証失効と区別する。ログアウトの明示操作はCookieを削除する。
- 永続的なトークン保存先は暗号化Cookieのみ。同時要求の共有キャッシュはハッシュキー・短期・件数上限を維持し、OAuth応答本文やトークンをログへ出さない。ロール制限と定期確認を外さない。
- `npm test` は `tests/report_gate_auth.test.cjs` の実Worker・ブラウザガード回帰テスト。各ゲートの `npm run check` は、このテスト・型検査・公開しないdry-runビルドを含む。
