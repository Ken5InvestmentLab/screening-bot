# Consensus V47 clean PIT handoff

Updated: 2026-09-14 13:35 JST
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
`Consensus V47 Daily PIT Materialization External` run `34799835035` completed SUCCESS and is the authoritative V47 daily source.

Outcome-blind acceptance receipt passed all daily gates:
- `daily_coverage_pass=true`
- `required_coverage_pass=true`
- `restored_daily_coverage_pass=true`
- `missing_required_symbols=0`
- `missing_required_symbol_dates=0`
- strategy returns/model scores remained unopened.

## Current action: frozen raw 1H acquisition
Commit `a0ff4cf07158977081c0ef161cb4e60520906602` triggered `Consensus V47 Raw1H Freeze` run `34800587082` from daily run `34799835035`.

At 13:35 JST the run is still in progress. Job-level progress at inspection time:
- completed SUCCESS: shards 1,3,4,7,8,9,10,11
- still running: shards 0,2,5,6
- do not duplicate-trigger while this run is active.

Important transport finding: completed shard 1 uploaded a valid receipt/artifact but contained **0/324 successful symbols** and **324/324 `http_429` fetch errors**. This is provider rate limiting, not strategy evidence. No returns or model scores were opened. Other completed artifacts were similarly tiny and therefore require the formal coverage pass before any downstream use.

The frozen raw acceptance contract remains unchanged for both price-policy arms:
- pair coverage >= 99.5%
- monthly minimum coverage >= 99.0%
- zero completely missing required symbols
- >=95% per-symbol coverage for symbols with >=20 required days
- restored/delisted required-pair coverage >=99.0%
- both `NOCAP` and `CAP1000_PIT` must pass
- failure emits missing symbol/date pairs and permits targeted-refetch only those pairs/codes
- no threshold lowering, candidate dropping, interpolation/backfill, provider/alias choice from returns, or production changes.

## Outcome-blind rate-limit mitigation now staged
Transport-only hardening was committed for future retry/refetch; it does not alter the active run because checkout is pinned to its trigger SHA.

- `2880cc20165ef35705290330052e40d5c3ba1975`: raw fetcher now alternates Yahoo query1/query2 hosts, uses a persistent session, honors Retry-After, applies bounded exponential backoff, raises attempts from 5 to 8, adds 0.55-second post-success pacing, and records the transport policy in the shard summary.
- `e61fcdfc4fb2f18eee41dde5ae79474e38b2a5be`: future raw workflow executions are throttled to `max-parallel: 2` and timeout 180 minutes to avoid another 12-shard burst.
- Incident log: `research/CONSENSUS_V47_RAW1H_RATE_LIMIT_2026-09-14.md`.

These are data-acquisition reliability changes only. Eligibility, price-policy arms, model, target, feature semantics, and all acceptance thresholds remain frozen.

## Next action
1. Let run `34800587082` finish; do not duplicate-trigger it.
2. Then run the existing outcome-blind raw coverage acceptance with daily run `34799835035` and raw run `34800587082`.
3. Inspect `v47_raw1h_coverage_receipt.json` and emitted missing-pair files before opening any feature/model outcome.
4. If `accepted=false`, targeted-refetch only emitted missing symbol/date pairs/codes using the staged throttled/backoff transport policy, then rerun the exact frozen coverage verifier. Do not lower thresholds or interpolate.
5. If `accepted=true`, freeze raw artifact hashes and proceed to V47 clean feature materialization only. Recompute cross-sectional features separately for `NOCAP` and `CAP1000_PIT`; use PIT nominal `log_price`, split-normalized relative-price technicals, PIT daily-volume technicals, and unchanged raw-1H-volume technicals.
6. Keep H2 return targets sealed. DEV H1 selection remains strict5/no replacement/0.5% round-trip cost with mean first, then Top3-ex, median, and NOCAP as final near-tie tiebreak.
7. V45 ATR remains deferred until V47 is complete.
