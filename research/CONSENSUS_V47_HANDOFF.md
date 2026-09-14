# Consensus V47 clean PIT handoff

Updated: 2026-09-14 11:38 JST
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
- Yahoo raw 1H volume stays unchanged for session-volume gate and session-volume-ratio technicals.
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
- 11 symbols remain below 90% required-date coverage: 1841, 2754, 3847, 5395, 6060, 6416, 8038, 8072, 8208, 8886, 9852
- merge receipt `accepted_for_daily_rebuild=true` means symbol-set recovery is complete; it does NOT override the downstream final daily coverage gate.
- no strategy returns or model scores were opened.

## Current action
Commit `5d9a424eeda5e9c6d70a16a3380de9678d099140` triggered `Consensus V47 Daily PIT Materialization External` run `34799835035`, using restored merge run `34799650589`.

At this handoff update the run is in progress. The workflow must fail closed unless `daily_coverage_pass=true`. Do not start raw 1H fetch before that receipt passes.

## Next action
1. When run `34799835035` completes, inspect only the outcome-free daily materialization receipt first.
2. If `daily_coverage_pass=false`, repair only the missing historical symbol/date coverage. Do not lower thresholds, interpolate, or open strategy outcomes.
3. If `daily_coverage_pass=true`, trigger `RUN_V47_RAW1H_FETCH` with `daily_run_id=34799835035` and the frozen 12-shard raw workflow.
4. Enforce raw acceptance: pair >=99.5%, monthly >=99%, no completely missing required symbol, >=95% per-symbol coverage for symbols requiring >=20 days, restored required-pair >=99%.
5. Only after accepted raw coverage may clean feature materialization begin.
