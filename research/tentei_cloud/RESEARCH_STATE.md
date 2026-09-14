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


## 2026-09-14 independent lane update — global regime gates rejected

This work was intentionally isolated from the parallel V12 state-entry and V14/structure lanes. Production was not modified.

### Fixed walk-forward Monster Watch/Prime + previous-day regime veto

Run `34764604761`, artifact `10319184830`, artifact SHA-256 `38375ca380fd602d9bc0b80db9378e4daebd0e1036e7bacc731d2b0b264bd40d`.

The already-fixed 4H walk-forward ensemble was reconstructed without changing features/model/seeds/Watch q65/Prime q90. Three fixed previous-day regime vetoes were applied retrospectively.

Aggregate:
- Watch baseline n70 mean +0.44%. Broad risk-off veto n45 mean +0.51%: only +0.07pt while removing 36% of picks; top-3-removed mean worsened. Other vetoes reduced mean.
- Prime baseline n20 mean +1.59%. Broad risk-off veto n15 mean +2.53%, but Jul-Aug worsened from -2.67% to -4.15% and the sample is too small/non-stationary.
- The veto sign changed by period. In particular Watch improved in Mar-Apr and Jul-Aug but worsened in 2025H2, Jan-Feb, and May-Jun.

Decision: **no hard market-regime veto for Watch or Prime**. Retain the Prime risk-off veto only as a forward-observation hypothesis; do not tune it on the already-opened periods. Detailed record: `WALKFORWARD_REGIME_VETO_FINDINGS.md`.

### Fixed reconstructed Core + previous-day regime gates

Final run `34764868293`, artifact `10319769611`, artifact SHA-256 `002e3da9d23a305a1a1c9d1564c584be0d83574d4a4bd61bb6fa7a6bec243a1b`.

Fixed reconstructed Core/SAFE definition: production-like universe filters, RSI12<45, previous three session closes descending, close>BB20 mid, ATR14/close<5%, 5BD same-symbol cooldown. This is the common split-13:00 reconstruction, not an exact claim about original 4H signals.

2026 Jan-Aug ungated Core:
- n118
- mean **+1.56%**
- median **+0.48%**
- win **53.4%**
- >=10% **8.47%**
- >=20% **1.69%**
- <=-10% **1.69%**
- top-1 removed **+1.27%**
- top-3 removed **+0.92%**
- top-5 removed **+0.66%**

Fixed regime gates all reduced mean:
- NOT_RISK_OFF n89 +1.17%
- R5_POS n61 +0.80%
- B5_50 n73 +0.73%
- R20_POS n41 +1.11%
- R5_AND_RISING n59 +0.82%

R20_POS removed <=-10% cases in 2026 but was negative in DEV and produced zero May-Jun candidates, so it is not a usable global gate.

Decision: **keep Core ungated by broad market regime**. Detailed record: `CORE_REGIME_FINDINGS.md`.

### Architecture consequence

The prior research priority of finding a single causal market-regime gate is now closed as a hard-filter path.

- Core remains the steadier lane and should be improved internally rather than by a global market ON/OFF switch.
- Monster remains separate and tail-seeking; broad market regime has non-stationary interaction with Monster setups.
- Market regime should be logged as context for future genuinely-forward evidence, not imposed as a shared blocker.
- Do not reuse current Stable as a component of the replacement system; it remains benchmark-only.


## 2026-09-14 independent Core continuation — simple pruning paths rejected

This continuation stayed outside the parallel V12/V15 event-representation and legacy-intraday reconstruction work. Production was not modified.

### Candidate-local single-feature audit

Run `34765124157`, artifact `10320890234`, artifact SHA-256 `1c576a3c7cec5c53e3f87f755a3edc41dc54b07385e732eb8a4a28532ff13ef1`.

Five fixed signal-time features were median-split using DEV only: RSI12, BB reclaim width, ATR14/close, reconstructed-session/previous-day volume ratio, and EMA75 gap. A side could advance only if BOTH DEV halves had n>=15, higher mean, no-worse median, and no-worse <=-10% rate.

Result: **no feature/side qualified**. ATR-high improved mean/median in both halves but worsened the large-loss rate; RSI, BB reclaim, and EMA75-gap changed preferred direction between DEV halves; higher session/previous-day volume ratio improved mean but not all robustness gates.

Decision: no hard local-quality filter. See `CORE_LOCAL_QUALITY_FINDINGS.md`.

### Yahoo 1H historical coverage topology

