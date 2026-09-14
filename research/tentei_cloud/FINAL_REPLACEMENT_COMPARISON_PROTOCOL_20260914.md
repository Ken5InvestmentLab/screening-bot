# Final replacement comparison protocol — frozen 2026-09-14 JST

Research coordination contract. No current strategy is promoted by this file.

## Purpose

When clean forward-qualified replacement lanes finally exist, compare them against the current Stable / Sniper / Mega roles without changing the evaluation method after seeing the result.

This protocol freezes the comparison surface, not a single mandatory numeric pass threshold.

## Eligibility before final comparison

A replacement lane may enter the final comparison only if its own preregistered validation / forward gate has already been completed.

Do not include:
- a retrospective descriptive subset;
- a survivor-shadow / non-promotion fallback;
- a lane whose validation was opened after threshold tuning on the same outcomes;
- the rejected fixed reconstructed Core as though it were production-qualified.

Current Stable / Sniper / Mega remain benchmarks only.

## Common-window rule

For each role comparison:
1. use the maximal date window where both benchmark and replacement have legitimately resolved outcomes under their own frozen records;
2. report the exact common start/end dates;
3. do not choose the date window based on performance;
4. if exact common-window benchmark rows are unavailable, label the comparison `NON_COMMON_WINDOW_REFERENCE` rather than pretending equivalence.

## Canonical 5BD endpoint

For replacement 5BD lanes:
- entry = next official XTKS open after the completed signal/event;
- exit = fifth official XTKS session/date close according to the frozen upstream endpoint contract;
- report gross and fixed 0.5% round-trip-cost stress.

Legacy benchmark metrics may retain their published endpoint convention, but any endpoint mismatch must be stated explicitly.

## Deduplication

When multiple qualified replacement lanes select the same symbol/date:
- preserve each lane's identity in the audit table;
- for simple system-union metrics, count the symbol/date only once;
- deterministic precedence for display only:
  1. Precision role
  2. Monster Prime
  3. Monster Watch
  4. other qualified lane
- precedence must not change the return value or silently discard role attribution.

Do not optimize dedup precedence using outcomes.

## Mandatory 5BD metrics

For every lane and the deduplicated union report:
- n;
- mean;
- median;
- win rate;
- >= +10%;
- >= +20%;
- <= -10%;
- maximum / minimum;
- top-1 / top-3 / top-5 winner-removed mean;
- monthly or fixed-block stability;
- gross result;
- 0.5% cost-stressed result where canonical execution is available.

For tail lanes additionally report:
- contribution of top 1 / 3 / 5 winners to total return sum;
- frequency of >= +20% outcomes.

For Precision additionally report:
- 0.5%-cost win rate;
- 0.5%-cost median;
- top-5-removed 0.5%-cost mean.

## Mandatory long-horizon metrics

For any Mega40-role consumer:
- use its preregistered long horizon only;
- n / mean / median / win;
- target-hit rate for the declared Deep/Wick-like target;
- <= -20% downside;
- top-winner-removed mean;
- calendar-block stability.

Do not compare 40BD mean directly with 5BD mean as though they were the same role.

## Benchmark questions

The final report must answer separately:

### Stable-like main performance
- Does the replacement system approach the current system's practical 5BD headline upside?
- Is that upside less dependent on a handful of winners?
- Is downside frequency better, similar, or worse?

### Sniper-like precision
- Is there a qualified lane with materially higher hit rate than the broad/tail lanes?
- Does it remain positive after cost stress and top-winner removal?

### Mega5-like short tail
- Does the qualified Monster family actually capture >=20% 5BD winners often enough to cover this role?
- If yes, a separate Mega5 clone is unnecessary.

### Mega40-like long horizon
- Is there a genuinely qualified long-horizon lane?
- If not, the replacement remains functionally incomplete even if 5BD performance is strong.

## No post-result optimization

After the final common-window table is opened, do not:
- tune lane thresholds;
- choose a different union only because it scores better;
- drop a bad month;
- change the cost stress;
- change the role definitions.

Any new architecture after that point must receive a new version and later validation evidence.

## Decision style

The final decision is multi-dimensional, not a one-number hard cutoff.

Allowed conclusions:
- `READY_TO_REPLACE`
- `PARTIAL_REPLACEMENT_ONLY`
- `RESEARCH_CONTINUE`
- `NO_GO`

The written rationale must explicitly discuss:
- headline return;
- robustness / winner concentration;
- downside;
- execution/cost;
- missing product roles;
- data/provenance confidence.

A higher mean alone is not sufficient for `READY_TO_REPLACE`.

Production modified: false.
