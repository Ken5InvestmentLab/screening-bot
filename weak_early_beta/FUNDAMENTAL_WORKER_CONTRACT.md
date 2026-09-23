# Weak+Early Beta Fundamental Worker Contract

未来の検出と、明示指示がある場合の過去検出を別系統で分析するための受け渡し仕様です。

- Claim source: `weak_early_beta/state/fundamental_queue.json`
- Isolated worker state: `weak_early_beta/fundamental_worker/state/premium_alert_state.json`
- Isolated worker output: `weak_early_beta/fundamental_worker/out/`
- Destination channel: `1550876675884060702`
- Model: `gpt-5.6-luna`
- Reasoning effort: `xhigh`
- Report quality: 現行 `premium_worker/AUTOMATION_PROMPT.md`、`FUNDAMENTAL_EXAMPLES.md`、`premium-fundamental-snapshot` skillと同一
- Dedup identity: `signal_date|symbol`
- Historical rows: 通常queueには入れない。明示指示がある場合のみ `historical_backfill_manifest.json` と `historical_backfill_receipts.json` で検出日×銘柄ごとに管理し、16:15 JST の予定検出時刻をas-of cutoffとして、開示公表日時をreceiptで検証する。過去分析はDiscordへ再投稿しない。
- Forward rows: `queued -> claimed -> complete`。曖昧なPOSTは再送せずDiscord receiptを照合
- Output receipt: `signal_date`, `symbol`, `status`, `discord_url`, optional `html`
- Import: `py -m weak_early_beta.cli import-fundamentals --receipts <file>`

`prepare-fundamentals` はSheetsを読まず、上記queueから現行Premium Worker互換のclaimを作る。Claimの `receivedAt` とファンダ分析のas-ofは検出日の16:15 JSTに固定する。
`export-fundamentals` は専用Discordの投稿receiptをledger用JSONへ変換する。
現行 `premium_worker/state/` とGoogle Sheetsは読み書きしない。

過去分の作業では、`py -m weak_early_beta.cli historical-fundamentals-manifest` で進捗を再構成し、`py -m weak_early_beta.cli historical-fundamentals-batch --limit 4` で未完了分だけを小分けに出力する。`py -m weak_early_beta.cli import-historical-fundamentals --input <validated-report-json>` は、as-of cutoffと全フィールド・一次資料の確認記録を検証し、専用receipt/manifest、検出ledger、Cloud HTMLを更新する。過去receiptにはDiscord URLを作らず、live Premiumのclaim/stateや歴史的なDiscord投稿runnerを使わない。

検出通知チャンネル `1550876104917520505` とファンダ分析チャンネルを混ぜないこと。
