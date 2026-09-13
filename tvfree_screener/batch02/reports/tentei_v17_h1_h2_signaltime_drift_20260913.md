# V17 H1-H2 signal-time drift audit — 2026-09-13

Research-only. No strategy-return values were used in this audit. 2026 outcomes remain closed.

## Frozen purpose

After V19 showed that the raw V12 ALL Core stream collapsed from H1 to H2, this audit asked whether the collapse was accompanied by ordinary covariate drift under the already-stable V17 representation.

Spec: `TENTEI_V17_H1_H2_SIGNALTIME_DRIFT_SPEC.json`.

## Cohorts

- H1: **8,227** feature-complete V12 events / **1,173** symbols / **82** active dates.
- H2: **12,418** feature-complete V12 events / **1,154** symbols / **124** active dates.
- events per active date: **100.33 -> 100.15**.
- AM share: **57.46% -> 60.67%**.

Thus event density is almost unchanged.

## Continuous V17 representation

Summary:
- SEVERE continuous features: **0**
- MODERATE continuous features: **2**
- LOW: **14**

All volatility-relative cross-sectional features remain LOW:
- `xrank_bb_width_pct`: KS 0.056 / PSI 0.016.
- `xrank_atr_pct`: KS 0.048 / PSI 0.011.
- `xrank_prev4_range_mean`: KS 0.023 / PSI 0.004.
- `xrank_range_pct`: KS 0.049 / PSI 0.013.

The only MODERATE continuous features are:
- `xrank_prior5_rsi_min`: KS 0.118 / PSI 0.233.
- `xrank_prior5_band_min`: KS 0.108 / PSI 0.205.

All eight retained absolute/relative features remain LOW.

## Trigger composition shift

- RSI recovery: **44.09% -> 52.64%**, +8.55pt — MODERATE.
- Trend flip: **8.59% -> 10.24%**, +1.65pt — LOW.
- Emergency reversal: **60.62% -> 44.44%**, **-16.17pt — SEVERE**.

Because the preregistered rule treats any >=10pt trigger-rate shift as material, the frozen decision is:

**MATERIAL_SIGNALTIME_SHIFT**

## Interpretation

The H2 collapse is **not** explained by broad instability of the V17 continuous representation. Same-date/bin market-relative features remain highly stable.

The material change is the mixture of V12 trigger families, especially the large drop in Emergency Reversal participation and corresponding increase in RSI Recovery share.

This suggests the next diagnostic should decompose H2 returns by the already-frozen V12 trigger paths, without changing any threshold:
- RSI_RECOVERY
- TREND_FLIP
- EMERGENCY_REVERSAL

If within-path performance remains similar to H1 but the mixture changed, composition drift is the main explanation. If the same paths themselves collapse, the problem is deeper concept drift within the trigger mechanisms.

No path should be promoted or threshold-tuned from this diagnostic.

2026 outcomes opened: false.
Production modified: false.