Run `34765338387`, artifact `10320545595`, artifact SHA-256 `022a8632015e467f859ce615ab826c6695355410b578f96889e9d9e396d56b05`.

Across the 1,332-symbol comparison set:
- 1,271 symbols had no failed chunks.
- 44 had failures only before the first observed Yahoo 1H bar.
- 17 were never observed.
- 0 had a failed interval overlapping an observed-history span.

The 44 before-first-only names comprise recent listings plus five legacy numeric codes with terminal-only history around delisting status. The 17 never-seen names are 2026 delistings. Therefore the Yahoo 1H panel has **no detected internal chunk holes where history exists**, but it is not point-in-time complete and has a delisting-linked survivorship hole. At least 22/1,332 target symbols have materially compromised historical intraday coverage from this effect.

Do not claim full-universe or survivorship-free historical intraday coverage. Repair/reconciliation of legacy intraday sources belongs to the separate V12/V15 data-quality lane; this branch does not duplicate it. See `FETCH_COVERAGE_FINDINGS.md`.

### Causal correlation-peer lag audit

Run `34765505153`, artifact `10320032194`, artifact SHA-256 `63b1063fe068ed9cf090ee1b05dfec77001efda2a6857784437a8ff1bee0fafe`.

Peers were selected using trailing 60 prior trading dates only, minimum 40 return overlaps, and the top five positively correlated symbols. No current-only industry map was used.

Positive peer momentum was harmful in DEV_A but mildly beneficial in DEV_B:
- DEV_A BASE ~0.00%; PEER1_POS -0.25%; PEER5_POS -1.40%.
- DEV_B BASE +2.16%; PEER1_POS +2.22%; PEER5_POS +2.45%.

No fixed peer gate passed the two-half robustness rule. Decision: **reject positive peer-momentum hard gating** and do not flip the sign post-hoc on the same opened data. See `CORE_PEER_LAG_FINDINGS.md`.

### Core architecture update

Three simple pruning paths are now closed for the fixed reconstructed Core:
1. broad-market hard regime gates;
2. simple single-feature local hard gates;
3. positive correlation-peer momentum hard gates.

The current evidence favors preserving Core breadth. The next independent Core task should quantify baseline stability/uncertainty rather than invent another threshold from already-opened outcomes.


### Core execution-cost sensitivity

Final logged run `34765954141`.

2026 Jan-Aug fixed Core:
- gross mean +1.56%; bootstrap P(mean>0) 99.24%; 95% CI +0.29%..+2.86%.
- assumed 0.5% round-trip cost: mean +1.06%; bootstrap P(mean>0) 95.12%; 95% CI -0.24%..+2.29%.
- assumed 1.0% round-trip cost: mean +0.56%; bootstrap P(mean>0) 80.08%; 95% CI -0.76%..+1.84%.

Because constant cost shifts the bootstrap mean distribution, the gross 2026 95% lower bound implies that round-trip cost above roughly 0.29% makes the 95% interval cross zero.

Interpretation: Core remains positive by point estimate under 0.5%-1.0% assumed costs, but strict 95% robustness does not survive 0.5%. Treat Core as **promising/stable gross, execution-sensitive net**, not production-proven net.


### Core executable-entry audit

Valid run `34770326228`, artifact `10322340573`, artifact SHA-256 `6d846e0f65a8a420c1e68fa12b0c51eb2869fd12ee855a7e021ca0aa4d484f48`.

The standard label's signal-session-close entry was replaced by the first raw Yahoo 1H bar strictly after the session's last raw timestamp, using that next bar OPEN. The existing five-business-day target close was unchanged.

Coverage was 100% (433/433 Core candidates across the studied blocks).

2026 Jan-Aug:
- signal-close entry mean +1.56%
- executable next-open mean **+1.71%**
- next-open top-3-removed mean +1.08%
- <=-10% unchanged at 1.69%
- assumed 0.5% round-trip cost: mean **+1.21%**, week-bootstrap P(mean>0) 97.52%, 95% CI **+0.002%..+2.43%**
- assumed 1.0% round-trip cost: mean +0.71%, P(mean>0) 88.08%, 95% CI -0.45%..+1.88%

DEV and 2025H2 were essentially unchanged by next-open execution. Therefore the 2026 Core strength is not an artifact of an impossible signal-close fill assumption.

A first implementation exposed a pandas datetime integer-unit bug and produced zero matched rows. That output was rejected, the lookup was fixed to timezone-aware Series.searchsorted, and a fail-closed >=90% coverage guard was added.

