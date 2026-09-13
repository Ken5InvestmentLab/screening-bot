# Consensus price-bucket descriptive stress — 2026-09-14

Research-only descriptive audit. No price threshold is promoted.

Population:
- fixed-min95 Consensus;
- frozen ATR OOD guard;
- correct 5-session same-symbol cooldown;
- no replacement;
- next-open -> D+5 close;
- 2025;
- n=52.

Signal-session price distribution:
- median about JPY 395.5
- 10th percentile about JPY 65.0
- 90th percentile about JPY 916.5
- min JPY 9
- max JPY 1,080 (prior completed close, not current session price, is the <=JPY1,000 eligibility input).

Descriptive buckets:

| signal price | n | mean | median | win | >=10% | <=-10% |
|---|---:|---:|---:|---:|---:|---:|
| <100 | 10 | -3.11% | 0.00% | 40.0% | 0.0% | 20.0% |
| 100-199 | 5 | +10.25% | +8.39% | 60.0% | 40.0% | 0.0% |
| 200-299 | 3 | +8.47% | +7.41% | 66.7% | 33.3% | 0.0% |
| 300-499 | 14 | +6.99% | +4.11% | 57.1% | 35.7% | 7.1% |
| 500-699 | 6 | +5.46% | +5.49% | 66.7% | 16.7% | 0.0% |
| 700-999 | 13 | -1.34% | -1.19% | 38.5% | 7.7% | 15.4% |
| >=1000 current session | 1 | -0.05% | -0.05% | 0.0% | 0.0% | 0.0% |

Interpretation:
- the +3.05% aggregate is not created by ultra-low-price names;
- the sub-JPY100 bucket is negative in this already-opened sample;
- the strongest descriptive region is mid-priced names;
- this must **not** be converted into a new price filter because these outcomes have already been inspected;
- any future production price-cap/floor change would require a new preregistered later-data experiment.

This supports treating liquidity/capacity and concentration as the primary current concerns rather than a penny-stock artifact.
