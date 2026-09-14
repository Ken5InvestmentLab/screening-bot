# Consensus V47 clean PIT handoff

Updated: 2026-09-14 12:36 JST
Branch: `research/consensus-atr-regime-gate`
Scope: research-only. Production/main/Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist-builder/updater untouched.

## Promotion boundary
Only V47 clean PIT evidence is promotion-relevant. V43/V44 returns remain non-promotion evidence because of point-in-time split/universe leakage.

## Frozen contracts
- PIT universe replay: run `34771221050` accepted.
- V46 split audit: run `34775030470` accepted.
- Price-policy arms: exactly `NOCAP` and `CAP1000_PIT`.
- Canonical target: next official XTKS open -> fifth official XTKS close.
- V11 3-head architecture / threshold 0.95 frozen for first clean comparison.
- 2026 outcomes forbidden for selection.
- PIT daily volume = frozen adjusted daily volume / cumulative future split factor.
- Prior volume gate and daily volume-ratio technicals use PIT daily volume.
- Yahoo raw 1H volume stays unchanged for session-volume gate and session-volume-ratio technicals; never divide raw 1H volume by split factor.
- Listing identity epochs isolate prelisting history from feature/target/cooldown state.
- H2 feature artifact must remain blind to return targets.

## Restored/delisted daily repair
Authoritative v6 daily materializer run `34788533946` identified 251 restored/delisted symbols needing external recovery.

96ut restoration run `34798987098` was merged/audited by run `34799650589` (SUCCESS):
- expected symbols: 251
- recovered symbols: 251
- missing symbols: 0
- extra symbols: 0
- merged rows: 109,230
- median required-date coverage: 100%
- minimum required-date coverage: 39.0625%
- 11 symbols were below 90% required-date coverage before the final rebuild: 1841, 2754, 3847, 5395, 6060, 6416, 8038, 8072, 8208, 8886, 9852
- merge receipt `accepted_for_daily_rebuild=true` meant symbol-set recovery only; the downstream final daily coverage gate remained authoritative.
- no strategy returns or model scores were opened.

## Authoritative V47 daily PIT materialization
`Consensus V47 Daily PIT Materialization External` run `34799835035` completed SUCCESS and is now the authoritative V47 daily source.

Outcome-blind acceptance receipt passed all daily gates:
- `daily_coverage_pass=true`
- `required_coverage_pass=true`
- `restored_daily_coverage_pass=true`
- `missing_required_symbols=0`
- `missing_required_symbol_dates=0`
- strategy returns/model scores remained unopened.

This supersedes the earlier in-progress status and authorizes raw 1H acquisition under the already-frozen contract.

## Current action: frozen raw 1H acquisition
Commit `a0ff4cf07158977081c0ef161cb4e60520906602` updated `research/RUN_V47_RAW1H_FETCH` with `daily_run_id=34799835035` and triggered `Consensus V47 Raw1H Freeze` run `34800587082`.

At 12:36 JST run `34800587082` is `queued`. Do not create a duplicate trigger while this run is queued/in progress.

The raw acceptance contract was re-audited before opening any strategy outcomes and matches the frozen requirements for both price-policy arms:
- pair coverage >= 99.5%
- monthly minimum coverage >= 99.0%
- zero completely missing required symbols
- >=95% per-symbol coverage for symbols with >=20 required days
- restored/delisted required-pair coverage >=99.0%
- both `NOCAP` and `CAP1000_PIT` must pass
- on failure emit missing symbol/date pairs and targeted-refetch only those pairs/codes
- no threshold lowering, candidate dropping, interpolation/backfill, provider/alias choice from returns, or production changes.

## Next action
1. Wait for run `34800587082` to leave queued/running state; do not duplicate-trigger it.
2. On completion, inspect `v47_raw1h_coverage_receipt.json` and the emitted missing-pair files before opening any feature/model outcome.
3. If `accepted=false`, targeted-refetch only missing symbol/date pairs, then rerun the exact frozen coverage verifier. Do not lower thresholds or interpolate.
4. If `accepted=true`, freeze raw artifact hashes and proceed to V47 clean feature materialization only. Recompute cross-sectional features separately for `NOCAP` and `CAP1000_PIT`; use PIT nominal `log_price`, split-normalized relative-price technicals, PIT daily-volume technicals, and unchanged raw-1H-volume technicals.
5. Keep H2 return targets sealed. DEV H1 selection remains strict5/no replacement/0.5% round-trip cost with mean first, then Top3-ex, median, and NOCAP as the final near-tie tiebreak.
6. V45 ATR remains deferred until V47 is complete.
