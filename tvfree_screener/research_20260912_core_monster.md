# TV-Free research update 2026-09-12

Research-only. No production writes. Do not use Stable/Sniper/Mega signal matching as an objective.

## Fixed evaluation premise
- 2026 is reporting/robustness only, never threshold tuning.
- Production Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView and watchlist workflows remain untouched.
- Main objective: independent TV-Free Core and Monster that can compete with or exceed legacy Stable★6 on forward 5BD performance and robustness.

## Core independent deterministic families — rejected
Using frozen run-80 daily OHLCV, four low-DOF non-ML families were tested with next-open -> 5BD:
- C1 controlled reversal
- C2 early momentum after pullback
- C3 compression continuation
- C4 rebound confirmation

All four failed cross-period robustness or lacked sufficient right-tail payoff. Typical means stayed around 0-1%, with Top3-excluded means frequently <=0. They are too defensive to compete with Stable★6 and are rejected rather than threshold-tuned.

## Monster weak+early gate — confirmed as a useful structure
Fixed gate:
1. market `med_ret5 <= 0`
2. candidate `ret10 <= 0.5735294117647058`

The gate is applied to the preserved causal V7 Tail population. No 2026 outcomes were used.

### Same-day ranking comparison, 2023-2024 development
One candidate per day, Tail CDF only as tie-break.

`volr20 LOW`:
- n=128
- mean +6.24%
- median +1.06%
- +20% 18.75%
- +50% 8.59%
- -10% 25.78%
- Top1 excluded +5.41%
- Top3 excluded +3.81%

`body_pct LOW`:
- n=128
- mean +6.46%
- median +1.25%
- +20% 17.97%
- +50% 7.81%
- -10% 28.12%
- Top1 excluded +5.64%
- Top3 excluded +4.03%

`volr20 + body_pct` mean percentile rank:
- n=128
- mean +7.16%
- median +1.81%
- +20% 19.53%
- +50% 8.59%
- -10% 25.78%
- Top1 excluded +6.35%
- Top3 excluded +4.75%

Period means for the combined rank:
- 2023H1 +9.07%
- 2023H2 +0.21%
- 2024H1 +10.41%
- 2024H2 +6.92%

### 2025 descriptive check
2025 is not treated as pristine because it has already been inspected in prior research.

`body_pct LOW`:
- n=44
- mean +6.78%
- Top3 excluded +0.03%
- +20% 20.45%
- -10% 31.82%

`volr20 LOW`:
- n=44
- mean +6.58%
- Top3 excluded -0.19%
- +20% 18.18%
- -10% 31.82%

`volr20 + body_pct`:
- n=44
- mean +6.09%
- Top3 excluded -0.71%
- +20% 18.18%
- -10% 34.09%

Interpretation: combining the two improves 2023-2024 development strongly, but does not improve 2025 tail robustness. `body_pct LOW` deserves to remain an independent Monster ranking candidate rather than being automatically blended into V16.

## Next research
1. Walk-forward/fold test `body_pct LOW` versus `volr20 LOW` under the fixed weak+early gate without adding thresholds.
2. Audit monthly/weekly concentration and symbol concentration for both rankers.
3. Core: stop pure low-volatility reversal families; next architecture must explicitly preserve a moderate right tail (+10/+20 capture) while constraining loss10.
