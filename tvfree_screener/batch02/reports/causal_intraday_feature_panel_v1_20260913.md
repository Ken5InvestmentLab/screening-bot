# Causal intraday feature panel v1 freeze — 2026-09-13

Research-only. No production writes. No strategy-return or precursor file was opened.

## Input and count-definition correction

The authorized Actions artifact contains 8,709 raw rows. The prior note that referred to 1,332 observed symbol-sessions mixed two populations:

- 1,324 symbol/date keys have normal hourly rows.
- 8 additional keys, all on 2026-09-11, contain only closing-snapshot rows.
- Therefore 1,332 is correct only for **all row types**, while **1,324 is the correct denominator for raw intraday clock-bin construction**.

This distinction is now frozen in the spec. Snapshot-only keys are not promoted into fake 4H bars.

## Materialized raw clock bins

From the 1,324 normal intraday symbol-sessions:

- AM `09/10/11/12` complete: **1,150**
- PM `13/14/15` complete: **1,155**
- total complete independent bins: **2,305**
- missing required-hour bin attempts: **343**

AM and PM are gated independently. A missing PM bin does not invalidate a complete AM bin and vice versa.

## Data-only feature distribution

No returns were consulted.

| feature | coverage | p01 | median | p99 |
|---|---:|---:|---:|---:|
| bar_log_return | 100% | -0.1519 | -0.0010 | +0.1407 |
| range_pct | 100% | 0.00475 | 0.03988 | 0.26270 |
| upper_wick_pct | 100% | 0 | 0.00888 | 0.11839 |
| lower_wick_pct | 100% | 0 | 0.00788 | 0.06664 |
| prev4_log_return_mean | 98.61% | -0.06960 | -0.00237 | +0.06341 |
| prev4_range_mean | 98.61% | 0.00915 | 0.04588 | 0.18929 |
| log_range_vs_prior20 | 86.12% | 0.21180 | 0.68294 | 2.27152 |

The raw `range_vs_prior20` reached 23.21 and `volume_rel20` reached 335.45. The range ratio is therefore log-transformed rather than hard-clipped. The volume ratio remains diagnostic-only.

## Redundancy audit

Spearman rank correlation on the feature panel showed:

- `body_pct` vs `body_to_range`: **0.928**
- `prev4_abs_body_mean` vs `prev4_range_mean`: **0.872**

Both redundant alternatives are excluded from v1. This is a dimensionality/robustness decision made without strategy outcomes.

## Frozen v1 model-candidate features

1. `bar_log_return`
2. `range_pct`
3. `upper_wick_pct`
4. `lower_wick_pct`
5. `prev4_log_return_mean`
6. `prev4_range_mean`
7. `log_range_vs_prior20`

All seven are required; no imputation is allowed. The 20-same-bin warmup makes **1,985 / 2,305 = 86.12%** of complete bins v1-eligible in this sample. The 320 unavailable rows are exactly the warmup cost across 8 symbols × 2 bins × 20 prior same-bin observations.

## Held back

- `close_location`: AM looked stable, but PM did not; omit from the unified v1 panel.
- `volume_rel20`: no same-day daily normalization is permitted before cutoff, prior-only absolute calibration remained noisy, and the source-internal ratio has an extreme right tail. Keep it diagnostic until semantics are stronger.
- absolute cross-bin/cross-day price deltas: deferred because split/adjustment discontinuities can contaminate them.
- current-day finalized daily H/L/C/volume: forbidden for an earlier feature cutoff.

## Important limitation

This 8-symbol artifact was selected around Monster examples and is **not representative of the whole TSE universe**. The feature engineering can be frozen from data-quality properties, but strategy performance must not be inferred from this sample. Before judging the v1 features, the next task is to locate or build a broader historical raw-intraday evaluation population without reopening the legacy mixed-provenance 4H sheet as if it were ground truth.

Local v1 panel SHA-256: `6fcc178be5d23d39126c053cc998a4cbca6ffedf07dc650c1c7875d22490b440`.
