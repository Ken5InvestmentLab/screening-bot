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

## Extended 1H history audit
A longer Yahoo 1H research pull was completed successfully for all 8 shards:
- source range actually returned: 2024-09-17 to 2026-09-10
- CSV rows: 4,019,524
- target symbols: 1,332
- symbols seen: 1,315
- missing symbols: 17
- failed chunks: 272 across 61 symbols
- persistent error groups: HTTP 400 = 153, HTTP 404 = 119

This is adequate for broad research but the missing/failed-symbol audit must remain visible. Do not describe the historical universe as perfectly complete.

## Causal pre-2026 MTF result — GENERIC 1H ADDITION REJECTED
Workflow run `34593465081` used only pre-2026 validation for model selection. The 2026 reporting block was kept closed because the validation gate failed.

Candidate pool:
- reconstructed fixed 4H TAIL gate
- 297 matured candidates in the full fetched span
- TRAIN 2024-11-01..2025-06-30: n103
- VALIDATION 2025-07-01..2025-12-31: n36
- 2026 reporting candidates held closed by the gate: n151

A +20% target was statistically impossible in TRAIN (1/103). A predeclared TRAIN-only feasibility rule therefore selected the highest return threshold with at least 8 positives and 8 negatives:
- >=20%: 1/103
- >=15%: 2/103
- >=10%: 6/103
- >=7.5%: 8/103
- selected classification target: **>= +7.5% at 5BD**

Validation base pool (n36):
- avg +2.21%
- median +1.19%
- win 55.6%
- >=10% 13.9%
- >=20% 5.6%
- <=-10% 2.8%

4H-only model:
- Watch n11: avg +5.03%, median +1.96%, win 63.6%, >=10% 36.4%, >=20% 18.2%, <=-10% 9.1%
- Prime n5: avg +6.76%, median +1.96%, win 80.0%, >=10% 40.0%, >=20% 20.0%, <=-10% 0%

MTF model (same RF architecture, adding recent 1H features):
- Watch n14: avg +3.51%, median +1.79%, win 64.3%, >=10% 21.4%, >=20% 14.3%, <=-10% 7.1%
- Prime n4: avg +2.94%, median +1.79%, win 75.0%, >=10% 25.0%, >=20% 0%, <=-10% 0%

The fixed validation gate failed because:
- MTF Watch n<15,
- MTF Prime n<8,
- MTF Prime mean did not beat 4H-only Prime.

Decision:
- **Reject generic 1H feature stacking for Monster scoring.**
- Keep 1H out of the primary rank for now.
- The 4H-only rank is materially more promising on this validation block, but n11/n5 is too small for production promotion.
- 1H may still be investigated later as a narrowly defined veto/precursor feature, but only as a separate exploratory layer.
- Do not open the withheld 2026 model report merely to rescue this result.

## 4H ensemble stability and walk-forward
A 7-seed stability audit confirmed that the fixed pre-2026 4H-only validation result was not primarily a random-seed accident:
- Watch across 7 seeds: n10-14, mean +2.45% to +5.03%, mean across seeds +4.32%
- Prime across 7 seeds: n5-7, mean +4.66% to +6.76%, mean across seeds +6.46%
- pairwise selection Jaccard: Watch avg 84.1%, Prime avg 91.8%
- seed42 bootstrap 95% CI still crosses zero because sample size is small (Watch n11 CI about -3.61%..+14.38%; Prime n5 about -0.79%..+16.10%)

A 7-seed ensemble quantile sweep on the already-opened 2025-H2 validation block found:
- q60 n16 avg +3.99%
- q65 n13 avg +4.62%
- q70/q75/q80 n10 avg +4.35%
- q85 n6 avg +4.72%
- q90 n5 avg +6.76%
This made q65 a plausible Watch boundary and q90 a plausible Prime boundary, but this sweep is exploratory because validation had already been inspected.

A stricter expanding walk-forward then fixed:
- target >= +7.5% at 5BD,
- Watch=q65,
- Prime=q90,
- 7-seed 4H-only ensemble,
- training labels only when target_date < next test start.

Walk-forward periods: 2025-H2, 2026 Jan-Feb, Mar-Apr, May-Jun, Jul-Aug.

