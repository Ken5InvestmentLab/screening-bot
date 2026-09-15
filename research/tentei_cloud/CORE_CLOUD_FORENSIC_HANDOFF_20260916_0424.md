# Core + Cloud forensic handoff — 2026-09-16 04:24 JST

## Canonical status after this run
- JPX exact-byte provenance: PASS for listing, delisting, segment-transfer and listed-issues anchor sources.
- Anchor workbook: effective `2026-08-31`, eligible domestic Prime/Standard/Growth universe contract unchanged.
- Listing/delisting forensic count through `2026-09-10`: **134 + 241 = 375**. This restores the original 375 receipt as count-consistent; the exploratory 395/261-delist claim is superseded.
- Segment-transfer reverse-replay input through anchor `2026-08-31`: **81 events** = 2024:5 + 2025:35 + current:41.
- Deterministic normalized/sorted transfer-ledger local SHA-256: `b2f838727d57499792a95a33b26c768e9ee96b94af909b20713c73b132fbe332`.
- `277A Globe-ing Inc.`: `2026-04-30 Growth -> Prime` confirmed in pinned current-transfer bytes.
- PIT membership: still FAIL-CLOSED pending integrated conflict-checked reverse replay.
- Cloud Monster: `HISTORICAL_EXACT_REPRO_UNAVAILABLE`; do not resume family guessing without new exact evidence.

## Important correction
Do not reuse exploratory transfer count 75. It came from vectorized mixed-date parsing that coerced valid month formats to `NaT`. Row-wise exact date parsing yields 81. Likewise do not reuse the exploratory `395 = 134 + 261` claim; pinned pages yield 375 exactly through 2026-09-10.

## Next P0
1. Parse the exact `2026-08-31` listed-issues workbook under the frozen eligible-segment contract.
2. Build integrated event stream from pinned listing/delisting plus 81 transfers. For reverse replay, use only events necessary between target `2024-09-17` and anchor `2026-08-31`; later 2026 events are report-only/provenance evidence.
3. Reverse replay with strict transition assertions and quarantine contradictions/impossible states.
4. Freeze target membership count, sorted membership SHA-256, event counts, quarantine count/details, source SHAs and parser version in a receipt.
5. PIT PASS only if quarantine/identity/transition checks satisfy the frozen contract; otherwise remain FAIL-CLOSED.
6. After PIT PASS, move to independent exact-hour activity evidence. Never manufacture hourly expected keys from PIT membership alone.

All new performance work in this lane remains cost 0% only; win = gross return > 0.