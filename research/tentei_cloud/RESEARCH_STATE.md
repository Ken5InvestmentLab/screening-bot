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

The workflow uses 8 shards, retries transient Yahoo errors, stores failure JSON, and uploads per-shard CSV artifacts. It is manual-dispatch only. The connected GitHub tool currently exposes workflow read/retry operations but not starting a new workflow, so dispatch must occur through another available execution path or the GitHub UI/CLI.

## Next research sequence
1. Fetch the 1H dataset for the same 1,332-symbol universe.
2. Reconstruct the same production universe filters and 5BD labels on 1H.
3. Evaluate 1H SAFE-like, 1H tail-capture, and independent reversal triggers.
4. Compare 1H vs 4H vs Daily on identical dates/symbols.
5. Test MTF: 1H early trigger -> 4H confirmation / veto -> Daily regime veto.
6. Keep metrics: n, mean, median, win rate, >=10/20/30%, <=-10%, top1/3/5 removed mean, monthly consistency.
7. Only after a robust trigger exists, test dilution/warrant risk and fundamentals as optional graded overlays.

## Naming
Working product name: **天底極致 Cloud**
