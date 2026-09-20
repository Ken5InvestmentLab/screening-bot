# Codex → ChatGPT Weak+Early Beta Handoff (2026-09-20)

1. Repo: `Ken5InvestmentLab/screening-bot`.
2. Branch: `research/weak-early-beta`; base SHA: `fc2d11e2f783b06c077639ea6d46adaec9fe2817`.
3. Core implementation commit: `a6d4fce600c4249b1330d1700b5fc3efe5957b22`; continue from the latest `research/weak-early-beta` HEAD.
4. Identity: `WEAK_EARLY_FIVE_LANE_BETA_V1`; Cloud Monster is not included in this beta.
5. Five frozen selectors use the public names `Silence`, `Dive`, `Shadow`, `Fusion`, and `Balance`; internal rules, thresholds, rank direction, Tail-CDF tie-break, causal timing, and no-cooldown contract are unchanged.
6. Exact 2023-2026 canonical rows were imported into `weak_early_beta/state/detections.csv` (967 condition units). No 2022 estimated price rows are used.
7. Combined performance is shown both as condition-stacked allocation (100 shares per matched condition) and symbol-equal allocation (100 shares per signal-date/symbol).
8. 2023-2026 condition-stacked: n=967 units, mean +6.30%, win 50.88%, 100-share-unit P/L +JPY1,828,335, reference capital JPY1,566,500, capital gain +116.71%, simple annualized +31.39%.
9. 2023-2026 symbol-equal: n=253 trades, mean +5.63%, win 49.80%, P/L +JPY433,262, reference capital JPY363,400, capital gain +119.22%, simple annualized +32.07%.
10. The protected total HTML is `reports/weak_early_beta_latest.html`, with five mode pages at `reports/weak_early_beta_<mode>.html`. Each page has an asset-growth chart based on reference capital plus realized 100-share P/L. Detection history search supports normalized symbol codes and company names, displays the result count, and has a clear action. Public labels use `確定取引数` / `未確定取引数`, year details expand to monthly tables, and current-system comparison copy is absent. The separate gate authorizes and syncs all six protected pages plus their free shells.
11. Historical company names are pinned in `weak_early_beta/state/company_names_202608.csv` (104/104 symbols, no blanks) with provenance in `company_names_202608.receipt.json`; generated ledger/HTML contain no literal `nan` names.
12. Dedicated signal channel is `1550876104917520505`; dedicated fundamental channel is `1550876675884060702`.
13. Signal flow is after-close scoring → one symbol notification with all matched modes and allocation count → next XTKS open entry → fifth XTKS close.
14. Future-only fundamental claims use isolated state under `weak_early_beta/fundamental_worker/`; the runner pins `gpt-5.6-luna` with `xhigh` and validates with the existing Premium Worker before posting.
15. Historical fundamental analysis is intentionally not generated. Production Premium state, Sheets, current Discord channels, Stable, Sniper, Mega, TradingView, watchlists, `main`, and production files were not changed.
16. 2026 outcomes are displayed only. They were not used to choose or retune features, gates, selectors, thresholds, or the Cloud Monster lineage; the SEALED boundary remains intact.
17. Verification: Python unittest 13/13 PASS; real browser test confirmed initial 20/254 rows, next-page 40/254, code/name search, inclusive date filtering, clear, dark-mode persistence after reload, relative mode links, both total charts, and Japanese TradingView URLs. Beta gate TypeScript + Wrangler dry-run PASS.
18. Data is refreshed through official session 2026-09-18. Receipt `weak_early_beta/state/latest_run_receipt.json` pins corpus SHA `492e735b3bceb345e784d9315189a8a98a9edf90663d0a46eee04895a85acabf`; the fixed 2026 reporting pass added the 2026-09-14 `7709 クボテック` detection in all five modes, entry 2026-09-15 open JPY80, still pending its fifth-session close. It is queued once in `fundamental_queue.json`; 2026 was not used for retuning or rule choice.
19. Free pages now expose mature history but remove the pending row identity, company, entry price, chart URL, and fundamental URL from the HTML itself. They show `5営業日終値確定まで会員限定` and link to the existing payment page. Full pages remain restricted by the same Discord role through the separate gate.
20. Current blockers: the existing Discord bot returns Missing Access for both new channels, so no webhook was created and no signal/fundamental message was sent. Local deploy cannot run because `CLOUDFLARE_API_TOKEN` is unavailable; GitHub has Cloudflare secrets, but `Weak Early Beta Daily` is not dispatchable until its workflow exists on the default branch. Do not claim the refreshed UI is live until a credentialed beta-only deploy succeeds. Required beta webhook secrets are `WEAK_EARLY_BETA_SIGNAL_WEBHOOK_URL` and `WEAK_EARLY_BETA_FUNDAMENTAL_WEBHOOK_URL`.
21. Before public gate deploy, set `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, and `SESSION_SECRET` for the new Worker and register its `/auth/callback` redirect URI. Do not reuse or overwrite the existing Worker deployment.
22. Next shortest action: provide `CLOUDFLARE_API_TOKEN` locally for one beta-only deploy or make the beta workflow dispatchable without modifying production behavior; then obtain the two dedicated webhooks, post the queued 7709 signal, run the isolated Luna xhigh fundamental worker, and verify both dedicated channels.

## Live completion addendum — 2026-09-20

23. The stale blockers in items 20-22 are resolved: dedicated webhook access and Cloudflare credentials are configured locally without committing secrets.
24. The 7709 signal notification is an Embed showing code/name, 2026-09-14 close JPY76, volume 2,405,500, and five matching modes. The old internal marker/evaluation copy is removed.
25. The validated Luna xhigh 7709 analysis was posted to the dedicated fundamental channel and imported into the ledger/HTML. Discord message: `1551177205411876886`.
26. The protected beta Worker is live at `https://scoring-bot-weak-early-beta.ipo-ken5-5489.workers.dev/`; deployed version: `9eefbc28-0482-42f7-9384-dc2ce3cc6b42`.
27. The top page is now `天底極致 -Cloud- アナリティクス`; the brand returns to the top page. P/L, required capital, capital gain, and simple annual rate are moved forward and visually emphasized.
28. `必要資金（目安）` replaces the unclear reference-capital label and has a tooltip/guide explanation. Detection history and monthly tables use 20-row progressive disclosure.
29. Real browser verification passed: symbol/name search, inclusive date range, clear, 20→40 rows, dark-mode persistence after reload, guide navigation, 7709 company name, and disclaimer.
30. Codex automation `cloud-2` runs the isolated daily pipeline at 16:15 JST on weekdays. The deterministic runner enforces same-day OHLCV freshness, bounded retry, detection, Luna xhigh analysis, receipt import, HTML/deploy, Discord Embed last, then research-only commit/push.
31. Codex automation `cloud-5` runs at 07:30 JST on weekdays and sends idempotent Embed reminders for positions reaching their fifth XTKS session that day.
32. Both launchers use `gpt-5.6-luna` with minimal reasoning; the nested fundamental analysis remains `gpt-5.6-luna` with xhigh. Japanese bank holidays are skipped by deterministic code.
33. 2026-09-24 is the next bank business day. Reminder dry-run returns exactly one pending reminder for 7709.
34. Python tests: 15/15 PASS. Worker typecheck/dry-run/deploy PASS. Production and main remain untouched; 2026 remains SEALED for tuning and selection.

