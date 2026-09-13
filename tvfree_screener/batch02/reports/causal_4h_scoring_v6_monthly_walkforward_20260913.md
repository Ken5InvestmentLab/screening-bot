# Causal 4H Scoring V6 — monthly expanding walk-forward — 2026-09-13

Research-only. No production writes. Historical 2026 outcomes were not opened.

## Frozen architecture

Preregistered before V6 row-level evaluation in `CAUSAL_4H_SCORING_V6_MONTHLY_WALKFORWARD_SPEC.json`.

V6 changes exactly one thing from V5: model refresh cadence.

At the beginning of each calendar month:
- fit the unchanged V5 AM/PM q10/q50/q90 HistGradientBoosting regressors;
- use candidate rows from 2025-01-01 up to the prior month only;
- require each training row's five-session exit date to be strictly before the evaluation month start;
- score only the current month;
- concatenate monthly scores;
- apply the same Top1/2/3/5 and five-session cooldown continuously across month boundaries within the named evaluation period.

No hyperparameter, feature, q-level, score formula or threshold was changed.

## Causal maturity verification

Examples:
- March model: max train candidate 2025-02-20; max train exit 2025-02-28.
- April: max exit 2025-03-31.
- May: max exit 2025-04-30.
- June: max exit 2025-05-30.
- July: max exit 2025-06-30.
- August: max exit 2025-07-31.
- September: max exit 2025-08-29.
- October: max exit 2025-09-30.
- November: max exit 2025-10-31.
- December: max exit 2025-11-28.

Thus no current-month/future 5BD label entered monthly training.

## H1 walk-forward — March through June

133,399 candidate rows were scored.

### Core
- Top1: n=164, net mean **+1.73%**, median -0.50%, win 44.5%, <=-10% 5.49%, Top3-removed mean -1.17%; FAIL.
- Top2: mean +0.64%, median -0.50%, win 45.7%; FAIL.
- Top3: mean +0.56%; FAIL.
- Top5: mean +0.34%; FAIL.

The positive Core means are driven by a small number of very large winners; the central and winner-removed metrics fail.

### Monster
- Top1: n=164, net mean **+1.28%**, median -0.50%, >=+20% **6.71%**, <=-10% 10.98%, Top1-removed mean **+0.38%**; FAIL only because the right-tail frequency remains below the frozen 10% objective and robustness gates are not all satisfied.
- Top2: mean +0.10%, +20% 5.49%; FAIL.
- Top3: mean -0.21%; FAIL.
- Top5: mean -0.23%; FAIL.

Monthly retraining improves Top1 stability relative to some static periods, but does not restore enough +20% capture.

## H2 retrospective walk-forward — July through December

The H2 period is retrospective/refutation-only and cannot promote V6.

### Core
- Top1: n=248, mean -0.40%, median -0.50%, win 41.5%, <=-10% 1.21%; FAIL.
- Top2/3/5 means: -0.50% / -0.46% / -0.52%; all FAIL.

### Monster
- Top1: n=248, mean **-1.87%**, median -2.85%, >=+20% **4.03%**, <=-10% 17.34%, Top1-removed mean -2.09%; FAIL.
- Top2: mean -1.29%, +20% 4.23%; FAIL.
- Top3: mean -0.73%, +20% 4.70%; FAIL.
- Top5: mean -0.54%, +20% 4.76%; FAIL.

## Interpretation

**REJECT V6 / NO PROMOTION.**

Monthly model refresh does not solve the H2 deterioration. Therefore the main failure is not simply stale model weights.

A useful clue remains from earlier architectures:
- V4 tail-first ranking can recover roughly 10% +20% frequency but admits too many losing candidates.
- V5/V6 quantile ranking improves downside/mean in some H1 periods but loses tail frequency.

The next preregistered hypothesis should combine those ideas structurally rather than tune a continuous risk coefficient: require a nonnegative predicted median (q50 >= 0) as a broad central-case viability gate, then rank surviving Monster candidates by q90. This asks for both a plausible ordinary outcome and exceptional upside without fitting a penalty weight.

## Reproduction

- H1 aggregate JSON SHA-256: `f5c44e192dde2b951e46df29b28501168c79ed9bd4e22e12920472ead493ee15`
- H2 aggregate JSON SHA-256: `02fe6a44c8c34901aa6aeedc39abd835211e85e7ddb807a301e9491317849a2c`
- March maturity metadata SHA-256: `41a6c3419033815c1eb0053f1c4a6bb58b07a7e0a62c8f0c9f4d25c332b6e1f1`
- December maturity metadata SHA-256: `6a18317920e69a320a1326774012c671e0873a53cfe2747173b41e631f36c3c1`

Evaluator: `eval_causal_4h_scoring_v6.py`.
