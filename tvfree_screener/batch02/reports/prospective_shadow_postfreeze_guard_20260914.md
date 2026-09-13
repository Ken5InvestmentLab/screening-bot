# Prospective shadow post-freeze temporal guard — 2026-09-14

## Scope
Research-only integrity control for genuine prospective shadow evidence. No strategy-return inspection, score inspection, model change, threshold change, ranking change, eligibility change, or production modification.

## Purpose
A candidate row is not genuinely prospective merely because it has a valid causal intraday cutoff. Its decision-time `feature_cutoff` must also be strictly later than the immutable model freeze timestamp. This guard therefore enforces:

`feature_cutoff > frozen_at`

Equality is rejected. Pre-freeze rows are rejected. Timezone-naive timestamps are rejected. UTC/JST-aware timestamps are compared as actual instants. Candidate experiment/freeze identity must match the manifest. One violating row blocks the whole input batch.

## Files
- `prospective_shadow_postfreeze_guard.py`
- `test_prospective_shadow_postfreeze_guard.py`

## Verification
Local equivalent execution: **8/8 PASS**.

Covered cases:
1. strictly post-freeze cutoff passes
2. cutoff equal to freeze blocks
3. pre-freeze cutoff blocks
4. UTC timestamp correctly compares against JST freeze
5. timezone-naive cutoff blocks
6. model-freeze identity mismatch blocks
7. one violating row blocks the entire batch
8. empty batch blocks

## Integrity boundaries
- `opens_strategy_returns: false`
- `uses_model_scores: false`
- `changes_model: false`
- `changes_thresholds: false`
- `production_modified: false`
- `batch_is_atomic: true`

This guard complements, rather than replaces, causal cutoff validation, freeze-manifest validation, start-readiness, branch staleness/ancestry checks, append-only integrity, and final authorization.
