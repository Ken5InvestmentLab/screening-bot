# Causal 4H Scoring V10 — source-internal relative volume — 2026-09-13

Research-only. No production writes. Historical 2026 strategy outcomes were not opened.

## Frozen design

Preregistered in `CAUSAL_4H_SCORING_V10_RELATIVE_VOLUME_SPEC.json`.

V10 returns to the intraday-only direction after V9:
- base 19 causal intraday/cross-sectional/context features;
- add only `log_volume_rel20`;
- add its same-date+bin percentile rank `xrank_log_volume_rel20`;
- no V9 prior-daily context;
- unchanged V6 monthly q10/q50/q90 model schedule;
- Core q50 ranking;
- Monster V8 q90/q10 Pareto-front selection.

The relative-volume feature is causal and source-internal only; current-day finalized daily volume is never used.

## Coverage

The raw broad audit produced 941,126 causal relative-volume rows.

For the frozen 2025 candidate panel:
- base candidate rows: 398,772
- V10 rows with all 21 features: **398,772 = 100%**

## H1 walk-forward — March through June

All frozen policies fail.

### Core
- Top1: n=164, mean +2.62%, median -0.50%, win 45.1%, <=-10% 4.27%, Top3-removed mean -0.46%; FAIL.
- Top2: mean +1.36%, median -0.50%, win 44.8%, Top3-removed mean -0.18%; FAIL.
- Top3: mean +0.62%, median -0.50%; FAIL.
- Top5: mean +0.24%, median -0.40%; FAIL.

Again, positive mean is dominated by a few extreme winners rather than central stability.

### Monster
- Top1: n=164, mean -1.44%, >=+20% 9.76%, <=-10% 28.66%, Top1-excluded -1.98%; FAIL.
- Top2: mean **-0.49%**, >=+20% **9.15%**, <=-10% 21.34%, Top1-excluded -0.82%; FAIL.
- Top3: mean -0.44%, >=+20% 7.11%; FAIL.
- Top5: mean -0.23%, >=+20% 6.10%; FAIL.

## Decision

**REJECT V10 after H1; H2 remains unopened for V10.**

The relative-volume feature passes data-quality requirements but does not rescue the all-bin ranking architecture. Keep the feature available for future event-gated experiments, but do not assume it has standalone predictive value.

The next hypothesis changes the candidate-generation architecture rather than adding another feature: create a causal 4H reversal/ignition event gate, then score only those event rows.

2026 outcomes opened: false.
Production modified: false.
