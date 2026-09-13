# Tentei-inspired 4H V18 — cross-sectional quantile model H1 result — 2026-09-13

Research-only. No production writes. Historical 2026 strategy outcomes were not opened.

## Frozen setup

V18 reused the V17 representation that had already passed the outcome-free drift gate.

Only the supervised target family changed:
- train only on resolved pre-2025 V12 events with exits before 2025-01-01;
- 4,924 rows / 966 symbols;
- predict continuous gross 5BD return quantiles q10/q50/q90 with fixed HistGradientBoostingRegressor parameters;
- no return clipping;
- quantile crossing resolved only by row-wise sorting;
- Core ranks by q50;
- Monster uses the first 3-objective Pareto front maximizing q90/q50/q10;
- Top1/2/3/5, same five-session cooldown and 0.5% primary cost.

2025 labels were not used for fitting.

## H1 result

Quantile crossing before sorting: **0.0365%**, so crossing is negligible.

### Core

| TopN | n | net mean | median | win | <=-10% | Top3-excluded mean | gate |
|---|---:|---:|---:|---:|---:|---:|---|
| 1 | 164 | -0.063% | -0.500% | 44.51% | 3.05% | -0.339% | FAIL |
| 2 | 328 | -0.416% | -0.635% | 40.55% | 4.27% | -0.734% | FAIL |
| 3 | 490 | -0.254% | -0.500% | 42.45% | 4.69% | -0.491% | FAIL |
| 5 | 796 | -0.221% | -0.500% | 43.34% | 4.90% | -0.382% | FAIL |

At zero cost, Core Top1 mean becomes +0.437%, but win remains 49.39% and winner-removed robustness is weak. Every frozen Core gate fails.

### Monster

| TopN | n | net mean | median | win | >=+20% | <=-10% | Top1-excluded mean | gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 164 | -0.518% | -1.550% | 40.85% | 3.05% | 14.02% | -0.933% | FAIL |
| 2 | 326 | -0.372% | -1.304% | 41.41% | 2.76% | 10.43% | -0.579% | FAIL |
| 3 | 479 | -0.384% | -1.149% | 43.01% | 2.09% | 8.77% | -0.525% | FAIL |
| 5 | 740 | -0.325% | -0.808% | 42.16% | 1.89% | 7.30% | -0.416% | FAIL |

All frozen Monster gates fail.

## Decision

**REJECT V18 AFTER H1 / DO NOT OPEN V18 H2.**

V17 solved the representation-drift problem, but both rare-tail classification (V17 supervised) and continuous quantile ranking (V18) degrade the raw V12 event population.

This suggests the current bottleneck is not merely model target choice. The strongest signal remains the sparse structural V12 event generator itself.

The next useful step should therefore evaluate the V12 ALL event stream as a Core-style baseline without ML ranking, rather than adding another supervised ranker. Because V12 H1 outcomes are already exposed, any such experiment must be labeled retrospective/post-hoc and H2 can only serve as refutation, not promotion.

2026 outcomes opened: false.
Production modified: false.
