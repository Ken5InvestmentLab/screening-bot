# Consensus target-alignment audit — 2026-09-14

Research-only diagnostic. No model is retrained and no policy is selected from this audit.

## Structural mismatch

Current Consensus heads are trained on `perf_5bd`:

- entry = reconstructed signal-bin close;
- exit = D+5 official daily close.

The cross-lane canonical comparison endpoint is now:

- entry = next official XTKS session open;
- exit = D+5 official daily close.

Therefore the current model is evaluated on a stricter target than the one it was trained to predict.

## ATR-gated raw 2025 selections

n=101.

- signal-close -> D+5 mean: **+8.28%**
- next-open -> D+5 mean: **+7.72%**
- difference: **+0.56 percentage points** in favor of signal-close entry
- mean overnight move from signal close to next open: +0.52%
- median overnight move: +0.42%
- median absolute overnight move: 1.96%
- 90th percentile absolute overnight move: 5.01%
- return correlation between the two endpoints: 0.966
- sign changes between endpoints: 8.91%

The raw ranking remains directionally similar under next-open returns:
- Spearman p_hit10 vs signal-close return: +0.477
- Spearman p_hit10 vs next-open return: +0.485
- Spearman pred_ret vs signal-close: +0.363
- Spearman pred_ret vs next-open: +0.350
- Spearman cons_min vs signal-close: +0.484
- Spearman cons_min vs next-open: +0.498

## Correct one-position-per-symbol 5-session cooldown

n=52, no replacement.

- signal-close -> D+5 mean: **+4.13%**
- next-open -> D+5 mean: **+3.05%**
- difference: **+1.08 percentage points**
- mean overnight move: +1.04%
- median overnight move: +0.89%
- median absolute overnight move: 2.08%
- 90th percentile absolute overnight move: 5.11%
- return correlation: 0.955
- endpoint sign changes: **13.46%**
- signal-close positive but next-open nonpositive: 9.62%
- signal-close nonpositive but next-open positive: 1.92%

Score rank relationships on this non-overlapping sample:
- p_hit10: +0.386 signal-close vs +0.390 next-open
- pred_ret: +0.299 vs +0.286
- cons_min: +0.222 vs +0.198

Thus target mismatch costs meaningful return, but the model ranking is not completely destroyed.

## 2025 Jul-Dec

5-session cooldown, n=22:

- signal-close mean +4.13%
- next-open mean +3.58%
- difference +0.55 percentage points
- mean overnight move +0.45%
- endpoint sign changes 4.55%
- return correlation 0.962

p_hit10 and pred_ret rank relationship is at least as strong against next-open return in this small H2 sample. This is descriptive only.

## Decision

1. V44 remains interpretable because it uses one fixed model/ranking and judges all cooldown policies on the same canonical next-open endpoint.
2. Do not change V44 training target mid-experiment.
3. If Consensus survives V44 and the data-contract checks, a future version should align the **training label itself** with next-open -> D+5.
4. That future model must keep architecture/hyperparameters frozen initially; do not use already-opened 2025/2026 outcomes to retune the model while changing the target.
5. A canonical-target retrain is a new versioned experiment, not a correction that can be silently substituted into V43/V44.

The target-aligned experiment should only be activated after V44 disposition; otherwise a failing V44 must not be rescued post-hoc by target redesign.
