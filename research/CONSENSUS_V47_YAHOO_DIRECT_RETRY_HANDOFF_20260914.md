# Consensus V47 Yahoo direct-daily retry handoff — 2026-09-14

## Scope
Research-only. Promotion-relevant Consensus work remains V47 clean PIT only. Strategy returns, model scores, H2, raw1H, and price-arm performance remain unopened.

## Prior blocker
Authoritative V47 daily v6 run `34788533946` completed workflow execution but failed the frozen restored/delisted daily acceptance: 251 required historical codes, 0 usable, all recorded failures HTTP 429. That was classified correctly as provider-rate-limit failure rather than historical-code unavailability.

## New outcome-blind provider canary
Run `34796452026` completed SUCCESS.

The canary used the exact v6 missing population only to choose a deterministic eight-symbol spread, plus current control symbol `7203`. It queried both Yahoo chart hosts with six-second spacing.

Results:
- `7203`: HTTP 200 with 420 daily timestamps on both query1 and query2.
- Eight restored/delisted sample codes (`1439, 2754, 3902, 5017, 6293, 7317, 8279, 9927`): all returned terminal HTTP 400/404 on both hosts.
- No sampled request returned HTTP 429.
- Strategy outcomes read: false.
- Model scores read: false.

Interpretation: Yahoo is currently reachable from the runner. The v6 all-429 state was transient provider limiting. A valid direct-provider attempt can now distinguish terminal historical-code unavailability from retryable provider failure. Query2 showed no advantage over query1 in the canary.

## Exact-251 direct retry
A dedicated outcome-blind retry is now staged and triggered:
- script: `research/no_tv_v47_restored_daily_direct_retry.py`
- workflow: `.github/workflows/consensus-v47-restored-daily-direct-retry.yml`
- trigger file: `research/RUN_V47_RESTORED_DAILY_DIRECT_RETRY`
- trigger commit: `0e6a027c20264625ba1ddf0dd0088b9b757a450e`
- frozen contract: `research/consensus_v47_restored_daily_direct_retry_spec.json`

It requests exactly the 251 v6 missing historical codes, uses query1 direct Yahoo only, spaces normal requests by 3.5 seconds, preserves 429/502/503/504 as retryable provider failures, fast-classifies 400/404/410/422 as terminal, and checks `7203` before and after the run.

## Next action
1. Inspect only the direct-retry receipt/artifact first.
2. Partition the 251 into direct-usable, terminal/unavailable, and unresolved-provider-failure groups.
3. Only terminal/unavailable codes may advance to official JPX/company identity-continuity verification under `research/consensus_v47_restored_data_repair_spec.json`.
4. Do not auto-adopt aliases.
5. Do not start raw1H until restored daily coverage is 100% and `daily_coverage_pass=true` in a rebuilt authoritative daily materialization.

Production/main/Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist-builder/updater remain untouched.
