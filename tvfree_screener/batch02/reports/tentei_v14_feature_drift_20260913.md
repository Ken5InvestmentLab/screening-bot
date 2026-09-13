# V14 outcome-free feature-distribution drift audit — 2026-09-13

Research-only. No strategy returns were opened for this audit. V14 H2 and all 2026 strategy outcomes remain closed.

## Parallel-lane check

Before starting this audit, the parallel ChatGPT lane was rechecked. Its latest work was on prospective-shadow CLI/export contracts and the separate V12 state-entry representation. No V14 feature-drift audit was present, so this lane proceeded without duplicating work.

## Frozen audit

Spec: `TENTEI_V14_FEATURE_DRIFT_SPEC.json`.

Cohorts:
- pre-2025 V14 model-fit-like feature cohort: **4,924 rows / 966 symbols**
- 2025 H1 feature-complete V12 cohort: **8,227 rows / 1,173 symbols**
- AM share: **60.78% -> 57.46%**

No return column was used. The comparison uses only the fixed 19 V14 causal intraday features plus signal-time cohort membership.

Frozen severe-drift criteria for continuous features:
- KS >= 0.20, or
- PSI >= 0.25, or
- absolute median shift >= 0.50 training IQR.

Binary trigger flags are severe at absolute rate change >= 10 percentage points.

## Result: MATERIAL_COVARIATE_SHIFT

Four continuous features are severe and one trigger flag is severe.

### Severe continuous features

| Feature | KS | PSI | median shift / train IQR | Train median | H1 median |
|---|---:|---:|---:|---:|---:|
| prev4_range_mean | **0.269** | **0.395** | **+0.653** | 0.01757 | 0.02643 |
| bb_width_pct | **0.332** | **0.651** | **+0.927** | 0.08135 | 0.13949 |
| atr_pct | **0.281** | **0.448** | **+0.667** | 0.01860 | 0.02693 |
| prior5_rsi_min | 0.187 | **0.270** | -0.166 | 30.85 | 29.57 |

The first three all point in the same direction: the H1 V12 event population is materially higher-volatility than the pre-2025 population used to fit V14.

### Severe trigger-composition shift

- `trigger_emergency_reversal`: **47.54% -> 60.62%**, change **+13.07 percentage points** — SEVERE.
- `trigger_rsi_recovery`: 51.08% -> 44.09%, -6.99pt — MODERATE.
- `trigger_trend_flip`: 8.55% -> 8.59%, essentially unchanged.

### Moderate continuous shifts

- `range_pct`: KS 0.130, median shift +0.271 IQR.
- `lower_wick_pct`: KS 0.100.
- `dist_prior5_low_atr`: KS 0.148, PSI 0.111.
- `prior5_band_min`: KS 0.137, PSI 0.156.

### Stable / low-drift examples

`bar_log_return`, `close_location`, `prev4_log_return_mean`, `bb_position`, `rsi12`, `rsi_delta`, and `log_volume_rel20` remained in the frozen LOW tier.

Notably, source-internal relative volume is stable across the two cohorts:
- train median 0.789
- H1 median 0.797
- KS 0.031
- PSI 0.014.

## Interpretation

The V14 failure is consistent with material covariate shift, especially in volatility-scale/state variables. This does **not** prove that covariate shift alone caused the negative V14 selections, because this audit deliberately does not inspect outcomes.

However, it makes another fixed absolute-feature supervised model trained only on Sep-Dec 2024 a poor next choice.

The next architecture should first make the event representation less regime-sensitive. A clean candidate is a preregistered V15 that replaces the severe absolute volatility-state inputs with causal relative/rank representations derived only from prior completed intraday history or same-date+bin cross-sectional ranks, while keeping V12 candidate generation unchanged. Any V15 H1 evaluation remains retrospective discovery and cannot be promoted without prospective shadow evidence.

2026 outcomes opened: **false**.
Production modified: **false**.