## ChatGPTへ貼るプロンプト

`Ken5InvestmentLab/screening-bot` の `research/weak-early-beta` 最新HEADを続行してください。引継ぎは `research/CODEX_TO_CHATGPT_WEAK_EARLY_BETA_HANDOFF_20260920.md` です。Cloudの5モードは `weak_early_beta/`、canonical ledgerは `weak_early_beta/state/detections.csv`、統合/月別成績は `weak_early_beta/state/metrics.csv` と `monthly_metrics.csv`、トップ/モード/ガイドHTMLは `reports/weak_early_beta_*.html`、ロール制限gateは `weak-early-beta-gate/` です。公開URLは `https://scoring-bot-weak-early-beta.ipo-ken5-5489.workers.dev/`。日次ランナーは `scripts/windows/weak-early-beta-daily-runner.mjs`、朝リマインダーは `scripts/windows/weak-early-beta-exit-reminder-runner.mjs`、Luna xhighファンダrunnerは `scripts/windows/weak-early-beta-fundamental-runner.mjs`。Codex予定タスクは16:15の `cloud-2` と07:30の `cloud-5` がACTIVEです。7709の検出Embed、Luna xhigh分析、HTML埋込み、Worker公開は完了済みです。次は2026-09-24の初回予定実行後に、runnerログ、Discord重複防止、当日OHLCV freshness、HTML更新、research-only commit/pushを確認してください。`main`、production、既存workflow、既存Discord、Spreadsheet、Stable、Sniper、Mega、TradingView、watchlistは変更禁止です。2026は表示/forward scoring専用のSEALEDを維持し、条件選択やretuneに使わないでください。Codex週間残量が10%以下なら作業せずユーザーの明示resumeを待ってください。`
