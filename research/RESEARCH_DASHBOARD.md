# Research Dashboard

Last updated: 2026-09-15 22:35+ JST  
Branch: `research/consensus-atr-regime-gate`  
Lane: Consensus specialist / V47 clean PIT pipeline

## Contract / safety
- Promotion-relevant path: **V47 clean PIT only**. V43/V44 are not promotion evidence.
- Arms: exactly `NOCAP` / `CAP1000_PIT`; no additional price-cap grid.
- Endpoint: **next official XTKS open -> D+5 close**.
- New calculations: **cost 0% only**; win = gross return > 0.
- 2026 selection/tuning prohibited. Same-family retune after an opened diagnostic prohibited.
- Production/main, production workflow, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater untouched.

## Formal acceptance
- Daily PIT: **PASS**.
- Raw 1H: **NOT PASSED**.
- Clean features: **UNOPENED FOR PROMOTION**.
- Formal H1: **UNOPENED FOR PROMOTION**.
- Formal H2: **UNOPENED FOR PROMOTION**.
- Formal candidate ranking: **NO CHANGE**.

## Authoritative raw retry
- Run `34849054884` remains non-terminal/queued at latest API check; **do not duplicate-trigger**.
- Independently opened completed shards continue to show systemic Yahoo HTTP429 and zero usable rows.
- Retry-only performance: `NOT_COMPUTABLE_NO_INPUT_DATA`.
- Formal thresholds remain unchanged; no interpolation, synthetic bars, or source-by-outcome selection.

## Core24 observed raw reuse
- Same preserved Yahoo seed run `34592896202`, source HEAD `a331b96c8b7391a146ed3a8d28dd5e66d6ae0679`.
- Bundle SHA-256 `de7710adaf52ba5a1fb783e7bde35feea9528294be557ef4e011dc4be7e8ed18`; 4,019,524 rows / 1,315 symbols.
- Deterministic frozen correction: `OHLC_adjusted = OHLC_core24_nominal / cumulative_future_split_factor(symbol,date)`; raw 1H volume unchanged.
- Contract CI `34943423800` SUCCESS; pin-required CI `34943685294` SUCCESS.
- Seed-only coverage remains insufficient for formal acceptance:
  - NOCAP: **301,897 / 853,061 = 35.3898%**, monthly min 33.9002%, 2,592 completely missing symbols, restored pairs 0%.
  - CAP1000_PIT: **258,339 / 310,831 = 83.1124%**, monthly min 77.3420%, 642 completely missing symbols, restored pairs 0%.

## Midterm diagnostic integrity
Old H1 and old NOCAP-H2 diagnostics are classified `MIDTERM_DIAGNOSTIC_INVALID_SOURCE_PRICE_BASIS` because Core nominal OHLC was passed directly to a materializer expecting adjusted OHLC. They remain audit trace only and cannot drive ranking or GO/NO-GO. H1 and NOCAP H2 remain opened/not untouched; holdout status is not reset.

## Corrected midterm H1 — `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE`
Corrected run `34943802848` completed **SUCCESS**. Artifact digest `sha256:e22b84ce4d9f10872060fabfc6af1f7636e62077c4b03298b46237ae587d0c9b`. Frozen contract unchanged: V11 3-head / min / .95 / guard none / both sessions / strict5 / no replacement / cost 0%.

Period 2025-01-06..2025-06-30; endpoint next XTKS open -> D+5 close.

| arm | coverage | n | mean | median | win | +10 | +20 | +50 | -10 | -20 | Top1-ex | Top3-ex |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| NOCAP | 35.3898% | 43 | +1.3817% | -0.7375% | 39.53% | 18.60% | 13.95% | 0.00% | 11.63% | 4.65% | +0.2759% | -1.0890% |
| CAP1000_PIT | 83.1124% | 41 | +1.7117% | -2.0305% | 43.90% | 14.63% | 7.32% | 2.44% | 9.76% | 0.00% | +0.2878% | -1.3069% |

Coverage caveat: partial preserved Yahoo seed only; missing pairs remain missing; no interpolation or synthetic bars. Formal raw acceptance is still FAIL/not passed.

**Corrected diagnostic H1 leader: `CAP1000_PIT`.** This is diagnostic only, not promotion evidence. H1 is opened/not untouched.

## Corrected H2 diagnostic status
- Pre-open spec now pins corrected H1 run `34943802848`, digest `sha256:e22b84ce4d9f10872060fabfc6af1f7636e62077c4b03298b46237ae587d0c9b`, and **CAP1000_PIT only**.
- H2 workflow now requires the same Core24 SHA pin and deterministic adjusted-price normalization used by corrected H1.
- Cost remains **0%**, endpoint remains next XTKS open -> D+5, strict5 cooldown state is carried from H1, and no threshold/ranker/cooldown/price-arm retune is permitted.
- Trigger marker commit: `bdc01fbc6480ee999dd9c63a452389c4ba9f4846`.
- At this checkpoint the corrected CAP1000_PIT H2 performance has **not yet been opened/reported**; wait for the new diagnostic run/artifact and receipt-check it before reading metrics.

## Next action
1. Observe corrected CAP1000_PIT H2 diagnostic registration/completion and inspect pre-open/hash/coverage receipts first.
2. If physically computable, report H2 period, n, mean, median, win, +10/+20/+50, -10/-20, Top1/Top3-ex, endpoint and coverage caveat at cost 0%; otherwise mark `NOT_COMPUTABLE_NO_INPUT_DATA`.
3. Do not retune from H1/H2 and do not open the other arm under the corrected basis.
4. Do not duplicate-trigger authoritative raw run `34849054884`; formal path remains sealed until unchanged raw acceptance passes both arms.
