# Core + Cloud forensic log — 2026-09-15 06:26 JST

## Run discipline
- Coordination STATE/README, Supervisor coordination, dashboard, research HEAD/handoff, Actions and artifacts were inspected first.
- Incoming Core HEAD `3b4a612358a9b8e9b872fc6a14457cdedeaa9385` was already marked processed; no duplicate strategy work was performed.
- Rejected Core / Failed-Breakdown / Prior-Close / Precision families stayed closed. Cloud exact stayed closed. Performance was not opened.
- No production/main, production workflow, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater changes.

## New forensic evidence: exact raw1H bytes recovered
Historical `RUN_1H` commit history identified the extended fetch trigger `a331b96c8b7391a146ed3a8d28dd5e66d6ae0679`. Its successful Actions run is `34592896202` (`Tentei Cloud 1H Research Fetch`).

All eight `tentei-cloud-1h-shard-{0..7}` artifacts were still retained and were downloaded. Every shard contained the expected raw CSV and failure receipt. The existing fail-closed manifest contract passed on the real bytes:
- shard count: 8/8
- total raw rows: **4,019,524**
- timestamp envelope: **2024-09-17 09:00 JST → 2026-09-10 15:00 JST**
- deterministic raw bundle SHA-256: `de7710adaf52ba5a1fb783e7bde35feea9528294be557ef4e011dc4be7e8ed18`
- performance opened: false
- production writes: false

The exact per-shard raw CSV SHA-256, artifact IDs, ZIP digests, sizes, row counts, symbol counts and expiry timestamps are now frozen in `RAW1H_ARTIFACT_PIN_20260915_0626.json`.

## Failure receipt cross-check
The downloaded `failures_{0..7}.json` receipts aggregate to:
- 272 failed chunks
- 61 unique symbols
- HTTP400: 153
- HTTP404: 119

This exactly matches the pre-existing `FETCH_COVERAGE_FINDINGS.md` aggregate. That earlier forensic already found 44 before-first-only symbols, 17 never-seen symbols, and zero detected failure intervals overlapping an observed history. This is a cross-check only; it is not permission to silently delete delisted/listing-boundary names from the formal expected universe.

## What changed in the gate
The previous two-part blocker was:
1. locate/pin the exact retained eight raw1H shard bytes;
2. pin the exact expected endpoint-key universe.

**Blocker 1 is now resolved at byte-identity level.** The observed dataset can be bound to exact raw hashes. It is not yet durably archived beyond GitHub artifact retention: the recovered artifacts expire on 2026-09-25, so the new receipt pins identity, not post-expiry availability.

**Blocker 2 remains open.** Do not manufacture expected keys from a naive `symbol × timestamp` grid. Exact historical listing eligibility, XTKS sessions and delisting/provider-truncation boundaries must be evidenced and SHA-pinned before running the one-shot missing inventory.

## Cloud Monster
No new contemporaneous identity-critical evidence was found. Status remains `HISTORICAL_EXACT_REPRO_UNAVAILABLE`; old `n=63 / 5BD mean +9.86%` remains historical evidence only. No surrogate/model-family guessing was restarted.

## Cost / outcome policy
No new backtest, portability, or strategy-performance statistic was computed. New performance, once the data gate passes, remains cost 0% only; win = gross return > 0; 2026 outcome report-only.
