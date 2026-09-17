# Phase2 2022 SUMMARY_ONLY decision receipt

Date: 2026-09-18 JST
Scope: research-only. No production/main/workflow/Discord/Spreadsheet/Stable/Sniper/Mega/TradingView/watchlist changes. No 2023-25 recomputation. 2026 outcome remains CLOSED.

## Decision status

Supervisor-directed fallback is now recorded: unresolved 2022 primary-candidate evidence is `SOURCE=SUMMARY_ONLY`; it MUST NOT be silently promoted to exact-row evidence. Summary-only 2022 data MUST NOT enter Meta discovery, Meta fitting, regime-label construction, row-level aggregation, endpoint audit, 100-share P/L, or any statistic that requires individual trades.

Primary pool:
1. `body_pct LOW`
2. `volr20 LOW`
3. `mean-rank(volr20,body_pct)`
4. `DUAL_TOP1_AGREEMENT`
5. `DUAL+G3`

Common contract remains: signal T -> next XTKS open -> fifth XTKS close; cost 0%; win = gross > 0. Existing frozen semantics are authoritative, including known same-day `med_ret5` vs previous-day semantic differences; do not repair/retune them during historical reconstruction.

## Candidate evidence matrix

| candidate | 2022 evidence class | source / SHA provenance currently pinned | summary metrics usable as frozen headline | rows-required metrics | Meta label |
|---|---|---|---|---|---|
| body_pct LOW | `SUMMARY_ONLY` | existing frozen 2022 fresh-validation summary/receipt; exact row generator chain unresolved in current P0 recovery | only values explicitly present in that frozen summary: n/mean/median/win/+10/-10/+20/-20/max-up/max-down/Top1-ex/Top3-ex where recorded | exact trade dates/symbols, entry/exit prices, entry_date>signal_date audit, duplicate audit, 100-share P/L, row-derived labels and any metric absent from frozen summary = `PENDING` | `BLOCKED_WITHOUT_ROWS` |
| volr20 LOW | `ROWS_RECOVERED_EXCEPTION` | backward-2022 trigger `bcc2b9f1ce2a2b8ce6bc02e21be72c48899690d5`; run `34605714116`; output artifact `10266990667`; preserved input run `34599959356` / `tvfree-frozen-dataset-run80-preserved`. Separate V16 provenance receipt commit `865978bcf5b12d01d2fa31db3ddbb04b4e5926d2`; freeze ref `4b37f18d7601f8fd6ff42155879faff5b7d1e9e3` | recovered backward-2022 ledger summary: n=31, mean=+1.2874%, median=-6.7340%, win=35.48%, +10=12.90%, +20=12.90%, -10=32.26%, -20=9.68%, max-up=+118.13%, max-down=-35.11%, Top1-ex mean=-2.6074%, Top3-ex mean=-7.2694%. Frozen headline record rounds total to n=31 / mean=+1.29% | canonical entry-date calendar proof remains `PENDING` unless separately evidenced; do not infer Meta eligibility from summary alone | `BLOCKED_WITHOUT_ROWS` for Meta until canonical row/endpoint eligibility is explicitly approved; recovered rows may be audited separately |
| mean-rank(volr20,body_pct) | `SUMMARY_ONLY` | existing frozen 2022 fresh-validation summary/receipt; exact row generator chain unresolved in current P0 recovery | only values explicitly present in frozen summary | exact rows and all row-dependent metrics = `PENDING` | `BLOCKED_WITHOUT_ROWS` |
| DUAL_TOP1_AGREEMENT | `SUMMARY_ONLY` | existing frozen 2022 fresh-validation summary/receipt; exact row generator chain unresolved in current P0 recovery | only values explicitly present in frozen summary | exact rows and all row-dependent metrics = `PENDING` | `BLOCKED_WITHOUT_ROWS` |
| DUAL+G3 | `SUMMARY_ONLY` | existing frozen 2022 fresh-validation summary/receipt; exact row generator chain unresolved in current P0 recovery | only values explicitly present in frozen summary | exact rows and all row-dependent metrics = `PENDING` | `BLOCKED_WITHOUT_ROWS` |

### Important provenance distinction for volr20

Commit `865978bcf5b12d01d2fa31db3ddbb04b4e5926d2` pins `.github/workflows/tvfree-v16-volr20-test.yml` blob `548e8ac2d954c4841f46b7e5d39fd2b1d145d4a8`, preserved dataset run `34599959356`, and causal Tail cache run `34600083474`. Its exact command is:

`python tvfree_screener/v16_pre2025_volr20_rank.py --cache tvfree_screener/out/tse_daily.csv --tail-cache tail_cache/v7_causal_tail_cache_2023_2025.csv`

That workflow consumes a 2023-2025 Tail cache and therefore is NOT proof of 2022 fresh-validation rows. The separate backward-2022 run/artifact chain above must remain distinct. Do not merge these provenance chains merely because both are named volr20/V16.

## What can and cannot be aggregated with 2023-25 exact rows

**Allowed for reporting only:** a two-layer display where 2022 frozen summary metrics are shown as `SUMMARY_ONLY` beside independently exact 2023-25 row-derived results. The layers must remain visibly separated. A descriptive comparison of each period is allowed.

**Not allowed:** concatenating synthetic/pseudo 2022 trades with 2023-25 rows; recomputing a 2022-25 row-weighted mean/median/win/tail rate from unavailable 2022 rows; constructing Meta labels from 2022 summary values; treating a headline n/mean pair as if it identifies trade composition; or using summary-only 2022 to tune thresholds/regime mappings.

A mathematically weighted aggregate of a metric can be reported only if (a) the exact same metric definition is frozen for every included period, (b) the required sufficient statistics are explicitly present, and (c) it is labeled `SUMMARY-AGGREGATE`, not `EXACT-ROWS`. Median, Top-k exclusion, extrema attribution, row-level overlap and Meta labels do not satisfy this condition without rows.

## Supervisor options for Meta design

**Option A — strict exact-row Meta (recommended default):** design/freeze Meta only on years/periods with canonical exact rows. Exclude all 2022 `SUMMARY_ONLY` candidates from discovery/fitting/labeling. Preserve 2022 only as an external descriptive robustness panel.

**Option B — wait for uniform rows:** defer Meta freeze until canonical 2022 rows exist for every primary candidate. This maximizes period symmetry but risks indefinite blockage and is the reason this receipt exists.

**Option C — dual-layer research reporting:** continue primary comparison using 2022 `SUMMARY_ONLY` + 2023-25 `EXACT_ROWS`, while Meta itself uses exact-row periods only. This advances non-Meta research without contaminating Meta discovery. Supervisor approval is required before adopting this as project policy.

No option authorizes opening 2026. The existing prereg/freeze gate remains controlling.

## Blocker

For `body_pct LOW`, `mean-rank`, `DUAL_TOP1_AGREEMENT`, and `DUAL+G3`, canonical 2022 trade-row ledgers and their exact generator/input SHA chains remain unresolved. Their frozen summary values remain usable only to the extent already explicitly recorded in the historical summary/receipt. Missing per-candidate numeric fields are intentionally not reconstructed or guessed in this receipt.

This receipt converts the blocker from an open-ended search task into an explicit evidence boundary. It does not adopt a Meta policy; it presents the choices for Supervisor decision.