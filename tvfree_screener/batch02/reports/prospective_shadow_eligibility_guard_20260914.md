# Prospective Shadow Eligibility / Skip-Before-Shadow Guard — 2026-09-14

## Scope
Research-only hardening of the prospective-shadow/data-integrity lane. No production writes, model changes, threshold changes, or strategy-return tuning.

## Supervisor / concurrency context
- The Event/Monster lane remains separate.
- Core is working on canonical-entry capacity diagnostics.
- Consensus owns the point-in-time universe / split-adjustment reconstruction work and related JPY 1,000-cap comparison.
- This change does not duplicate those lanes.

## Problem found
The existing prospective-shadow chain already enforced causal source, post-freeze timing, immutable admission receipts, and verified append. However, it did not require an explicit proof that a candidate had passed data-sufficiency/eligibility checks before being admitted. A producer could therefore accidentally serialize a row that should have been skipped for missing data.

## Changes
1. Added `prospective_shadow_eligibility_guard.py`.
2. Every prospective-shadow candidate must now explicitly carry:
   - `eligibility_status = ELIGIBLE`
   - `data_sufficient = true`
   - no `skip_reason`
   - no non-empty `missing_fields`
3. Empty batches fail closed.
4. Integrated the eligibility guard into `prospective_shadow_admission_gate.py`.
5. Updated admission and verified-append tests to the new contract.
6. Updated the synthetic E2E path to:
   `eligibility -> admission -> receipt -> verified append -> append-only guard -> 5BD resolution`.

## Verification
Equivalent contract execution performed for the new guard and integrated admission contract:
- eligibility guard: 6/6 PASS
- integrated admission contract: 10/10 PASS
- combined focused verification: 16/16 PASS

## Expected fail-closed behavior
A candidate is blocked before receipt creation / append when any row is marked skipped, lacks explicit eligibility proof, has insufficient data, or declares missing fields. Because verified append replays admission immediately before writing, changing an admitted row into an ineligible/missing-data row after receipt creation also blocks the append before the shadow JSONL is modified.

## Relevant commits
- `b23650a6afe7e9e08b4131f08d0107f7abb9f7fe` — add eligibility guard
- `62fa8776cac91a1093bcbe52fd14fc5500c3a40b` — eligibility guard tests
- `53368de5c91bfc7a9d56c1e9acd684eaee0f2b9e` — require eligibility in admission gate
- `feff133c7205ed11278ed3787e4d65ca0f2be36e` — update admission tests
- `bd93cef1be0bdcb1f95d6612691adba2bb14fe7e` — update verified-append tests
- `2a39e3a42739716f09ea92e5dbcec326c16a883d` — update synthetic E2E to verified eligibility path

## Disposition
`ELIGIBILITY_SKIP_BOUNDARY_HARDENED`

This does not authorize a real prospective-shadow launch. Fresh branch HEADs, current supervisor contract, start-readiness, authorization, and real candidate freeze evidence remain required at the actual launch boundary.
