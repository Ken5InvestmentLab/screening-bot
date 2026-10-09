# Weak+Early Beta Fundamental Worker Contract

未来の検出と、明示指示がある場合の過去検出を別系統で分析するための受け渡し仕様です。

- Claim source: `weak_early_beta/state/fundamental_queue.json`
- Isolated worker state: `weak_early_beta/fundamental_worker/state/premium_alert_state.json`
- Isolated worker output: `weak_early_beta/fundamental_worker/out/`
- Destination: HTML only; legacy Discord receipts from channel `1550876675884060702` remain readable
- Forward model: `gpt-6.1-sol` (Astra is not permitted)
- Historical generation receipts/checker: preserve their original `gpt-6-luna` contract
- Reasoning effort: `xhigh`
- Report quality: 現行 `premium_worker/AUTOMATION_PROMPT.md`、`FUNDAMENTAL_EXAMPLES.md`、`premium-fundamental-snapshot` skillと同一
- Dedup identity: `signal_date|symbol`
- Historical rows: 通常queueには入れない。明示指示がある場合のみ `historical_backfill_manifest.json` と `historical_backfill_receipts.json` で検出日×銘柄ごとに管理し、16:15 JST の予定検出時刻をas-of cutoffとして、開示公表日時をreceiptで検証する。過去分析はDiscordへ再投稿しない。
- Forward rows: `queued -> claimed -> complete`。`--save-only` で検証済み本文を保存し、HTMLへのimport成功までclaimを保持する。ファンダ分析のDiscord通知は送らない
- Output receipt: `signal_date`, `symbol`, `status`, `discord_url` (HTML-onlyでは空欄), optional `html`
- Import: `py -m weak_early_beta.cli import-fundamentals --receipts <file>`

`prepare-fundamentals` はSheetsを読まず、上記queueから現行Premium Worker互換のclaimを作る。Claimの `receivedAt` は検出日の16:15 JSTを検出日時として保持する。通常forwardの分析基準日時 `analysisCutoff` は、runnerが分析開始直前に別途記録し、その基準時点までの公表資料を使う。検証済み本文のimport-only retryでは元の分析基準日時と旧モデル記録を維持する。明示的historical分析だけは元の予定検出cutoffを保持する。
`export-fundamentals` はHTML保存済みsnapshotと既存Discord投稿receiptをledger用JSONへ変換する。
現行 `premium_worker/state/` とGoogle Sheetsは読み書きしない。

新規forward分析の長期資本リスク・好悪材料と内部証拠の契約は `FUNDAMENTAL_CAPITAL_RISK_CONTRACT.md` と `FUNDAMENTAL_LONG_TERM_MATERIAL_CONTRACT.md` を参照する。モデルpreflightと実分析は同じ専用CLIを使い、任意の `codexExecutable` 指定時はネイティブCLI、未指定時は従来の `nodePath` + `cliJs` とする。指定runtimeが失敗した場合に別runtime/モデルへ自動変更しない。

過去分の作業では、`py -m weak_early_beta.cli historical-fundamentals-manifest` で進捗を再構成し、`py -m weak_early_beta.cli historical-fundamentals-batch --limit 4` で未完了分だけを小分けに出力する。`py -m weak_early_beta.cli import-historical-fundamentals --input <validated-report-json>` は、as-of cutoffと全フィールド・一次資料の確認記録を検証し、専用receipt/manifest、検出ledger、Cloud HTMLを更新する。過去receiptにはDiscord URLを作らず、live Premiumのclaim/stateや歴史的なDiscord投稿runnerを使わない。

検出通知チャンネル `1550876104917520505` とファンダ分析チャンネルを混ぜないこと。
