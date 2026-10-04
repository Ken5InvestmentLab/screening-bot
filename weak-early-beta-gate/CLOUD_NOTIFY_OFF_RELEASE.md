# 通知OFFのCloud統合候補と公開・復旧手順

## 統合レビュー

公開対象は `research/weak-early-beta`、Workerは `tentei-kyokuchi-cloud`。候補はローカル `codex/cloud-notify-off-integration`。レビュー時にGitHubから取得した対象HEADは `0dc12cb5d8a6acd226a830d3e83ebc84e368986e`、準備HEADは `e081eabe65243942079c35775e81f358e40e6f8d`。前者は後者の祖先であり、対象側だけの未統合commitは0件。準備側の13commitを含む候補を作り、元のブランチやmainは動かしていない。

対象側のチャートボタン・買付保持・会社名/ファンダ表示・進捗変更を含んだ履歴を保持。`weak_early_beta/progress.py` とWindowsの日次runnerは対象と同一。準備側の分析・設定UI・D5/D6・実株数・無料開示修正は候補の仕様として残し、古い生成HTMLを一括上書きして取り込む方式は使わない。候補のgeneratorで全16ページを再生成し、全tracked stateのSHA256が不変であることを確認した。検出972行のSHA256は `7574c18d72948e8faa3b1e0e8d718690242750f5459e68a3f98d7e18b9a55909`。

候補で追加した公開条件：

- Productionの `CLOUD_DB` は既存D1 `e0cdb3a7-b682-4db8-96ac-f2afcc9c23cb` を保持。
- push登録は `false`、送信modeは `disabled`。scheduler・queue consumer・公開送信APIなし。
- `preview_urls: false`。明示的な `env.preview` はD1なし。`npm run dev:preview` はローカルで動かす。Production設定で `wrangler dev --remote` を使わない。`remote: false` は通常のローカル開発指定で、明示的な `--remote` を安全にする指定ではない。
- 公開前とdeployの `verify-release` はDB・通知OFF・Discord guild/role・Worker先行asset制御・preview分離を検証する。
- Console適用済み0001〜0003は履歴不足だけで再適用しない。公開workflowにmigration実行は含まれない。

