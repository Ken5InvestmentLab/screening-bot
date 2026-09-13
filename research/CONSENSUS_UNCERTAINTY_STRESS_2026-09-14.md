# Consensus uncertainty stress — 2026-09-14

Research-only descriptive audit. No thresholds, model parameters, ATR cap, cooldown, or Top-K policy are selected from this result.

## Population

Fixed-min95 Consensus + frozen ATR OOD cap + next-open -> D+5 endpoint.

To avoid overlapping same-symbol positions:
- one position per symbol;
- 5 official-session cooldown;
- re-entry allowed after the holding interval;
- no replacement candidate.

Full 2025:
- n=52
- mean +3.05%
- median +0.29%

2025 Jul-Dec:
- n=22
- mean +3.58%
- median +0.29%

## Bootstrap method

20,000 deterministic resamples.

Reported ranges are percentile 95% intervals for the mean.

Four views:
1. ordinary row bootstrap;
2. symbol-cluster bootstrap;
3. calendar-month-cluster bootstrap;
4. calendar-week-cluster bootstrap.

Cluster bootstrap resamples whole clusters with replacement and therefore keeps within-symbol / within-period dependence together better than IID resampling.

## Full 2025

| method | 95% interval for mean | bootstrap P(mean>0) |
|---|---:|---:|
| ordinary rows | -0.05% to +6.40% | 97.3% |
| symbol clusters | **-1.55% to +7.43%** | 88.1% |
| month clusters | -0.67% to +5.82% | 95.2% |
| week clusters | -0.10% to +6.33% | 97.1% |

Leave-one-out:
- remove 2334 (worst symbol removal for mean): remaining n=46, mean +0.89%.
- most favorable symbol removal: mean +3.75%.
- remove August 2025 (worst month removal): remaining n=43, mean +1.66%.
- worst week removal leaves mean +2.21%.

Interpretation:
- the positive point estimate is not caused by a single symbol or a single week;
- however symbol-cluster uncertainty still crosses zero materially;
- n=52 does not justify calling the specialist edge statistically settled.

## 2025 Jul-Dec

| method | 95% interval for mean | bootstrap P(mean>0) |
|---|---:|---:|
| ordinary rows | -1.75% to +9.58% | 89.6% |
| symbol clusters | **-2.17% to +9.39%** | 85.8% |
| month clusters | **-1.64% to +8.36%** | 74.3% |
| week clusters | -2.08% to +9.03% | 88.2% |

Leave-one-out:
- remove 2334: remaining n=18, mean +0.50%.
- remove August 2025: remaining n=13, mean **-0.65%**.
- worst single-week removal still leaves mean +1.53%.

Interpretation:
- H2 point estimate is positive but sample uncertainty is large;
- month dependence remains important;
- Top3-ex was already negative (-0.81%), so the H2 specialist case is not robust enough to promote on current evidence alone.

## Decision

This audit does not change V44 preregistration.

It strengthens the reason V44 must be judged on:
- mean retention;
- symbol concentration;
- Top3-excluded mean;
- H2 stability;
- not just the headline average.

If V44 fails its frozen development gate, do not search for a looser cooldown or a different Top-K using these opened outcomes.

If V44 passes, the result remains a research specialist candidate and still requires prospective/shadow evidence before production promotion.
