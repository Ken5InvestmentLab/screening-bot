# 天底極致 Cloud — TV-Free / MTF Research State

Updated: 2026-09-11 JST

## Safety / branch policy
- Production `main`, Discord, Spreadsheet are unchanged.
- Research branch: `research/tentei-cloud-mtf`.
- Do not promote research logic to production without explicit approval.

## Goal
Build a TradingView-free JPX stock screening system that can compete with the current 天底極致 + Stable★6 / Sniper / Mega stack, while preserving the ability to catch rare monster winners.

## Source data currently available
- Confirmed BOTTOM teacher set: 3,938 rows, 2026-03-05 to 2026-09-02.
- Raw 4H/session OHLCV: 426,282 source rows; de-duplicated research frame 425,796 rows; 1,332 symbols; 2025-12-23 to 2026-09-10.
- Independent 5BD label reconstructed from raw OHLCV has correlation 0.9166 with teacher `perf_5bd` on 3,909 matched teacher signals. Median absolute difference is 0.029 percentage points; mean absolute difference is 0.294 percentage points.

## Old benchmark that must remain visible
Historical V3 Short result (exact thresholds lost; do not claim reproducibility):
- Mar-Aug 2026: 29 trades
- 5BD average +5.42%
- median +2.06%
- win rate 65.5%

Current Stable★6 is strongly tail-dependent. Removing the top 5 2026 winners reduced the mean from about +6.06% to about -0.31%. Monster capture is therefore an explicit objective, not an outlier to suppress.

## Teacher-signal filter research
V3R-A (filter applied to confirmed existing BOTTOM signals; NOT yet TV-free final):
`ich_price_tenkan AND NOT rci26_os AND pre_down3 AND gap_up AND vp_no_overhead`
- Train n39 avg +5.74%
- Validation n9 avg +7.28%, win 88.9%
- Previously opened Aug holdout n10 avg +6.62%, median +1.95%, win 60.0%, no <=-10% cases

V3R-B:
`ich_price_tenkan AND NOT ich_cloud_above AND pre_down3 AND gap_up AND vp_no_overhead`
- Holdout n7 avg +8.66%, median +2.4%, win 71.4%
- Sample is too small to promote.

## Independent 4H/session research
Universe constraints are aligned to current production intent:
- previous daily close <= 1,000 JPY
- previous daily volume >= 10,000 shares
- candidate session volume >= 5,000 shares
- 5 business-day return is measured from candidate-session close
- repeated picks in the same symbol are suppressed with a 5-business-day cooldown

### SAFE lane (independent, no TradingView BOTTOM)
Conditions:
- RSI(12) < 45
- previous 3 completed session closes are descending
- current close > Bollinger(20) midline
- ATR(14) / close < 5%

With 5BD cooldown, Feb-Aug:
- n114
- average +1.28%
- median +0.54%
- win rate 51.75%
- >=10%: 9.65%
- >=20%: 1.75%
- <=-10%: 1.75%
- top-5 removed average +0.33%

Pseudo forward block Jul-Aug:
- n26
- average +1.25%
- median +1.35%
- win rate 73.08%
- <=-10%: 0%

A stricter exploratory overlay using ATR 3%-8% produced roughly +5% mean in Train/Validation but only 6 later observations, so it is research-only due to sample size.

### TAIL lane (independent, no TradingView BOTTOM)
Conditions:
- close is NOT above EMA75
- MACD histogram is NOT positive
- current close > Bollinger(20) midline
- current candle is NOT bullish (close <= open)
- session high-low range / close >= 2%

With 5BD cooldown, Feb-Aug:
- n215
- average +2.20%
- median 0.00%
- win rate 46.98%
- >=10%: 11.63%
- >=20%: 5.58%
- >=30%: 3.26%
- <=-10%: 3.72%
- max +97.44%
- top-1 removed average +1.75%
- top-3 removed average +1.13%
- top-5 removed average +0.76%

Large examples include 4170 +97.44%, 6085 +76.21%, 462A +58.05%, 4259 +42.30%, 7256 +38.84%, 6166 +38.00%.

