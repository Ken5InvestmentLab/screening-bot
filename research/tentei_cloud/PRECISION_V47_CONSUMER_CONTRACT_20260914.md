# Sniper-like precision role consumer contract — frozen 2026-09-14 JST

Research coordination contract. No model is trained here and no outcome is opened by this file.

## Purpose

The replacement system still lacks a validated Sniper-like 5BD high-hit-rate role.

Four simple hand-written raw1H event families have already failed and are closed. The next evidence must come from a materially different representation.

The clean V47 materializer being built on `research/consensus-atr-regime-gate` provides such a representation:
- clean PIT universe;
- restored/delisted membership handling;
- daily PIT volume semantics;
- raw1H session shape;
- daily technicals;
- cross-sectional ranks;
- market breadth/regime features;
- canonical next-XTKS-open -> D+5-close endpoint.

This branch will **not train a competing model** on those features.

Instead, after an upstream V47 candidate/selector is frozen and its locked validation is legitimately opened, this contract defines whether that upstream lane also fills the Sniper-like product role.

## Benchmark role

Current Sniper reference shape:
- 5BD horizon;
- saved-report mean around +2.4%;
- saved-report win rate around 65.8%;
- separate current_logic snapshot mean around +3.1%, decisive win ~66.7%.

The replacement does not need exact equality or the same legacy indicators.

## Eligible upstream evidence

Only evaluate a V47-derived selected set if ALL are true:
1. clean-PIT daily acceptance passed;
2. raw1H coverage acceptance passed;
3. feature receipt is promotion-grade, not a V47S survivor-only shadow fallback;
4. candidate/selector policy was frozen before locked-validation targets were opened;
5. canonical return is next official XTKS open -> fifth XTKS close;
6. no 2026 outcome was used to choose the policy.

If any condition fails, Precision role status remains `NOT_EVALUABLE`.

## Frozen Sniper-role gate

On the legitimate locked 2025H2 selected set, call the role **PRECISION_SUPPORTED** only if ALL are true:

- resolved n >= 30;
- 0.5% round-trip-cost net mean > 0;
- 0.5% round-trip-cost net median > 0;
- 0.5% round-trip-cost win rate >= 60%;
- gross <= -10% rate <= 8%;
- 0.5%-cost top-5-winner-removed mean > 0.

Rationale:
- 60% is deliberately below the legacy ~66% reference, allowing model/system differences while still requiring a clearly high-hit-rate role;
- top-5 removal prevents a hidden Monster lane from masquerading as Precision;
- 8% loss10 ceiling keeps the role meaningfully lower-downside.

## Role classification

- all gates pass -> `PRECISION_SUPPORTED`
- mean positive but win <60% -> `NOT_SNIPER_ROLE`
- win >=60% but top-5-removed mean <=0 -> `TAIL_DEPENDENT_NOT_PRECISION`
- n<30 -> `INSUFFICIENT_SAMPLE`
- data/provenance eligibility fails -> `NOT_EVALUABLE`

No threshold may be lowered after seeing locked H2.

## 2026 policy

2026 is report-only after the locked H2 role classification is frozen.

If H2 supports Precision, 2026 reports persistence but cannot retroactively alter the H2 classification.

If H2 fails, do not use a strong 2026 period to rescue or retune the same selector.

## Relationship to upstream Stable/Monster objective

One upstream V47 selector may potentially satisfy more than one product role.

That is allowed only if each role passes its own frozen metrics.

Do not assume:
- a Stable-like high mean implies Sniper-like precision;
- a Monster tail hit implies Precision;
- a high win rate alone implies attractive return.

This consumer contract changes no upstream V47 optimization objective.

## Ownership

Upstream V47/Consensus lane owns:
- PIT restoration;
- feature materialization;
- model/selector training;
- locked validation opening.

This branch owns only:
- role classification against the current-system benchmark map.

Production modified: false.
