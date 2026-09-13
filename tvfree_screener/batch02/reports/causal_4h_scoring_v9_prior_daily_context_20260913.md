# Causal 4H Scoring V9 — prior-completed daily context — 2026-09-13

Research-only. No production writes. Historical 2026 outcomes were not opened.

## Frozen design

Preregistered before V9 row-level evaluation in `CAUSAL_4H_SCORING_V9_PRIOR_DAILY_CONTEXT_SPEC.json`.

V9 keeps the causal 4H/intraday representation primary (19 features) and adds only seven prior-completed-daily context features:
- d1/d5/d20 log return
- 20-session realized volatility
- 20-session close position
- 5-vs-20 volume log ratio
- prior-day range percent

All daily context is computed at `prior_date`; no current candidate-day finalized daily values are used.

The model schedule remains V6 monthly expanding causal refit with unchanged q10/q50/q90 tree parameters. Core ranks q50. Monster uses the V8 first Pareto front on q90/q10.

## Coverage

After the original causal intraday and prior-day liquidity/price gates:
- original 2025 candidate rows: 398,772
- rows with all 26 V9 features: **398,751 = 99.995%**

Thus the daily-context block does not materially reduce coverage.

## H1 walk-forward — March through June

All frozen Core and Monster Top1/2/3/5 policies fail.

### Core
- Top1: n=164, mean +1.30%, median -0.50%, win 45.1%, <=-10% 6.10%, Top3-removed mean -1.16%; FAIL.
- Top2: mean +0.75%, median -0.16%, win 47.0%, Top3-removed mean -0.56%; FAIL.
- Top3/5 means -0.19% / -0.44%; FAIL.

Positive top-line mean remains winner-driven and central/robustness gates fail.

### Monster
- Top1: n=164, mean **-3.41%**, median -6.16%, >=+20% **10.98%**, <=-10% 35.98%, Top1-excluded mean -3.95%; FAIL.
- Top2: mean -1.62%, >=+20% 8.84%, <=-10% 25.00%; FAIL.
- Top3: mean -1.11%, >=+20% 7.32%; FAIL.
- Top5: mean -0.67%, >=+20% 5.61%; FAIL.

The added daily context does not solve the central-loss problem; Monster is materially worse than V8 H1.

## Decision

**REJECT V9 after H1; do not open V9 H2.**

Because every preregistered policy already fails in the H1 discovery period, opening H2 for V9 would add no decision value and would only increase outcome exposure.

This result argues against adding more generic daily technical context to the current architecture. Keep the final system 4H/intraday-led.

Next research should return to an intraday feature that was intentionally held back for data-quality reasons: source-internal relative volume. Before any outcome test, audit whether a same-bin historical volume ratio can be made causally stable using raw intraday data and a log transform without relying on same-day finalized daily volume.

2026 outcomes opened: false.
Production modified: false.
