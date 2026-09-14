# WEAK+EARLY Phase 2 — 2022 vs 2023-2025 Structural Audit

## Purpose

Fresh 2022 validation failed robustness. Before any new gate search, compare the **signal-time candidate population only**. No return/target/outcome column is used for this audit, and no new trading threshold is selected here.

Frozen candidate population in both blocks:
- V7 extreme Tail detector unchanged
- `tail_cdf >= 0.999`
- `med_ret5 <= 0`
- `ret10 <= 0.5735294117647058`
- 2022 uses the same preserved run-80 source and same causal generator

Population sizes:
- 2022 computable block: 29 candidate rows / 23 signal dates
- 2023-2025: 273 candidate rows / 172 signal dates

## Largest signal-time median shifts

Shift scale below is `(median_2022 - median_2023_25) / IQR_2023_25`; it is descriptive only.

| Feature | 2022 median | 2023-25 median | Shift / 2023-25 IQR |
|---|---:|---:|---:|
| range_pct | 0.1377 | 0.1820 | -0.512 |
| med_ret1 | -0.0029 | 0.0000 | -0.349 |
| gap | -0.0179 | +0.0050 | -0.331 |
| breadth_ret1_pos | 0.3382 | 0.4299 | -0.317 |
| volr5 | 1.0839 | 1.5111 | -0.317 |
| breadth_ma20 | 0.3602 | 0.4332 | -0.316 |
| log_dv | 20.9957 | 21.4252 | -0.299 |
| ret1 | -0.0036 | +0.0526 | -0.292 |
| rsi14 | 69.38 | 64.85 | +0.272 |
| ma5_gap | 0.0619 | 0.1033 | -0.255 |
| atr14p | 0.0984 | 0.1158 | -0.242 |
| bbwidth | 0.6170 | 0.7385 | -0.193 |
| tail_p | 0.8380 | 0.8339 | +0.192 |

## Candidate multiplicity

| Block | signal dates | candidates/day median | mean | P75 | max | single-candidate-day share |
|---|---:|---:|---:|---:|---:|---:|
| 2022 | 23 | 1.0 | 1.26 | 1.5 | 2 | 73.9% |
| 2023-25 | 172 | 1.0 | 1.59 | 2.0 | 5 | 62.2% |

## Outcome-blind interpretation

The 2022 computable candidate population is structurally different from 2023-25:

1. **weaker broad-market participation** — lower `breadth_ret1_pos`, lower `breadth_ma20`, and negative `med_ret1`;
2. **less immediate ignition / participation** — lower candidate `ret1`, lower `gap`, lower `volr5`, smaller `range_pct`, lower `atr14p`;
3. **less cross-sectional choice** — 73.9% of signal dates have only one weak+early Tail candidate vs 62.2% in 2023-25;
4. **not simply a lower Tail-score problem** — `tail_p` is slightly higher in 2022, while the candidate population is otherwise quieter/weaker;
5. **RSI is not lower** — 2022 median RSI is actually higher, suggesting a mixture of prior extension with weak immediate participation rather than straightforward early momentum.

## Decision

This audit supports a **population/regime mismatch hypothesis**, not a new gate.

Do **not** create thresholds from the values above. In particular, do not now optimize `range_pct`, `gap`, `breadth_ret1_pos`, `volr5`, `breadth_ma20`, `ret1`, or RSI using the observed 2022 outcomes.

Next high-information work should distinguish:
- model warm-up / calibration effects from the short pre-2022 history;
- candidate-scarcity effects (one candidate/day vs multiple choices);
- whether the same structural shifts appear in the already-known weak half-years 2023H2 and 2025H2 **without using returns to choose cutoffs**.

Only after that audit may a qualitatively new regime family be preregistered. Any new family must use semantic, predeclared thresholds rather than a grid fit to these opened outcomes.