### SAFE OR TAIL union
With 5BD cooldown, Feb-Aug:
- n326
- average +1.85%
- median 0.00%
- win rate 48.16%
- >=10%: 10.74%
- >=20%: 4.29%
- >=30%: 2.45%
- <=-10%: 3.07%
- top-1 removed average +1.56%
- top-3 removed average +1.15%
- top-5 removed average +0.91%

This is not yet competitive with the historical +5.42% V3 target. Keep separate SAFE and TAIL lanes rather than flattening them too early.


### MONSTER lane — range threshold sweep
Base conditions are the TAIL structure, but the session range threshold is raised to explicitly target explosive moves:
- close <= EMA75
- MACD histogram <= 0
- close > Bollinger(20) midline
- close <= open
- session high-low range / close >= threshold
- same production-like universe filters and 5BD symbol cooldown

Range 4.0% exploratory version:
- Feb-Aug n23
- average +5.94%
- median +1.02%
- win rate 56.52%
- >=10% 26.09%
- >=20% 13.04%
- >=30% 8.70%
- <=-10% 4.35%
- later Jul-Aug block n14, average +6.42%, median +1.42%, win 64.29%
- top-1 removed all-period average +3.57%
- top-3 removed +1.04%
- top-5 removed -0.71%

This is intentionally tail-dependent and is therefore similar in character to historical V3, but sample distribution is thin (early Train only 3 picks). It is NOT a final winner yet.

Range sweep summary:
- 2.5%: n66, avg +4.04%, win 46.97%, >=20% 7.58%, top-5 removed +0.25%
- 3.0%: n47, avg +3.79%, win 48.94%, >=20% 8.51%, top-5 removed +0.12%
- 3.5%: n36, avg +3.64%, win 50.00%, >=20% 8.33%, top-5 removed -0.59%
- 4.0%: n23, avg +5.94%, win 56.52%, >=20% 13.04%, top-5 removed -0.71%
- 4.5%: n17, avg +4.60%, win 52.94%
- 5.0%: n15, avg +1.33%
- 6.0%: n9, avg +0.61%

Interpretation: 4% maximizes explosive average but 2.5-3% supplies more observations. Treat them as separate Monster / Monster-Lite candidates rather than choosing a single threshold from the already-inspected Jul-Aug block.

## Regime finding
Simple market-regime filters changed behavior materially across Feb-Jun vs Jul-Aug. Several rules that looked excellent in early samples stopped firing later. Therefore:
- do not hard-code a month/regime threshold just because it improves one block;
- retain temporal Train / Validation / later-block reporting;
- the Aug block has already been inspected and must no longer be described as untouched.

## 1H research setup
Existing GAS already proves Yahoo Finance 1H retrieval works for JPX via:
`query1.finance.yahoo.com/v8/finance/chart/<symbol>?interval=1h...`

Research branch now contains:
- `research/tentei_cloud/fetch_1h.py`
- `research/tentei_cloud/symbols_4h_universe.txt` (1,332-symbol same-universe comparison set)
- `.github/workflows/tentei-cloud-1h-research.yml`

The workflow uses 8 shards, retries transient Yahoo errors, stores failure JSON, and uploads per-shard CSV artifacts. A research-branch-only push trigger is now available through `research/tentei_cloud/RUN_1H`; production workflows remain untouched.

## 1H full-universe result — DIRECT 1H REPLACEMENT REJECTED
Actions fetch run `34591970828` completed all 8 shards successfully.
- 1H rows: 1,253,032
- usable symbols: 1,315 / 1,332 target symbols
- date range: 2026-02-02 to 2026-09-10
- production-like eligible 1H bars: 451,702

Direct 1H translation of the 4H SAFE/Core rule:
- n291
- average -0.13%
- median -0.11%
- win 47.8%
- >=10% 5.15%
- <=-10% 6.87%
- Jul-Aug average -1.09%

This is materially weaker and less stable than the existing 4H SAFE lane (+1.28% all-period, +1.25% Jul-Aug). **Do not replace 4H Core with this 1H rule.**

Direct 1H translation of the 4H TAIL/Monster structure also failed:
- Watch/Prime test output n70
- average -2.28%
- median -3.11%
- win 35.7%
- <=-10% 11.4%

The first Watch/Prime implementation ranked the already-sparse Monster pool at each exact 1H timestamp. Watch and Prime therefore collapsed to the same set when a timestamp had only one candidate. Treat that tiering as invalid and do not use those results to define user-facing thresholds.

