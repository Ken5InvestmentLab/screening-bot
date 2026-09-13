# Tentei-inspired 4H V13 — V12 events ranked by existing V6 quantiles — 2026-09-13

Research-only. No production writes. Historical 2026 strategy outcomes were not opened.

## Frozen design

Preregistered in `TENTEI_INSPIRED_4H_V13_V6_QUANTILE_RANK_SPEC.json` before V13 selection metrics.

- Candidate generator: **all V12 signals unchanged**.
- No post-hoc choice of RSI recovery vs emergency reversal.
- Ranking input: the already-existing V6 monthly causal q10/q50/q90 predictions trained for the broader all-bin universe.
- Selection: first Pareto front maximizing q90 and q10, q90-first ranking, Top1/2/3/5, no dominated/non-V12 backfill, same five-session cooldown.

## H1 result

V12 rows that also had V6 scores: 8,207.

At 0.5% cost:
- Top1 n=164: mean **+0.67%**, median **-1.87%**, win 42.68%, >=+20% **6.10%**, <=-10% 14.02%, Top1-excluded +0.22%. FAIL.
- Top2 n=327: mean +0.47%, median -0.78%, >=+20% 5.81%, Top1-excluded +0.25%. FAIL.
- Top3 n=485: mean +0.38%, median -0.76%, >=+20% 4.33%. FAIL.
- Top5 n=770: mean +0.23%, median -0.50%, >=+20% 3.51%. FAIL.

## Decision

**REJECT V13 after H1; H2 remains unopened.**

The V6 quantile ranker was trained on the broad all-bin candidate universe. Filtering its scores down to V12 reversal events does not preserve the strong central performance of the V12 event population and still does not reach the frozen right-tail gate.

The next experiment must train specifically on V12-like events. To avoid fitting 2025, V14 will train once using only resolved pre-2025 V12 events (2024-09-26 through 2024-12-30; 7,099 events / 1,065 symbols), with separate +20% tail and -10% downside classifiers.

2026 outcomes opened: false.
Production modified: false.
