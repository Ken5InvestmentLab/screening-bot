# Weak+Early Beta Gate

現行 `report-gate` と同じDiscord OAuth・ロール確認実装をimportし、別Worker `tentei-kyokuchi-cloud`（`https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev/`）と別asset bundleでベータHTMLだけを配信します。公開前に `wrangler.jsonc` の `name` がこのWorker名と一致することを確認してください。
検証・deploy前に `report-gate/src/index.ts` をベータ配下へ機械コピーし、SHA256 receiptを作るため、認証ロジックは同一のまま別bundleになります。

```bash
npm ci
npm run check
npm run deploy
```

ローカルにCloudflare認証がない場合は、`research/weak-early-beta` の最新コミットへ `cloud-deploy-*` の軽量タグを付けてpushすると、Cloud専用のGitHub Actionsが同じ検査を実行してからデプロイします。タグのコミットが研究ブランチの最新HEADと一致しない場合はデプロイを拒否します。

初回deploy前に、このWorkerへ `DISCORD_CLIENT_ID`、`DISCORD_CLIENT_SECRET`、`SESSION_SECRET` をsecretとして設定し、Discord Developer PortalへベータWorkerの `/auth/callback` をRedirect URIとして追加します。ロールIDは現行gateと同じです。

Cloudの通常版HTMLは既存セッションと、独立検証で結び付いた有効なWhop有料資格の両方が必要です。未連携・失効・確認不能の場合は対応する `_free.html` を返します。無料版は検出から6営業日後の実始値が取得・検証済みの銘柄だけを含み、未解禁銘柄のコード・社名・価格・チャート・ファンダURLはHTMLやCSVへ渡しません。資格連携・会員設定の保存・無送信の通知判定については [CLOUD_MEMBERSHIP_SETUP.md](CLOUD_MEMBERSHIP_SETUP.md) を参照してください。本番の設定・公開はこのPRでは実施していません。
