# Weak+Early Beta Gate

現行 `report-gate` と同じDiscord OAuth・ロール確認実装をimportし、別Worker `tentei-kyokuchi-cloud`（`https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev/`）と別asset bundleでベータHTMLだけを配信します。公開前に `wrangler.jsonc` の `name` がこのWorker名と一致することを確認してください。
検証・deploy前に `report-gate/src/index.ts` をベータ配下へ機械コピーし、SHA256 receiptを作るため、認証ロジックは同一のまま別bundleになります。

```bash
npm ci
npm run check
npm run dev:preview
```

ローカルにCloudflare認証がない場合は、`research/weak-early-beta` の最新コミットへ `cloud-deploy-*` の軽量タグを付けてpushすると、Cloud専用のGitHub Actionsが同じ検査を実行してからデプロイします。タグのコミットが研究ブランチの最新HEADと一致しない場合はデプロイを拒否します。

初回deploy前に、このWorkerへ `DISCORD_CLIENT_ID`、`DISCORD_CLIENT_SECRET`、`SESSION_SECRET` をsecretとして設定し、Discord Developer PortalへベータWorkerの `/auth/callback` をRedirect URIとして追加します。ロールIDは現行gateと同じです。

Cloudの通常版HTML・auth/check・full bundleは既存Discord OAuthと設定済み許可ロールで保護します。追加のWhop認証は表示条件にしません。ロールなしは対応する `_free.html`、未ログインは既存のログイン導線です。無料版は検出から6営業日後の実始値が取得・検証済みの銘柄だけを含み、未解禁銘柄のコード・社名・価格・チャート・ファンダURLはHTMLやCSVへ渡しません。Discord ID別のサーバー設定保存は通知OFFならWhop未設定でも可能です。通知登録・送信だけは別途Whop等の検証を要求し、今回の公開候補ではOFFです。現在の契約は [CLOUD_DISCORD_PUSH_READINESS.md](CLOUD_DISCORD_PUSH_READINESS.md)、D1の本番適用済み証跡は [CLOUD_D1_RELEASE_PREP.md](CLOUD_D1_RELEASE_PREP.md) を参照してください。

`env.preview` はD1を持たず、productionのbindingを継承しません。設定保存APIの503はこの環境では意図した状態です。production設定の `wrangler dev --remote` は使わないでください。`remote: false` は通常のローカル開発用で、明示的な `--remote` の安全な代替にはなりません。通知OFF公開の設定チェックは `npm run verify-release`、productionとpreviewの非公開ビルドは `npm run check` です。適用済み0001〜0003をmigration履歴がないという理由だけで本番へ再適用しません。
