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
- Simple breadth regime switch: failed in 2026; rejected.
- 10BD Meta gate based on recent Low-Vol Core results: did not improve robustness; rejected for now.

Current reproducible research candidates in `v3_swing.py`:

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

### Swing Attack — MomCross transition event

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

2026 March-August contaminated check:

- mean: about +0.85%
- +10% rate: about 19.1%
- +20% rate: about 9.6%
- -10% rate: about 20.2%

Interpretation: MomCross retains an Attack-like large-winner profile, but loss risk is too high to promote to production.

## Next research direction

The evidence so far says that a daily Top-1 Swing model is structurally too noisy. The next Swing iteration should keep event/transition detection as the first-stage universe, then develop a future-safe risk/quality gate inside those events. Do not tune that gate from 2026 alone.
