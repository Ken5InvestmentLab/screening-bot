# 天底極致 Cloud — architecture decision snapshot — 2026-09-14 JST

> **SUPERSEDED STATUS NOTICE:** This snapshot predates the canonical-endpoint rejection of the fixed reconstructed Core and the later role-gap audits. Preserve it as historical evidence, but use `ROLE_COVERAGE_AND_RESEARCH_PRIORITY_20260914.md` for the current coordination status.

Research coordination document. This does not change production.

## Goal

Build a TradingView-independent replacement that can compete with the current system without reusing current Stable as a production component.

Current Stable remains benchmark-only.

## Fixed product-facing lane structure

Keep three user-facing labels:

1. **Core**
2. **Monster Watch**
3. **Monster Prime**

Do not rename them to A/B-style variants and do not flatten them into a single confidence ladder.

Reason: reconstructed Core and the fixed walk-forward Monster tiers selected **zero identical symbol-date candidates** across the audited 2025H2/2026 folds. They are different setup families, not merely different score thresholds.

## Core decision

Current reconstructed Core definition remains fixed:
- production-like low-price/liquidity filters;
- RSI12 < 45;
- previous three reconstructed session closes descending;
- close > BB20 mid;
- ATR14/close < 5%;
- 5BD same-symbol cooldown.

### Evidence supporting Core

2026 Jan-Aug:
- n118
- signal-close mean +1.56%
- executable next-open mean +1.71%
- <=-10% rate 1.69%
- 7/8 positive months
- every leave-one-month-out mean remains positive
- week-cluster bootstrap gross 95% mean CI stays above zero
- next-open + assumed 0.5% round-trip cost: mean +1.21%, bootstrap P(mean>0) 97.52%, 95% CI approximately +0.00%..+2.43%

### What was rejected for Core

Do not add:
- global market-regime hard gates;
- simple RSI/BB/ATR/volume/EMA single-feature pruning;
- positive correlation-peer momentum gates;
- gap-up continuation rescue from the separate Core experiment.

These paths did not improve robustly across development halves / periods.

### Core status

**KEEP / RESEARCH-READY STEADY LANE**

Not production-proven because:
- 2025H2 was essentially flat;
- Yahoo historical 1H is not survivorship-free;
- live/forward fill evidence is still required.

Do not keep searching opened historical outcomes for another pruning threshold simply because Core can be made to look better in one block.

## Monster decision

The fixed reconstructed 4H learned Watch/Prime rank studied on this branch is **not** a standalone production scoring engine.

Walk-forward:
- 2025H2 strong;
- 2026 regime stability poor;
- 2026 Watch weighted mean across folds about -0.51%;
- 2026 Prime weighted mean across folds about -0.14%, with one large May-Jun tail hit.

Broad market vetoes did not stabilize it reliably.

### Monster role

Monster remains valuable as a **separate rare-positive-skew / tail-seeking lane**, not as a filter applied to Core.

Do not blindly union all Monster picks with Core; historical union helped in a tail-hit pocket and diluted Core in other periods.

Separate V20 / Consensus Monster / prospective-shadow work is owned by the parallel research lane and may supersede this branch's learned-rank Monster implementation. Do not duplicate that work here.

## Core / Monster relationship

Audited overlap:
- exact symbol+date+session overlap: 0
- same symbol+date overlap ignoring session: 0

Daily activation often had low or negative count correlation.

Decision:
- preserve separate lane identity;
- do not average their scores;
- do not infer that Prime is “better Core”;
- eventual Discord output should make the setup family explicit.

## Market regime

Market regime may be logged as context.

Do **not** make it a system-wide ON/OFF switch from the current evidence.

Monster interaction with weak/strong market states is non-stationary; Core also lost performance under tested hard regime gates.

## Historical data limitations

Yahoo extended 1H comparison panel:
- target symbols 1,332
- seen 1,315
- no detected internal failed-chunk holes where history exists
- 17 never-seen names tied to 2026 delistings
- 5 additional legacy numeric names with materially truncated history around delisting status

At least 22/1,332 target names therefore have delisting-linked compromised historical intraday coverage.

Do not call the panel full-universe or survivorship-free.

Legacy intraday/PIT reconstruction is owned by the parallel V20/data-quality lane.

## Execution assumptions

For Core:
- signal-session CLOSE is not required for the positive 2026 result;
- first executable next Yahoo 1H OPEN produced similar/slightly stronger aggregate results;
- 0.5% assumed round-trip cost is survivable in the 2026 point estimate;
- 1.0% cost materially weakens robustness.

Future live monitoring must record actual signal timestamp, actionable entry quote/open, and realized slippage.

## Closed paths on this branch

Do not reopen without genuinely new evidence:
- generic 1H feature stacking into the Monster rank;
- learned 4H rank threshold tuning on already-opened blocks;
- global market regime veto;
- simple Core local threshold pruning;
- positive peer-lag gate;
- blind Core+Monster union.

## Ownership / non-overlap

This branch should focus on:
- fixed-Core validation and operational characteristics;
- architecture-level Core/Monster complementarity;
- descriptive audits that do not duplicate V20 prospective-shadow / PIT / source-reconciliation work.

Parallel V20 lane currently owns:
- temporal/PIT coverage contracts;
- prospective-shadow admission;
- query-mode/source compatibility;
- current Monster-family forward hardening.

## Current architecture conclusion

**天底極致 Cloud should remain a two-family system:**

- **Core** = broad steadier lane.
- **Monster Watch / Prime** = separate tail-seeking family, pending a robust forward-qualified implementation.

The most important near-term work is no longer “find another historical Core filter.” It is to preserve the fixed Core, continue genuinely forward validation, and let the separate V20 Monster lane prove or disprove its forward edge.
