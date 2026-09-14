# Research Dashboard

Last updated: 2026-09-14 21:42 JST
Branch: `research/consensus-atr-regime-gate`
Lane: Consensus specialist / V47 clean PIT pipeline

## Consensus V47 status
- Progress: **73%** (research-progress estimate; not promotion probability)
- Latest observed HEAD before this dashboard write: `263b91afdffbf0c38a3318f80394a95a4b506f44`
- Promotion-relevant path: **V47 clean PIT only**
- V43/V44: leakage/reproduction-contaminated; not promotion evidence
- Price arms: exactly `NOCAP` and `CAP1000_PIT`
- Endpoint: next official XTKS open -> D+5 close
- New calculations: **cost 0% only**; win = gross return > 0
- 2026 selection/tuning: prohibited

## Data acceptance
- PIT universe run `34771221050`: accepted
- V46 run `34775030470`: accepted
- Authoritative daily materialization lineage: v6 contract; daily coverage currently treated as PASS from accepted rebuilt daily artifact used by raw fetch workflow
- Formal raw 1H acceptance: **NOT PASSED**
- Formal clean features: **NOT OPENED for promotion**
- Formal H1/H2 performance: **UNOPENED / not promotion evidence**

## Current raw retry
- Run: `34810592135` — Consensus V47 Raw1H Freeze
- Overall GitHub run status observed: `queued` while matrix jobs progress
- Duplicate trigger: **prohibited / not triggered**
- Observed completed jobs: shard 0,1,2,3 all hit the 180-minute fetch boundary and ended `cancelled`
- Uploaded artifacts for shard 0..3 are only **166 bytes each**, so they are not usable as meaningful raw 1H payloads
- Active matrix at last inspection: later shards continue under max-parallel=2; remaining jobs queued
- Root blocker: Yahoo historical 1H transport/rate-limit throughput relative to GitHub 180-minute job ceiling
- Prepared next-run mitigation already present in branch workflow: **48 shards, max-parallel=2, shard-count=48**
- Acceptance thresholds remain frozen; no interpolation and no threshold lowering

## Midterm diagnostic — NOT promotion evidence
Label: `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE`

### 2025 H1 arm comparison, partial raw, cost 0%
- NOCAP raw coverage: **35.39%**
  - n=50
  - mean **+0.107%**
  - median **-2.727%**
  - win **36.0%**
  - +10 **16.0%**
  - +20 **8.0%**
  - Top3-ex mean **-2.015%**
  - endpoint: next XTKS open -> D+5 close
  - caveat: partial/coverage-bypassed diagnostic only
- CAP1000_PIT raw coverage: **83.11%**
  - n=60
  - mean **-1.157%**
  - median **-0.401%**
  - win **46.67%**
  - +10 **13.33%**
  - +20 **0%**
  - Top3-ex mean **-2.060%**
  - endpoint: next XTKS open -> D+5 close
  - caveat: partial/coverage-bypassed diagnostic only
- H1 diagnostic chooser: NOCAP advanced only under frozen mean-first rule. H1 is now opened and cannot be treated as untouched holdout. Same-family retune prohibited.

### 2025 H2 NOCAP diagnostic, cost 0%
Run `34832358609`: SUCCESS
- period: 2025-07-01 through 2025-12-30
- n=37
- mean **+3.03%**
- median **+0.38%**
- win **51.35%**
- +10 **27.03%**
- +20 **16.22%**
- +50 **2.70%**
- -10 **13.51%**
- -20 **2.70%**
- Top1-ex mean **+1.56%**
- Top3-ex mean **-0.54%**
- endpoint: next XTKS open -> D+5 close
- caveat: partial raw / coverage-bypassed; H2 now opened and is not untouched holdout
- interpretation: positive mean/median but material top-winner dependence; not sufficient for promotion

CAP1000_PIT H2: **UNOPENED**
2026: **UNOPENED for selection/tuning**

## NOCAP vs CAP1000_PIT comparison stage
- H1 midterm diagnostic comparison completed on partial raw
- NOCAP won the frozen H1 diagnostic chooser on mean, but robustness diagnostics are weak
- Only NOCAP H2 diagnostic was opened
- No additional price-cap grid search permitted
- Formal arm comparison remains blocked on raw acceptance + clean PIT feature materialization

## Cross-lane coordination
- Do not duplicate Canonical/Event, Core, or Monster work
- Production/main, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater remain untouched

## Blocker
Formal raw 1H acquisition is not completing within the current 12-shard retry's 180-minute shard runtime. Early retry artifacts are effectively empty. This is a data transport/runtime blocker, not strategy evidence.

## Next action
1. Do **not** duplicate-trigger run `34810592135`.
2. Inspect its next completed shard artifacts and final run disposition.
3. When current retry is no longer active, launch the already-prepared 48-shard missing-only retry using the same frozen data contract.
4. Merge only real observed raw with preserved seed data using provenance; rerun frozen acceptance.
5. Only after formal raw acceptance may promotion clean features/formal H1/H2 proceed.

## Candidate ranking impact
- No promotion ranking change.
- Midterm-only diagnostic: NOCAP is provisionally more interesting than CAP1000_PIT, but coverage is inadequate and Top3-ex fragility prevents promotion inference.
