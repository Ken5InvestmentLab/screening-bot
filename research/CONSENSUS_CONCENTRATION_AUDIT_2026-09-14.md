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


## Overlapping 5BD episode audit — critical finding

Because the evaluation target is a 5-business-day holding horizon, repeated signals in the same symbol can represent overlapping exposure to the same move.

Episode definition:
- same symbol;
- consecutive selected signals belong to the same episode while the next signal occurs fewer than 5 trading days after the previous selected signal;
- a gap of 5 or more trading days starts a new episode.

ATR-gated 2025 min95:
- 101 selected signals
- only **43 non-overlapping symbol episodes**
- 57.4% of signal rows are additional observations inside an already-open 5BD episode.

Extreme examples:
- 3350: 30 signals but only **2 episodes** (one episode contains 20 selected rows, the other 10).
- 2334: 15 signals but only **3 episodes**.
- 7318: 8 signals but only **2 episodes**.

Using realistic next-open -> D+5 returns and retaining only the first selected signal of each episode:

Full 2025:
- n=43
- mean **+0.23%**
- median -0.05%
- win 41.86%
- +10% 9.30%
- +20% 2.33%
- <=-10% 11.63%
- Top3-ex mean **-1.17%**

2025 Jul-Dec:
- original gated signals n=34, mean +6.33%, Top3-ex +2.94%
- non-overlapping episode-first n=19
- mean **+0.27%**
- median 0.00%
- win 42.11%
- +10% 10.53%
- +20% 5.26%
- <=-10% 15.79%
- Top3-ex mean **-2.49%**

This materially changes the interpretation.

The current Top-1 Consensus headline is largely generated by repeatedly selecting symbols **after an episode is already underway**. It is not yet evidence of 101 independent opportunities.

This does not prove the ranking signal is useless:
- a user could pyramid/re-enter the same symbol, so repeated signals can have economic value;
- later signals may genuinely identify continuation within a winning episode.

But for a practical one-position-per-symbol / finite-capital system, the unadjusted mean substantially overstates diversification and independent opportunity count.

This makes V44 cooldown-with-replacement the decisive next test. If Top-K replacements preserve a strong mean when the currently-held symbol is blocked, Consensus can still become a useful diversified specialist. If replacement performance collapses, the current architecture should be demoted to a same-symbol continuation/pyramiding signal rather than a Stable★6 replacement.


## Episode-position diagnostic — do not promote as a tuned rule

Within the 43 non-overlapping 2025 symbol episodes, next-open -> D+5 performance differs sharply by prior Consensus-selection history:

- episode first signal: n=43, mean +0.23%, Top3-ex -1.17%
- any repeat signal (position >=2): n=58, mean **+13.27%**, median +13.75%, win 79.31%, +10% 62.07%, Top3-ex +11.43%
- second signal only: n=15, mean -0.38%, Top3-ex -4.01%
- third-or-later signal: n=43, mean **+18.03%**, median +15.16%, win 90.70%, +10% 79.07%, +20% 37.21%, <=-10% 0%, Top3-ex +15.86%

2025 Jul-Dec:
- first signal: n=19, mean +0.27%, Top3-ex -2.49%
- repeat signal: n=15, mean +14.00%, Top3-ex +7.16%
- second signal: n=6, mean -0.76%
- third-or-later: n=9, mean +23.84%, all 9 positive

This is a retrospective diagnostic and must **not** be converted directly into a promoted "third signal" rule because these outcomes are already open and heavily concentrated in a few symbols.

Interpretation:
- the current Consensus model is not primarily discovering strong new independent episodes;
- its apparent edge is concentrated in repeated confirmation after a persistent winning move is underway;
- if V44 cooldown-with-replacement succeeds, the underlying ranker may still be useful as a diversified selector;
- if V44 fails, Consensus should be reclassified as a continuation/re-entry or pyramiding specialist rather than a Stable★6 replacement.

A future continuation rule, if pursued, must be separately preregistered and tested on genuinely later data.


## Same-day duplication is not the main cause

Because both 09:00 and 13:00 selections on the same symbol/day share the same next-day-open and D+5 daily-close return, a same-day duplicate check was also run.

ATR-gated 2025:
- raw: n=101, next-open mean +7.72%, Top3-ex +6.52%
- one row per symbol/day: n=80, mean **+6.23%**, Top3-ex +4.65%

2025 Jul-Dec:
- raw: n=34, mean +6.33%, Top3-ex +2.94%
- one row per symbol/day: n=29, mean **+7.13%**, Top3-ex +3.18%

Therefore the concentration problem is **not primarily 09:00/13:00 duplicate counting**. The larger issue is repeated selection of the same symbol across multiple trading days inside one continuing 5BD move.


