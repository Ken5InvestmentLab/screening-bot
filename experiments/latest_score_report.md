# Experimental 5BD Scoring Logic Report

- Generated: `2026-04-29T12:40:09Z`
- Objective: `perf_5bd`
- Feature-complete rows: `1254` (skipped no-features: `2`)
- Split: train `752`, validation `251`, holdout `251`
- Selected cutoff: `score >= 100`
- Recommendation: **no robust candidate**

## Selected Conditions

| # | Weight | Condition | Validation n | Validation win | Validation avg |
|---:|---:|---|---:|---:|---:|
| 1 | 4 | 3d return <= -0.024 | 18 | +77.8% | +2.6% |
| 2 | 12 | upper wick percent <= 0.009 | 16 | +87.5% | +3.5% |
| 3 | 14 | 5d rebound from low <= 0.089 | 16 | +87.5% | +3.5% |
| 4 | 14 | 5d return <= -0.010 | 16 | +87.5% | +3.5% |
| 5 | 14 | close vs EMA5 <= 0.009 | 16 | +87.5% | +3.5% |
| 6 | 14 | close vs EMA10 <= 0.000 | 16 | +87.5% | +3.5% |
| 7 | 14 | volume vs prior 5d <= 2.429 | 16 | +87.5% | +3.5% |
| 8 | 14 | volume vs prior 10d <= 2.429 | 16 | +87.5% | +3.5% |
| 9 | 14 | 10d realized volatility <= 0.080 | 16 | +87.5% | +3.5% |
| 10 | 14 | candle body percent >= -0.030 | 16 | +87.5% | +3.5% |
| 11 | 14 | RSI14 <= 47.48 | 16 | +87.5% | +3.5% |
| 12 | 14 | Stochastic K14 <= 53.85 | 16 | +87.5% | +3.5% |

## Performance

| Slice | n | Win rate | Avg | Median | +10% | -10% |
|---|---:|---:|---:|---:|---:|---:|
| Baseline train | 752 | +34.4% | -0.4% | -1.0% | +5.3% | +4.4% |
| Baseline validation | 251 | +45.4% | +0.1% | +0.0% | +2.8% | +1.6% |
| Baseline holdout | 251 | +32.7% | -0.5% | -1.8% | +7.2% | +6.4% |
| New validation cutoff | 16 | +87.5% | +3.5% | +2.7% | +6.2% | +0.0% |
| New holdout cutoff | 5 | +60.0% | +0.7% | +3.2% | +0.0% | +0.0% |
| New all cutoff | 67 | +53.7% | +2.0% | +0.5% | +7.5% | +0.0% |
| New all top decile | 136 | +42.6% | +0.9% | -0.3% | +5.9% | +0.7% |
| Current logic star6 all | 56 | +55.4% | +5.8% | +0.5% | +14.3% | +3.6% |

## Score Buckets (All Data)

| Score bucket | n | Win rate | Avg | Median | +10% | -10% |
|---|---:|---:|---:|---:|---:|---:|
| 90-100 | 215 | +39.5% | +0.3% | -0.5% | +5.6% | +2.8% |
| 80-89 | 107 | +37.4% | -0.8% | -0.6% | +2.8% | +2.8% |
| 70-79 | 191 | +29.8% | -1.4% | -1.3% | +2.1% | +3.7% |
| 60-69 | 181 | +33.7% | -0.6% | -1.0% | +2.2% | +0.6% |
| 50-59 | 223 | +37.2% | -0.4% | -0.9% | +2.7% | +1.3% |
| 0-49 | 337 | +38.3% | +0.3% | -1.8% | +10.7% | +9.8% |

## Recommendation Notes

- holdout sample 5 < minimum 7

This is a paper-test artifact only. It does not update production scoring, pending logic, Discord behavior, or deployment files.
