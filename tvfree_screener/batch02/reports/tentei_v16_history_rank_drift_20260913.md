# Tentei-inspired 4H V16 — prior-history rank representation drift gate — 2026-09-13

Research-only. No strategy-return metric was opened for V16. V16 H1/H2 returns and all 2026 strategy outcomes remain closed.

## Parallel-lane boundary

Before V16 work, the latest branch commits were checked. The parallel ChatGPT lane was working on prospective-shadow evidence/reporting and ledger reconciliation, not V16 representation research. No duplicate V16 experiment was found.

## Frozen representation

Spec: `TENTEI_V16_HISTORY_RANK_REPRESENTATION_SPEC.json`.

V12 candidate generation remained unchanged.

V16 retained eight low-drift V14 features:
- bar_log_return
- upper_wick_pct
- close_location
- prev4_log_return_mean
- bb_position
- rsi12
- rsi_delta
- log_volume_rel20

The eight V14/V15 volatility/state features were represented only as bounded empirical ranks against the previous 20 complete bins for the same symbol and same AM/PM bin.

The preregistered representation gate required:
- zero SEVERE features;
- at most four MODERATE features.

## Cohorts

After V12 candidate generation, prior-day price/volume gates and all 16 V16 features finite:
- pre-2025 train-like: **2,672 rows / 793 symbols**
- 2025 H1: **8,207 rows / 1,166 symbols**

No strategy-return column was used.

## Result

**FAIL_REDESIGN_OUTCOME_FREE**

Summary:
- SEVERE: **1**
- MODERATE: **5**
- LOW: **10**

### Severe

`bb_width_pct_rank20`
- KS **0.2015**
- PSI 0.1738
- median shift **+0.4167 train IQR**
- train median 0.55
- H1 median 0.80

It is only narrowly over the frozen KS severe threshold of 0.20, but the threshold was preregistered and is not relaxed post hoc.

### Moderate

- `atr_pct_rank20`: KS **0.1986**, PSI 0.1735, median shift +0.400 IQR.
- `prev4_range_mean_rank20`: KS **0.1950**, PSI 0.1885, median shift +0.333 IQR.
- `dist_prior5_low_atr_rank20`: KS 0.1166, median shift +0.286 IQR.
- `prior5_rsi_min_rank20`: KS **0.1975**, PSI 0.1847, median shift -0.400 IQR.
- `prior5_band_min_rank20`: KS 0.1196, PSI 0.1172.

### Low-drift

Notable low-drift features include:
- `range_pct_rank20`: KS 0.0704 / PSI 0.0502.
- `lower_wick_pct_rank20`: KS 0.0409 / PSI 0.0112.
- `bar_log_return`: KS 0.0518 / PSI 0.0434.
- `bb_position`: KS 0.0984 / PSI 0.0927.
- `rsi12`: KS 0.0681 / PSI 0.0814.
- `rsi_delta`: KS 0.0528 / PSI 0.0379.
- `log_volume_rel20`: KS 0.0617 / PSI 0.0333.

## Interpretation

V16 materially improves stability versus V15, but same-symbol prior-20 ranking still carries market-wide volatility-regime information. In 2025 H1, BB width / ATR / recent range are simultaneously high for many names, so a large fraction of symbols sit near the top of their own recent history.

The next outcome-free representation should therefore remove the common market component directly: compute same-date + same-bin cross-sectional percentile ranks across the eligible TSE candidate universe at the 4H cutoff.

## Decision

**REJECT V16 REPRESENTATION BEFORE ANY RETURN EVALUATION.**

No V16 supervised-return evaluation is authorized.

2026 outcomes opened: false.
Production modified: false.
