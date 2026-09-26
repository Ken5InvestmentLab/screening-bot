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

ロール保持者には通常版HTML、非保持者には対応する `_free.html` を返します。無料版は5営業日目終値が未確定の銘柄について、証券コード・社名・エントリー価格・チャート・ファンダURLをHTMLへ埋め込まず、購入ページへの導線だけを表示します。5営業日目終値が確定した過去行は表示できます。
