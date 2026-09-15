# Core + Cloud forensic log — 2026-09-16 06:24 JST

## Core24
Frozen machine-readable PIT membership receipt `CORE_JPX_PIT_MEMBERSHIP_RECEIPT_20260916.json` on the Core research branch. It binds the exact-byte JPX listing/delisting source receipt, anchor artifact/run, segment-transfer artifact/digests, corrected row-wise date parser contract, reverse-replay event counts, zero-conflict result, target count and membership SHA.

Canonical replay remains: anchor 2026-08-31 count 3,707; reverse window `(2024-09-17, 2026-08-31]`; 134 listings + 261 delistings + 81 transfers = 476; target count 3,834; quarantine/identity/transition conflicts 0; sorted `CODE,SEGMENT\n` SHA-256 `9f54f11242b0c6b510de44b3b9adc900a9892d43ed084b70b9d9eda1cec1332e`.

Date parser remains row-wise `%b. %d, %Y` OR `%b %d, %Y`, unknown non-empty dates fail closed. The superseded 375/241 count is not restored.

## Next
Proceed only to independent exact-hour activity evidence. Do not synthesize expected hourly keys from PIT membership.

## Cloud
No new exact evidence. `HISTORICAL_EXACT_REPRO_UNAVAILABLE` remains closed; no family guessing.

No performance opened; no costed calculations; no rejected-family retune; no production/main changes.
