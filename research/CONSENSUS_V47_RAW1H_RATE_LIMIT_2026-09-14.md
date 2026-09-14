# Consensus V47 raw1H rate-limit incident — 2026-09-14

Research-only. No production/main/Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist-builder/updater changes.

## Observation

Authoritative daily PIT materialization `34799835035` passed and authorized frozen Yahoo raw 1H acquisition run `34800587082`.

During the run, shard 1 completed successfully at the GitHub job level but its uploaded receipt showed transport failure for every requested symbol:
- requested symbols: 324
- ok symbols: 0
- non-ok symbols: 324
- total rows: 0
- error class: `http_429` for all inspected rows

This is a provider-rate-limit/data-acquisition failure, not strategy evidence. No strategy returns or model scores were opened.

At inspection time, 8 of 12 shard artifacts had uploaded while shards 0/2/5/6 were still running. The current run remains authoritative only as a raw acquisition attempt; acceptance must still be decided by the frozen `v47_raw1h_coverage_receipt.json` workflow after all shards finish.

## Outcome-blind mitigation staged for future retry/refetch

The raw fetcher was hardened without touching eligibility, model, score, target, or acceptance thresholds:
- alternate `query1` / `query2` Yahoo chart hosts;
- persistent HTTP session;
- bounded exponential backoff with `Retry-After` support for 429/502/503/504;
- 0.55-second post-success pacing;
- 8 attempts per symbol;
- transport-policy metadata included in shard summary.

The raw workflow was also throttled to `max-parallel: 2` and timeout increased to 180 minutes, reducing burst pressure from 12 simultaneous shards.

These changes are transport-only and must not be used to reinterpret or lower frozen coverage gates.

## Frozen next action

1. Let run `34800587082` finish; do not duplicate-trigger while it is active.
2. Run the existing outcome-blind raw coverage acceptance using daily run `34799835035` and raw run `34800587082`.
3. If `accepted=false`, use only emitted missing symbol/date pairs/codes for retry. No interpolation, threshold lowering, candidate dropping, or return-aware provider choice.
4. The staged rate-limit mitigation applies to that retry path.
5. Only after exact frozen coverage passes may V47 clean feature materialization begin.
