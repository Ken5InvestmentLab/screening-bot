# Weak+Early Cloud 公開URL 302調査

調査日: 2026-09-24
調査担当: GPT-6 Sol xhigh
対象: `https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev/`
対象Worker: `tentei-kyokuchi-cloud`（ベータ専用）

## 結論

未ログイン状態でトップを開いた際の `302 Found` は、Discordロールゲートが未認証ユーザーをログインへ送る想定どおりの挙動です。`/` から `/auth/login`、さらにDiscord OAuth認可画面へ進み、観測した範囲ではWorkerへのリダイレクトループやコード不整合はありませんでした。したがって、302自体を直すコード変更は行っていません。

## 再現・観測

- `GET /` → `302`、`Location: /auth/login?return_to=%2F`
- `GET /auth/login?return_to=%2F` → `302`、Discord OAuth認可URLへ遷移
- OAuth URLの `redirect_uri` → `https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev/auth/callback`
- Discord OAuth認可URLを未ログインで開く → `200` の認可画面HTML
- `GET /healthz` → `200`
- 未認証の `GET /auth/check` → `401 login_required`
- state/codeなしの `GET /auth/callback` → `400 Invalid login state`（不正なcallbackの安全な拒否）
- Analytics HTMLも未認証では同じログイン誘導

## コード照合

`report-gate/src/index.ts` の共有OAuth実装では、`serveReport` が有効セッションのないアクセスに `loginRedirect` を返し、ログイン処理がDiscord OAuthへ302を返します。`callbackUrl()` は現在の公開ホストから `/auth/callback` を組み立て、認可URL生成とtoken交換の双方で使用するため、観測したcallbackと一致します。

## 未確認事項・ユーザー確認が必要な場合

実際のDiscord認証完了・ロール別HTMLの表示までは実行していません。またDiscord Developer Portal上のRedirect URI登録値は読み取れないため未確認です。ログイン後もトップへ戻れない、またはDiscordがredirect URIエラーを出す場合は、Developer PortalのOAuth2 Redirectsに次のURLが完全一致で登録されているか確認してください。

`https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev/auth/callback`

コード変更、Worker再デプロイ、Discord設定変更、本番系変更はありません。
