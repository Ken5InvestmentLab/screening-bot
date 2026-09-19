# Weak+Early Beta Fundamental Worker Contract

未来の検出だけを、現行Premium Workerと同じ品質契約で分析するための受け渡し仕様です。

- Claim source: `weak_early_beta/state/fundamental_queue.json`
- Isolated worker state: `weak_early_beta/fundamental_worker/state/premium_alert_state.json`
- Isolated worker output: `weak_early_beta/fundamental_worker/out/`
- Destination channel: `1550876675884060702`
- Model: `gpt-5.6-luna`
- Reasoning effort: `xhigh`
- Report quality: 現行 `premium_worker/AUTOMATION_PROMPT.md`、`FUNDAMENTAL_EXAMPLES.md`、`premium-fundamental-snapshot` skillと同一
- Dedup identity: `signal_date|symbol`
- Historical rows: `not_requested_historical` のまま。一括分析しない
- Forward rows: `queued -> claimed -> complete`。曖昧なPOSTは再送せずDiscord receiptを照合
- Output receipt: `signal_date`, `symbol`, `status`, `discord_url`, optional `html`
- Import: `py -m weak_early_beta.cli import-fundamentals --receipts <file>`

`prepare-fundamentals` はSheetsを読まず、上記queueから現行Premium Worker互換のclaimを作る。
`export-fundamentals` は専用Discordの投稿receiptをledger用JSONへ変換する。
現行 `premium_worker/state/` とGoogle Sheetsは読み書きしない。

検出通知チャンネル `1550876104917520505` とファンダ分析チャンネルを混ぜないこと。
