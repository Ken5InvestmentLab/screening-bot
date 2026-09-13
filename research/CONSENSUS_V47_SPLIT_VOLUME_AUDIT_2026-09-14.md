# V47 split-volume semantics audit — 2026-09-14

Outcome-free data-semantics audit. No strategy returns were used to choose the correction.

## Result

Yahoo daily and Yahoo 1H volume do **not** share the same split-adjustment convention in the frozen research data.

### Daily
For forward stock splits, run80 daily volume is retrospectively expressed on the post-split share-count scale. Therefore historical point-in-time share volume is:

`PIT daily volume = frozen daily volume / cumulative future split factor`.

### 1H
Existing V43 session-volume receipts were compared against both:
- frozen split-adjusted daily volume, and
- reconstructed PIT daily volume.

Among 22 selected symbol-dates where both synthetic sessions were available and a future split factor existed, **22/22** were closer to the PIT daily-volume scale.

Strong example:
- 6574: cumulative future split factor = 100;
- raw1H session-sum / frozen daily volume ≈ 0.0094;
- raw1H session-sum / reconstructed PIT daily volume ≈ 0.944.

This is incompatible with 1H volume being multiplied by the same future split factor as daily volume.

## Frozen V47 rule

- Daily OHLC price: keep split-normalized for relative technicals; reconstruct PIT nominal absolute price where required.
- Daily volume: divide by cumulative future split factor before prior-volume eligibility and daily volume-ratio features.
- Raw 1H price: split-normalized for relative features; reconstruct PIT nominal entry price for absolute `log_price`.
- Raw 1H volume: **do not split-adjust again**; use unchanged for session volume and session volume ratio.
- Price cap: remains performance-selected NOCAP vs CAP1000_PIT.

This correction is mandatory before V47 strategy/model outcomes.