Decision: fixed Core passes the executable-entry sanity check. See `CORE_EXECUTION_FINDINGS.md`.


### Core / Monster complementarity audit

Run `34770490191`, artifact `10321568115`, artifact SHA-256 `7c1712d8ff6a099277990c93ba4b240432c0538cda025e5a367a95f924e8c2ed`.

Across 2025H2 and all four 2026 walk-forward blocks:
- Core vs Monster Watch exact overlap (symbol+date+session): **0**
- Core vs Monster Prime exact overlap: **0**
- same-symbol same-date overlap even ignoring session: **0**

The lanes are therefore genuinely distinct on the audited reconstructed baseline, not duplicate confidence tiers over the same names.

Daily signal-count correlation Core vs Watch was generally near zero or negative (-0.02, -0.55, -0.38, -0.05, -0.61 by fold), with few common active days.

However distinctness does not justify blind union:
- fixed Monster Watch across 2026 folds: n57, weighted mean about -0.51%
- fixed Monster Prime across 2026 folds: n15, weighted mean about -0.14%
- Monster helped the union in the May-Jun tail-hit period but diluted Core in several other blocks.

Decision:
- **keep Core and Monster as separate named lanes**;
- do not merge them into one score or undifferentiated signal class;
- Core remains the steadier lane;
- Monster remains a separate positive-skew/tail lane requiring stronger forward evidence;
- preserve lane identity in eventual Discord/user-facing output.

See `CORE_MONSTER_COMPLEMENTARITY_FINDINGS.md`.


### Core operational load / capacity / cluster context

Operational-load run `34771263457`, artifact `10322007138`.

2026 Jan-Aug:
- 118 signals over 68 active signal days.
- active-day median 1 signal, p95 4, max 11.
- active-session p95 3, max 8.
- only 2/68 active days had >=5 signals.
- AM 43.2%, PM 56.8%.
- weekly active-week mean 3.93 signals, max 15.

Decision: alert volume does **not** justify pruning Core. Preserve every signal. For eventual Discord delivery, batch by completed Core session (AM / PM) and split messages only for presentation limits; never top-N truncate.

Capacity run `34771393714`, artifact `10321544380`.

With first executable next-bar date as entry and existing 5BD target date as exit:
- 2026 concurrent positions: median 3, p90 8, p95 10, max 16.
- 2025H2 max 22.
- DEV stress episode max **57** concurrent positions after the April 2025 burst.

Decision: do **not** put a fixed position-capacity filter inside the signal detector. Store/notify every Core candidate. Any future capital allocator is a separate downstream layer and must not redefine the Core signal set.

Cluster-risk run `34787773571`, artifact `10326733411`.

Fixed same-day density buckets showed non-stationary sign:
- DEV 5+ candidate bucket mean +3.33%.
- 2025H2 5+ bucket mean -1.30%.
- 2026 Jan-Aug 5+ bucket mean +3.22%.

Decision: signal density is **not** a validated quality/risk score. Do not suppress or score-down burst-day Core signals. A neutral `集中発生` context marker is acceptable for operational awareness only.

Detailed records:
- `CORE_OPERATIONAL_LOAD_FINDINGS.md`
- `CORE_CAPACITY_FINDINGS.md`
- `CORE_CLUSTER_RISK_FINDINGS.md`


### Current-system benchmark and missing long-horizon role

Current benchmark-gap run `34787973886`, artifact `10326869014`.

Saved report snapshot generated 2026-09-11 14:14:31 JST:
- Stable★6: 5BD/+10%, n56, mean +6.1%, win 55.4%.
- Sniper: 5BD positive-return target, n40, mean +2.4%, win 65.8%.
- Mega5: 5BD/+20%, n10, mean +14.5%.
- Mega40 Deep: 40BD/+30%, n26, mean +17.6%.
- Mega40 Wick: 40BD/+50%, n8, mean +10.6%.

On Stable's parsed confirmed-date window 2026-03-05..2026-09-03:
- Stable★6 n56 mean +6.06%, >=20% 14.29%, <=-10% 12.50%, top-5-removed mean -0.31%.
- fixed Core executable-next-open n88 mean +1.68%, >=20% 2.27%, <=-10% 1.14%, top-5-removed mean +0.55%.

Interpretation: Core supplies a much more robust floor but not Stable's positive tail. Monster must supply the missing upside. With Core fixed at n88/+1.68%, a no-overlap Monster set of roughly 43 signals would need about +15.0% mean to make the simple union reach Stable's +6.06% headline mean. The already-recorded descriptive weak+early Monster n43/+14.56% is the right order of magnitude but is not a validated common-window union.

