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

## Full-universe / uncapped audit results

### V40 Full Universe Fixed — completed
Run 34614216028, historical watchlist-union, no 350-symbol cap.

- min97: n=41, mean -3.051%, median -5.044%, win 29.27%, +10% 7.32%, min -19.70%
- min98: n=32, mean -3.955%, median -5.910%, win 31.25%, +10% 6.25%, min -19.70%
- June min98 mean -0.31%; July min98 mean -10.03%
- Yahoo 1h: 1474/1555 symbols fetched; positive-key coverage 87.21%

Interpretation: the old V29/V31 +4.7% to +4.9% headline does not survive removal of the 350-symbol sampling on the historical-watchlist universe. Treat V29/V31 as sample-dependent research evidence, not a standalone production candidate.

### V42 2026 Uncapped Frozen — completed
Run 34616757127, current-JPX-survivor frozen universe, no 1000-symbol/day cap.

- min90: n=83, mean -5.90%, median -6.48%, win 19.51%, +10% 3.61%, <=-20% 5 trades
- min97: n=55, mean -7.31%, median -8.15%, win 16.36%, +10% 3.64%, <=-20% 5 trades
- min98: n=47, mean -9.57%, median -9.12%, win 10.64%, +10% 0%, <=-20% 5 trades
- min99: n=25, mean -10.95%, median -9.28%, win 4%, +10% 0%

Interpretation: raising consensus threshold makes 2026 uncapped performance worse, not better. This rejects the idea that the V31 min98 result was a generally monotonic high-confidence signal on the full eligible universe.

### V43 2025 Uncapped — completed
Run 34617009116. Reverse-time robustness test, evaluation 2025-01-06..2025-12-30, no 1000-symbol/day cap. Current-survivor bias remains.

Fixed thresholds all positive, with monotonic improvement as threshold rises:
- min90: n=197, mean +4.82%, median +1.77%, win 58.95%, +10% 28.43%, <=-20% 2.03%
- min95: n=112, mean +6.35%, median +4.67%, win 66.97%, +10% 36.61%, <=-20% 3.57%
- min97: n=71, mean +7.65%, median +7.54%, win 66.20%, +10% 45.07%, +20% 21.13%, +50% 2.82%, <=-10% 15.49%, <=-20% 5.63%
- min98: n=55, mean +10.23%, median +11.29%, win 74.55%, +10% 54.55%, +20% 25.45%, +50% 1.82%, <=-10% 10.91%, <=-20% 5.45%
- min99: n=39, mean +13.18%, median +17.39%, win 82.05%, +10% 66.67%, +20% 33.33%, +50% 2.56%, <=-10% 10.26%, <=-20% 7.69%

V43 min98 destructive concentration checks:
- top1 removed mean +9.37%
- top3 removed mean +8.19%
- best week removed mean +8.65%
- best month (2025-01) removed mean +6.84%
- max +56.41%, min -47.12%

V43 min97:
- top1 removed +6.90%
- top3 removed +5.68%
- best week removed +6.06%
- best month removed +4.12%

Interpretation: Consensus has genuine signal in 2025 even without the historical 1000-symbol cap and is not explained by one top trade/week/month. However it reverses sharply in 2026. The core problem is regime/time instability, not simply lack of predictive signal.

## Updated decision

1. V29 fixed_min98_both remains a useful historical clue but is demoted as a production candidate because V40 full-universe results collapse.
2. V31 remains a reproducible research architecture, not a final model.
3. V43 proves the 3-head Consensus architecture can be extremely strong in some regimes; do not discard it.
4. V42 proves a single static min-threshold policy is unsafe across regimes.
5. Next priority is a pre-2026/purge-safe regime gate or model-selection rule learned strictly before each evaluation block, with 2026 used only as descriptive robustness. The objective is to retain V43-style upside while avoiding V42-style failure.
6. Do not tune a 2026-specific threshold or rule.
7. Run execution-timing-realistic returns (next-open / next-close where applicable) before production promotion.
8. Never merge to production main without explicit user Go.

## Running / next research

V41 destructive stress was prepared for V40 but V40 itself collapsed, so destructive stress on V40 is no longer priority.

Next concrete experiment:
- characterize pre-2026 market/regime variables on V43 candidate blocks;
- define only a very low-DOF gate (ideally 1-2 conditions) from pre-2026 data;
- nested/purged validation only;
- freeze the gate before looking at 2026 descriptive results;
- evaluate 5BD mean, median, win, +10/+20/+50, -10/-20, n, month/week concentration, Top1/Top3, and implementation simplicity.

Production main remains untouched.