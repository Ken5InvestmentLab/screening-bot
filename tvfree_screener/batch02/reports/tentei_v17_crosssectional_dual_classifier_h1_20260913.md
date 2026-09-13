# Tentei-inspired 4H V17 — cross-sectional dual-classifier H1 result — 2026-09-13

Research-only. No production writes. Historical 2026 strategy outcomes were not opened.

## Frozen setup

V17's representation first passed the preregistered outcome-free drift gate (0 severe / 1 moderate feature). Only after that pass, the supervised evaluation was separately preregistered in `TENTEI_V17_CROSSSECTIONAL_DUAL_CLASSIFIER_SPEC.json`.

The supervised architecture is deliberately identical to V14 except for the representation:
- V12 ALL candidate generator unchanged;
- train only on resolved pre-2025 V12 events whose 5BD exit is before 2025-01-01;
- 4,924 training rows / 966 symbols;
- separate balanced HistGradientBoosting classifiers for >=+20% and <=-10%;
- same fixed hyperparameters as V14;
- same date+bin Pareto front maximizing p(+20) and minimizing p(-10);
- same Top1/2/3/5 and five-XTKS-session cooldown;
- 0.5% primary cost.

2025 labels were not used for model fitting.

## H1 March-June result

Feature-complete H1 rows: **8,227**.

| TopN | n | net mean | median | win | >=+20% | <=-10% | Top1-excluded mean | gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 163 | **-0.476%** | -1.642% | 37.42% | **6.13%** | 14.11% | -0.894% | FAIL |
| 2 | 322 | -0.404% | -1.251% | 40.06% | 3.73% | 11.18% | -0.615% | FAIL |
| 3 | 458 | -0.134% | -0.938% | 42.36% | 3.06% | 8.73% | -0.281% | FAIL |
| 5 | 619 | **+0.061%** | -0.500% | 44.26% | 2.75% | 8.08% | **-0.048%** | FAIL |

Even with zero assumed cost, Top1/2 remain near zero and winner-excluded means remain negative; Top5 improves to +0.561% mean but median is exactly 0% and the +20% rate is only 2.75%.

## Decision

**REJECT V17 SUPERVISED AFTER H1 / DO NOT OPEN V17 H2.**

The key finding is now separated cleanly:
- representation drift was solved;
- rare-tail classification still does not produce a robust ranking.

The pre-2025 +20% training prevalence is only **1.056%**, about 52 positive examples in 4,924 rows. That makes direct +20% classification a data-sparse learning problem.

The next architecture should therefore avoid treating +20% as the direct supervised target. A natural next test is an event-specific continuous/quantile model on the same stable V17 representation, trained only on pre-2025 events. Continuous returns provide information from every training row while preserving q90 tail potential and q10 downside information.

2026 outcomes opened: false.
Production modified: false.
