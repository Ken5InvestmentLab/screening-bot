# Consensus concentration audit — 2026-09-14

Research-only. No production writes.

## Scope

Audit fixed-min95 Consensus after the frozen ATR OOD gate and realistic next-business-day-open entry.

The goal is not to add a tuned cooldown. It is to determine whether the apparent 2025 edge is broadly distributed or depends on repeatedly selecting the same exceptional symbols.

## 2025 gated sample

Frozen ATR cap: 2.8640659721.

- n=101
- next-open mean +7.72%
- median +7.41%
- win 63.37%
- +10% 39.60%
- +20% 16.83%
- <=-10% 7.92%
- Top3-ex mean +6.52%
- unique symbols: 29

However symbol concentration is high:
- 3350: 30 trades, mean +15.32%
- 2334: 15 trades, mean +22.64%
- 7318: 8 trades
- 6574: 6 trades

Remove 3350 entirely:
- n=71
- mean +4.51%
- Top3-ex mean +2.63%

Remove 2334 entirely:
- n=86
- mean +5.12%
- Top3-ex mean +4.09%

Remove both 3350 and 2334:
- n=56
- mean **-0.35%**
- median -0.56%
- Top3-ex mean **-1.54%**

Interpretation: the full-year headline is heavily dependent on two repeated winners.

## 2025 Jul-Dec forward-validation segment

ATR-gated next-open:
- n=34
- mean +6.33%
- Top3-ex mean +2.94%
- unique symbols: 14
- 2334 appears 9 times.

Remove 2334:
- n=25
- mean +2.06%
- Top3-ex mean -0.46%

Remove best week:
- n=31
- mean +3.67%
- Top3-ex mean +1.56%

Remove best month (2025-08):
- n=23
- mean +2.23%
- Top3-ex mean -0.16%

The H2 result is therefore positive but not broadly diversified.

## Naive repeat-removal stress

This is deliberately a destructive stress test, not a candidate production rule.

Capping the number of chronological trades per symbol in the 2025 gated sample:

- max 1 per symbol: n=29, mean +0.80%, Top3-ex -1.28%
- max 2: n=41, mean -0.25%, Top3-ex -1.91%
- max 3: n=52, mean +1.10%, Top3-ex -0.63%
- max 5: n=62, mean +3.21%, Top3-ex +1.37%
- max 8: n=72, mean +4.73%, Top3-ex +3.21%
- max 10: n=76, mean +5.39%, Top3-ex +3.98%

Simple dropping of repeat symbols sacrifices too much edge.

Calendar cooldown stress shows the same pattern:
- 2-day no-repeat: H2 n=25, mean +5.30%, Top3-ex +1.75%
- 5-day no-repeat: H2 n=22, mean +3.58%, Top3-ex -0.81%
- 10-day no-repeat: H2 n=21, mean +1.50%, Top3-ex -1.58%

## Decision

Do not promote current Consensus as a complete replacement yet.

The next useful experiment is **cooldown with replacement**, not cooldown by dropping trades:

1. export Top-K ranked candidates for every date/session before the final causal-top step;
2. freeze a simple same-symbol cooldown such as 3 or 5 trading days before inspecting replacement outcomes;
3. when rank #1 is blocked by cooldown, select the highest-ranked eligible replacement;
4. compare mean, median, +10/+20, loss10, Top3-ex, unique-symbol count, max-symbol share and month/week concentration;
5. do not tune the cooldown against 2026;
6. keep the ATR OOD gate frozen.

This requires the full candidate pool or Top-K artifact. The existing V42/V43 artifacts contain only the final selected row per date/session, so a valid replacement-candidate test cannot be reconstructed from those artifacts alone.

## Implication for system architecture

Consensus remains interesting as a **specialist signal** because:
- it survives next-open execution delay;
- it survives meaningful friction stress;
- the frozen ATR OOD gate prevents the observed 2026 collapse.

But the current selector may be exploiting persistent single-symbol runs rather than consistently finding independent opportunities across the market. Diversification/generalization must be demonstrated before promotion.


## Benchmark concentration vs preserved Stable★6

Preserved exact Stable★6 teacher (2026-03-05..2026-08-31):
- n=55
- unique symbols=54
- max symbol count=2
- max symbol share=3.64%
- top-2 symbol share=5.45%
- top-5 symbol share=10.91%
- HHI=0.0188
- trades belonging to repeated symbols=3.64%

Consensus fixed-min95, 2025 ATR-gated:
- n=101
- unique symbols=29
- max symbol count=30
- max symbol share=29.70%
- top-2 symbol share=44.55%
- top-5 symbol share=62.38%
- HHI=0.1297
- trades belonging to repeated symbols=83.17%

The periods are not identical, so this is not a direct performance comparison. It is a structural diagnostic: legacy Stable★6 is naturally diversified across symbols, while current Consensus repeatedly reselects persistent winners. The diversification concern is therefore materially larger than in the benchmark system.
