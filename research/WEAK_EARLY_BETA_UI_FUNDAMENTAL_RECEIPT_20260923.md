# Cloud ベータ 2026-09-23 作業receipt

- Branch: `research/weak-early-beta`。作業開始元: `32cc4a7f042f30515ea3fa63e575e81d1474debf`。
- 2026年の結果は表示・forward scoringのみ。閾値やモード条件の変更には使っていない。
- 検出履歴とモード導線を `reports/weak_early_beta_latest.html`、合算成績・資産推移を `reports/weak_early_beta_analytics.html` に分離。各ページの `_free.html` も生成。
- 集計期間は ledger の最小・最大 signal date から自動生成。単純年率は実際に観測した signal～exit の期間で換算。
- ファンダ分析ボタンはイベント委譲で開閉。2026-09-03 と 09-02 の4052についてローカルブラウザで展開を確認。開示リンクのHTML内クリック先も確認。
- 銘柄名検索、開始日フィルタ、20件追加表示、モード別カード遷移、端末内テーマ保存をローカルブラウザで確認。
- タイトルロゴはユーザー添付のライト用・ダーク用画像を編集し、黒背景を透過したPNGへ差し替え。両画像の左上/余白 pixel alpha=0 を確認し、ブラウザでも矩形の黒背景が消えたことを確認。
- ライトロゴ SHA256: `1B2904EA6EDDDB2C1C32261D5317E78DC6FF9B69BC33EE02AD5B554EE347952E`。
- ダークロゴ SHA256: `52C9A7C5260F915CD610D7D82CC22277D58CCF1EE0A3E3D65BA72EA23B987C02`。
- Luna xhigh の claim は `weak-early-beta:2026-09-03:4052` の1件。analysis cutoff は `2026-09-03T23:59:59+09:00`。
- Analysis source: `research/WEAK_EARLY_FUNDAMENTAL_20260903_4052.json`。SHA256: `0DC8C23411BC42FEB14419156302E63884CAC4199BE194788AC91BA90C198605`。
- Discord fundamental receipt: https://discord.com/channels/1479418833352785944/1550876675884060702/1552074149923528705 。専用チャンネルへ1件投稿済み。
- `weak_early_beta/fundamental_worker/state/premium_alert_state.json` は claims=0、failed=0、pendingLogEvents=0。`weak_early_beta/state/detections.csv` に同じDiscord URLとHTML本文を取り込み済み。
- 09-02時点の4052 raw reportは作業開始元 commit の `weak_early_beta/fundamental_worker/out/premium_reports.json` に保存されている。今回の単一claim用出力で上書きしてもGit履歴から復元可能。09-14の7709の旧投稿は上場廃止除外履歴として残し、再importしない。
- 09-03版は会社IR・TDnet相当の基準日以前資料だけで構成。09-04以降の開示は含めていない。09-03提出の大株主変更報告書は会社IRではないため、このPremium形式の本文には含めていない。対象資料の範囲を拡げる場合は別途訂正・追記として扱うこと。
- `py -3 -m unittest tests.test_weak_early_beta` 20件成功。`weak-early-beta-gate` の `npm run check`（TypeScript検査とWorker dry-run）成功。
- ローカル `.env` とプロセス環境に `CLOUDFLARE_API_TOKEN` は見つからず、このreceipt時点で公開Workerへの反映は未確認。研究branchへのcommit/push後、beta-onlyのデプロイ経路を確認すること。main、本番Worker、既存Discord/Spreadsheetには変更なし。
