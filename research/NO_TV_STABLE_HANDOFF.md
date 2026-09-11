# No-TV Stable/Core Research Handoff

Updated: 2026-09-12 JST

## Goal

Replace or complement production TradingView Stable★6 with a TradingView-free system that can compete on 5BD performance.

Research principle:
- primary objective: economically meaningful 5BD mean and +10/+20 hit rate;
- stability is a constraint, not the objective;
- +1% to +2% is not sufficient merely because losses are low;
- positive skew / strong-regime concentration is allowed, but must be measured.

Production main is untouched.

## Production benchmark

Preserved exact Stable★6 teacher, 2026-03-05..2026-08-31:
- n=55
- mean +6.587%
- median +1.5%
- win 56.36%
- +10% 18.18%
- +20% 14.55%
- <=-10% 10.91%
- max +90.2%
- top1 removed mean +5.039%

## Stable-reproduction lane

V37 Bottom gate: August n=31, mean +1.068%, +10% 12.90%, <=-10% 3.23%. Too weak as final.

V38 payoff rank: August n=15, mean +1.912%, +10% 26.67%, <=-10% 6.67%. Better but still too weak.

V39 purged monthly payoff:
- best fixed s6_return_top1: n=51, mean +1.667%, +10% 17.65%, +20% 5.88%, <=-10% 7.84%, top1 removed +0.861%
- adaptive validation-selected: n=95, mean +0.283%

Conclusion: Stable reproduction plus extra filtering is not the primary replacement path.

## Independent 3-head Consensus lane

This lane learns directly from 5BD outcomes, not TradingView BOTTOM labels:
1. probability of positive 5BD return;
2. probability of >= +10%;
3. predicted 5BD return.

Each head is percentile-ranked within date/session. cons_min is the minimum of the three ranks.

V29 horizon-purged rolling:
- min97: n=50, mean +3.695%, robust +3.790%, +10% 26.0%
- min98: n=35, mean +4.859%, median +2.899%, robust +5.067%, +10% 31.43%

V31 five-business-day prequential:
- min97: n=51, mean +4.304%, robust +4.121%, +10% 25.49%, worst -15.35%
- min98: n=35, mean +4.746%, robust +4.707%, +10% 28.57%, worst -15.35%, no <=-20% trades

Threshold 0.97 is also strong, so 0.98 is not a one-point accident.

## Concentration warning

V31 is heavily concentrated in 2026-08-12..2026-08-18.
- min98 raw +4.746%; remove strongest block -> approx -0.314%
- min97 raw +4.304%; remove strongest block -> approx +0.471%

This is a diagnostic, not an automatic rejection. Production Stable★6 is also positively skewed.

## Candidate-universe cap finding

Frozen current-JPX-survivor daily OHLCV, eligibility = previous close <=1000 and previous volume >=10000.

2026-03-05..2026-08-31:
- 121 days
- mean eligible/day 933.7
- median 931
- max 1158
- days over 1000: 12
- unique eligible symbols: 1516

2025:
- 243 days
- mean eligible/day about 1047.5
- max 1669
- days over 1000: 171
- unique eligible symbols: 1870

Therefore the historical TradingView 1000-symbol cap matters much more in 2025.

## Running research

V40 Full Universe Fixed
- run 34614216028
- purpose: remove old 350-symbol sampling and test fixed min97/min98 across all historical watchlist symbols
- caveat: daily historical watchlist may still be capped at 1000

V41 destructive stress
- code/workflow prepared; consumes V40 artifact
- removes best trade, top 3 trades, best day, best 3 days, best week, best 2 weeks
- also monthly/session/symbol concentration and day-block bootstrap

V42 2026 Uncapped Frozen
- run 34616757127
- eliminates 1000-symbol/day cap
- frozen daily data defines historical eligibility
- Yahoo 1h only for 1516 symbols ever eligible
- fixed thresholds 0.90 / 0.95 / 0.97 / 0.98 / 0.99
- caveat: current-survivor bias remains

V43 2025 Uncapped
- run 34617009116
- initial history 2024-10..2024-12
- evaluation 2025-01..2025-12 in 5-signal-day prequential blocks
- no 1000-symbol/day cap
- fixed thresholds 0.90 / 0.95 / 0.97 / 0.98 / 0.99
- reverse-time robustness test; current-survivor bias remains

## Decision logic

1. If V40 collapses, old +4.8% was likely 350-symbol sample dependent.
2. If V40 survives but V42 collapses, historical cap/watchlist composition mattered.
3. If V42 survives and adjacent thresholds survive, Consensus becomes a serious standalone candidate.
4. V43 is the key time/regime robustness check.
5. If V43 also survives, next: destructive stress, live 09/13 implementation parity, complementarity vs Stable★6, then shadow run.
6. Never merge to production main without explicit user Go.