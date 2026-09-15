# Core24 JPX PIT date-parser correction — 2026-09-16 05:23 JST

Research-only. No production/performance changes.

## Finding
Direct re-parse of immutable Actions artifact `10411777912` exposed a second mixed-month date-format bug. JPX English pages use both abbreviated months with a period (for example `Apr. 30, 2026`) and `May` without a period (for example `May 29, 2026`). Any parser requiring `%b. %d, %Y` or regex requiring a literal period silently drops valid May rows.

## Corrected row-wise contract
For every listing/delisting/segment-transfer date, parse row-wise and accept exactly these two English forms:
- `%b. %d, %Y`
- `%b %d, %Y`

No vectorized coercion and no `errors=coerce` is permitted. An unrecognized non-empty date is quarantine/fail-closed.

## Consequences on pinned bytes
- Segment transfers remain **81** through anchor 2026-08-31 (the already-corrected count).
- Listing count through 2026-09-10 remains **134** for the target window.
- Delisting count through 2026-09-10 is **263**, not 241.
- Therefore the previously re-restored `375 = 134 + 241` claim is again superseded. Correct listing+delisting count through 2026-09-10 is **397 = 134 + 263**.
- For strict reverse replay from the 2026-08-31 anchor to target 2024-09-17, replay-eligible event counts are **134 listings + 261 delistings + 81 transfers = 476 events**.

## Strict reverse replay result
Anchor eligible universe: 3,707 domestic Prime/Standard/Growth codes. Reverse replay over the 476 corrected events completed with **0 quarantine/identity/transition conflicts** and produced target membership count **3,834**.

Canonical sorted membership serialization is one line per code as `CODE,SEGMENT\n`, sorted lexicographically by canonical code. SHA-256: `9f54f11242b0c6b510de44b3b9adc900a9892d43ed084b70b9d9eda1cec1332e`.

This is a provenance/integrity correction, not retuning. PIT may advance only under this corrected parser contract; the old 375 receipt must not be used as canonical input.