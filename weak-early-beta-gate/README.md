# Weak+Early Beta Gate

現行 `report-gate` と同じDiscord OAuth・ロール確認実装をimportし、別Worker `scoring-bot-weak-early-beta` と別asset bundleでベータHTMLだけを配信します。
検証・deploy前に `report-gate/src/index.ts` をベータ配下へ機械コピーし、SHA256 receiptを作るため、認証ロジックは同一のまま別bundleになります。

```bash
npm ci
npm run check
npm run deploy
```

初回deploy前に、このWorkerへ `DISCORD_CLIENT_ID`、`DISCORD_CLIENT_SECRET`、`SESSION_SECRET` をsecretとして設定し、Discord Developer PortalへベータWorkerの `/auth/callback` をRedirect URIとして追加します。ロールIDは現行gateと同じです。
