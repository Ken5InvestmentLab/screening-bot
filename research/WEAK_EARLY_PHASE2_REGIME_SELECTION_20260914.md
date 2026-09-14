# WEAK+EARLY Phase 2 Regime Selection Note — 2026-09-14

2023-2024 preregistered discovery results after applying the four frozen gates:

| Gate | n | Mean | Median | Win | Top3-ex |
|---|---:|---:|---:|---:|---:|
| BASE DUAL_TOP1 | 103 | +6.88% | +1.39% | 53.40% | +3.86% |
| G1 TREND_SUPPORT | 27 | +12.46% | +2.39% | 62.96% | +1.97% |
| G2 NO_PANIC_DAY | 46 | +3.51% | +1.32% | 52.17% | -1.76% |
| G3 NO_ACUTE_SELLOFF | 83 | +7.38% | +1.74% | 55.42% | +3.62% |
| G4 TREND_AND_NO_PANIC | 18 | +13.65% | +2.43% | 66.67% | +0.57% |

Strict prereg target (mean>=6, win>=55, Top3-ex>=4, n>=60) is met by **0 gates**.

For one unchanged 2025 confirmation only, freeze **G3 NO_ACUTE_SELLOFF** as the sole near-pass diagnostic:
- passes n / mean / win discovery targets;
- misses Top3-ex target only (+3.62% vs +4.00%);
- uses the largest sample among win>=55 gates;
- no threshold change is allowed;
- G1/G4 are not carried forward because n is too small and Top3-ex is weak;
- G2 is rejected.

2025 confirmation rule remains exactly:
`med_ret1 >= -0.01` on the same causal market row used at signal time.

After opening 2025, do not adjust -1% threshold or add gates based on the result.