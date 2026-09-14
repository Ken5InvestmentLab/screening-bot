# Parallel Condition Exploration — Wave 1 Frozen Manifest

Date frozen: 2026-09-15 JST
Branch: `research/parallel-condition-exploration`
Status: FROZEN BEFORE PERFORMANCE

## Common contract
- Research-only; isolated from Weak+Early Phase-2.
- Transaction cost = **0%**.
- Win = **gross return > 0**.
- Canonical endpoint = **next XTKS session open -> fifth XTKS session close**.
- One candidate/day inside each tested state unless the source family already has an explicit frozen lower-frequency state.
- 2026 outcomes = report/robustness-only, never selection/tuning.
- Opened 2022 Weak+Early outcomes are not tuning input.
- No dense threshold grid, no feature weights, no post-open threshold rescue.
- All feature rows must be causal as of signal-session close. Missing/duplicate/non-finite required data = FAIL_CLOSED / no trade for that state/date.

## Source receipt requirement
No performance may be treated as formal until the execution artifact records: source artifact/run id, source SHA-256, row count, min/max date, schema list, XTKS calendar/version used for endpoint mapping, and code/manifest commit SHA.

## Selected Wave-1 families
Only **A, B, E** are opened in Wave 1. C and D remain deferred.

### A — COMPRESSION_EXPANSION
Purpose: detect a compressed candidate that shows a causal range expansion before next-session entry.

Definitions, computed per symbol using daily rows through signal date `t`:
- `range_pct[d] = (high[d] - low[d]) / close[d-1]` for valid positive prior close.
- `compress5 = median(range_pct[t-5:t-1])` (five sessions strictly before signal day).
- `baseline20 = median(range_pct[t-20:t-1])` (twenty sessions strictly before signal day).
- `signal_range = range_pct[t]`.

Frozen state A1:
- `compress5 / baseline20 <= 0.75`
- AND `signal_range / baseline20 >= 1.25`
- denominator must be positive and finite.

No alternate A thresholds are permitted in Wave 1.

### B — RELATIVE_REVERSAL
Purpose: isolate candidate-specific weakness/reversal versus the causal broad-market cross-section rather than market-wide drift.

Definitions:
- `ret5_sym[t] = close[t] / close[t-5] - 1`.
- `ret1_sym[t] = close[t] / close[t-1] - 1`.
- For each date, `mkt_ret5[t]` and `mkt_ret1[t]` are the median corresponding returns across the same preserved causal daily universe with valid rows on that date.
- `rel5 = ret5_sym - mkt_ret5`.
- `rel1 = ret1_sym - mkt_ret1`.

Frozen state B1:
- `rel5 <= -0.05`
- AND `rel1 >= 0.00`

Interpretation: at least 5 percentage points of 5-session underperformance versus market, followed by a signal-day relative turn nonnegative before entry.

No alternate B thresholds or sector substitutions are permitted in Wave 1.

### E — PRIOR_STRUCTURE_PROXIMITY
Purpose: identify candidates near a causal prior downside structure boundary without look-ahead pivots.

Definitions:
- `prior20_low[t] = min(low[t-20:t-1])`, strictly excluding signal day.
- `dist_prior20_low = close[t] / prior20_low[t] - 1`.
- prior low must be positive and finite.

Frozen state E1:
- `0.00 <= dist_prior20_low <= 0.05`

Interpretation: signal close is between the prior 20-session low and 5% above it. No centered pivots, future confirmation, or alternate lookback is allowed in Wave 1.

## Candidate choice inside a state
To avoid hidden feature-weight tuning, if more than one candidate qualifies on a date:
1. use the existing causal `tail_p` descending tie-break if it is available in the preserved generator output;
2. if `tail_p` is unavailable in the bound source receipt, use symbol ascending as deterministic fallback and mark that arm `TAIL_P_UNAVAILABLE_FALLBACK`;
3. do not invent a new weighted ranker.

## Evaluation blocks
- Discovery performance may use the pre-2026 research period excluding opened 2022 Weak+Early outcomes as tuning input. If the execution implementation cannot establish an untouched confirmation block independent of this manifest, the result is diagnostic only and cannot be promoted.
- At least one holdout/walk-forward block must remain untouched until after A1/B1/E1 are frozen and implemented.
- 2026 remains report-only.

## Advancement screens
Stable-replacement archetype:
- win >= 55%
- mean >= +4%
- median > 0
- Top3-ex >= +3%
- sufficient n and no tiny-period dominance.

Monster archetype:
- mean >= +6%
- Top3-ex >= +4%
- sufficient n
- win, median, and tail concentration reported explicitly.

These are research-advancement screens only, not production GO criteria.

## Prohibited actions after performance is opened
- Change 0.75/1.25 in A1.
- Change -5%/0% in B1.
- Change 20-session/5% in E1.
- Add A2/B2/E2 from observed results.
- Combine A/B/E based on observed returns in the same Wave 1.
- Modify Weak+Early DUAL/G3 or use Wave-1 results to rescue opened Weak+Early evidence.

Next step: implement one fail-closed batch for A1/B1/E1 against the bound causal source, then report all arms at cost 0% with n/mean/median/win/Top3-ex and time-block stability.

Current decision: **NO-GO / MANIFEST FROZEN, PERFORMANCE UNOPENED**.
