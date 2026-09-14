# Precision three-family discovery batch — findings — 2026-09-14 JST

Research-only. Three families were preregistered together before development outcomes were opened.

Experiment:
`PRECISION-BATCH-20260914-01`

Development-only run:
- workflow run: `34799307163`
- artifact: `10330489226`
- artifact ZIP SHA-256: `ff0ef8785b67c21d922fbe8318c1000905fb263a913e2cdc06a5bb7ea6abce33`

Internal validation was NOT opened.
2025H2 was NOT opened.
2026 was NOT opened.

## Frozen development result at 0.5% round-trip cost

| family | resolved n | net mean | net median | net win | gross <=-10% | top3-removed net mean |
|---|---:|---:|---:|---:|---:|---:|
| PRIOR_HIGH_BREAKOUT | 7,255 | -0.41% | -0.50% | 42.36% | 3.74% | -0.45% |
| TWO_DAY_PULLBACK_RECLAIM | 8,965 | -0.48% | -0.50% | 41.86% | 3.56% | -0.51% |
| INSIDE_RANGE_STRENGTH | 6,327 | -0.35% | -0.50% | 40.95% | 3.10% | -0.41% |

All three failed:
- net mean > 0;
- net median > 0;
- net win >= 60%;
- net top3-removed mean > 0.

All passed only the large-loss-rate ceiling, which is insufficient for a precision lane.

Eligible family count: **0**.
Selected winner: **none**.

## Decision

**REJECT the entire three-family Precision discovery batch.**

Do not open internal validation for any member.

Combined with the separately preregistered prior-close-reclaim failure, four simple low-DOF raw1H event hypotheses have now failed to approach the Sniper-like high-hit-rate role.

This is enough evidence to stop inventing more adjacent candle/reclaim rules on the same historical archive in this lane.

The Sniper role remains uncovered, but further work should require a materially different information source or representation, not another nearby hand-written candle condition.

Examples of materially different future directions:
- a clean PIT cross-sectional rank built in a separate preregistered experiment;
- fundamental/event information;
- a future V20/canonical event stream;
- genuinely forward observations.

Do not continue same-day historical rule enumeration.
