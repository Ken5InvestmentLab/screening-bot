# WEAK+EARLY Phase 2 Model-Period Audit — 2026-09-14 21:00 JST

## Purpose

2022 fresh validationの失敗が、V7/V9 monthly causal Tail modelの初期warm-up不足に集中しているのか、それともtraining rowsが十分増えた後も残るのかを診断する。

これは**原因診断のみ**。Phase-2 frozen条件、G3=-1%、ranker、endpoint、cost0契約は変更しない。結果を見てthreshold/gateを追加・調整しない。

## Source / reconstruction integrity

- preserved artifact: `10264205130` (`tvfree-frozen-dataset-run80-preserved`)
- **actual artifact source run: `34599959356`**
- artifact digest: `sha256:095e58986d45bda0092be1767e1b44a4791bf3c617179791d0c99c6d7d01bcb0`
- raw 2022 rows: **825,735**
- reconstruction: unchanged `v7_full_tail_research.py` + `run.py` 45 signal-time features
- Tail target: causal monthly `y_top025`, `tail_cdf >= 0.999`
- minimum training rows: **30,000**
- endpoint: next XTKS open -> fifth XTKS close
- transaction cost: **0%**

The reconstruction reproduced the already-frozen 2022 Phase-2 metrics exactly to rounding:
- body n23 / mean +1.77% / median -6.37% / win 26.09% / Top3-ex -7.51%
- volr20 n23 / mean +1.95% / median -6.19% / win 26.09% / Top3-ex -7.31%
- DUAL n21 / mean +2.62% / median -6.19% / win 28.57% / Top3-ex -7.55%
- DUAL+G3 n17 / mean +6.08% / median -6.00% / win 29.41% / Top3-ex -6.26%

This exact-match check supports using the monthly decomposition below as the same frozen 2022 experiment rather than a surrogate.

## Monthly DUAL_TOP1 diagnostics

| Model period | Train rows | n | Mean | Median | Win | Candidate rows/dates | Single-candidate share | Tail-p median |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2022-06 | 40,602 | 1 | -17.82% | -17.82% | 0.00% | 1 / 1 | 100% | 0.7711 |
| 2022-07 | 67,528 | 3 | -11.11% | -9.57% | 0.00% | 3 / 3 | 100% | 0.8359 |
| 2022-08 | 91,462 | 4 | -5.12% | -6.03% | 0.00% | 5 / 4 | 75.0% | 0.8392 |
| 2022-09 | 117,301 | 2 | +41.51% | +41.51% | 50.00% | 2 / 2 | 100% | 0.8458 |
| 2022-10 | 141,014 | 3 | +25.24% | +27.93% | 100.00% | 3 / 3 | 100% | 0.8400 |
| 2022-11 | 165,509 | 0 | — | — | — | 0 | — | — |
| 2022-12 | 189,183 | 8 | -4.00% | -6.09% | 25.00% | 13 / 9 | 55.56% | 0.8369 |

September is highly right-tail dependent: the two outcomes include approximately **+118.13%** and **-35.11%**.

### DUAL maturity split

| Block | n | Mean | Median | Win | Top3-ex |
|---|---:|---:|---:|---:|---:|
| Jun-Aug, early-stage | 8 | **-8.95%** | **-7.69%** | **0.00%** | **-11.96%** |
| Sep-Dec, train >100k from Sep | 13 | **+9.75%** | **-0.39%** | **46.15%** | **-6.43%** |

The raw mean flips positive in the mature block, but median remains negative, win remains below 50%, and Top3-ex remains strongly negative.

## DUAL + G3 diagnostics

G3 remains exactly `med_ret1 >= -0.01`; no threshold change.

| Model period | n | Mean | Median | Win |
|---|---:|---:|---:|---:|
| 2022-06 | 0 | — | — | — |
| 2022-07 | 2 | -13.31% | -13.31% | 0.00% |
| 2022-08 | 4 | -5.12% | -6.03% | 0.00% |
| 2022-09 | 1 | +118.13% | +118.13% | 100.00% |
| 2022-10 | 3 | +25.24% | +27.93% | 100.00% |
| 2022-11 | 0 | — | — | — |
| 2022-12 | 7 | **-6.21%** | **-6.19%** | **14.29%** |

### G3 maturity split

| Block | n | Mean | Median | Win | Top3-ex |
|---|---:|---:|---:|---:|---:|
| Jun-Aug (actual G3 Jul-Aug) | 6 | **-7.85%** | **-7.69%** | **0.00%** | **-11.67%** |
| Sep-Dec, train >100k from Sep | 11 | **+13.67%** | **-0.39%** | **45.45%** | **-5.07%** |

## Key finding

**Simple model warm-up / undersized-training is rejected as the primary explanation for the 2022 failure.**

Why:
1. Sep-Dec begins with 117k training rows / 335 positive labels and reaches 189k / 541 by December.
2. Mature-period mean becomes positive only because a few large winners dominate the average.
3. Mature DUAL still has median -0.39%, win 46.15%, Top3-ex -6.43%.
4. Mature G3 still has median -0.39%, win 45.45%, Top3-ex -5.07%.
5. December is especially diagnostic: with **189,183 train rows / 541 positives**, DUAL win is only **25%** and G3 win **14.29%** with median about **-6.2%**.
6. `tail_p` remains around the low/mid-0.8s rather than collapsing on the bad months, so simple score-confidence degradation does not identify the failures.

## Interpretation

2022 exhibits **persistent right-tail dependence plus weak central tendency**. The model can still occasionally find very large winners after it is mature, but the ordinary pick is not robustly positive. Candidate scarcity also remains visible: Sep/Oct are effectively forced-choice one-candidate days and even December has a thin pool.

This does **not** justify converting candidate count into a new gate after seeing outcomes. It is a root-cause clue only.

## Disposition

- 2022 fresh validation: **FAIL ROBUSTNESS — unchanged**
- simple warm-up hypothesis: **REJECTED AS PRIMARY EXPLANATION**
- G3: **frozen; no retune**
- Regime Round2: **CLOSED / NOT ACTIVATED**
- candidate-level new ranker search: **STOPPED**
- production: **NO-GO**

## Next high-information checks

1. Outcome-blind population/scarcity audit across 2022, 2023H2 and 2025H2: candidate-count distribution, forced-choice share, symbol concentration and causal market structure. Do not turn any split into a gate from this opened evidence.
2. If a qualitatively different market-level hypothesis for 2025H2 can be theoretically justified **before** looking at its outcome-conditioned performance, preregister it before any Round2 test.
3. Keep Consensus formal raw retry and OSS cost0-contract work isolated under their existing owners.

## Provenance correction

Previous coordination notes sometimes listed artifact `10264205130` with source run `34545440155`. GitHub artifact metadata shows artifact `10264205130` belongs to **run `34599959356`**; run `34545440155` instead had expired artifact `10179500303`. Coordination state/dashboard should use the corrected source run going forward.
