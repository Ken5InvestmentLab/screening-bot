# Old Cloud Monster forensic disposition — 2026-09-14 JST

Research-only forensic record. Production `main`, Discord, Spreadsheet, canonical V20, Consensus/PIT restoration, and forward Monster logic are unchanged.

## Purpose

Recover what can still be established about the historical Cloud Monster result that reported:

- Priority A: 63 matured candidates
- 5BD mean: +9.86%
- median: +3.33%
- win rate: 57.1%
- >= +20%: 30.2%
- >= +30%: 19.0%
- <= -10%: 22.2%
- top-5-removed mean: +4.03%

This note exists so future workers do not mistake the headline +9.86% for a fully reproducible or clean forward benchmark.

## What is recoverable from saved conversation evidence

The original research sequence recorded:

1. Watch seed:
   - daily `pre_down3`
   - daily `gap_up`
   - recent 4H 3-bar return >= +6%
2. The historical conversation described the Watch pool as 575 candidates after the then-current filtering/calendar correction.
3. Priority was assigned by a **probability score**:
   - Priority A = top 10%
   - Priority B = next 20%
   - remainder = Watch / no-priority
4. The probability model was trained only on **March-June 2026** and July-August 2026 was treated as a later evaluation block.
5. A+B recovered all seven evaluable known Monster references; one additional reference (4840) was not evaluable because the needed 4H data was missing.
6. The exact model class, objective implementation, feature list, transforms, probability calibration and serialized model were not preserved in the surviving files or Git history.

The surviving comparison CSV contains exact probability-like scores for 19 high-return Priority-A examples, but not the training code.

## Surviving source artifacts

Library artifacts recovered:

- `cloud_two_lane_union_jpx.csv`: historical selected Stable/Monster rows, including the 63 Priority-A Monster rows.
- `cloud_priorityA_monsters_compare_teacher.csv`: 19 high-return Priority-A rows with exact saved `score` values.
- `teacher_ohlcv_4h_raw.csv`: historical raw 4H/session OHLCV, 426,282 rows, 1,332-symbol teacher universe.

The original probability model itself was not saved next to these artifacts and was not found in the Sep-11 Git history.

## Entry-gate reconstruction

Using the historical 4H/session raw data, a broader forensic Watch reconstruction can recover 62 of the 63 historical Priority-A symbol/timestamps.

However the reconstructed pool contains 696 rows, whereas the original conversation recorded 575 Watch candidates. Therefore:

- the broad structural gate is substantially recovered;
- the original Watch implementation is **not exact**;
- at least one additional filter, data treatment, session/calendar detail or dedup rule remains missing.

Do not call the 696-row forensic table the original Watch set.

## Headline result decomposed by the original train/post split

Historical Priority-A rows from `cloud_two_lane_union_jpx.csv`:

### March-June 2026 (model-development era)

- n = 46
- mean = +11.99%
- median = +4.85%
- win rate = 58.7%
- >= +20% = 37.0%
- >= +30% = 23.9%
- <= -10% = 23.9%
- top-1-removed mean = +9.51%
- top-3-removed mean = +6.47%
- top-5-removed mean = +4.18%

### July-August 2026 (later evaluation block)

- n = 17
- mean = +4.09%
- median = +1.95%
- win rate = 52.9%
- >= +20% = 11.8%
- >= +30% = 5.9%
- <= -10% = 17.6%
- top-1-removed mean = +0.86%
- top-2-removed mean = -0.70%
- top-3-removed mean = -2.13%
- top-5-removed mean = -4.12%

Therefore the full +9.86% headline materially overstates the forward-like portion of the evidence.

## Did the later Priority-A selection still add value?

On the available July-August forensic Watch comparison:

- Watch pool: n = 149, mean = -0.76%
- Priority A: n = 17, mean = +4.09%
- non-A: n = 132, mean = -1.39%

A randomization test drawing 17 names from the 149-row Watch pool placed the observed A mean at about the **94th percentile**:

- P(random subset mean >= observed A mean) ~= 5.9%

This is suggestive that Priority A had real selection information, but the sample is small and highly tail-sensitive.

Bootstrap on the 17 A rows:

- approximate 95% CI of mean: -2.99% to +12.74%
- bootstrap P(mean > 0): about 84.6%

Interpretation: evidence of selection skill is plausible, but not promotion-grade.

## Exact-score recovery attempt

Two independent forensic paths were tried without using 2025 returns to tune the score.

### A-label reconstruction

Using only pre-signal technical/price/volume inputs, leave-one-month-out classifiers could reproduce historical A membership moderately well:

- pooled AUC roughly 0.81 for the best tree ensemble
- top-A-rate recall roughly 43%

But the model scores correlated weakly with the 19 exact saved probability scores.

### Historical portability sanity check

A frozen A-membership surrogate was trained from 2026 A labels only and then applied once to the reconstructed 2025 Watch pool.

Result:

- 2025 Watch pool: n = 912, mean +2.50%
- frozen surrogate A-like selection: n = 69, mean **-1.36%**

The 2025 result was not used for retuning.

Decision: **reject the surrogate as a replacement for the lost historical Priority model.**

### Replaying likely return targets

Models trained on March-June Watch returns with plausible Monster targets (including 5BD >= +20%) could reach historical-A discrimination AUC around 0.82, but:

- they did not reproduce the exact saved score values;
- their July-August performance did not reproduce the historical A result;
- no tested standard model can be claimed as the original model.

## Disposition

1. **Do not use +9.86% as the current leading performance estimate.**
2. Preserve it only as a historical research clue that a tail-seeking rank can add value after the Watch gate.
3. Do not publish or implement the forensic surrogate.
4. Do not tune against the opened 2025 portability result to rescue the old score.
5. Do not restart model-family guessing unless genuinely new source evidence appears (original script, serialized model, feature table or exact training notebook).
6. The modern forward-qualified Monster/event lane remains owned by the canonical/V20 work. This forensic lane is diagnostic only.
7. Future common-window comparisons should use qualified modern lanes, not the unrecoverable +9.86% model.

## Bottom line

The historical Cloud Monster result was not pure noise: its July-August A selection outperformed the contemporaneous Watch pool and landed near the 94th percentile of random same-size selections.

But the exact probability model is lost, the forward-like sample is only 17 rows, and most of the headline +9.86% came from the development-era block and a small number of large winners.

Status: **HISTORICAL SIGNAL / NOT REPRODUCIBLE / NOT A CURRENT PROMOTION CANDIDATE**.
