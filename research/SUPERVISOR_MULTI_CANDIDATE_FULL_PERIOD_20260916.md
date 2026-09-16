# Supervisor multi-candidate full-period comparison — 2026-09-16 15:24 JST

## User decision
Do not prematurely eliminate close scoring conditions. Replace the prior DUAL+G3-only result P0 with a frozen multi-candidate full-period comparison.

## Primary apples-to-apples comparison pool
All five are frozen, already-opened Weak+Early/Phase-2 conditions using the same preserved causal base and canonical endpoint family. No threshold/ranker/gate retune is allowed.

1. `body_pct LOW`
2. `volr20 LOW`
3. `mean-rank(volr20, body_pct)`
4. `DUAL_TOP1_AGREEMENT`
5. `DUAL_TOP1_AGREEMENT + G3 NO_ACUTE_SELLOFF` with frozen `med_ret1 >= -0.01`

Common contract:
- preserved causal source/generator only; no surrogate logic
- canonical endpoint = next XTKS open -> fifth XTKS close
- transaction cost = 0%
- win = gross return > 0
- 2022 is fresh/opened robustness evidence, not tuning input
- 2026 is report/robustness-only and must not affect selection or retuning
- no post-hoc threshold/ranker/weight/gate/period/endpoint changes

## Required deterministic recovery
Before opening any new 2026 result, recover exact per-trade rows or build one deterministic reproducer capable of regenerating the frozen historical candidates.

The reproducer must first match the already-recorded frozen rows/summaries for each candidate. At minimum:
- 2023-2025 n and headline summary must match the frozen Phase-2 report.
- 2022 computable block must match the frozen fresh-validation report.
- Exact `signal_date + symbol + candidate` identity is preferred and becomes mandatory wherever historical trade rows are recoverable.
- Entry/exit dates must satisfy next-XTKS-open / fifth-XTKS-close.
- Freeze source SHA, ledger SHA, endpoint SHA, and code/ref SHA before 2026 performance is opened.

## Frozen historical anchors

| Candidate | 2022 computable n | 2022 mean | 2023-25 n | 2023-25 mean | 2023-25 median | 2023-25 win | 2023-25 Top3-ex |
|---|---:|---:|---:|---:|---:|---:|---:|
| body_pct LOW | 23 | +1.77% | 172 | +6.54% | +0.99% | 50.58% | +4.60% |
| volr20 LOW | 23 | +1.95% | 172 | +6.33% | +1.06% | 51.74% | +4.38% |
| mean-rank(volr20, body_pct) | 23 | +1.73% | 172 | +6.89% | +1.45% | 52.33% | +4.95% |
| DUAL_TOP1_AGREEMENT | 21 | +2.62% | 140 | +7.17% | +1.25% | 52.14% | +4.79% |
| DUAL + G3 | 17 | +6.08% | 117 | +7.98% | +1.74% | 53.85% | +5.14% |

## New P0 deliverable
Produce one normalized table for all five candidates:
- rows: candidate x calendar year 2022 / 2023 / 2024 / 2025 / 2026 plus each candidate's full-period aggregate
- 2022: only the computable frozen block under unchanged model-history rules; label this explicitly
- 2026: report-only; only trades with confirmed fifth-XTKS-close exits by the data cutoff
- columns: n, mean, median, win, +10, +20, -10, -20, max up, max down, Top1-ex, Top3-ex
- also add 100-share cash P/L as a descriptive side metric only if exact entry/exit prices are pinned

Do not eliminate a candidate solely because one calendar year is negative. Single-year failures are robustness warnings; comparison should emphasize the frozen full-period aggregate plus year-by-year stability, median, win, tail-exclusion durability, and downside.

## Reference-only pool — retained, not eliminated
These remain in research history but are not allowed into the normalized primary ranking until exact replay/normalization is possible:
- Old Cloud Monster Priority A: historical n63 / mean +9.86%; exact probability model lost, therefore legacy evidence only.
- V29 fixed_min98_both: different target/population and historical 350-name watchlist; inputs no longer replayable.
- weak+early x V31 full-JPX: exact historical result retained, but strong April-2025 regime concentration means it should be shown as a reference until its rows are normalized under the same comparison contract.
- Consensus CAP1000_PIT: diagnostic H1/H2 evidence has different raw-coverage contract and is not directly comparable to the Weak+Early five.

## Stop condition
Do not declare a final winner before the five primary candidates have the same-year table through 2026 report-only under the frozen contract. If an exact candidate cannot be reproduced, mark it `NOT_REPRODUCIBLE` rather than substituting a nearby rule.

Production/main and all production integrations remain untouched.
