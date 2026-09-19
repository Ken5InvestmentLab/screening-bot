# Codex → ChatGPT Weak+Early Beta Handoff (2026-09-20)

1. Repo: `Ken5InvestmentLab/screening-bot`.
2. Branch: `research/weak-early-beta`; base SHA: `fc2d11e2f783b06c077639ea6d46adaec9fe2817`.
3. Core implementation commit: `a6d4fce600c4249b1330d1700b5fc3efe5957b22`.
4. Identity: `WEAK_EARLY_FIVE_LANE_BETA_V1`; Cloud Monster is not included in this beta.
5. Five frozen selectors are implemented with renamed Japanese labels only; internal rules, thresholds, rank direction, Tail-CDF tie-break, causal timing, and no-cooldown contract are unchanged.
6. Exact 2023-2026 canonical rows were imported into `weak_early_beta/state/detections.csv` (967 condition units). No 2022 estimated price rows are used.
7. Combined performance is shown both as condition-stacked allocation (100 shares per matched condition) and symbol-equal allocation (100 shares per signal-date/symbol).
8. 2023-2026 condition-stacked: n=967 units, mean +6.30%, win 50.88%, 100-share-unit P/L +JPY1,828,335, reference capital JPY1,566,500, capital gain +116.71%, simple annualized +31.39%.
9. 2023-2026 symbol-equal: n=253 trades, mean +5.63%, win 49.80%, P/L +JPY433,262, reference capital JPY363,400, capital gain +119.22%, simple annualized +32.07%.
10. The protected beta HTML is `reports/weak_early_beta_latest.html`; free denial shell is separate. The gate reuses the current Discord OAuth/role source byte-for-byte at build time and deploys as separate Worker `scoring-bot-weak-early-beta`.
11. Dedicated signal channel is `1550876104917520505`; dedicated fundamental channel is `1550876675884060702`.
12. Signal flow is after-close scoring → one symbol notification with all matched conditions and stacked unit count → next XTKS open entry → fifth XTKS close.
13. Future-only fundamental claims use isolated state under `weak_early_beta/fundamental_worker/`; the runner pins `gpt-5.6-luna` with `xhigh` and validates with the existing Premium Worker before posting.
14. Historical fundamental analysis is intentionally not generated. Production Premium state, Sheets, current Discord channels, Stable, Sniper, Mega, TradingView, watchlists, `main`, and production files were not changed.
15. 2026 outcomes are displayed only. They were not used to choose or retune features, gates, selectors, thresholds, or the Cloud Monster lineage; the SEALED boundary remains intact.
16. Verification: Python unittest 8/8 PASS; report generation 967 rows / 35 metric rows; Node syntax PASS; beta gate TypeScript + Wrangler dry-run PASS; npm audit 0 vulnerabilities.
17. Current blockers: the existing Discord bot returns Missing Access for both new channels, so no webhook was created and no message was sent. User must create webhooks or grant a dedicated bot Manage Webhooks/View Channel access. Required secrets are `WEAK_EARLY_BETA_SIGNAL_WEBHOOK_URL` and `WEAK_EARLY_BETA_FUNDAMENTAL_WEBHOOK_URL`.
18. Before public gate deploy, set `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, and `SESSION_SECRET` for the new Worker and register its `/auth/callback` redirect URI. Do not reuse or overwrite the existing Worker deployment.
19. Usage automation `weak-early-beta-5` checks every 30 minutes: resume only after the five-hour window recovers; stop all autonomous work at weekly remaining <=10% until the user explicitly resumes.
20. Next shortest action: push this branch, obtain the two dedicated webhooks, configure beta Worker OAuth secrets/redirect, manually dispatch `Weak Early Beta Daily` on this research branch with notification disabled first, inspect artifacts, then enable beta-only notification.

## ChatGPTへ貼るプロンプ

`Ken5InvestmentLab/screening-bot` の `research/weak-early-beta` を続行してください。起点は core SHA `a6d4fce600c4249b1330d1700b5fc3efe5957b22`、引継ぎは `research/CODEX_TO_CHATGPT_WEAK_EARLY_BETA_HANDOFF_20260920.md` です。Weak+Earlyの5条件は `weak_early_beta/`、exact canonical ledgerは `weak_early_beta/state/detections.csv`、統合成績は `weak_early_beta/state/metrics.csv`、ベータHTMLは `reports/weak_early_beta_latest.html`、ロール制限gateは `weak-early-beta-gate/`、Luna xhighの未来分ファンダrunnerは `scripts/windows/weak-early-beta-fundamental-runner.mjs` です。全5条件合計は「1条件=100株の条件別積上げ」と「同日同銘柄=100株の銘柄均等」の両方を比較できます。未解決はDiscord専用webhook 2本と新Cloudflare WorkerのOAuth secrets/redirectです。既存Botは両チャンネルにMissing Accessでした。次はブランチを同期し、通知OFFでmanual workflow検証、artifact確認、webhook設定後にベータ専用通知を有効化してください。`main`、production、既存workflow、既存Discord、Spreadsheet、Stable、Sniper、Mega、TradingView、watchlistは変更禁止です。2026は表示専用のSEALEDを維持し、条件選択やretuneに使わないでください。Codex週間残量が10%以下なら作業せずユーザーの明示resumeを待ってください。`
