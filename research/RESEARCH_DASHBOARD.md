# Research Dashboard

Last updated: 2026-09-15 16:39+ JST  
Branch: `research/consensus-atr-regime-gate`  
Lane: Consensus specialist / V47 clean PIT pipeline

## Consensus V47 status
- Progress: **79%** (research-progress estimate; not promotion probability).
- Latest HEAD before this dashboard write: `26d7d3fce573ade567dcf7d788d02443a6ea59af`.
- Promotion-relevant path: **V47 clean PIT only**. V43/V44 are not promotion evidence.
- Arms: exactly `NOCAP` / `CAP1000_PIT`; no extra price-cap grid.
- Endpoint: **next official XTKS open -> D+5 close**.
- New calculations: **cost 0% only**; win = gross return > 0.
- 2026 selection/tuning: prohibited.
- Production/main, production workflow, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater: untouched.

## Formal acceptance
- Daily PIT: **PASS**.
- Raw 1H: **NOT PASSED**.
- Clean features: **UNOPENED FOR PROMOTION**.
- Formal H1: **UNOPENED FOR PROMOTION**.
- Formal H2: **UNOPENED FOR PROMOTION**.
- Formal candidate ranking: **NO CHANGE**.

## Core24 observed raw reuse
- Source identity resolved: Core24 pin is the same preserved Yahoo raw seed run **34592896202** already audited by V47.
- Source HEAD: `a331b96c8b7391a146ed3a8d28dd5e66d6ae0679`.
- Bundle SHA-256: `de7710adaf52ba5a1fb783e7bde35feea9528294be557ef4e011dc4be7e8ed18`.
- Observed bundle: **4,019,524 rows / 1,315 symbols**, 2024-09-17 09:00 JST .. 2026-09-10 15:00 JST.
- Timestamp/session shape and raw 1H volume are compatible with V47.
- Direct price ingestion is not compatible: Core explicit-period OHLC is PIT nominal while V47 feature materializer expects split-normalized/adjusted OHLC before recovering PIT nominal `log_price`.
- Frozen repair: `OHLC_adjusted = OHLC_core24_nominal / cumulative_future_split_factor(symbol,date)`; raw 1H volume unchanged.
- Source raw pin: `research/consensus_v47_core24_raw_pin.json`.
- Compatibility spec: `research/CONSENSUS_V47_CORE24_RAW_REUSE_COMPATIBILITY_20260915.md`.
- Normalizer: `research/normalize_core24_raw1h_for_v47.py`.
- Contract CI **34943423800 SUCCESS**; SHA-pin-required CI **34943685294 SUCCESS**.
- Seed-only coverage remains insufficient:
  - NOCAP: **301,897 / 853,061 = 35.3898%**, monthly min 33.9002%, completely missing symbols 2,592, restored pair coverage 0%.
  - CAP1000_PIT: **258,339 / 310,831 = 83.1124%**, monthly min 77.3420%, completely missing symbols 642, restored pair coverage 0%.

## Authoritative raw retry
- Superseded run `34810592135`: completed/cancelled; no duplicate trigger.
- Current run `34849054884`, trigger SHA `7849ad975d1e0420e250ab4d5f411ce136f9d867`: **non-terminal**.
- Matrix state at latest check: shards **0-11 completed**, **12/13 in progress**, later shards queued; **12 artifacts visible**.
- Shards 10/11 were independently opened this cycle: **162 / 162 requested symbols = HTTP429, ok=0, raw rows=0**.
- Earlier independently opened shards show the same systemic failure pattern.
- Current retry-only performance state: **`NOT_COMPUTABLE_NO_INPUT_DATA`**.
- No threshold reduction, interpolation, synthetic bars, source-by-outcome selection, or duplicate Yahoo bulk retry.

## Midterm diagnostic integrity correction
The old H1 and NOCAP-H2 printed diagnostics used Core explicit-period nominal OHLC directly in the V47 materializer. That double-applied future split factors to the absolute `log_price` path on affected rows.

Classification of the old printed results:
**`MIDTERM_DIAGNOSTIC_INVALID_SOURCE_PRICE_BASIS`**

They are retained only for audit trace and **must not drive arm ranking or GO/NO-GO**.

Holdout state is not reset:
- H1: **OPENED / NOT UNTOUCHED**.
- NOCAP H2: **OPENED / NOT UNTOUCHED**.
- CAP1000_PIT H2: **UNOPENED**.
- Same-family retune: **FORBIDDEN**.
- 2026: **UNOPENED FOR SELECTION/TUNING**.

### Historical invalid H1 NOCAP — audit only
- coverage 35.3898%; period 2025-01-06..2025-06-30
- n 50; mean +0.1074%; median -2.7270%; win 36.00%
- +10 16.00%; +20 8.00%; +50 0.00%; -10 12.00%; -20 2.00%
- Top1-ex -0.7566%; Top3-ex -2.0148%
- endpoint next XTKS open -> D+5 close; cost 0%
- **INVALID FOR RANKING — SOURCE PRICE BASIS**

### Historical invalid H1 CAP1000_PIT — audit only
- coverage 83.1124%; period 2025-01-06..2025-06-30
- n 60; mean -1.1568%; median -0.4011%; win 46.67%
- +10 13.33%; +20 0.00%; +50 0.00%; Top3-ex -2.0601%
- endpoint next XTKS open -> D+5 close; cost 0%
- **INVALID FOR RANKING — SOURCE PRICE BASIS**

### Historical invalid H2 NOCAP — audit only
- period 2025-07-01..2025-12-30
- n 37; mean +3.0295%; median +0.3817%; win 51.35%
- +10 27.03%; +20 16.22%; +50 2.70%; -10 13.51%; -20 2.70%
- Top1-ex +1.5562%; Top3-ex -0.5393%
- endpoint next XTKS open -> D+5 close; cost 0%
- **INVALID FOR RANKING — SOURCE PRICE BASIS**

## Corrected midterm H1
- Correction freeze: `research/CONSENSUS_V47_MIDTERM_PRICE_BASIS_CORRECTION_20260915.json`.
- Corrected run: **34943802848**, trigger commit `6d31d4f8ef76c088246235c7d8a2ffd53995af8e`.
- Contract unchanged: V11 frozen 3-head / min / threshold .95 / guard none / both sessions / strict5 / no replacement / exactly two price arms / cost 0%.
- Source pin verification: passed.
- Core24 OHLC price-basis normalization: passed.
- Current step: **partial clean feature materialization in progress**.
- Corrected H1 performance: **NOT YET OPENED**; run `34943802848` remains in corrected partial feature materialization.
- Current diagnostic ranking: **PENDING CORRECTED H1**.
- H2 must not be rerun/opened from the old invalid H1 leader lock.

## Existing-source audit
- V43 artifact run `34617009116` was inspected: artifact contains summary JSON plus selected-trade CSVs only, **not full raw 1H**, so it cannot fill V47 formal raw coverage.
- Core24 remains the only currently verified reusable observed raw bundle in this lane; it is partial and requires the frozen deterministic price-basis normalization.

## Blocker / next action
1. Do not duplicate-trigger raw run `34849054884`.
2. Complete corrected H1 run `34943802848`; use only its unchanged frozen chooser to identify the diagnostic arm leader.
3. If/when H2 is recomputed, open only the corrected H1 winner and use the same source normalization; do not retune from already-opened outcomes.
4. Formal path stays sealed until provenance-compatible observed raw is merged and the unchanged formal raw acceptance passes both arms.
