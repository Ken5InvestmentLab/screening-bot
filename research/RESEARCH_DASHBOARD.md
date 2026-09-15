# Research Dashboard

Last updated: 2026-09-16 04:35+ JST  
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

## Corrected CAP1000_PIT H2 — `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE`
Run `34976174775` completed **SUCCESS**. Artifact digest `sha256:ad2bd2388425aaad55ed8485f5f20dfefbf62014c1f746e464851d9c093d7688`. Pre-open contract fixed CAP1000_PIT from corrected H1 before H2 was opened; NOCAP H2 was not opened under the corrected basis. Cost 0%, same threshold/ranker/price arm, strict5 cooldown state carried from H1, no replacement and no retune.

Period 2025-07-01..2025-12-30; endpoint next XTKS open -> D+5 close.

| arm | coverage | n | mean | median | win | +10 | +20 | +50 | -10 | -20 | Top1-ex | Top3-ex |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CAP1000_PIT | 83.1124%* | 26 | +3.8194% | 0.0000% | 30.77% | 19.23% | 7.69% | 3.85% | 15.38% | 3.85% | -0.6236% | -3.0563% |

`*` Coverage is the frozen required-pair coverage of the preserved Core24 seed used by the corrected diagnostic, not formal raw acceptance. The run explicitly bypassed formal coverage for diagnostic use only. Missing pairs stayed missing; no interpolation or synthetic bars. Unique symbols=22; max-symbol share=11.54%.

Interpretation: the positive H2 mean is **tail-dependent**. Removing the best trade turns mean negative, and removing the top three worsens it further. H2 therefore does not provide robust broad-based support despite a higher headline mean than H1. This is diagnostic evidence only and cannot promote the family.

H2 is now opened/not untouched. Same-family retuning from these results remains prohibited; no additional price-cap grid is allowed and 2026 remains sealed from selection/tuning.

## Current disposition
- Formal promotion: **NO CHANGE / BLOCKED** until unchanged V47 raw acceptance passes both arms.
- Midterm diagnostic: CAP1000_PIT survived H1-to-H2 at the headline mean level but failed robustness to tail exclusion; treat as **weak / concentrated diagnostic support**, not a reason to relax data gates.
- V47 may still be worth completing as a clean PIT falsification/confirmation exercise because CAP1000_PIT has materially higher preserved-seed coverage than NOCAP, but the diagnostic does not justify additional tuning or acquisition-by-outcome choices.

## Next action
1. Freeze corrected H1/H2 as opened diagnostic evidence; no same-family retune and no corrected-basis NOCAP H2 opening.
2. Continue outcome-blind formal-data work only: verify whether any already-observed/provenance-compatible raw can close the unchanged required-pair gap, otherwise follow only preregistered legal/free acquisition-only routes.
3. Do not duplicate-trigger authoritative raw run `34849054884` while it remains queued/non-terminal.
4. Keep formal performance sealed until unchanged raw acceptance passes; if formal raw never becomes physically available, retain `NOT_COMPUTABLE_NO_INPUT_DATA` rather than weakening acceptance.
