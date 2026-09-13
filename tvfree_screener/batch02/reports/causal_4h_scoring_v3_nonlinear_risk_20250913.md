# Causal 4H Scoring V3 — nonlinear risk-adjusted diagnostic — 2026-09-13

Research-only. No production writes. Historical 2026 outcomes were not opened.

## Frozen architecture

Preregistered before V3 row-level H2 outcome access in `CAUSAL_4H_SCORING_V3_NONLINEAR_RISK_SPEC.json`.

- Same seven causal 4H features as V2.
- Separate AM and PM `HistGradientBoostingClassifier` models.
- Fixed model parameters: learning_rate 0.05, max_iter 150, max_leaf_nodes 15, min_samples_leaf 200, L2 1.0, max_bins 63, early_stopping false.
- Balanced training sample weights.
- Core gain target: >0%; Monster gain target: >=+20%; shared loss target: <=-10%.
- Risk score: `logit(p_gain) - logit(p_loss10)`.
- Same price/liquidity candidate gates, Top1/2/3/5, five-session cooldown and 0.5% primary cost.
- H2 is retrospective refutation only because aggregate V2 H2 results were already known before V3 design. V3 cannot be promoted from H2.

The evaluator is committed as `eval_causal_4h_scoring_v3.py`; focused gate tests are in `test_eval_causal_4h_scoring_v3.py`.

## Runtime note

A monolithic first execution exceeded the 120-second local tool limit after entering the H2 stage. No result-driven rule change was made. The exact frozen evaluator was then run as three independent windows. This is a runtime partition only.

## H1 causal fold 1 — March-April

Training rows: 50,728. Evaluation rows: 67,972.

At 0.5% cost:

- Core Top1: n=82, mean -0.48%, median +0.05%, win 52.4%, <=-10% 2.44%.
- Core Top2: mean -0.49%; Top3 -0.59%; Top5 -0.66%.
- Monster Top1: n=82, mean -0.51%, >=+20% 0%, <=-10% 4.88%.
- Monster Top5: mean -0.48%, >=+20% 0%, <=-10% 5.61%.

All frozen comparability gates failed.

## H1 causal fold 2 — May-June

Training rows: 118,369. Evaluation rows: 65,427.

- Core Top1: n=82, mean -0.05%, median -0.33%, win 46.3%.
- Core Top2: mean +0.32% but median -0.37% and win 41.5%; gate FAIL.
- Monster Top1: n=82, mean +0.69%, >=+20% 3.66%, <=-10% 4.88%.
- Monster Top2: mean +0.55%, >=+20% 3.66%.
- Monster Top5: mean -0.08%, >=+20% 2.93%.

All gates failed. The model can suppress large losses, but the right-tail capture remains far below the 10% Monster gate.

## 2025H2 retrospective refutation

Training rows: 183,925. Evaluation rows: 206,871.

### Core

| TopN | n | net mean | median | win | >=+20% | <=-10% | gate |
|---|---:|---:|---:|---:|---:|---:|---|
| 1 | 248 | +0.21% | -0.35% | 45.6% | 0.40% | 0.00% | FAIL |
| 2 | 496 | -0.09% | -0.36% | 43.5% | 0.20% | 0.40% | FAIL |
| 3 | 744 | -0.23% | -0.43% | 41.4% | 0.00% | 0.27% | FAIL |
| 5 | 1240 | -0.17% | -0.28% | 43.5% | 0.00% | 0.40% | FAIL |

### Monster

| TopN | n | net mean | median | >=+20% | <=-10% | gate |
|---|---:|---:|---:|---:|---:|---|
| 1 | 248 | -0.40% | -1.56% | 2.42% | 5.65% | FAIL |
| 2 | 496 | -0.16% | -1.60% | 3.23% | 6.45% | FAIL |
| 3 | 744 | -0.28% | -1.56% | 3.36% | 7.66% | FAIL |
| 5 | 1240 | -0.61% | -1.50% | 2.98% | 8.15% | FAIL |

All frozen gates failed.

## Interpretation

V3 materially improved downside control versus V2, especially Core H2 Top1 where <=-10% fell to 0%. However, it over-optimized safety relative to the project objective:

- Core central tendency remains weak: H2 Top1 mean is slightly positive but median/win-rate fail.
- Monster right-tail capture collapses to roughly 2-4%, far below the >=10% objective.
- This is the exact failure mode the user warned against: stability is useful only if performance is not neutered.

Decision: **REJECT V3 / NO PROMOTION**.

This does not invalidate the causal 4H data pipeline. It rejects the current seven-feature nonlinear risk-adjusted ranking architecture.

## Reproduction hashes

- H1 fold1 local JSON SHA-256: `c7a2ce88331ce8fc65522abaad94b4fc6311b944ef1b467ece04ed0f11b77dc8`
- H1 fold2 local JSON SHA-256: `508e71a5e960fe307763ce43d5d1eb4ac05969a437c04a05d55b0d517add3fde`
- H2 retrospective local JSON SHA-256: `4e38d1a946b4eacfcafd6818a4b4a7e8e1cef6a4c1d96b2b40a1d279f61d9522`

## Next hypothesis

The next architecture must add causal 4H regime/context information rather than increasing risk penalties. Candidate direction: cross-sectional percentile/rank features within each date+bin cohort plus causal intraday market breadth/context, while preserving a tail-first Monster head and keeping 2026 closed.
