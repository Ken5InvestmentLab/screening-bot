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
13. Python verification: 13 tests passed; JavaScript syntax checks passed.
14. Gate verification: TypeScript and Wrangler dry-run passed with all 12 HTML pages and both beta scripts synchronized.
15. Live deploy attempted but stopped before upload because the local environment lacks `CLOUDFLARE_API_TOKEN`.
16. Discord signal and Luna xhigh fundamental notification remain unposted because the two dedicated beta webhook secrets are absent.
17. Queue and receipt: `weak_early_beta/state/fundamental_queue.json` and `weak_early_beta/state/latest_run_receipt.json`.
18. Safe next action: credentialed beta-only Worker deploy, then configure the two dedicated webhooks and process the single queued claim.
