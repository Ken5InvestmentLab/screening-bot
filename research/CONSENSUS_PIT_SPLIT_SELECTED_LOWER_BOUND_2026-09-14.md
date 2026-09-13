# Consensus point-in-time split leakage — selected-row lower bound — 2026-09-14

Research-only data-integrity audit. **No strategy return is used to construct this count.** Production is untouched.

## Purpose

Before the full V46 all-symbol split-event audit runs, quantify a conservative lower bound using only:
- frozen run80 daily prior close / prior volume;
- V43 fixed-min95 selected rows;
- stock splits independently confirmed for a small set of selected symbols.

Any selected symbol without a confirmed event in this lower-bound table is left unchanged. Therefore this audit can undercount contamination; it cannot create extra false positives from unverified names.

## Reconstruction rule

For a historical previous-day close:
`point_in_time_nominal_close = frozen_current_basis_close × product(future split ratios after that previous-day date)`.

The historical price gate is:
- point-in-time previous close <= JPY 1,000;
- historical previous volume >= 10,000 shares.

No future return or model score is used.

## Confirmed corporate-action factors used

| symbol | later split(s) relevant to 2025 historical rows |
|---|---|
| 3350 | 1 -> 10, effective 2025-04-01 |
| 2334 | 1 -> 10, effective 2025-11-13 |
| 6574 | 1 -> 10, effective 2025-08-02; another 1 -> 10, effective 2025-09-01 |
| 7273 | 1 -> 10, effective 2025-06-01 |
| 4935 | 1 -> 5, effective 2026-01-01 |
| 6039 | 1 -> 5, effective 2025-12-17 |
| 7409 | 1 -> 3, effective 2026-01-01 |
| 3137 | 1 -> 2, effective 2025-10-01 |
| 7318 | 1 -> 4, effective 2025-12-01 |
| 5578 | 1 -> 3, effective 2025-12-01 |
| 7138 | 1 -> 5, effective 2025-09-01 |
| 6085 | 1 -> 3, effective 2025-04-11 |

Corporate-action receipts were cross-checked against JPX/company disclosures. The upcoming V46 run will replace this hand-curated subset with the full machine-fetched split-event table and hash.

## V43 fixed-min95 lower bound

Total selected rows: **112**.

Confirmed adjusted-only false-positive eligibility rows: **71 / 112 = 63.39%**.

By symbol:

| symbol | selected | confirmed false-positive rows |
|---|---:|---:|
| 3350 | 34 | **34** |
| 2334 | 16 | **15** |
| 7318 | 8 | **8** |
| 6574 | 6 | **5** |
| 7409 | 3 | **3** |
| 4935 | 2 | **2** |
| 6039 | 1 | **1** |
| 5578 | 1 | **1** |
| 7273 | 1 | **1** |
| 7138 | 2 | **1** |

Examples:
- 3350 2025-01-06 prior close on frozen basis = 348 JPY; after restoring the later 10-for-1 split = **3,480 JPY**, historically ineligible.
- 2334 2025-05-09 prior close = 73.3; ×10 = 733 JPY, still eligible. Later 2334 selected rows with adjusted prior closes >=127 become >1,000 JPY and are ineligible.
- 6574 pre-August rows require the two later 10x splits to be undone (100x cumulative on sufficiently early dates).
- 4935 July 2025 prior closes 706/808 become 3,530/4,040 JPY after undoing the 2026-01-01 5x split.

## Frozen ATR-gated subset

Current frozen ATR cap: 2.8640659721.

ATR-gated selected rows: **101**.

Confirmed adjusted-only false-positive eligibility rows: **67 / 101 = 66.34%**.

Time split:
- 2025H1: 48 / 67 = **71.64%** confirmed contaminated;
- 2025H2: 19 / 34 = **55.88%** confirmed contaminated.

This is already a majority in both halves before the full V46 split table is available.

## Decision impact

This materially changes the status of V43/V44.

1. V44 remains useful only as a **mechanics/concentration diagnostic inside the old adjusted-price universe**.
2. Even if V44 passes its frozen replacement gates, it cannot establish promotion-grade Stable★6 replacement evidence.
3. Point-in-time eligibility reconstruction is now a mandatory predecessor to any clean Consensus retrain/re-evaluation.
4. V46 remains outcome-free and must quantify both:
   - adjusted-only false positives from later forward splits;
   - PIT-only false negatives from later reverse splits.
5. A clean V47 must rebuild monitor dates from PIT prior-close eligibility and retrain from scratch; simply deleting contaminated V43 selections after the fact is not sufficient because cross-sectional ranks, market features, model training rows and omitted reverse-split candidates can all change.
6. The current-listed run80 survivorship limitation remains separate and unresolved.

## What NOT to do

- Do not salvage current 2025 performance by deleting these 71 rows and quoting the return of the remainder as a new validated strategy.
- Do not tune a new threshold from the contaminated/remaining outcomes.
- Do not use 2026 returns to choose the correction.
- Do not treat the selected-row lower bound as the final PIT universe; V46 must audit all frozen symbols.
