# Core + Cloud handoff — 2026-09-16 01:24 JST

Core lane remains outcome-blind and fail-closed.

## Newly frozen
JPX segment-transfer events are mandatory PIT state transitions. Use official current/2025/2024 transfer pages, exact-byte pin them, and parse `(effective_date, code, previous_segment, new_segment)` with source lineage.

## Blocked from PASS
- Do not use the old 375-event receipt as canonical input until its difference from the 395-event forensic recount is explained.
- Do not issue PIT membership PASS until transfer ledger + corrected listing/delisting ledger reverse-replay with zero unresolved state/identity conflicts.
- Do not generate `membership × XTKS × hour` yet.

## Next action
1. Extend research-only JPX byte capture to transfer current/2025/2024.
2. Freeze their SHA-256 receipts.
3. Build normalized transfer ledger.
4. Audit 375-vs-395 exact row-set delta.
5. Reverse replay from effective 2026-08-31 anchor to 2024-09-17 and freeze membership count/SHA/quarantine receipt.

Cloud exact forensic remains closed: `HISTORICAL_EXACT_REPRO_UNAVAILABLE`.
