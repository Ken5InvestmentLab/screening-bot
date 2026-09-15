# Research Dashboard

Last updated: 2026-09-15 16:39 JST  
Branch: `research/consensus-atr-regime-gate`  
Lane: Consensus specialist / V47 clean PIT pipeline

## Consensus V47 status
- Progress: **78%** (research-progress estimate; not promotion probability)
- Promotion-relevant path: **V47 clean PIT only**; V43/V44 are not promotion evidence.
- Frozen arms: `NOCAP` / `CAP1000_PIT`; no additional price-cap grid search.
- Endpoint: **next official XTKS open -> D+5 close**.
- New calculations: **cost 0% only**; win = gross return > 0.
- 2026 selection/tuning prohibited.
- Production/main, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater untouched.

## Latest HEAD / Actions
- Latest research CI-bearing HEAD before this dashboard write: `7769131120f2549a402d0c36dd95553bdd167812`.
- Core24->V47 price-basis normalization contract CI: run **34943423800**, job **104297144102**, **SUCCESS** on `f3e266e4f1167a1a62dbec1615b3cf78c7764b86`.
- Authoritative raw retry: run **34849054884**, non-terminal; trigger SHA `7849ad975d1e0420e250ab4d5f411ce136f9d867`.
- Raw matrix: shards **0-11 completed**, shards **12/13 in progress**, later shards queued; **12 artifacts visible**.
- No duplicate raw retry was triggered.

## Formal acceptance
- Daily PIT: **PASS**.
- Raw 1H: **NOT PASSED**.
- Clean features: **UNOPENED FOR PROMOTION**.
- Formal H1: **UNOPENED FOR PROMOTION**.
- Formal H2: **UNOPENED FOR PROMOTION**.
- Formal performance ranking / candidate ranking impact: **no change**.

## Core24 observed raw reuse audit
Outcome-blind source identity is now resolved.

- Core24 SHA-pinned source is exactly V47's preserved seed run **34592896202**.
- Source HEAD: `a331b96c8b7391a146ed3a8d28dd5e66d6ae0679`.
- Eight artifact IDs/ZIP digests match the existing V47 seed audit.
- Core24 pin adds per-CSV SHA-256 plus bundle SHA `de7710adaf52ba5a1fb783e7bde35feea9528294be557ef4e011dc4be7e8ed18`.
- Observed bundle: **4,019,524 rows / 1,315 symbols**, 2024-09-17 09:00 JST .. 2026-09-10 15:00 JST.
- Session/timestamp shape and raw 1H volume are compatible with V47; raw volume stays unchanged.
- Price basis is **not directly compatible**: Core explicit-period OHLC is PIT nominal while V47 materializer expects split-normalized/adjusted raw OHLC before reconstructing PIT nominal `log_price`.
- Frozen repair: for Core seed only, divide OHLC by V47 cumulative future split factor(symbol,date); leave volume unchanged; preserve source/output SHA receipts.
- Compatibility spec: `research/CONSENSUS_V47_CORE24_RAW_REUSE_COMPATIBILITY_20260915.md`.
- Normalizer + synthetic contract test implemented and CI-passed.

### Seed coverage under unchanged V47 inventory
- NOCAP: **301,897 / 853,061 = 35.3898%**; monthly min 33.9002%; completely missing symbols 2,592; restored pair coverage 0%.
- CAP1000_PIT: **258,339 / 310,831 = 83.1124%**; monthly min 77.3420%; completely missing symbols 642; restored pair coverage 0%.
- Verdict: **provenance-compatible partial seed after normalization, but insufficient for formal acceptance by itself**.

## Raw retry / transport blocker
- Superseded run `34810592135`: completed/cancelled; do not duplicate-trigger.
- Current run `34849054884`: still non-terminal.
- Independently opened early shards showed systemic Yahoo HTTP429 and zero usable rows; no non-zero retry raw has been accepted as evidence.
- Retry-only performance state: **`NOT_COMPUTABLE_NO_INPUT_DATA`**.
- No interpolation, threshold lowering, source-by-outcome choice, strategy retune, or additional price-cap search.
- Frozen merge contract: `research/CONSENSUS_V47_RAW_MERGE_ACCEPTANCE_SPEC_20260915.md`.

## Midterm diagnostic status — corrected integrity classification
The previously printed H1 and NOCAP-H2 diagnostics are **not promotion evidence** and are now additionally invalid for ranking because their workflow passed the Core explicit-period nominal OHLC directly into a materializer expecting adjusted OHLC.

Classification: **`MIDTERM_DIAGNOSTIC_INVALID_SOURCE_PRICE_BASIS`**.

Opened-period consequences remain:
- H1: **OPENED / NOT UNTOUCHED**.
- NOCAP H2: **OPENED / NOT UNTOUCHED**.
- CAP1000_PIT H2: **UNOPENED**.
- Same-family retune: **FORBIDDEN**.
- 2026: **UNOPENED FOR SELECTION/TUNING**.

Historical printed values are retained only for audit trace and **must not drive ranking or GO/NO-GO**:

### 2025 H1 NOCAP — invalid source price basis
- coverage 35.3898%; period 2025-01-06..2025-06-30
- n 50; mean +0.1074%; median -2.7270%; win 36.00%
- +10 16.00%; +20 8.00%; +50 0.00%; -10 12.00%; -20 2.00%
- Top1-ex -0.7566%; Top3-ex -2.0148%
- endpoint next XTKS open -> D+5 close; cost 0%
- status: **INVALID FOR RANKING — SOURCE PRICE BASIS**

### 2025 H1 CAP1000_PIT — invalid source price basis
- coverage 83.1124%; period 2025-01-06..2025-06-30
- n 60; mean -1.1568%; median -0.4011%; win 46.67%
- +10 13.33%; +20 0.00%; +50 0.00%
- Top3-ex -2.0601%; other tail fields retained in original receipt where available
- endpoint next XTKS open -> D+5 close; cost 0%
- status: **INVALID FOR RANKING — SOURCE PRICE BASIS**

### 2025 H2 NOCAP — invalid source price basis
- period 2025-07-01..2025-12-30
- n 37; mean +3.0295%; median +0.3817%; win 51.35%
- +10 27.03%; +20 16.22%; +50 2.70%; -10 13.51%; -20 2.70%
- Top1-ex +1.5562%; Top3-ex -0.5393%
- endpoint next XTKS open -> D+5 close; cost 0%
- status: **INVALID FOR RANKING — SOURCE PRICE BASIS**

## Blocker / next action
1. Do not duplicate-trigger authoritative raw run `34849054884`.
2. Preserve Core24 seed identity with its pinned raw SHA bundle.
3. Use only the CI-passed deterministic OHLC basis normalizer; raw 1H volume unchanged.
4. Corrected midterm H1 may be recomputed with the **exact unchanged frozen family/threshold/ranker/cooldown and cost 0%**; this is input repair, not retuning. The previously opened results cannot be used to alter parameters.
5. Formal path remains stricter: merge only provenance-accepted observed rows, rerun unchanged raw coverage acceptance, and keep formal features/H1/H2 sealed until both arms pass.