## CORRECTION — chained episode audit superseded

The earlier "43 episode / +0.23% episode-first" section above used a **chained-gap episode definition**: a continuing stream of signals with each adjacent gap <5 sessions was treated as one episode indefinitely. That is too strict for a real 5BD holding policy because a position opened from signal day D can be closed at D+5 and the symbol can then be entered again.

Therefore the 43-episode and "episode-first +0.23%" figures are retained only as a persistence diagnostic and are **superseded for capital/position interpretation**.

Correct causal one-position-per-symbol stress:
- select the first eligible Top-1 signal;
- block the same symbol while the existing 5BD position is active;
- once 5 official trading sessions have elapsed from the selected signal date, allow re-entry;
- no replacement candidate is used in this stress.

2025 full-year:
- raw gated signals: n=101, mean +7.72%, Top3-ex +6.52%
- 5-session same-symbol cooldown, no replacement: n=52
- mean **+3.05%**
- median +0.29%
- win 50.00%
- +10% 19.23%
- +20% 9.62%
- <=-10% 9.62%
- Top3-ex mean **+1.21%**
- unique symbols 29
- max-symbol share 11.54%

2025 Jul-Dec:
- raw gated: n=34, mean +6.33%, Top3-ex +2.94%
- 5-session same-symbol cooldown, no replacement: n=22
- mean **+3.58%**
- median +0.29%
- win 50.00%
- +10% 18.18%
- +20% 13.64%
- <=-10% 13.64%
- Top3-ex mean **-0.81%**

Additional frozen cooldown stresses:
- 2 sessions: 2025 n=64 mean +5.04%, Top3-ex +3.22%; H2 n=25 mean +5.30%, Top3-ex +1.75%.
- 3 sessions: 2025 n=56 mean +3.76%, Top3-ex +1.86%; H2 n=23 mean +4.11%, Top3-ex +0.01%.
- 5 sessions: figures above.

Revised interpretation:
- the earlier claim that a one-position-per-symbol implementation reduces Consensus to near-flat was **too pessimistic**;
- nevertheless, a realistic 5-session no-overlap policy roughly halves the full-year headline mean (+7.72% -> +3.05%) and weakens robust H2 performance;
- concentration/overlap remains a real issue, but Consensus still retains some positive edge before replacement;
- V44 cooldown-with-replacement remains the correct decisive test.

The earlier "third-or-later signal" analysis is also **not valid as a production holding-policy rule**, because its positions were defined inside the same chained episode construction. It may still describe persistence in long trends, but it must not be used to claim that the third signal is independently tradable or superior.


## Capital-capacity fairness check

A separate 5BD exposure-count check shows that Consensus is **not** obviously worse than Stable★6 in raw simultaneous-position capacity. The main issue is symbol independence, not an impossible number of concurrent holdings.

Using signal D -> enter D+1 -> exit D+5:

Preserved Stable★6 teacher:
- max simultaneous positions: 8
- 95th percentile concurrent positions: 5
- mean active positions across the covered trading-date span: 2.20

Consensus raw ATR-gated 2025 signals:
- max simultaneous positions: 10
- 95th percentile: about 7.7
- mean active positions: 2.04

Consensus with correct 5-session same-symbol cooldown and no replacement:
- max simultaneous positions: 7
- 95th percentile: 4
- mean active positions: 1.06

Therefore the concern should be stated precisely:
- raw Consensus does not require absurdly larger portfolio capacity than Stable★6;
- it does reuse the **same symbols** far more often;
- enforcing one-position-per-symbol reduces both trade count and performance;
- V44 asks whether unused Top-K alternatives can fill that freed capacity without destroying edge.


## Repeated-symbol structure: same-day duplication vs multi-day persistence

Using the ATR-gated 2025 min95 selected rows:

### 3350
- selected rows: 30
- unique signal days: **18**
- session 09 rows: 12
- session 13 rows: 18
- days with both sessions selected: 12

### 2334
- selected rows: 15
- unique signal days: **11**
- session 09 rows: 6
- session 13 rows: 9
- days with both sessions selected: 4

### 7318
- selected rows: 8
- unique signal days: 7
- only one day has both sessions.

### 6574
- selected rows: 6
- unique signal days: 4
- two days have both sessions.

Interpretation:
- same-day 09/13 duplication contributes, especially for 3350;
- it is **not** sufficient to explain the concentration;
- the dominant structural issue is repeated selection of the same symbol across multiple trading days during persistent trends;
- therefore deduplicating same-day alerts alone would not solve the generalization/capital-allocation problem;
- cooldown-with-replacement remains the relevant test.