See `CURRENT_SYSTEM_BENCHMARK_GAP_20260914.md`.

Long-horizon role run `34788118628`, artifact `10327581179`.

Fixed current Cloud lanes do not cover Mega40:
- Core 2026 matured 40BD: n103 mean +2.88%, >=30% 8.74%.
- learned Monster Watch 2026 matured: n42 mean -5.29%.
- learned Monster Prime 2026 matured: n11 mean -0.40%.

Decision: a dedicated long-horizon lane is required. See `LONG_HORIZON_ROLE_GAP_20260914.md`.

### Dedicated long-horizon direct-semantic baseline — rejected

Run `34788285067`, artifact `10327507225`, artifact SHA-256 `c7b49e043865a3e4677d07310334975eb66c955f386e8bd26c274b0378b67321`.

Published Mega40 Deep/Wick semantics were applied directly to the TV-free daily universe, without a TradingView/BOTTOM entrance. Formulas and CAP1000/NO_PRICE_CAP variants were frozen before opening results.

Executable next-day-open:
- CAP1000 Deep DEV 2025H1: n561 +18.47%, but VALID 2025H2 n289 **-0.44%**, 2026 matured n475 **-0.86%**.
- CAP1000 Wick DEV n101 +10.48%, VALID n79 +3.03% with median -8.0% / top5-removed -7.16%, and 2026 n111 **-1.00%**.
- removing the price cap worsened the main out-of-period blocks: Deep VALID -2.04%, 2026 -1.65%; Wick VALID -0.03%, 2026 -1.84%.

Decision: **reject direct daily application of the four Mega40 overlay conditions**. Event timing is essential. Do not threshold-tune these opened results.

The parallel canonical/V20 lane owns TV-free event reconstruction/PIT/source contracts. This branch will consume a frozen event stream for long-horizon overlays if one exists, not build a competing event detector.

See `LONG_DAILY_BASELINE_FINDINGS.md`.


## 2026-09-14 current coordination status — role coverage supersedes earlier Core-KEEP snapshot

Current authoritative coordination file:
`research/tentei_cloud/ROLE_COVERAGE_AND_RESEARCH_PRIORITY_20260914.md`.

Where older notes call the fixed reconstructed Core a KEEP / research-ready replacement lane, that promotion status is **superseded** by the later canonical-endpoint evidence:
- canonical DEV remained positive;
- canonical 2025H2 was essentially flat gross and negative after 0.5% stress;
- therefore `REJECT_CURRENT_FIXED_CORE_AS_REPLACEMENT_CANDIDATE` remains the current status.
- The fixed Core may still be used as a robust-floor research baseline / diagnostics reference.

Raw1H PIT lineage clarification:
- run `34798921728`, artifact `10330772110` passed;
- this reconstructed Core derives prior close / prior volume / session volume from explicit-period raw1H;
- shared V47 receipts establish raw1H volume as PIT share-count scale;
- do not apply frozen-daily split-volume correction again to this path;
- this data-lineage clarification does not reverse the performance rejection.

Current benchmark-role coverage:
- Stable-like 5BD headline/tail: not qualified; future clean Monster/event lane is the main bottleneck.
- Sniper-like 5BD high-hit precision: **uncovered**.
- Mega5 short-tail: not proven; may ultimately be covered by a forward-qualified Monster family.
- Mega40 long horizon: **uncovered**; direct daily baseline rejected and canonical event timing is required.

Sniper-role exploration on this branch is now closed for simple candle-event enumeration:
- `PRIOR_CLOSE_RECLAIM` preregistered and rejected before 2025H2/2026 were opened.
- Three-family preregistered DEV-only batch (`PRIOR_HIGH_BREAKOUT`, `TWO_DAY_PULLBACK_RECLAIM`, `INSIDE_RANGE_STRENGTH`) produced zero qualifying family.
- Internal validation remained closed for the three-family batch; 2025H2 and 2026 remained closed.
- Do not add neighboring candle thresholds to rescue these failures.

Priority:
1. Let canonical-batch02 / Consensus finish clean PIT, survivorship and prospective-shadow infrastructure.
2. Forward-qualify the tail/Monster event lane.
3. Revisit Sniper precision only with a materially different clean representation/data source.
4. Revisit Mega40 only as a consumer of a frozen canonical event stream.
5. Final common-window benchmark only after individual lanes have valid evidence.

Do not duplicate upstream V20/Consensus data repair or shadow-provenance work from this branch.