Wranglerは環境のD1 bindingを継承しない。preview dry-runの「CLOUD_DB未設定」warningは意図した分離を示し、そのbinding一覧にD1がないことを確認した。[Cloudflare設定仕様](https://developers.cloudflare.com/workers/wrangler/configuration/#d1-databases)

## 検証と公開範囲

- `npm run check`：243 passed / 0 failed、TypeScriptとProduction/preview両方のWrangler dry-run成功。ProductionにCLOUD_DBあり、previewにはなし。共有認証sourceの機械コピーとSHA検証を維持。
- Python：レポート・無料開示・価格根拠・設定・notification adapter等179件、corporate actions/trade basis53件、計232件成功。ローカルPython3.14.7、numpy2.5.3/pandas2.3.3。workflowのPython3.12によるCI実行は本番タグ未作成なので未実施。
- 実ローカルWorkerと隔離D1：14項目成功。実装の0001〜0003は合成DB IDへ `--local` で適用した。本番DB・本物のCookie・本物のproviderは使っていない。
- 既存Discordセッション＋許可ロールでフルHTML/auth-check/full bundle。ロールなしは無料HTML・full bundle403。匿名、期限切れ、ログアウト、provider error、ロール剥奪、跨origin、フル/無料cache分離は回帰テストで確認。OAuth scopesや本番Secret値は変更しない。
- 無料生成物は検証済み6営業日始値を持つ解禁済み銘柄だけ。未解禁行を追加しても無料HTML・集計・価格境界・CSVが変わらない回帰テスト成功。full bundleはWorkerのロール判定後に取得可能。private receipts/raw ledgerはsync対象外。
- Whop未設定でも通知OFFの設定PUT/GETが成功。A/Bの合成Discordセッションが実D1へ異なる条件を保存し、再取得後も分離。query/bodyの任意member IDによる他人の設定取得・上書きを認めない。Whop不明時の通知ONは403。
- Edgeで再生成後のPC表示、390pxのカード表示、設定ダイアログ、ライトの確認とキャンセルによるダーク復帰、既存ファンダpopupを確認。390px時のdocument幅375px。通知2項目はOFFかつ操作不可。実通知許可・購読・配信はしない。静的UI確認のAPI連携未設定表示と、実Worker/D1の保存検証は分けて記録。
- 本番をEdgeで読取のみ再確認：active `64bee25d`100%、ProductionにCLOUD_DB、Previews BaseはNo connected bindings、既存Discord guild/roleと3つのSecret名を保持。値は開いていない。

証跡はワークスペースの `qa/integration-review-20261004/`。最終commit・refsと短い報告は同フォルダーの `INTEGRATION_REVIEW.md` / `final-refs.json` を参照。過去のQAは保持。

## 承認後の公開手順（今回未実行）

1. `git fetch origin` で対象HEADを再確認する。レビュー時HEADから更新されていたら新差分をレビュー・統合して再検証する。候補はmainへ入れない。
2. 承認された候補を `research/weak-early-beta` へfast-forwardで反映する。現時点では候補のpush、対象ブランチ更新、PRのmergeも未実行。
3. `git ls-remote origin refs/heads/research/weak-early-beta` と `git rev-parse HEAD` の完全SHAが一致することを確認する。対象への反映後も最新HEAD条件を確認する。
4. 明示的な公開承認後だけ、確定した完全SHAを指定して未使用の軽量 `cloud-deploy-*` タグを作成・pushする（例の `<...>` は実値へ置換）。

```powershell
git tag cloud-deploy-<unique-release-name> <approved-latest-research-head>
git push origin refs/tags/cloud-deploy-<unique-release-name>
```

`.github/workflows/weak-early-beta-report-deploy.yml` はタグと対象最新HEADの一致を検証し、同じsource ledgerから生成、`npm ci` / `npm run check`、Cloud専用Worker deploy、healthzを実行する。既存GitHub Actions secretsを使う。main/他Worker、検出・Discord通知を実行しない。本番migrationの再実行を追加しない。

5. workflow成功と新versionの100%を確認する。healthzだけで認証成功としない。本人の既存Discordセッションで表示・通知OFFの保存/再読込を確認し、別端末共有、ロールなし無料表示、権限剥奪時の範囲も確認する。Previews Baseの未接続と通知OFFを再確認する。問題時は次の復旧手順へ進む。

## 64bee25dへの復旧手順（今回未実行）

Cloudflare Dashboard → Workers & Pages → `tentei-kyokuchi-cloud` → Deployments → Version Historyで、D1 binding追加済みの `64bee25d` を選び、右側の三点メニューのRollbackを実行する。対象versionを確認して100%に戻し、Deployment History・CLOUD_DB接続・既存サイト表示・Discord設定・preview未接続を再確認する。CLIを使う場合はDashboardから取得した同versionの完全IDを確認して、既存認証で `wrangler rollback <full-version-id> --name tentei-kyokuchi-cloud` を使う。短縮IDから完全IDを推測しない。CLI認証追加は別途確認する。

WorkerのrollbackはD1の内容を巻き戻さない。保存されたユーザー設定と9テーブルを保持し、DB restore・SQL再適用は実行しない。通知関連varsが存在する場合は引き続きOFFを確認する。資源を削除せずに維持する。[Cloudflare公式rollback手順](https://developers.cloudflare.com/workers/versions-and-deployments/rollbacks/)

## 残る問題・公開状態

今回のコード・schema・分離テストに未解決の失敗はない。numpyの既存DeprecationWarningはテスト失敗ではない。Wrangler previewのDB未設定warningは意図的な構成。

本番コードは未公開。実セッションによる新保存API/別端末共有と実有料/無料cohortの公開後確認は未実施。既存ロールの支払期限・返金に伴う付与/剥奪運用をコードだけで証明することはできず、既存の表示契約として維持する。通知は実Whop schema/identity link/VAPID/provider設定と本人端末テストが残り、今回の通知OFF公開へ混ぜない。新規キー・権限変更が必要なら具体的な操作を別途確認する。
