# Consensus raw-1H split-adjustment cross-check — 2026-09-14

Research-only input-provenance audit. No strategy rule or production behavior changed.

## Sources compared

Consensus V43 selected artifact:
- run 34617009116
- Yahoo request path used by V10/V43: `range=730d&interval=1h`

Existing Core-lane raw 1H archive:
- source fetch run 34592896202
- same calendar day (2026-09-11)
- explicit `period1/period2&interval=1h&events=div,splits` chunk requests
- 1,332-symbol target set

The existing raw archive is used only for overlap/reproducibility diagnostics. It is not substituted for the V43 1,910-symbol cross-sectional universe.

## Coverage of V43 selected rows

V43 fixed-min95 selected:
- 112 rows
- 30 unique symbols

Existing Core raw panel overlaps:
- **89 / 112 selected rows**
- **23 / 30 selected symbols**

Representative high-concentration names:
- 3350: present
- 2334: present
- 6574: present
- 7318: absent from the narrower Core panel

## Session-shape match

Raw 1H rows were reconstructed with the exact V43 `synthetic_sessions()` rule:
- timestamp before 13:00 JST -> session 9
- timestamp at/after 13:00 -> session 13
- first open / max high / min low / last close / summed volume

Across all 89 overlapping V43 selected rows:

- `session_volume`: **exact match 89/89**, max absolute difference 0
- session return: max absolute difference about 7.21e-8
- session range / open: max absolute difference about 5.90e-8
- session body / open: max absolute difference about 7.21e-8
- session close-location: max absolute difference about 1.04e-6

So the two sources describe the same intraday path/shape for the overlapping selected observations.

## Absolute-price mismatch

Absolute OHLC scale is not always the same.

Among 89 overlapping selected rows:
- ratio raw/V43 = 1x: 62 rows
- 2x: 3 rows
- 3x: 1 row
- 5x: 4 rows
- 10x: 19 rows

Examples:
- 3137: raw/V43 2x on early-2025 selections
- 7273: 10x
- 2334: 10x before the later split-adjustment boundary
- 4935: 5x
- 5578: 3x
- 7138: 5x
- 6085: 10x
- 6039: 5x
- 6574: 10x for pre-split-history selections, then 1x later

These integer ratios are consistent with subsequent stock-split factors. Public corporate-action records independently confirm, for example:
- 7273: 1-to-10 split in 2025;
- 6574: 1-to-10 split announcements in 2025 (including the August split sequence);
- 3137: 1-to-2 split in 2025;
- 4935: 1-to-5 split announced in 2025;
- 2334: 1-to-10 split announced later in 2025.

Because both research pulls occurred on 2026-09-11, months after those corporate actions, the systematic difference strongly indicates **Yahoo query-mode / historical split-adjustment semantics**, not a random four-hour provider revision.

## Consequence for V43/V44 reproducibility

Most percentage/shape features are invariant to a uniform price scale and reproduce extremely closely.

However V11/V43 also includes the absolute feature:
- `log_price`

Therefore the Core raw archive cannot be a byte-for-byte or feature-for-feature drop-in replacement for V43/V44 without first reproducing the same corporate-action adjustment convention used by the V43 `range=730d` query.

Decision:
1. Existing Core raw shards remain valuable for intraday-shape and provider-drift diagnostics.
2. Do **not** replace V43/V44 input with them directly.
3. If the authoritative V44 run hits DATA_REPRO_FAILURE, first preserve/reconstruct exact split-adjustment semantics rather than silently using the narrower raw panel.
4. A future canonical data layer should store raw bars plus an explicit, versioned corporate-action adjustment table so model features do not depend on provider query mode.
5. This issue strengthens the case for freezing raw intraday inputs before production research rather than refetching historical Yahoo 1H on every experiment.

## Important non-finding

This audit does **not** show that V43 returns are wrong.

The V43 selected rows align with the frozen daily price scale, and the relative session features match the existing raw panel. The finding is about exact reproducibility and provider adjustment semantics, especially for `log_price`.


## V43 internal scale-consistency check

All 112 V43 fixed-min95 selected rows were joined to the preserved run80 daily OHLCV on symbol/date.

Result:
- daily OHLCV match available: **112/112**
- reconstructed session close (`entry`) inside the same-day frozen daily low/high range: **112/112**
- out-of-range rows: **0**

Therefore the observed query-mode split-adjustment mismatch is **not evidence that V43 itself mixes inconsistent price scales**.

The V43 path is internally coherent:
- historical completed-day context comes from the frozen daily panel;
- its live/reconstructed current-session price scale is consistent with that frozen panel on every selected row checked.

The reproducibility risk arises when attempting to substitute the Core explicit-period raw 1H archive for the V43 range-query 1H source without reproducing V43's corporate-action adjustment convention.
