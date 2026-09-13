# Core Gap-Down Partial Reclaim — discovery

- Decision: `REJECT_GAP_RECLAIM_DISCOVERY`.
- This is retrospective screening evidence; these years were already viewed in other families and are not untouched OOS.
- Candidate, score, q80 policy, and cooldown were frozen before outcomes. There is no Top-N cap; all ties at the daily q80 cutoff are selected.
- The 2024+ numerical OHLCV values were not opened. Failure means reject this family without threshold tuning.
- Primary return subtracts a hypothetical 0.5% round-trip cost; actual fills and friction are unmeasured.

| Selected | Resolved | Coverage | Net mean | Median | Win | +10% | +20% | +50% | -10% | -20% | Ex-top1 mean | Ex-top3 mean | Complete days | Avg/month | Positive months | Gate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2361 | 2146 | 0.909 | -0.004684952042418154 | -0.00609463911350699 | 0.3788443616029823 | 0.02749301025163094 | 0.007455731593662628 | 0.001863932898415657 | 0.021435228331780055 | 0.0013979496738117428 | -0.00529086577297406 | -0.005862977894766171 | 207 | 131.17 | 6/18 | REJECT_GAP_RECLAIM_DISCOVERY |

The unchanged full candidate pool contains 11419 signals; its resolved net mean / median / win rate are -0.004550461714035051 / -0.006180637544273888 / 0.40431493415522557.
The current Bot context is not directly comparable because its BOTTOM-signal timing and entry definition differ.
