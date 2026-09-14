# WEAK+EARLY Phase 2 — 2022 Fresh Validation

## Status

**FRESH VALIDATION OPENED / FAILED ROBUSTNESS**

No Phase-2 threshold, ranker weight, gate, endpoint, or cost assumption was changed after seeing 2022.

## Exact source / reconstruction

- preserved source: frozen run-80 dataset artifact `10264205130` (`tvfree-frozen-dataset-run80-preserved`)
- original source run: `34545440155`
- raw dataset date range: 2022-01-04 through 2026-09-11
- total raw rows: 4,061,361
- 2022 raw rows: 825,735
- causal Tail generator: existing V7/V9 implementation (`v7_full_tail_research.py` / `v9_conditional_quality_research.py`)
- Tail model: existing full 45-feature monthly causal top-0.25% model
- Tail gate: `tail_cdf >= 0.999`
- model minimum history: existing `train >= 30,000` rows; not relaxed
- Phase-2 gate: `med_ret5 <= 0`, `ret10 <= 0.5735294117647058`
- endpoint: next session open -> fifth session close
- transaction cost: 0%

The frozen raw data starts on 2022-01-04. Under the unchanged `train >= 30,000` rule, January-May cannot produce an eligible monthly Tail model. The first computable month is June 2022. No synthetic history or surrogate model was added.

### Reconstructed 2022 Tail cache

- usable months: 2022-06 through 2022-12
- extreme Tail candidates: 89
- after frozen weak+early gate: 29 candidate rows across 23 signal dates

## Fresh validation results — cost 0%

| Candidate | n | Mean | Median | Win | +10 | +20 | +50 | -10 | -20 | Top1-ex | Top3-ex |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| body_pct LOW | 23 | +1.77% | -6.37% | 26.09% | 17.39% | 13.04% | 4.35% | 21.74% | 4.35% | -3.52% | -7.51% |
| volr20 LOW | 23 | +1.95% | -6.19% | 26.09% | 17.39% | 13.04% | 4.35% | 21.74% | 4.35% | -3.33% | -7.31% |
| mean-rank(volr20, body_pct) | 23 | +1.73% | -6.37% | 26.09% | 17.39% | 13.04% | 4.35% | 21.74% | 4.35% | -3.56% | -7.56% |
| DUAL_TOP1_AGREEMENT | 21 | +2.62% | -6.19% | 28.57% | 19.05% | 14.29% | 4.76% | 23.81% | 4.76% | -3.15% | -7.55% |
| DUAL + G3 NO_ACUTE_SELLOFF | 17 | +6.08% | -6.00% | 29.41% | 17.65% | 17.65% | 5.88% | 17.65% | 0.00% | -0.93% | -6.26% |

## Combined descriptive view — 2022 computable block + frozen 2023-2025

This is descriptive aggregation, not a new tuning block.

| Candidate | n | Mean | Median | Win | Top3-ex |
|---|---:|---:|---:|---:|---:|
| body_pct LOW | 195 | +5.98% | -0.39% | 47.69% | +4.20% |
| volr20 LOW | 195 | +5.81% | 0.00% | 48.72% | +4.03% |
| mean-rank(volr20, body_pct) | 195 | +6.28% | 0.00% | 49.23% | +4.51% |
| DUAL_TOP1_AGREEMENT | 161 | +6.57% | 0.00% | 49.07% | +4.43% |
| DUAL + G3 | 134 | +7.74% | +1.06% | 50.75% | +5.17% |

## Interpretation

- 2022 is a clear out-of-period warning for the entire weak+early family.
- DUAL and G3 retain positive headline means only because the right tail remains large; the negative medians and negative Top3-ex values in 2022 show that the fresh block is not broadly profitable.
- G3 is still the best descriptive aggregate, but its 2022 win rate is only 29.41%; therefore it does **not** solve the robustness/win-rate objective.
- The fresh block fails the desired win-rate target and fails tail-exclusion robustness.
- Do not tune the `ret10` cutoff, `med_ret5` gate, G3 `-1%` cutoff, ranker weights, or Tail gate using this 2022 result.

## Decision

**NO-GO / ROOT-CAUSE AUDIT BEFORE FURTHER WIN-RATE OPTIMIZATION.**

Because 2022 fresh validation was possible, do not automatically enter the fallback Round-2 regime search specified only for the case where 2022 reconstruction was impossible. The next high-information step is an outcome-blind structural audit of why 2022 differs from 2023-2025, especially model warm-up / candidate-population / market-regime availability. Any new gate family must be separately preregistered only after that audit and must not be fitted to the observed 2022 losses.
