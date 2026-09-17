# V16 backward-2022 endpoint audit — 2026-09-18

## Scope
Research-only forensic audit. No production/main/workflow/Discord/Spreadsheet/Stable/Sniper/Mega/TradingView/watchlist changes. 2026 remains SEALED.

## Source chain
- workflow run: `34605714116`
- artifact: `10266990667` (`tvfree-v16-backward-2022-34605714116`)
- artifact digest: `sha256:8254745a3508742de49339e6460a095a51c0a904442bb7f9cf3636da1aaa012e`
- workflow head SHA: `bcc2b9f1ce2a2b8ce6bc02e21be72c48899690d5`
- recovered picks: `v16_backward_2022_picks.csv`, 31 rows
- recovered picks SHA-256: `68ecf2f0344471c486577c80e67302ba1c17334ed6f2a2dfd0dc414cafab78d6`
- pinned daily corpus artifact: `10264205130`
- daily corpus SHA-256: `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`

## Canonical endpoint audit
For all 31 recovered V16 backward-2022 rows, the pinned daily corpus was used to reconstruct the XTKS session calendar and symbol/date O/C endpoints.

Results:
- `entry_date > signal_date`: 31 / 31 PASS
- entry date = next XTKS session: 31 / 31 PASS
- entry open matches artifact `next_open`: 31 / 31 PASS
- exit date = fifth XTKS session after signal: 31 / 31 PASS
- exit date matches artifact `target_end_date`: 31 / 31 PASS
- return from pinned `entry_open -> exit_close` matches artifact `target5_no`: 31 / 31 PASS
- entry endpoint true missing: 0
- exit endpoint true missing: 0

Recomputed headline from the 31 rows matches the artifact report: n=31, mean=+1.2873866913%, median=-6.7340067340%, win=35.4838709677%.

## Identity / contract mismatch vs current primary `volr20 LOW`
This artifact MUST NOT be promoted to the current Phase-2 primary `weak+early + volr20 LOW` 2022 ledger.

Reason:
- current frozen Phase-2 2022 document `research/WEAK_EARLY_PHASE2_2022_FRESH_VALIDATION_20260914.md` defines gate `med_ret5 <= 0` AND `ret10 <= 0.5735294117647058`, then reports primary `volr20 LOW` as n=23 / mean +1.95% / median -6.19% / win 26.09% / Top3-ex -7.31%.
- the V16 backward artifact report defines `market_gate: med_ret5 <= 0` and `rank_feature: volr20 low` but does not include the Phase-2 `ret10 <= 0.5735294117647058` gate; its selected ledger is n=31.
- therefore n=31 V16 backward rows and n=23 frozen Phase-2 primary rows are different candidate contracts/ledgers.

Status: `ENDPOINT_EXACT_FOR_ITS_OWN_V16_CONTRACT / EXCLUDED_AS_PRIMARY_PHASE2_VOLR20_2022_SOURCE`.

This resolves a false recovery path without overwriting the frozen Phase-2 primary values. The next correct recovery path is the Phase-2 2022 causal Tail reconstruction described in `WEAK_EARLY_PHASE2_2022_FRESH_VALIDATION_20260914.md` (89 extreme Tail candidates -> frozen weak+early gate -> 29 candidate rows across 23 signal dates), using the pinned daily corpus and the exact historical generator/code chain.
