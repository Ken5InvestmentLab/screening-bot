# Tentei-inspired 4H V17 — same-date/bin cross-sectional rank drift gate — 2026-09-13

Research-only. No strategy-return metric was opened for V17. V17 H1/H2 strategy evaluation and all 2026 strategy outcomes remained closed during this representation audit.

## Parallel-lane boundary

Before V17, the latest branch commits were checked again. The parallel ChatGPT lane remained on prospective-shadow evidence/reporting and ledger reconciliation, not cross-sectional representation research. No duplicate V17 experiment existed.

## Frozen representation

Spec: `TENTEI_V17_CROSSSECTIONAL_RANK_REPRESENTATION_SPEC.json`.

V12 candidate generation remained unchanged.

The eight V14 features that showed moderate/severe drift were converted to same-date + same-bin cross-sectional percentile ranks. The rank universe is all complete causal AM/PM bins satisfying the same prior-day close/volume gates, not only V12 signals.

Causal timing:
- AM rank after the 09:00-13:00 raw clock bin is complete;
- PM rank after the conservative 16:00 cutoff;
- no candidate-day finalized daily OHLCV is used.

Eight already-low-drift features remained in absolute/relative form.

## Cohorts

Cross-sectional rank universe:
- **283,750** eligible bin rows
- **181** dates
- **1,248** symbols

Feature-complete V12 event cohorts:
- pre-2025 train-like: **4,924 rows / 966 symbols**
- 2025 H1: **8,227 rows / 1,173 symbols**

No strategy-return column was used.

## Result

**PASS_TO_SUPERVISED_PREREGISTRATION**

Frozen summary:
- SEVERE: **0**
- MODERATE: **1**
- LOW: **15**

The preregistered gate required zero severe and <=4 moderate, so V17 passes comfortably.

### Previously problematic volatility features are now LOW

| Feature | KS | PSI | median shift / train IQR | Tier |
|---|---:|---:|---:|---|
| xrank_bb_width_pct | 0.0614 | 0.0272 | -0.076 | LOW |
| xrank_atr_pct | 0.0329 | 0.0091 | -0.059 | LOW |
| xrank_prev4_range_mean | 0.0346 | 0.0100 | -0.044 | LOW |
| xrank_range_pct | 0.0402 | 0.0117 | -0.073 | LOW |
| xrank_dist_prior5_low_atr | 0.0464 | 0.0212 | -0.006 | LOW |
| xrank_prior5_band_min | 0.0741 | 0.0793 | -0.069 | LOW |

### Only moderate feature

`xrank_prior5_rsi_min`
- KS 0.0829
- PSI **0.1365**
- median shift -0.036 IQR
- tier: MODERATE

### Stable retained features

All eight retained V14 low-drift features remain LOW. In particular:
- `log_volume_rel20`: KS 0.0308 / PSI 0.0138
- `rsi12`: KS 0.0608 / PSI 0.0285
- `bb_position`: KS 0.0787 / PSI 0.0408
- `bar_log_return`: KS 0.0620 / PSI 0.0585

## Interpretation

V17 directly removes the common market volatility component that defeated V15/V16. The 2025 H1 event population may be in a higher absolute-volatility regime, but the event's position relative to the same-date same-bin market is much more stable.

This is the first representation in the V14->V17 sequence to pass the preregistered outcome-free stability gate.

Passing the drift gate is **not** evidence of return predictiveness. It only authorizes a separately preregistered supervised evaluation.

## Decision

**PASS REPRESENTATION GATE.**

The next allowed step is a separately frozen V17 supervised evaluation using the unchanged V14 training/evaluation architecture:
- train only on resolved pre-2025 V12 events;
- same +20% and <=-10% dual classifiers;
- same fixed tree parameters;
- same Pareto selection and Top1/2/3/5;
- only the feature representation changes to V17.

2026 outcomes opened: false.
Production modified: false.
