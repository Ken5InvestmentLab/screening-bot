# Research Dashboard

Last updated: 2026-09-15 01:48 JST
Branch: `research/consensus-atr-regime-gate`
Lane: Consensus specialist / V47 clean PIT pipeline

## Consensus V47 status
- Progress: **75%** (research-progress estimate; not promotion probability)
- Latest observed HEAD before this dashboard write: `d809bb200ec342eb58dd673b3d991fb4d7decd34`
- Promotion-relevant path: **V47 clean PIT only**
- V43/V44: leakage/reproduction-contaminated; not promotion evidence
- Price arms: exactly `NOCAP` and `CAP1000_PIT`
- Endpoint: next official XTKS open -> D+5 close
- New calculations: **cost 0% only**; win = gross return > 0
- 2026 selection/tuning: prohibited

## Data acceptance
- PIT universe run `34771221050`: accepted
- V46 run `34775030470`: accepted
- Authoritative Daily PIT materialization: accepted
- Daily acceptance: **PASS**
- Formal raw 1H acceptance: **NOT PASSED**
- Formal clean features: **NOT OPENED for promotion**
- Formal H1/H2 performance: **UNOPENED / not promotion evidence**

## Raw retry state
### Superseded retry
- Run `34810592135` — Consensus V47 Raw1H Freeze
- Final status: **completed / cancelled**
- First observed shards hit the 180-minute fetch boundary and did not yield meaningful raw payloads
- Transport-failure evidence only; no strategy conclusion

### Current authoritative retry
- Run `34849054884` — Consensus V47 Raw1H Freeze
- Trigger HEAD: `7849ad975d1e0420e250ab4d5f411ce136f9d867`
- Configuration: **48 shards, max-parallel=2, shard-count=48**
- shard 0: workflow **SUCCESS**, artifact `10357093848`, but raw payload **0 rows**, `0/81` ok symbols, **81/81 HTTP 429**
- shard 1: workflow **SUCCESS**, artifact `10357611796`, but raw payload **0 rows**, `0/81` ok symbols, **81/81 HTTP 429**
- shard 2: **in_progress** at raw 1H fetch at last observation
- shard 3: **in_progress** at raw 1H fetch at last observation
- later shards: queued under max-parallel=2
- Duplicate trigger: **prohibited / not triggered**
- Formal interpretation: workflow completion is not data success. Completed shard 0/1 contribute **zero usable raw rows**.
- Current transport diagnosis: **SYSTEMIC_YAHOO_HTTP_429**
- Frozen raw acceptance unchanged: pair>=99.5%, monthly>=99%, completely missing required symbol=0, symbols requiring >=20 days >=95%, restored pair>=99%
- No interpolation and no threshold lowering
- Detailed receipt: `research/CONSENSUS_V47_RAW48_429_DIAGNOSIS_20260915.md`

### Targeted retry hardening
- No new retry has been triggered while `34849054884` is active.
- Future missing-only retry mechanics now include an outcome-blind systemic-429 preflight:
  - first two shard symbols x both Yahoo chart hosts = four probes;
  - if all four are HTTP 429, write `transport_circuit_open/systemic_http_429` receipts and fail fast instead of spending hours retrying every symbol;
  - if the preflight is not unanimously 429, existing fetch/retry behavior remains.
- This changes transport mechanics only. NOCAP/CAP1000_PIT, threshold, ranker, cooldown, endpoint, features, model, and acceptance thresholds remain frozen.
- On the new shard 0/1 zero-row artifacts alone: **`NOT_COMPUTABLE_NO_INPUT_DATA`**.

## Midterm diagnostic — NOT promotion evidence
Label: `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE`
All figures below are **cost 0%** and use gross return > 0 for win rate.

### 2025 H1 arm comparison, partial raw
#### NOCAP
- raw pair coverage: **35.3898%**
- period: **2025-01-06..2025-06-30**
- n = **50**
- mean **+0.1074%**
- median **-2.7270%**
- win **36.00%**
- +10 **16.00%**
- +20 **8.00%**
- +50 **0.00%**
- -10 **12.00%**
- -20 **2.00%**
- Top1-ex mean **-0.7566%**
- Top3-ex mean **-2.0148%**
- endpoint: next XTKS open -> D+5 close
- caveat: partial/coverage-bypassed diagnostic only

#### CAP1000_PIT
- raw pair coverage: **83.1124%**
- period: **2025-01-06..2025-06-30**
- n = **60**
- mean **-1.1568%**
- median **-0.4011%**
- win **46.67%**
- +10 **13.33%**
- +20 **0.00%**
- +50 **0.00%**
- -10/-20: not recorded in the current authoritative H1 receipt available to this dashboard
- Top1-ex: not recorded in the current authoritative H1 receipt available to this dashboard
- Top3-ex mean **-2.0601%**
- endpoint: next XTKS open -> D+5 close
- caveat: partial/coverage-bypassed diagnostic only

H1 diagnostic chooser: **NOCAP** advanced only under the frozen mean-first rule. H1 is opened and cannot be treated as untouched holdout. Same-family retune prohibited.

### 2025 H2 NOCAP diagnostic
Run `34832358609`: SUCCESS
- period: **2025-07-01..2025-12-30**
- n = **37**
- mean **+3.0295%**
- median **+0.3817%**
- win **51.35%**
- +10 **27.03%**
- +20 **16.22%**
- +50 **2.70%**
- -10 **13.51%**
- -20 **2.70%**
- Top1-ex mean **+1.5562%**
- Top3-ex mean **-0.5393%**
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
- `RESEARCH_DASHBOARD.md` re-read at start of this run
- `CONSENSUS_V44_HANDOFF.md` re-read at start of this run
- Canonical/Event overlap: none
- Core overlap: none
- Monster overlap: none
- Production/main, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater remain untouched

## Blocker
Formal raw 1H acquisition is now specifically blocked by **systemic Yahoo HTTP 429**, not merely shard timeout. Shards 0 and 1 of run `34849054884` both completed mechanically but returned zero rows for all 81 symbols each. This is transport failure, not strategy evidence.

## Next action
1. Do **not** duplicate-trigger run `34849054884`.
2. Preserve shard receipts; workflow SUCCESS with zero raw rows must not be counted as data success.
3. When the active pinned run is terminal, merge only genuinely observed raw rows plus preserved seed raw with source/artifact/digest provenance.
4. Rerun the unchanged frozen formal coverage verifier.
5. If formal acceptance fails, retry only missing symbol/date pairs after Yahoo transport is healthy, using the new systemic-429 fail-fast preflight; never lower thresholds or interpolate.
6. Only after formal raw acceptance may promotion clean features/formal H1/H2 proceed.

## Candidate ranking impact
- **No promotion ranking change.**
- Formal performance remains unopened.
- The newly completed zero-row shards add no performance evidence.
- Midterm-only diagnostic ranking remains: NOCAP is provisionally more interesting than CAP1000_PIT, but partial coverage and Top3-ex fragility prohibit promotion inference.
