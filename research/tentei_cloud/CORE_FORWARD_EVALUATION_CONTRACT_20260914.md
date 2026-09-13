# Core forward evaluation contract — frozen 2026-09-14 JST

Research coordination contract. This file defines how future genuinely new Core observations are judged. It does not create a new shadow-ingest mechanism and does not modify production.

The parallel V20 / canonical-batch02 lane owns prospective-shadow admission, provenance, receipt verification, and PIT/source-eligibility enforcement.

This file owns only the **Core evaluation rule after future observations mature**.

## Why freeze this now

The historical reconstructed Core has already been inspected extensively. Further threshold searching on those outcomes would increase overfitting risk.

Therefore future evidence must be judged by a rule written **before** those future 5BD outcomes are known.

## Frozen Core signal definition

Do not change for this forward evaluation:
- production-like price/liquidity universe filters;
- RSI12 < 45;
- previous three reconstructed session closes descending;
- close > BB20 mid;
- ATR14 / close < 5%;
- 5BD same-symbol cooldown.

No market-regime gate, local-feature pruning, peer-lag gate, density filter, or capacity filter.

## Entry / outcome convention

Primary forward return:
- entry = first executable intraday bar OPEN strictly after the completed Core signal session;
- exit = existing 5-business-day target-date close.

Also record:
- gross return;
- net return under a fixed **0.5% round-trip cost stress assumption**.

The 0.5% value is a stress scenario, not a claim about actual execution cost. Actual observed slippage should be stored separately when available.

## Eligibility

Only use observations that pass the parallel prospective-shadow provenance / PIT / eligibility contract.

Never mix:
- historical backfill inserted after outcomes were known;
- unverifiable manual rows;
- rows that fail the parallel eligibility proof;
with the forward Core evaluation set.

## Checkpoints

Do not judge Core from a handful of trades.

### Early checkpoint

Open only when BOTH are true:
- at least **30 matured Core signals**;
- signals span at least **8 distinct active ISO weeks**.

This checkpoint can block promotion but cannot by itself prove production readiness.

### Main checkpoint

Open only when BOTH are true:
- at least **60 matured Core signals**;
- signals span at least **16 distinct active ISO weeks**.

If 60 signals take longer than expected, keep collecting; do not lower the sample requirement because results look attractive.

## Frozen metrics

At each checkpoint report all of:

- n;
- active weeks;
- gross mean;
- gross median;
- win rate;
- >= +10%;
- >= +20%;
- <= -10%;
- top-1 / top-3 / top-5 winner-removed gross mean;
- 0.5%-cost net mean;
- 0.5%-cost net median;
- whole-ISO-week cluster bootstrap P(mean > 0);
- 95% week-cluster bootstrap interval for gross mean;
- 95% week-cluster bootstrap interval for 0.5%-cost net mean;
- maximum same-day signal count;
- maximum concurrent 5BD position-slot demand.

No metric may be hidden because it is unfavorable.

## Early checkpoint decision rule

At n>=30 and >=8 active weeks:

**CONTINUE / NO PROMOTION** unless all are true:
- gross mean > 0;
- top-3-removed gross mean > 0;
- <= -10% rate <= 7.5%;
- 0.5%-cost net mean > 0.

Passing the early checkpoint only means the Core thesis remains alive. It does not authorize production promotion.

If any condition fails, continue collecting to the main checkpoint unless there is a clear implementation/data-integrity failure.

## Main checkpoint promotion gate

At n>=60 and >=16 active weeks, Core qualifies as a forward-supported steady lane only if ALL are true:

1. **0.5%-cost net mean > 0**.
2. **gross top-5-winner-removed mean > 0**.
3. **<= -10% rate <= 5%**.
4. **week-cluster bootstrap P(gross mean > 0) >= 90%**.
5. No provenance / PIT / executable-entry coverage failure is unresolved.

Interpretation:
- net-positive mean protects against an edge too small to survive realistic friction stress;
- top-5 removal protects against turning Core into a hidden Monster/tail lane;
- <=-10% <=5% preserves the intended lower-downside role;
- week-cluster probability guards against one short calendar pocket carrying the result.

## What is intentionally NOT required

Do not require:
- gross mean >= historical 2026 +1.71%;
- 95% bootstrap lower bound > 0;
- median > 0 after the 0.5% cost stress;
- a minimum >=20% tail rate.

Those would over-anchor forward Core to one favorable historical block or incorrectly demand Monster-like behavior from the steady lane.

## Failure interpretation

If the main gate fails:
- do not retune Core on the failed forward sample immediately;
- freeze and diagnose whether failure is data/PIT, execution, market-regime drift, or structural signal decay;
- any replacement Core hypothesis must be registered as a new version and evaluated on later evidence.

Never mutate the current Core thresholds and then reuse the same failed forward outcomes as clean validation.

## Relationship to Monster

Core forward qualification is independent of Monster.

A successful Core does not validate Monster.
A successful Monster does not rescue a failed Core.

Final replacement-system comparison against current Stable★6/Sniper/Mega should happen only after each lane has its own forward-qualified evidence.

## Current status at freeze

Historical reconstructed evidence supports Core as a promising steady lane, especially in 2026, but this contract explicitly treats that history as already-opened retrospective evidence.

**Forward status at freeze: NOT YET QUALIFIED.**
