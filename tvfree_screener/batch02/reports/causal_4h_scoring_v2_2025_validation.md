# Causal 4H scoring V2 — 2025 locked validation

Research-only. No production writes. Historical 2026 outcomes were not opened for this experiment.

## Why V2 exists

The preregistered V1 split used signal dates through 2025-06-30 as training rows. Because the target exits on the fifth official XTKS session after the signal date, the last June signals do not have mature labels by the locked validation start on 2025-07-01. This is a causal label-maturity flaw: a model available at the start of validation could not have trained on those labels.

V1 results were already opened when this was detected. They are preserved as invalid causal-validation evidence and were not used to change any feature, model parameter, Top-N set, cooldown, cost assumption, rank rule, or gate. The only V2 change was frozen first in `CAUSAL_4H_SCORING_V2_MATURE_LABEL_SPEC.json`: training rows must have `exit_date < 2025-07-01`.

## Inputs and frozen design

- Frozen feature panel: `CAUSAL_INTRADAY_FEATURE_PANEL_V1_SPEC.json`
- Features: `bar_log_return`, `range_pct`, `upper_wick_pct`, `lower_wick_pct`, `prev4_log_return_mean`, `prev4_range_mean`, `log_range_vs_prior20`
- Canonical daily panel SHA-256: `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`
- Candidate gates: previous completed daily close <= 1,000 JPY; previous completed daily volume >= 10,000 shares; no primary current-bin volume gate
- Models: fixed L2 LogisticRegression, C=1, lbfgs, class_weight=balanced; RobustScaler fit on training rows only
- Core target: `ret5bd_gross > 0`; Monster target: `ret5bd_gross >= 20%`; shared loss diagnostic: `ret5bd_gross <= -10%`
- Validation cohorts: date + AM/PM bin independently; Top1/2/3/5; five-XTKS-session same-symbol cooldown; AM earlier than PM on the same date
- Primary assumed round-trip cost: 0.5%
- 2026: unopened / report-only only after a policy passes and is fixed

The exact canonical daily panel was already present locally; no external price request was made.

## Population

- 2025 candidate feature rows after prior-day liquidity/price gates: **398,772**
- endpoint-resolved rows: **398,772**
- V1 training rows before maturity correction: 191,901
- V2 mature training rows: **183,925**
- locked validation candidate rows: **206,871**
- validation endpoint-resolved: **206,871**
- V2 training target counts: positive 91,494; +20% 2,622; <=-10% 7,962

## Locked validation — Core

At 0.5% cost:

| Top-N | requested | net mean | net median | net win | +20% gross | <=-10% gross | Top3-removed net mean | gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 248 | -1.47% | -0.78% | 38.71% | 1.21% | 8.87% | -1.94% | FAIL |
| 2 | 496 | -1.42% | -0.94% | 37.90% | 0.81% | 7.26% | -1.66% | FAIL |
| 3 | 744 | -1.09% | -0.71% | 38.71% | 0.81% | 5.51% | -1.29% | FAIL |
| 5 | 1,240 | -0.46% | -0.50% | 42.02% | 1.29% | 3.79% | -0.65% | FAIL |

No Core Top-N passes the frozen gates. `chosen_top_n = null`.

## Locked validation — Monster

At 0.5% cost:

| Top-N | requested | net mean | net median | net win | +20% gross | <=-10% gross | Top1-removed net mean | gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 248 | -4.30% | -7.66% | 26.21% | 6.85% | 40.73% | -4.83% | FAIL |
| 2 | 496 | -2.81% | -5.36% | 31.45% | 7.86% | 31.65% | -3.07% | FAIL |
| 3 | 744 | -1.93% | -3.96% | 34.01% | 7.39% | 26.21% | -2.11% | FAIL |
| 5 | 1,240 | -0.61% | -2.79% | 36.94% | 7.66% | 20.65% | -0.72% | FAIL |

No Monster Top-N passes the frozen gates. `chosen_top_n = null`.

The report-only 5,000-share current-bin sensitivity did not rescue the primary policies and is not allowed to change the primary choice. The primary result therefore remains NO-PROMOTION.

## Decision

**REJECT / NO-PROMOTION for Causal 4H Scoring V2.**

This is not a reason to tune thresholds against 2025H2. The fixed seven-feature panel plus a simple global linear logistic ranker does not generalize sufficiently. In particular, the Monster head does not preserve the intended right tail strongly enough: even Top5 reaches only 7.66% of outcomes at +20% or better versus the frozen >=10% gate, while its central return remains negative.

The next research step should be architectural rather than threshold micro-tuning. Keep the causal 4H feature pipeline, but test a genuinely new preregistered ranking architecture that can represent nonlinear interactions/regimes while explicitly preserving right-tail capture and loss control. 2026 must remain unopened for tuning.

## Audit notes / pending diagnostic

- The strict daily path/actionability metric is separate from endpoint resolution and is not needed for the already-failed promotion gates. It remains to be calculated for selected rows; do not encode an uncomputed value as zero.
- Session dates in this runtime were derived from the exact canonical all-TSE daily panel without forward filling. Before any promotion claim, reproduce against the committed `xtks_sessions.csv` calendar and record the hash equality/date-set check.
- First implementation attempts hit runtime limits; candidate feature shards were persisted and one truncated gzip (`shard6`) was detected with `gzip -t` and rebuilt before evaluation. No outcome-based change resulted from these runtime fixes.
- Result summary SHA-256: `4ee183b802a3b6ba361a555f0107ed8fd93f1d5121c97e50d91c1ad3890e940b`.
- Historical 2026 outcomes opened by this V2 run: **false**.
- Production modified: **false**.
