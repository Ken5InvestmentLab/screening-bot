# Consensus V47 handoff addendum — 2026-09-14

## Current promotion path
Only V47 clean PIT remains promotion-relevant. V43/V44 returns remain non-promotion evidence. V47 compares exactly NOCAP vs CAP1000_PIT under canonical next-XTKS-open -> D+5 with 2026 closed for selection.

## Frozen volume semantics correction
Before any V47 strategy outcome access, the Consensus worker detected that commits `f16884b050bee965d43ca191d6205d01387b0f88` / `2e5136bab6c07b6db3657d17c41acfee0c58b74e` had drifted from the frozen split-volume contract by rebasing prior raw 1H volume for `session_vol_ratio20` and by changing daily-volume feature history to signal-date rebasing.

This was corrected in commit `464043b538faf4cd785fd5fff893af258a1ead02`:
- daily PIT volume = adjusted daily volume / cumulative future split factor for each historical date;
- prior-volume gate and daily volume-ratio technicals use PIT daily volume;
- raw Yahoo 1H volume remains unchanged for both session-volume gate and `session_vol_ratio20`;
- no split-factor multiplication/division is applied to raw 1H volume.

Clean-feature contract run `34790368989` completed **SUCCESS** on the corrected commit.

No V47 strategy returns or model scores were opened by this correction.

## Current authoritative daily gate
Authoritative daily v6 remains run `34788533946`, which materializes PIT nominal price + PIT daily volume + listing identity epochs with 100% restored/delisted daily coverage required. At this handoff update it is still `in_progress` in the outcome-blind materializer step.

Do not trigger raw 1H while v6 is in progress. Once it completes:
- if `daily_coverage_pass=true`, create/advance `research/RUN_V47_RAW1H_FETCH` with `daily_run_id=34788533946` exactly once and run the frozen 12-shard raw fetch;
- if false, keep raw/features/performance closed and repair only missing historical codes under `research/consensus_v47_restored_data_repair_spec.json`, requiring official JPX/company identity continuity for aliases.

## Downstream frozen order
`daily acceptance -> raw1H fetch -> raw coverage acceptance -> clean features -> 2025H1 DEV NOCAP vs CAP1000_PIT -> winner-only H2`.

Raw acceptance remains: pair >=99.5%, monthly >=99.0%, zero completely missing required symbols, >=95% per-symbol coverage for symbols requiring >=20 days, restored required-pair >=99.0%. No threshold lowering or bar interpolation.

Production/main/Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist-builder/updater remain untouched.
