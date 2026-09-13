# Consensus liquidity/capacity stress — 2026-09-14

Research-only. No liquidity threshold is promoted from this retrospective audit.

## Scope

Fixed-min95 Consensus, frozen ATR OOD cap, next-open -> D+5 endpoint.

Primary stress population:
- correct one-position-per-symbol 5-session cooldown;
- no replacement;
- 2025;
- n=52.

Liquidity variables are taken only from information observable by signal time:
- previous completed daily close × previous completed daily volume;
- current reconstructed signal-session close × signal-session volume.

## Distribution

Previous-day traded value:
- median: about **JPY 456.1m**
- 10th percentile: about JPY 37.9m
- minimum: about JPY 4.73m
- below JPY 10m: 3.85%
- below JPY 50m: 11.54%

Signal-session traded value:
- median: about **JPY 37.4m**
- 10th percentile: about JPY 4.11m
- minimum: about JPY 0.46m
- below JPY 5m: 11.54%

2025H2 has similar scale:
- previous-day traded-value median about JPY 692m;
- signal-session traded-value median about JPY 38.1m.

## Operational stress only

Baseline 5-session cooldown:
- n=52
- mean +3.05%
- Top3-ex +1.21%

Exclude previous-day traded value < JPY 10m:
- n=50
- mean +3.21%
- Top3-ex +1.31%

Exclude previous-day traded value < JPY 50m:
- n=46
- mean +3.00%
- Top3-ex +0.91%

Exclude signal-session traded value < JPY 5m:
- n=46
- mean **+3.71%**
- median +0.92%
- Top3-ex **+1.66%**

Require both previous-day >= JPY 50m and signal-session >= JPY 5m:
- n=43
- mean **+3.59%**
- median +1.27%
- Top3-ex +1.38%

## Interpretation

The current Consensus edge is **not being created by the thinnest liquidity outliers**.

This is useful operationally, but the thresholds above were inspected retrospectively and are not promoted as new filters. The existing price/volume eligibility rules remain unchanged for V44.

If a future production design needs a minimum traded-value capacity rule, it should be frozen from execution requirements (expected order size / participation rate), not chosen because one historical threshold improved returns.
