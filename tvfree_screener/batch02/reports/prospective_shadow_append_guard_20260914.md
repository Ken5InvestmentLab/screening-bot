# Prospective shadow append-only integrity guard verification — 2026-09-14

## Scope

Research-only evidence integrity infrastructure. No model, feature, threshold, ranking, cooldown, eligibility rule, production workflow, Discord, Sheets, TradingView, or historical outcome logic was changed.

Parallel model-research status at verification time:
- V16 representation drift failed.
- V17 cross-sectional rank representation subsequently passed its outcome-free representation gate.
- This shadow lane did not interpret that pass as model promotion and did not start prospective collection automatically.

## Added

- `prospective_shadow_append_guard.py`
- `test_prospective_shadow_append_guard.py`

The guard compares an older shadow JSONL snapshot with a newer snapshot and permits only exact historical-prefix preservation plus optional appended rows.

Blocked conditions:
- historical row rewrite
- truncation / deletion of prior rows
- historical row reordering

The guard reports old/new row counts, appended-row count, first mismatch row, and deterministic content SHA-256 digests.

## Verification

Focused cases: **6/6 PASS**.

Covered cases:
1. clean append -> PASS
2. identical snapshot -> PASS, zero append
3. historical rewrite -> BLOCK
4. truncation -> BLOCK
5. reordering -> BLOCK
6. blank-line formatting difference -> ignored while non-empty record order remains preserved

## Integrity

- permits historical rewrite: false
- permits truncation: false
- permits reordering: false
- uses strategy returns: false
- changes model or thresholds: false
- promotion authorized: false
- production modified: false

## Operational role

A future shadow evidence run should retain the prior snapshot or its exact bytes and run this guard before accepting the new snapshot as an evidence continuation. A V17 representation pass alone is not sufficient to start shadow evidence; a separately frozen evaluation/selection policy and immutable freeze manifest are still required.
