# Research Dashboard

Last updated: 2026-09-15 03:35 JST
Branch: `research/consensus-atr-regime-gate`
Lane: Consensus specialist / V47 clean PIT pipeline

## Consensus V47 status
- Progress: **76%** (research-progress estimate; not promotion probability)
- Latest observed HEAD before this dashboard write: `f2bc6f3c97292930ccaefae9035e182dee33d821`
- Promotion-relevant path: **V47 clean PIT only**
- V43/V44: leakage/reproduction-contaminated; not promotion evidence
- Price arms: exactly `NOCAP` and `CAP1000_PIT`
- Endpoint: next official XTKS open -> D+5 close
- New calculations: **cost 0% only**; win = gross return > 0
- 2026 selection/tuning: prohibited

## Data acceptance
- PIT universe run `34771221050`: accepted
- V46 run `34775030470`: accepted
- Authoritative Daily PIT materialization: run `34788533946`; accepted
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
- GitHub run-level status at this observation: **queued** while the matrix still has work active/queued
- shard 0: workflow **SUCCESS**, artifact `10357093848` (1647 bytes ZIP), but raw payload **0 rows**, `0/81` ok symbols, **81/81 HTTP 429**
- shard 1: workflow **SUCCESS**, artifact `10357611796` (1646 bytes ZIP), but raw payload **0 rows**, `0/81` ok symbols, **81/81 HTTP 429**
- shards 2 and 3: explicitly observed **in_progress** at `Fetch raw 1H shard`
- remaining matrix jobs: queued under max-parallel=2; only two artifacts are visible so far
- Duplicate trigger: **prohibited / not triggered**
- Formal interpretation: workflow completion is not data success. Completed shard 0/1 contribute **zero usable raw rows**.
- Current transport diagnosis: **SYSTEMIC_YAHOO_HTTP_429**
- Frozen raw acceptance unchanged: pair>=99.5%, monthly>=99%, completely missing required symbol=0, symbols requiring >=20 days >=95%, restored pair>=99%
- No interpolation and no threshold lowering
- Detailed receipt: `research/CONSENSUS_V47_RAW48_429_DIAGNOSIS_20260915.md`

### Targeted retry hardening
- No new retry has been triggered while `34849054884` is active.
- Future missing-only retry mechanics include the already implemented outcome-blind systemic-429 preflight:
  - first two shard symbols x both Yahoo chart hosts = four probes;
  - if all four are HTTP 429, write `transport_circuit_open/systemic_http_429` receipts and fail fast instead of spending hours retrying every symbol;
  - if the preflight is not unanimously 429, existing fetch/retry behavior remains.
- This changes transport mechanics only. NOCAP/CAP1000_PIT, threshold, ranker, cooldown, endpoint, features, model, and acceptance thresholds remain frozen.
- On shard 0/1 zero-row artifacts alone: **`NOT_COMPUTABLE_NO_INPUT_DATA`**.

### Raw merge + formal acceptance contract frozen
- Spec: `research/CONSENSUS_V47_RAW_MERGE_ACCEPTANCE_SPEC_20260915.md`
- Freeze commit: `4304be47319ccedbd7827dc471b08fe2541d5926`
- When run `34849054884` is terminal, only genuinely observed shard raw rows may be merged with preserved seed raw.
- Workflow `success` with zero rows is provenance/failure evidence only, never market data.
- Duplicate `(symbol, ts_jst)` rows must agree exactly after canonical type normalization; conflicts fail closed.
- Retained rows must preserve source/run/artifact/shard/file-SHA provenance.
- Formal coverage thresholds remain unchanged; failed coverage produces an exact missing `(symbol,date)` set for missing-only retry.
- This freeze used no strategy outcomes and does not open formal performance.

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
Formal raw 1H acquisition remains blocked by **systemic Yahoo HTTP 429**. Shards 0 and 1 of run `34849054884` both completed mechanically but returned zero rows for all 81 symbols each. Shards 2 and 3 are still fetching and only the original two artifacts are visible, so transport recovery has not yet been demonstrated. This is transport failure, not strategy evidence.

## Next action
1. Do **not** duplicate-trigger run `34849054884`.
2. Preserve all shard receipts; workflow SUCCESS with zero raw rows must not be counted as data success.
3. When the active pinned run is terminal, enumerate all 48 shard artifacts/receipts and admit only genuinely observed raw rows under `CONSENSUS_V47_RAW_MERGE_ACCEPTANCE_SPEC_20260915.md`.
4. Merge admitted rows with preserved seed raw using source/artifact/digest provenance and rerun the unchanged frozen formal coverage verifier.
5. If formal acceptance fails, emit the exact missing `(symbol,date)` set and retry only those pairs after Yahoo transport is healthy, using the systemic-429 fail-fast preflight; never lower thresholds or interpolate.
6. Only after formal raw acceptance may promotion clean features/formal H1/H2 proceed.

## Candidate ranking impact
- **No promotion ranking change.**
- Formal performance remains unopened.
- Zero-row shards add no performance evidence.
- Midterm-only diagnostic ranking remains: NOCAP is provisionally more interesting than CAP1000_PIT, but partial coverage and Top3-ex fragility prohibit promotion inference.
