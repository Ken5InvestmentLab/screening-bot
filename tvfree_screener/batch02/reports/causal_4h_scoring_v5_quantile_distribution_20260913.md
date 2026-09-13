# Causal 4H Scoring V5 — quantile-distribution architecture — 2026-09-13

Research-only. No production writes. Historical 2026 outcomes were not opened.

## Frozen architecture

Preregistered before V5 row-level evaluation in `CAUSAL_4H_SCORING_V5_QUANTILE_DISTRIBUTION_SPEC.json`.

- Same causal 4H + cross-sectional/context representation as V4.
- Separate AM/PM HistGradientBoostingRegressor models for q10 / q50 / q90 of continuous gross 5BD return.
- No return clipping and no imputation.
- Quantile crossing is corrected deterministically by sorting the three per-row predictions.
- Core score = predicted q50.
- Monster score = q90 + min(q10, 0), a unit-consistent upside-minus-downside score.
- Same Top1/2/3/5, five-session cooldown, prior-day price/liquidity gates and 0.5% primary cost.
- 2025H2 remains retrospective refutation only and cannot promote the model.

Evaluator: `eval_causal_4h_scoring_v5.py`.

## H1 causal fold 1 — March-April

- Raw quantile crossing rate: 0%.
- Core all policies FAIL. Top1 mean -1.25%, median -0.50%, win 43.9%.
- Monster Top1: n=82, mean **+1.78%**, median -0.50%, >=+20% 3.66%, <=-10% 10.98%, Top1-excluded mean -0.04%. FAIL.
- Monster Top2/3 means +0.60% / +0.51%, but right-tail rates remained below 6% and Top1-excluded means were negative.

This fold shows a large-winner dependency rather than broad tail capture.

## H1 causal fold 2 — May-June

- Raw quantile crossing rate: 0.063%.
- Core Top2/3/5 means +0.09% / +0.33% / +0.33% but median remained negative and Top3-removed mean did not pass. All Core gates FAIL.
- Monster Top1: n=82, mean **+3.35%**, >=+20% **9.76%**, <=-10% 9.76%, Top1-excluded mean **+2.03%**. It narrowly misses the frozen 10% right-tail gate.
- Monster Top2: mean +1.10%, +20% 6.71%.
- Monster Top5: mean +1.14%, +20% 6.83%, Top1-excluded mean +0.96%.
- All frozen gates formally FAIL, but this is materially stronger than V3/V4 in the later H1 regime.

## 2025H2 retrospective refutation

- Raw quantile crossing rate: 1.37%.

### Core
- Top1: n=248, mean -0.22%, median -0.50%, win 44.0%, <=-10% 2.02%.
- Top2/3/5 means -0.35% / -0.52% / -0.47%.
- All gates FAIL.

### Monster
- Top1: n=248, mean **-0.05%**, median -2.24%, >=+20% 6.05%, <=-10% 16.94%, Top1-excluded mean -0.48%.
- Top2/3/5 means -0.55% / -0.44% / -0.65%.
- All gates FAIL.

## Interpretation

V5 is the strongest Monster architecture so far in H1 fold2: it produced positive mean, positive Top1-excluded mean and much lower downside while nearly reaching the +20% gate. However, a single static model trained through June decays badly across H2.

This suggests a **model-staleness/regime-adaptation** problem rather than a simple need for more risk penalties or threshold changes.

Decision: **REJECT STATIC V5 / NO PROMOTION**.

Do not tune q-levels, tree parameters, or score weights against H2. The next hypothesis keeps the entire V5 model fixed but changes only the production-realistic training schedule: monthly expanding causal retraining using only labels matured before each month begins.

## Reproduction hashes

- H1 fold1: `ad16fbc3ea3c7b370cf92fd0cf78af293f7d668795d10863ddf1e347492c9d4d`
- H1 fold2: `36b6e34fa67c35cfae07a34542b45cdcdcb83799b25237156f9144ecc3f47e2b`
- H2 retrospective: `09a9152fa4a676072a9756af3c0d9dea42e70873f3d7162bfd2de4b7e4b74447`

## Next

V6: monthly expanding walk-forward V5. At each calendar month start, retrain the unchanged q10/q50/q90 AM/PM models using only rows whose 5BD exit date is strictly before that month start. Score only that month's candidates, concatenate all monthly scores, and apply the same TopN/cooldown policies across the entire evaluation period without resetting cooldown at month boundaries.
