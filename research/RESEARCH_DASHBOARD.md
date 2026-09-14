# Research Dashboard

Last updated: 2026-09-14 22:39 JST
Branch: `research/consensus-atr-regime-gate`
Lane: Consensus specialist / V47 clean PIT pipeline

## Consensus V47 status
- Progress: **74%** (research-progress estimate; not promotion probability)
- Latest observed HEAD before this dashboard write: `7849ad975d1e0420e250ab4d5f411ce136f9d867`
- Promotion-relevant path: **V47 clean PIT only**
- V43/V44: leakage/reproduction-contaminated; not promotion evidence
- Price arms: exactly `NOCAP` and `CAP1000_PIT`
- Endpoint: next official XTKS open -> D+5 close
- New calculations: **cost 0% only**; win = gross return > 0
- 2026 selection/tuning: prohibited

## Data acceptance
- PIT universe run `34771221050`: accepted
- V46 run `34775030470`: accepted
- Authoritative daily materialization lineage: v6 contract; accepted rebuilt daily artifact used by raw fetch workflow
- Daily acceptance: **PASS**
- Formal raw 1H acceptance: **NOT PASSED**
- Formal clean features: **NOT OPENED for promotion**
- Formal H1/H2 performance: **UNOPENED / not promotion evidence**

## Raw retry state
### Superseded retry
- Run `34810592135` — Consensus V47 Raw1H Freeze
- Final status: **completed / cancelled**
- shard 0..3 observed to hit the 180-minute fetch boundary; artifacts were only 166 bytes each and unusable as meaningful raw payloads
- This run is transport-failure evidence only and does not alter strategy conclusions

### Current authoritative retry
- Run `34849054884` — Consensus V47 Raw1H Freeze
- Trigger HEAD: `7849ad975d1e0420e250ab4d5f411ce136f9d867`
- Configuration: **48 shards, max-parallel=2, shard-count=48**
- Status at 2026-09-14 22:39 JST: workflow `queued` while matrix executes
- shard 0: **in_progress**, accepted Daily artifact download/coverage check + fetcher contract tests passed; raw 1H fetch running
- shard 1: **in_progress**, accepted Daily artifact download/coverage check + fetcher contract tests passed; raw 1H fetch running
- remaining shards: queued under max-parallel=2
- Duplicate trigger: **prohibited / not triggered**
- Frozen raw acceptance unchanged: pair>=99.5%, monthly>=99%, completely missing required symbol=0, symbols requiring >=20 days must be >=95%, restored pair>=99%
- No interpolation and no threshold lowering
- If this run still fails coverage, retry only missing symbol/date pairs

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
  - +50: not recorded in current diagnostic receipt
  - -10/-20: not recorded in current diagnostic receipt
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
  - +50: not recorded in current diagnostic receipt
  - -10/-20: not recorded in current diagnostic receipt
  - Top3-ex mean **-2.060%**
  - endpoint: next XTKS open -> D+5 close
  - caveat: partial/coverage-bypassed diagnostic only
- H1 diagnostic chooser: NOCAP advanced only under frozen mean-first rule. H1 is opened and cannot be treated as untouched holdout. Same-family retune prohibited.

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
- Supervisor coordination re-read at start of this run
- Canonical/Event overlap: none
- Core overlap: none
- Monster overlap: none
- Production/main, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater remain untouched

## Blocker
Formal raw 1H acquisition remains the active blocker. The prior 12-shard retry exceeded the 180-minute shard runtime. The current 48-shard retry is the unchanged-contract transport mitigation and is now actively fetching shard 0/1.

## Next action
1. Do **not** duplicate-trigger run `34849054884`.
2. Inspect the first completed 48-shard artifacts for real row payload and timeout/rate-limit behavior.
3. Allow the current matrix to proceed under max-parallel=2.
4. On completion, merge only observed raw plus preserved seed data with provenance and rerun frozen formal acceptance.
5. If formal acceptance fails, construct missing symbol/date-only targeted retry; never lower thresholds or interpolate.
6. Only after formal raw acceptance may promotion clean features/formal H1/H2 proceed.

## Candidate ranking impact
- No promotion ranking change.
- Formal performance remains unopened.
- Midterm-only diagnostic: NOCAP remains provisionally more interesting than CAP1000_PIT, but partial coverage and Top3-ex fragility prohibit promotion inference.
