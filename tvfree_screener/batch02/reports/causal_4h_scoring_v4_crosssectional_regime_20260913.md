# Causal 4H Scoring V4 — cross-sectional regime / tail-first Monster — 2026-09-13

Research-only. No production writes. Historical 2026 outcomes were not opened.

## Frozen architecture

Preregistered before V4 row-level evaluation in `CAUSAL_4H_SCORING_V4_CROSSSECTIONAL_REGIME_SPEC.json`.

- Same seven causal raw 4H features as V1-V3.
- Added same-date + same-bin cross-sectional percentile ranks for the seven features plus current bin volume.
- Added causal cohort context: breadth positive, median bar return, median range, median range-vs-prior20.
- Same fixed AM/PM HistGradientBoosting parameters as V3.
- Core remains risk-adjusted: `logit(p_positive)-logit(p_loss10)`.
- Monster is tail-first: rank by `p_plus20`; `p_loss10` only breaks ties.
- 2025H2 is retrospective refutation only; it cannot promote the architecture.

Evaluator: `eval_causal_4h_scoring_v4.py`.

## H1 causal fold 1 — March-April

- Core Top1: n=82, mean -0.63%, median -0.25%, win 46.3%, <=-10% 3.66%. All Core policies FAIL.
- Monster Top1: n=82, mean -0.53%, median -2.03%, >=+20% **10.98%**, <=-10% 30.49%, Top1-excluded mean -1.43%. FAIL.
- Monster Top2/3/5 +20% rates: 6.10% / 7.72% / 6.34%. All FAIL.

The tail-first change restores right-tail capture, but central returns and robustness are poor.

## H1 causal fold 2 — May-June

- Core all policies FAIL. Best mean was Top2 -0.32%.
- Monster Top1: mean -1.09%, >=+20% 9.76%, <=-10% 29.27%, FAIL.
- Monster Top3: mean **+0.60%**, >=+20% 8.54%, <=-10% 21.14%, Top1-excluded mean +0.17%; fails the frozen >=10% tail gate.
- Monster Top5: mean **+0.76%**, >=+20% 7.32%, <=-10% 18.05%, Top1-excluded mean +0.42%; fails the tail gate.

## 2025H2 retrospective refutation

### Core
- Top1: n=248, mean -0.20%, median -0.50%, win 39.9%, <=-10% 0.40%.
- Top2/3/5 means: -0.11% / -0.12% / -0.18%.
- All gates FAIL.

### Monster
- Top1: n=248, mean **-1.71%**, median -4.28%, >=+20% **10.08%**, <=-10% 31.05%, Top1-excluded mean -2.24%.
- Top2: mean -1.14%, >=+20% 7.26%.
- Top3: mean -1.26%, >=+20% 7.93%.
- Top5: mean -0.95%, >=+20% 7.10%.
- All gates FAIL.

## Interpretation

V4 demonstrates a useful distinction:

- Cross-sectional/regime representation plus tail-first Monster ranking can recover the desired +20% frequency to about the 10% target at Top1.
- But the selected set has too many mediocre/losing names; the mean and top-winner-excluded mean stay negative.
- Therefore V3 was too defensive, while V4 is too permissive.

Decision: **REJECT V4 / NO PROMOTION**.

Do not tune a risk-weight coefficient between V3 and V4 against H2. The next hypothesis should avoid an arbitrary probability penalty and instead model the conditional return distribution directly.

## Reproduction hashes

- H1 fold1: `ebb47f75daf78b5f5e01baacdcf999a3f71479ffad66747f19ade6d4cdd01adc`
- H1 fold2: `f046c1a883959c21cb3fff789d9a25ce1c7302ce386d2448536b0e8471784df4`
- H2 retrospective: `6a9a6d9c6e55fb17127eec7a1e04cbbb9606037c3ad5f4339f11b5dab8e734e3`

## Next hypothesis

Use fixed quantile regression on the same causal 4H + cross-sectional context representation:
- q10 for downside,
- q50 for stable/Core central tendency,
- q90 for right-tail potential.
This models return magnitude directly instead of balancing two classification probabilities with a tunable risk coefficient.
