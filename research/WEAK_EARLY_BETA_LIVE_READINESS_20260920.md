# Weak+Early Beta Live Readiness Receipt — 2026-09-20

1. Branch: `research/weak-early-beta`; production and `main` were not modified.
2. Identity: `WEAK_EARLY_FIVE_LANE_BETA_V1`; selectors remain frozen.
3. Input latest official session: `2026-09-18`.
4. Daily corpus SHA256: `492e735b3bceb345e784d9315189a8a98a9edf90663d0a46eee04895a85acabf`.
5. Fixed reporting range scored: `2026-09-11` through `2026-09-18`; no 2026 outcome was used for tuning.
6. New queued identity: `2026-09-14|7709`, company `クボテック`, all five modes.
7. Entry: `2026-09-15` open JPY80; fifth-session close is not yet present, so the row is pending.
8. Full HTML shows the pending identity; free HTML omits its symbol, company, entry price, chart URL, and fundamental URL.
9. Free HTML displays `5営業日終値確定まで会員限定` and the existing purchase route.
10. Role contract: the separate gate uses the same allowed Discord role as the current report gate.
11. Browser verification: initial 20 rows, +20 pagination, code/name search, inclusive date range, clear, theme persistence, and relative mode navigation all passed.
12. TradingView chart URLs use the Japanese domain.
13. Python verification: 15 tests passed; JavaScript syntax checks passed.
14. Gate verification: TypeScript and Wrangler dry-run passed with all protected/free HTML pages, guide pages, and beta scripts synchronized.
15. Live deploy completed to `https://scoring-bot-weak-early-beta.ipo-ken5-5489.workers.dev/` (Worker version `9eefbc28-0482-42f7-9384-dc2ce3cc6b42`).
16. The 7709 signal Embed was updated in place and the validated Luna xhigh fundamental analysis was posted to the dedicated channel at `https://discord.com/channels/1479418833352785944/1550876675884060702/1551177205411876886`.
17. Queue and receipt: `weak_early_beta/state/fundamental_queue.json` and `weak_early_beta/state/latest_run_receipt.json`.
18. UI completion: title/navigation, highlighted P/L metrics, 20-row pagination, date-range search, persistent dark mode, guide/disclaimer page, footer, and 7709 company name were verified in a real browser.
19. Automation: `cloud-2` runs the isolated daily pipeline at 16:15 JST on weekdays; `cloud-5` sends fifth-session reminders at 07:30 JST on weekdays. Both use Luna/minimal as launchers and code-side Japanese bank-holiday gates.
20. The next Japanese bank business day is 2026-09-24. Dry-run identifies one 7709 fifth-session reminder for that date.
21. Production/main/Stable/Sniper/Mega/TradingView/watchlist/Spreadsheet and existing production workflows remain unchanged; 2026 remains SEALED for selection and retuning.
