# Tentei-inspired 4H V19 — V12 ALL Core H2 refutation — 2026-09-13

Research-only. No production writes. Historical 2026 strategy outcomes were not opened.

## Purpose

V12 ALL H1 was already exposed and showed positive central tendency, while every learned ranking layer tested afterward degraded the event pool. V19 therefore tests the raw V12 structural event stream itself in 2025H2 with no ML ranking.

This is retrospective refutation only, not untouched OOS and not promotable evidence.

## Frozen setup

- V12 ALL signal generator unchanged.
- Prior-day close <=1000 JPY and volume >=10000 shares.
- No ranking and no TopN cap.
- Same five-official-session same-symbol cooldown, AM before PM.
- Endpoint: next XTKS session open to fifth XTKS session close.
- Primary cost: 0.5%.

## 2025H2 result

- raw signal rows before cooldown: **12,438**
- rows after cooldown: **6,205**
- unique active dates: **124**
- signals per active date: **50.04**

At 0.5% assumed round-trip cost:
- mean: **-0.502%**
- median: **-0.500%**
- win rate: **41.05%**
- >=+10%: 3.63%
- >=+20%: 1.03%
- >=+50%: 0.26%
- <=-10%: 3.63%
- <=-20%: 0.55%
- Top1-excluded mean: **-0.545%**
- Top3-excluded mean: **-0.574%**
- positive-month fraction: **33.3%**

The frozen Core gate fails.

At zero assumed cost:
- mean: **-0.002%**
- median: 0.000%
- win rate: 46.25%
- Top3-excluded mean: **-0.074%**

So the H2 failure is not merely the 0.5% transaction-cost assumption.

Symbol concentration is very low:
- top single symbol share 0.21%
- top five symbols share 1.02%

Thus concentration does not explain the result.

## Decision

**REJECT V12 ALL AS A STANDALONE CORE MECHANISM.**

The contrast is material:
- H1 V12 ALL after cooldown: mean +1.43%, median +0.58%, win 55.0%.
- H2 V12 ALL after cooldown: mean -0.50%, median -0.50%, win 41.0%.

The structural candidate generator itself is regime-sensitive.

The next useful step is an outcome-free H1-vs-H2 representation/regime audit on the V17 stable signal-time features. If H2 feature distributions remain stable while outcomes collapse, the project is facing concept drift / missing explanatory state rather than ordinary covariate drift. If the signal-time distribution shifts materially, another regime representation may still be justified.

2026 outcomes opened: false.
Production modified: false.
