# Research Dashboard

Last updated: 2026-09-15 06:34 JST
Branch: `research/consensus-atr-regime-gate`
Lane: Consensus specialist / V47 clean PIT pipeline

## Consensus V47 status
- Progress: **76%** (research-progress estimate; not promotion probability)
- Promotion-relevant path: **V47 clean PIT only**; V43/V44 are not promotion evidence.
- Frozen arms: `NOCAP` / `CAP1000_PIT`; no additional price-cap grid search.
- Endpoint: **next official XTKS open -> D+5 close**.
- New calculations: **cost 0% only**; win = gross return > 0.
- 2026 selection/tuning prohibited.
- Production/main, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater untouched.

## Formal acceptance
- Daily PIT: **PASS**.
- Raw 1H: **NOT PASSED**.
- Clean features / formal H1 / formal H2: **UNOPENED FOR PROMOTION**.
- Formal performance ranking: **no change**.

## Raw retry
- Superseded run `34810592135`: completed/cancelled; do not duplicate-trigger.
- Current authoritative run `34849054884`, trigger HEAD `7849ad975d1e0420e250ab4d5f411ce136f9d867`: **in progress / non-terminal**.
- Configuration: 48 shards, max-parallel=2, frozen acceptance unchanged.
- shards 0-3: workflow SUCCESS but **324/324 requested symbols HTTP 429, 0 ok, 0 raw rows**; artifacts 4 total.
- At 06:34 JST there is **no new artifact** beyond shards 0-3.
- shards **4 and 5 are in progress** at `Fetch raw 1H shard`; later matrix jobs remain queued.
- Current transport diagnosis: **SYSTEMIC_YAHOO_HTTP_429**. Zero-row retry data status: **`NOT_COMPUTABLE_NO_INPUT_DATA`**.
- No interpolation, threshold lowering, strategy retune, or duplicate trigger.
- Frozen merge contract: `research/CONSENSUS_V47_RAW_MERGE_ACCEPTANCE_SPEC_20260915.md`.
- After terminal state: enumerate receipts -> admit only genuinely observed rows -> provenance merge with preserved seed raw -> rerun unchanged frozen acceptance -> emit exact missing `(symbol,date)` pairs if still failing.

## Midterm diagnostic — `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE`
All figures are **cost 0%**, win = gross return > 0, endpoint next XTKS open -> D+5 close. Opened H1/H2 periods are no longer untouched holdouts; same-family retune prohibited.

### 2025 H1 NOCAP — partial raw
- coverage **35.3898%**; period **2025-01-06..2025-06-30**
- n **50**; mean **+0.1074%**; median **-2.7270%**; win **36.00%**
- +10 **16.00%**; +20 **8.00%**; +50 **0.00%**; -10 **12.00%**; -20 **2.00%**
- Top1-ex mean **-0.7566%**; Top3-ex mean **-2.0148%**
- caveat: partial / coverage-bypassed diagnostic only.

### 2025 H1 CAP1000_PIT — partial raw
- coverage **83.1124%**; period **2025-01-06..2025-06-30**
- n **60**; mean **-1.1568%**; median **-0.4011%**; win **46.67%**
- +10 **13.33%**; +20 **0.00%**; +50 **0.00%**
- -10/-20 and Top1-ex: not recorded in current authoritative H1 receipt; Top3-ex mean **-2.0601%**
- caveat: partial / coverage-bypassed diagnostic only.

### 2025 H2 NOCAP — partial raw
- period **2025-07-01..2025-12-30**
- n **37**; mean **+3.0295%**; median **+0.3817%**; win **51.35%**
- +10 **27.03%**; +20 **16.22%**; +50 **2.70%**; -10 **13.51%**; -20 **2.70%**
- Top1-ex mean **+1.5562%**; Top3-ex mean **-0.5393%**
- caveat: partial raw / coverage-bypassed; material top-winner dependence; not promotion evidence.

CAP1000_PIT H2: **UNOPENED**. 2026: **UNOPENED for selection/tuning**.

## Blocker / next action
Formal raw acquisition remains blocked by Yahoo transport rate limiting. Continue the already-running pinned matrix without duplicate trigger. The next evidence-bearing event is either a non-zero raw artifact from shards 4/5 or terminal completion of run `34849054884`; only then proceed with the frozen provenance merge and formal acceptance rerun.
