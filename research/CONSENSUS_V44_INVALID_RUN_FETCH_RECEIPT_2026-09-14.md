# V44 invalid-run fetch receipt diagnostic — 2026-09-14

Research-only data-quality diagnostic. No strategy-performance metrics from this invalid run were inspected or used.

## Source

Invalid/superseded V44 run:
- run id: `34765427789`
- artifact id: `10320613795`
- artifact digest: `sha256:0d49c432ca3103c6c3c891a4456e2ff712d87e9617a04088aa02927068661c88`

This run remains invalid for research conclusions because it opened all H2 cooldown metrics before the locked-validation correction.

## Fetch receipt only

Observed `hourly_fetch`:
- requested_symbols: **1,910**
- ok_symbols: **1,850**
- errors: HTTPError **59**, too_few_sessions **1**
- candidate_symbols: **1,793**
- candidate_rows: **519,231**

Frozen V43 reference / V44 acceptance floor:
- requested_symbols: 1,910 exact
- ok_symbols: >=1,850
- candidate_symbols: >=1,793
- candidate_rows: >=519,163

The invalid run therefore meets the frozen live-fetch coverage floor.

## Interpretation boundary

This does **not** rehabilitate run 34765427789 and says nothing about its return performance.

It only shows that one of the overlapping Yahoo-heavy runs completed with coverage at least as good as the preserved V43 reference. The authoritative hardened run `34767664140` must independently pass the same acceptance guard before any performance interpretation.

Performance fields inspected for this diagnostic: **false**.
Production modified: **false**.
