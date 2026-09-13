# Causal 4H Monster V8 — Pareto-front selection — 2026-09-13

Research-only. No production writes. Historical 2026 outcomes were not opened.

## Frozen rule

Preregistered before V8 selection metrics in `CAUSAL_4H_MONSTER_V8_PARETO_FRONT_SPEC.json`.

V8 reuses the unchanged V6 monthly causal q10/q50/q90 predictions and changes only Monster selection.

Within each date + bin cohort:
- maximize q90 (predicted upside quantile);
- maximize q10 (predicted downside quantile);
- remove every candidate dominated by another candidate on both objectives;
- use only the first nondominated Pareto front;
- rank the front by q90 descending, then q10, then symbol;
- do not backfill from dominated rows;
- retain the same Top1/2/3/5 and five-session cooldown.

No scalar risk coefficient or outcome-tuned threshold is used.

## H1 walk-forward — March through June

- Pareto-front rows: 5,057 / 133,399 = 3.79%.

TopN results at 0.5% cost:
- Top1: n=164, mean -1.44%, >=+20% 9.15%, <=-10% 23.78%, Top1-excluded -1.97%; FAIL.
- **Top2: n=328, mean +0.88%, >=+20% 10.06%, <=-10% 18.90%, Top1-excluded +0.56%; PASS all frozen Monster gates.**
- Top3: mean +0.16%, >=+20% 7.52%, Top1-excluded -0.06%; FAIL.
- Top5: mean -0.05%, >=+20% 5.37%; FAIL.

This is the first causal-4H architecture in the current sequence to satisfy all frozen Monster comparability gates on a named retrospective period.

## H2 retrospective — July through December

- Pareto-front rows: 10,757 / 206,871 = 5.20%.

- Top1: mean -1.92%, >=+20% 7.26%, <=-10% 28.63%, Top1-excluded -2.45%; FAIL.
- Top2: mean -1.28%, >=+20% 5.44%, <=-10% 22.78%, Top1-excluded -1.56%; FAIL.
- Top3: mean -0.30%, >=+20% 5.65%, <=-10% 17.20%, Top1-excluded -0.49%; FAIL.
- Top5: mean -0.42%, >=+20% 4.76%, <=-10% 14.11%, Top1-excluded -0.53%; FAIL.

## Decision

**REJECT V8 AS A STANDALONE PRODUCTION ARCHITECTURE.**

The H1 Top2 pass is meaningful retrospective evidence that the two-objective Pareto structure can balance right tail and downside without a tuned scalar penalty. However, it does not survive H2 and cannot be promoted.

The correct next step is not to choose Top2 from the exposed H1 result. Instead, diagnose whether the H1/H2 failure is associated with a causal regime/context variable already available at signal time. Any new regime rule must be preregistered separately and remains retrospective discovery only until prospective shadow evidence exists.

2026 outcomes opened: false.
Production modified: false.
