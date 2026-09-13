# Tentei-inspired 4H V15 — regime-normalized representation drift gate — 2026-09-13

Research-only. No strategy-return metric was opened for V15. V15 H1/H2 strategy evaluation and all 2026 strategy outcomes remain closed.

## Parallel-lane boundary

Before V15 work, the latest branch commits were checked. The parallel ChatGPT lane was working on prospective-shadow evidence/reporting and ledger reconciliation, not V15 representation research. This lane therefore continued the V14-drift -> V15 representation path without duplicating the other lane.

## Frozen representation

Spec: `TENTEI_V15_REGIME_NORMALIZED_REPRESENTATION_SPEC.json`.

V12 candidate generation remained unchanged. V15 removed V14 features already classified as moderate/severe in the frozen outcome-free V14 drift audit and replaced them with:
- prior-20 same-symbol same-bin log ratios for range, prev4 range, BB width, and ATR;
- prior-20 empirical ranks for lower wick, distance from prior5 low in ATR units, prior5 RSI minimum, and prior5 Bollinger-position minimum.

Eight V14 low-drift features were retained unchanged.

The preregistered representation gate required:
- **zero SEVERE features**, and
- at most **four MODERATE features**.

Only if that gate passed could a separate V15 supervised-return evaluation be registered.

## Cohorts

After V12 candidate generation, prior-day price/volume gates, and all-16-feature finiteness:
- pre-2025 train-like cohort: **2,672 rows / 793 symbols**
- 2025 H1 cohort: **8,207 rows / 1,166 symbols**

The smaller pre-2025 cohort relative to V14 is expected because V15 normalized features require 20 prior comparable same-bin observations.

No return column was used.

## Drift result

**FAIL_REDESIGN_OUTCOME_FREE**

Summary:
- SEVERE: **3**
- MODERATE: **4**
- LOW: **9**

### Severe features

| Feature | KS | PSI | median shift / train IQR | Train median | H1 median |
|---|---:|---:|---:|---:|---:|
| `atr_rel20_log` | **0.315** | **0.588** | **+0.633** | 0.0046 | 0.2143 |
| `bb_width_rel20_log` | **0.284** | **0.496** | **+0.578** | 0.0514 | 0.4060 |
| `prev4_range_rel20_log` | **0.262** | **0.392** | **+0.601** | 0.0841 | 0.4485 |

Thus a simple ratio to the previous-20 median does not remove the volatility-regime shift.

### Moderate features

- `range_rel20_log`: KS 0.132, median shift +0.253 IQR.
- `dist_prior5_low_atr_rank20`: KS 0.117, median shift +0.286 IQR.
- `prior5_rsi_min_rank20`: KS 0.197, PSI 0.185, median shift -0.400 IQR.
- `prior5_band_min_rank20`: KS 0.120, PSI 0.117.

### Low-drift retained / rank features

Examples:
- `bar_log_return`: KS 0.052 / PSI 0.043.
- `bb_position`: KS 0.098 / PSI 0.093.
- `rsi12`: KS 0.068 / PSI 0.081.
- `rsi_delta`: KS 0.053 / PSI 0.038.
- `log_volume_rel20`: KS 0.062 / PSI 0.033.
- `lower_wick_rank20`: KS 0.041 / PSI 0.011.

## Decision

**REJECT V15 REPRESENTATION BEFORE ANY RETURN EVALUATION.**

No V15 supervised model is authorized from this representation.

The next outcome-free representation should replace the three severe log-ratio volatility features, and preferably `range_rel20_log` too, with bounded empirical prior-history percentile ranks. The candidate generator and all low-drift retained features remain unchanged.

This is a representation-stability decision only; it makes no claim about returns.

2026 outcomes opened: **false**.
Production modified: **false**.
