# Core JPX segment-transfer byte-pin spec — 2026-09-16

## Canonical source family
The PIT event family must include exact captured bytes for JPX official segment-transfer pages current, 2025 archive, and 2024 archive in addition to the already required listing/delisting and listed-issues anchor sources.

## Acceptance
A transfer source is canonical only when the research-only capture workflow records source URL, final URL, HTTP status 200, byte size, SHA-256 and retrieval timestamp from the exact response bytes, and the immutable Actions artifact is retained/identified. Rendered/search text is discovery evidence only.

## Fail-closed rules
- No PIT PASS while any transfer source is missing or uncaptured.
- No surrogate/nearby source may be called exact reproduction.
- The legacy 375 listing/delisting event receipt is non-canonical until the separately observed 395 replay-eligible count delta is reconciled row-by-row.
- Segment-transfer integration must preserve code/date/from-segment/to-segment identity; unknown labels or impossible reverse transitions are quarantined rather than guessed.
- Reverse replay begins only after anchor, listing, delisting and transfer inputs are byte-pinned and their parser receipts are frozen.

## Performance isolation
This is provenance/data repair only. No return opening, no retune, no costed comparison. Any later new performance remains transaction cost 0% and win = gross return > 0; 2026 outcome remains report-only.
