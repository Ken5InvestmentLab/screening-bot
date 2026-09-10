# TV-Free V3 research status (TEST ONLY)

This document records the handoff state without pretending that unrecovered parameters are known.

## Guardrails

- Branch: `test/tvfree-screener-v1`
- Draft PR: #13
- No merge to `main` without explicit user Go approval.
- No production Discord or Spreadsheet writes.
- No modification of production Stable★6 / Sniper / Mega / TradingView flows.
- Primary realistic entry is next trading session open.
- 2026 has already been inspected during research, so it is not a pristine holdout.

## V3 Short (5BD) — reference result from the previous research session

Known 2026 March-August result with one-business-day cooldown:

- n: 29
- next-open -> 5BD mean: +5.42%
- median: +2.06%
- win rate: 65.5%
- +10% rate: 13.8%
- -10% rate: 6.9%

Known architecture:

1. Core: monthly-updated relative-ranking model.
2. Meta: uses only already-confirmed recent Core outcomes; previous handoff states a recent-40 style gate.
3. Attack: enabled only when Meta is ON; intended to catch large winners.
4. Deep Reversal: fallback lane during Meta OFF periods.
5. One-business-day same-symbol cooldown.

Important: the exact Short V3 parameter set/thresholds was not committed to PR #13 and no PR comments contain it. Therefore this branch must not claim an exact reproduction yet. Reconstruct and revalidate it from data rather than inventing missing values.

## V3 Swing (10BD) research findings

Rejected during continuation:

- Fixed XGBoost relative-ranking model: regime decay inside 2025H2.
- Monthly-retrained multi-head classifiers using absolute probability scales: rejected.
- Monthly-retrained classifiers converted to daily percentiles: rejected at useful sample sizes.
- Continuous relative-rank XGB regression: rejected.
- Static Trend T2 factor: strong in 2025H2 but failed in 2026; rejected.
- Simple breadth regime switch: failed in 2026 when used as a standalone engine.
- 10BD Meta gate based only on recent 10BD outcomes: too slow to recover after regime changes; rejected.
- 5BD outcome-only Meta gate: reacts faster but still selected early bad trades and over-stopped recovery; rejected as a standalone gate.
- Big-winner / +20% classifier Attack variants: good development numbers did not survive the fixed 2026 side; rejected.
- Six intuitive 10BD Deep Reversal rule families: failed to remain positive across development and validation; rejected.

Current reproducible baseline candidates in `v3_swing.py`:

### Swing Core — Low-Vol Momentum

Cross-sectional score:

- 25% ret10 percentile
- 20% ret20 percentile
- 15% pos60 percentile
- 20% inverse ATR14% percentile
- 10% inverse volr20 percentile
- 10% MA20-gap percentile

Pre-2026 half-year mean 10BD returns observed during research:

- 2024H1: +1.35%
- 2024H2: +0.06%
- 2025H1: +0.60%
- 2025H2: +2.06%

This is defensive and stable pre-2026, but 2026 March-August was only about +0.10%, so it is not strong enough alone.

### Swing Attack baseline — MomCross transition event

Event definition:

- previous 5-day return <= 0
- current 5-day return >= +5%
- current 1-day return >= +3%
- 60-day range position >= 0.50
- volume / 20-day average between 0.80 and 5.00
- RSI14 <= 82

Within event candidates, rank by the defensive Core score and select one per day with one-day same-symbol cooldown.

Pre-2026 half-year mean 10BD returns observed during research:

- 2024H1: +4.59%
- 2024H2: +0.63%
- 2025H1: +0.76%
- 2025H2: +1.78%

2026 March-August contaminated check from the earlier baseline:

- mean: about +0.85%
- +10% rate: about 19.1%
- +20% rate: about 9.6%
- -10% rate: about 20.2%

Interpretation: MomCross retains an Attack-like large-winner profile, but loss risk is too high without a second-stage quality mechanism.

## V3 Swing v2 — current leading 10BD candidate

Implemented in `v3_swing_v2.py`.

Architecture:

1. MomCross event filter.
2. Semiannual event-quality model; every training row's 10BD outcome must end before the prediction half-year begins.
3. Return-regression prediction and -10% loss prediction are converted to empirical CDF percentiles using that period's training prediction distribution.
4. `score_R = cdf_return - cdf_loss10`; raw model probabilities are never thresholded.
5. Breadth Meta: require more than 40% of the TSE candidate universe to be above MA20 at signal close.
6. Daily best MomCross event, with one-selection-day same-symbol cooldown.
7. Swing S gate: `score_R >= 0.20`.

The score threshold was checked only with pre-2026 periods using a coarse fixed sweep `[-0.50, -0.25, 0.00, 0.10, 0.20, 0.30]`. A minimum of 30 signals was required in both 2025H1 development and 2025H2 validation. Under the locked robust utility, 0.20 was the best eligible threshold before looking at the fixed-side report.

Observed next-open -> 10BD results for the locked Swing S candidate:

### 2025H1 development

- n: 33
- mean: +2.68%
- median: +2.12%
- win rate: 57.6%
- +10% rate: 15.2%
- -10% rate: 6.1%

### 2025H2 validation

- n: 31
- mean: +1.95%
- median: -0.70%
- win rate: 45.2%
- +10% rate: 16.1%
- -10% rate: 6.5%

### 2026 March-August contaminated fixed-side check

- n: 30
- mean: +1.42%
- median: +1.63%
- win rate: 60.0%
- +10% rate: 10.0%
- -10% rate: 3.3%
- max: about +17.5%

Interpretation: this is not a Stable★6-level large-winner engine. It is currently the most credible defensive 10BD Swing S candidate because its median/win/loss profile survives into 2026 much better than prior Swing models. It should remain research-only until a new untouched forward period exists.

The same Swing S candidates weaken at 20BD and especially 40BD, so this lane should be treated as a 10BD-specific engine rather than a generic long-hold strategy.

## Next research direction

- Keep `v3_swing_v2.py` as the current Swing S candidate and do not retune it from 2026.
- Continue searching for a separate Swing A / Attack lane; do not weaken Swing S merely to capture large winners.
- Favor a genuinely different event family for Attack rather than increasingly tuning MomCross to the already-seen 2026 winners.
- Preserve 5BD V3 Short separately; its exact missing parameters still need reconstruction/revalidation before claiming exact reproducibility.
- Final promotion remains blocked until explicit user Go approval and a genuinely new forward period is available.
