# Causal 4H Monster V7 — median viability then tail rank — 2026-09-13

Research-only. No production writes. Historical 2026 outcomes were not opened.

## Frozen rule

Preregistered before V7 selection metrics in `CAUSAL_4H_MONSTER_V7_MEDIAN_VIABILITY_TAIL_SPEC.json`.

V7 did not retrain any model. It reused the already-frozen V6 monthly q10/q50/q90 scores and changed Monster selection only:

1. keep rows with predicted q50 >= 0;
2. within each date + bin cohort, rank by predicted q90 descending;
3. tie-break by q50 descending then symbol;
4. no backfill if the viability gate leaves fewer than TopN names;
5. keep the same five-session cooldown and 0.5% cost.

The q50 threshold was fixed before the V7 metrics were opened and is not adjusted from these results.

## H1 walk-forward — March through June

- Viable rows: 73,272 / 133,399 = 54.93%.
- Top1: n=125, net mean **+1.31%**, median -0.50%, win 39.2%, >=+20% **7.20%**, <=-10% 12.0%, Top1-excluded mean **+0.11%**. FAIL.
- Top2: mean +0.31%, >=+20% 5.31%, Top1-excluded -0.30%. FAIL.
- Top3: mean +0.75%, >=+20% 6.32%, Top1-excluded +0.34%. FAIL.
- Top5: mean -0.17%, >=+20% 4.00%. FAIL.

The gate preserves some mean robustness but reduces right-tail frequency below the 10% target.

## H2 retrospective — July through December

- Viable rows: 87,277 / 206,871 = 42.19%.
- Top1: n=146, net mean **-1.66%**, median -1.05%, win 39.7%, >=+20% **3.42%**, <=-10% 19.86%, Top1-excluded mean -2.00%. FAIL.
- Top2: mean -1.30%, >=+20% 2.78%. FAIL.
- Top3: mean -1.24%, >=+20% 2.09%. FAIL.
- Top5: mean -1.43%, >=+20% 1.97%. FAIL.

## Decision

**REJECT V7 / NO PROMOTION.**

A hard q50 >= 0 viability gate removes too much of the Monster right tail and does not solve H2 central-return weakness. Do not tune the q50 threshold against 2025.

The next hypothesis should preserve tail candidates while eliminating only candidates that are clearly dominated on both upside and downside dimensions. A weight-free Pareto selection is a better structural next step than another scalar risk coefficient.

2026 outcomes opened: false.
Production modified: false.