Decision:
- 1H is **not** a standalone replacement for 4H Core or 4H Monster.
- Keep Core anchored to 4H/session + daily context.
- Use 1H only as a possible MTF precursor/context feature around a 4H candidate.

## 1H Monster precursor test — HIGH RECALL, LOW STANDALONE PRECISION
Actions analysis run `34592471625` tested three fixed 1H momentum precursor families against the 1H universe and eight already-known Monster reference events. This is descriptive 2026 research, not untouched validation.

Known-Monster recall within the preceding 7 calendar days:
- fast: 8/8, median lead 143.5h
- balanced: 8/8, median lead 117.0h
- breakout: 6/8, median lead 142.5h

But as standalone universe signals after the same production-like eligibility filter and 5BD cooldown:
- fast: n5,366 matured, avg -0.90%, win 37.5%, <=-10% 12.1%
- balanced: n3,369, avg -1.32%, win 36.3%, <=-10% 16.5%
- breakout: n4,295, avg -0.84%, win 38.9%, <=-10% 11.2%

Interpretation:
- 1H activity clearly appears before the known Monster events, so 1H contains useful precursor information.
- The precursor fires far too broadly and often several days too early; it is not a buy signal by itself.
- The useful hypothesis is now narrower: **at the moment a 4H Monster candidate appears, score the recency/strength of recent 1H activation**. The 4H structure remains the gate.

## 4H reconstruction audit
The original full 4H candidate table was not persisted as a reusable artifact, so two-session bars were reconstructed from genuine Yahoo 1H data as a recovery test.

Observed genuine 1H clocks are 09:00 through 15:00. Three fixed split schemes were tested. Splitting at 12:30 or 13:00 is equivalent on this dataset and was materially closer to the known 4H aggregate baseline than splitting at 12:00.

Best reconstruction (09:00-12:00 -> AM / 13:00-15:00 -> PM):
- reconstructed TAIL: n117, avg +1.87% vs known original n215, avg +2.20%
- reconstructed 4% Monster: n30, avg +2.09% vs known original n23, avg +5.94%

Conclusion:
- session semantics are plausible and the TAIL mean is close,
- but candidate counts and Monster-tail behavior are not close enough to claim exact recovery,
- therefore reconstructed 4H must NOT be presented as the original 4H signal set.
- It is still useful as a controlled common baseline for measuring the *incremental value* of 1H context, because 4H-only and MTF can be compared on the identical reconstructed candidate pool.

## Predeclared causal MTF comparison
Before opening extended historical results, `research/tentei_cloud/mtf_monster_model.py` fixes this protocol:
- fetch 1H history back to 2024-09-16 for warmup,
- reconstructed 4H TAIL gate with 13:00 split and range >=2%,
- 5BD same-symbol cooldown,
- development/train: 2024-11-01 to 2025-06-30,
- validation: 2025-07-01 to 2025-12-31,
- target: 5BD >= +20%,
- compare the same Random Forest architecture using 4H-only features vs 4H + recent 1H context,
- Watch = >= training OOB probability 70th percentile,
- Prime = >= training OOB probability 90th percentile,
- do not subtract a loss model from tail rank,
- 2026 remains reporting-only and is opened only if a fixed 2025 validation gate passes.

This is specifically designed to test whether 1H adds real incremental information instead of merely producing more signals.

## Next research sequence
1. Reconstruct or recover the full 4H Monster candidate table, including losers, so 1H features can be evaluated at the 4H candidate timestamp rather than on known winners only.
2. Test recent-1H context windows at each 4H candidate: same session / prior 3h / 6h / 12h / prior trading day, using signal-time-only features.
3. Build user-facing tiers from the full 4H candidate pool: **Monster Watch** = broader high-quality candidates, **Monster Prime** = stricter top score. Do not percentile-rank within a sparse exact-timestamp subset.
4. Compare MTF score against the fixed 4H baselines on n, mean, median, >=10/20/30%, <=-10%, top1/3/5 removed mean, and monthly consistency.
5. Keep **Core** separate; do not force Monster logic into the stable lane.
6. Only after MTF scoring is robust, test dilution/warrant risk and fundamentals as optional graded overlays.

## Naming
Working product name: **天底極致 Cloud**
