# Shadow resolution continuity guard — 2026-09-14

Research-only integrity work on `research/tvfree-canonical-batch02`.

## Purpose
Prevent retrospective mutation of prospective-shadow 5BD resolution evidence after a candidate row has been admitted.

## Contract
- Candidate identity fields and admitted prefix are immutable.
- `PENDING_5BD -> RESOLVED` is allowed when the canonical endpoint becomes available.
- `UNRESOLVED_ENDPOINT -> RESOLVED` is allowed only with the same pinned entry/exit dates.
- `RESOLVED -> unresolved/pending` is forbidden.
- Once resolved, entry date, exit date, entry open, exit close, and gross 5BD return are immutable.
- New candidates may only append after the existing prefix.
- Return consistency is checked mechanically from `exit_close / entry_open - 1`.
- The guard does not select candidates or tune any model/threshold and does not touch production.

## Evidence
Implementation commits:
- `ba3a7020cfedbf7c24091dbf854ac6d29e1616f4` — continuity guard.
- `82ec671aa3b782c1a78385a696308f96cc70fb27` — contract tests.
- `8e708d6e7b180e257872bfcb390cb23ad54c0bef` — dedicated CI workflow.

GitHub Actions run `34795293067` completed **SUCCESS**.

## V20 isolation
This integrity work did not read or interpret V20 H1/H2 outcomes. V20 remains blocked by the unchanged raw acceptance failure from run `34791959735`: 1,806/1,810 observed symbols and 734 missing canonical-active symbol/date pairs. No acceptance threshold was relaxed and no missing bar was interpolated or synthesized.

## Next safe action
Keep V20 outcomes closed. The next Event-side action remains outcome-blind raw-data recovery/diagnosis of the 734 missing canonical-active symbol/date pairs. Shadow/Data may now require this continuity guard before accepting any updated prospective resolution snapshot.
