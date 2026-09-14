# Consensus V47 existing Yahoo raw1H seed audit — 2026-09-14

Updated: 2026-09-14 16:39 JST
Branch: `research/consensus-atr-regime-gate`
Scope: outcome-blind data-acquisition audit only. No strategy returns, model scores, H1/H2 outcomes, or 2026 selection were opened.

## Purpose
The active V47 missing-universe retry (`34810592135`) remains transport-limited at Yahoo. Before launching any further retry after it completes, audit whether already-preserved Yahoo raw 1H artifacts can safely seed the exact V47 candidate-date coverage calculation and reduce unnecessary provider requests.

This does **not** change the frozen acceptance thresholds, price arms, feature semantics, eligibility rules, target, or model. It only asks which required `(symbol,date)` pairs already exist in an earlier frozen Yahoo raw 1H capture.

## Source artifacts
Existing Core-lane raw Yahoo 1H run: `34592896202`, captured 2026-09-11, source window 2024-09-16..2026-09-10.

Eight still-live artifacts were downloaded and audited read-only:
- shard 0 artifact `10196449529`, digest `sha256:9421fc93cc39c875a45dad09eb199e991e856f89b407cdf50e2a365fd529a137`
- shard 1 artifact `10196417793`, digest `sha256:20ae841c47304d0c7f27ab9a42ccd23a499375dd1676e797dc70b5ababe41a56`
- shard 2 artifact `10196390666`, digest `sha256:a221b36de3153dd256a977861166239ce19c829890cc085aa37cc33e39f771db`
- shard 3 artifact `10196390156`, digest `sha256:141ce33f9c4f678dbd1a6800e33ead97e0c7e0fa8654b78adc5f7cd0e357fa72`
- shard 4 artifact `10196451479`, digest `sha256:dc48120319252a460009213e36faf286815869f91162a492bc75dedc89e62c34`
- shard 5 artifact `10196398807`, digest `sha256:c476912bd559cdf310cdbf1e5b18ad7ed68950aa1b3bd21819398449f6638c54`
- shard 6 artifact `10196399262`, digest `sha256:459f4303e7b6d873fd6e1c67a32a71e6b39d39982dc4e256b177d9d5f8ed428c`
- shard 7 artifact `10196438873`, digest `sha256:3123938c92c1b16d0ac2b34ea6776cb949283e1fe9a692b54843cd8315d84f2d`

Authoritative V47 daily artifact: run `34799835035`, artifact `10331600267`, digest `sha256:ac9d3cc54ba72b6578cbd1b0e650b781b793331c4ee21074a1f9211677b204a6`.

## Observed old raw panel
After concatenating the eight preserved CSV shards and deduplicating `(symbol,date)`:
- unique raw symbol/date pairs: **618,775**
- unique symbols with at least one raw row: **1,315**
- date range observed: **2024-09-17 .. 2026-09-10**

## Frozen V47 pair coverage from the preserved panel
Required pairs are taken only from `v47_daily_candidate_symbol_dates.csv` in authoritative V47 daily run `34799835035`; no outcomes are consulted.

### NOCAP
- required pairs: **853,061**
- preserved-panel present pairs: **301,897**
- pair coverage: **35.3898%**
- required symbols: **3,885**
- symbols with at least one required pair present: **1,293**
- completely missing required symbols: **2,592**
- monthly minimum pair coverage: **33.9002%** (`2024-10`)
- symbols requiring >=20 dates whose pair coverage is >=95%: **35.43%**
- restored required pairs: **40,048**
- restored pair coverage: **0.0%**

### CAP1000_PIT
- required pairs: **310,831**
- preserved-panel present pairs: **258,339**
- pair coverage: **83.1124%**
- required symbols: **1,886**
- symbols with at least one required pair present: **1,244**
- completely missing required symbols: **642**
- monthly minimum pair coverage: **77.3420%** (`2024-10`)
- symbols requiring >=20 dates whose pair coverage is >=95%: **73.67%**
- restored required pairs: **15,492**
- restored pair coverage: **0.0%**

## Interpretation
The preserved panel is nowhere near sufficient to pass the V47 frozen acceptance by itself, especially for NOCAP and restored historical identities. It therefore **must not** be treated as accepted V47 raw coverage.

However, it is materially useful as an outcome-blind seed:
- it already covers about **35.4%** of NOCAP required pairs;
- it already covers about **83.1%** of CAP1000_PIT required pairs;
- reusing those exact historical Yahoo bars can reduce unnecessary re-requests during later missing-only retries;
- the remaining gaps must still be closed under the unchanged frozen verifier, especially restored/predecessor identities.

This reuse is permissible only if the bars remain immutable, provenance-hashed, and merged by exact `(symbol,timestamp)` without interpolation or synthetic filling. It does not authorize cross-sectional evaluation, model scoring, or performance inspection.

## Current run boundary
Retry `34810592135` is still active. Job-level state at 16:39 JST remains:
- `fetch (0)` in progress at `Fetch raw 1H shard`;
- `fetch (1)` in progress at `Fetch raw 1H shard`;
- remaining 10 shard jobs queued by `max-parallel: 2`.

No duplicate retry was launched and the active run was not cancelled.

## Frozen next action
1. Allow `34810592135` to complete or fail naturally; do not duplicate-trigger while active.
2. Before any further Yahoo retry, combine only immutable raw bars from the completed retry and the preserved run `34592896202`, retaining source/artifact/digest provenance for every source shard.
3. Run the exact frozen V47 coverage verifier on the merged outcome-blind raw pool.
4. If rejected, use the verifier's newly emitted missing `(symbol,date)` set to drive the next targeted acquisition. Do not re-request pairs already present in the merged pool.
5. Keep acceptance thresholds unchanged: pair>=99.5%, monthly>=99%, completely-missing symbols=0, >=20-day symbol coverage>=95%, restored pair>=99%.
6. Features/H1/H2 remain sealed until both NOCAP and CAP1000_PIT pass.