Result:
- 2025-H2 remained strong (Watch n13 +4.62%, Prime n5 +6.76%)
- 2026 Jan-Feb: Watch -1.64%, Prime -1.85%
- 2026 Mar-Apr: Watch -2.40%, Prime -1.53%
- 2026 May-Jun: Watch +1.60%, Prime one hit +27.0%
- 2026 Jul-Aug: Watch +0.31%, Prime -2.67%
- aggregate OOS base pool n185 avg +1.05%
- aggregate OOS Watch n70 avg +0.44%
- aggregate OOS Prime n20 avg +1.59%

Decision:
- **Reject the current learned 4H rank as a standalone production scoring engine.**
- The 2025 validation strength was real enough to survive seed changes but did not survive changing market regimes.
- The next research priority is a causal market-regime gate/veto using previous-day market breadth/trend, not further threshold tuning on the same 4H score.

## Next research sequence
1. Treat the **4H-only learned rank** as the current promising research branch; do not promote it yet because validation n is small.
2. Quantify uncertainty on 4H-only Watch/Prime (bootstrap / monthly stability) without changing the already-fixed model.
3. Run TRAIN-only 1H feature/veto ablation only if it can be defined without using the opened validation outcomes; otherwise wait for future forward data.
4. Preserve user-facing tiers **Core / Monster Watch / Monster Prime**. Prime must be a stricter score tier over a sufficiently broad candidate pool, never an exact-timestamp percentile.
5. Keep **Core** separate from Monster scoring.
6. Investigate the 17 missing Yahoo symbols / persistent 400/404 failures before claiming full-universe historical coverage.
7. Only after the 4H score is robust, test dilution/warrant risk and fundamentals as optional graded overlays.

## Naming
Working product name: **天底極致 Cloud**


## 2026 descriptive cross-check — weak-market + early-maturity Monster gate
Added 2026-09-12 JST. Research-only; no production writes.

A new descriptive cross-check connected the saved Cloud two-lane 2026 Monster picks to the persisted 4H/session OHLCV. This does **not** create a new 2026-fitted threshold. It combines two gates that already existed from pre-2026 research:
- previous-day market gate: cross-sectional median 5D return <= 0 (same contrarian context used in V12/V13/V14-family research);
- maturity gate: candidate 10D return <= 0.5735294117647058 (threshold previously sourced from the 2023 V18-consensus median in the separate V20 early-maturity experiment).

Cloud Monster descriptive results:
- all Monster: n63, mean +9.86%, median +3.33%, win 57.1%, >=20% 30.2%, <=-10% 22.2%, top-3-removed mean +5.79%.
- previous-day weak market only: n49, mean +12.91%, win 61.2%, >=20% 36.7%, <=-10% 20.4%, top-3-removed mean +7.81%.
- early-maturity only: n56, mean +11.03%, win 60.7%, >=20% 32.1%, <=-10% 21.4%, top-3-removed mean +6.50%.
- **weak market + early maturity**: n43, mean **+14.56%**, median **+5.86%**, win **65.1%**, >=20% **39.5%**, <=-10% **18.6%**, top-3-removed mean **+8.81%**.

Monthly weak+early Monster means: Mar +22.98%, Apr +25.92%, May +15.63%, Jun +4.80%, Jul +9.73% (n4, median negative), Aug +2.75% (n3). June is improved versus the severe V13/V14 failure pocket but is not solved; loss10 in June remains 36.4%.

Stable + Monster union comparison on the saved 2026 Cloud picks:
- Stable + all Monster: n210, mean +4.74%, win 61.0%, <=-10% 8.10%, >=20% 10.95%, top-3-removed mean +3.49%.
- Stable + 09:00 Monster: n182, mean +5.11%, win 63.7%, <=-10% 6.04%, >=20% 9.89%, top-3-removed mean +3.79%.
- **Stable + weak+early Monster**: n190, mean **+5.27%**, win **63.2%**, <=-10% **5.79%**, >=20% **11.05%**, top-3-removed mean **+3.89%**.

Interpretation:
- This is stronger than the arbitrary 09:00 hard filter and has a causal story consistent with earlier research: Monster is a contrarian/early-momentum lane, but already-matured 10D runners are lower quality.
- Do not promote these 2026 descriptive numbers as validation. The next task is to reproduce the **same fixed two-gate structure** on pre-2026 / purge-safe Three-head Consensus (V29-family) picks, without changing thresholds.
- Keep V31 secondary because its headline remains week-dependent.
