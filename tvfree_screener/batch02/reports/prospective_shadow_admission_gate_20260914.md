# Prospective Shadow Admission Gate Verification — 2026-09-14

## Scope
Outcome-free/data-integrity lane only. No model, threshold, strategy-return, production, Discord, Sheets, or TradingView changes.

## Purpose
Unify the previously separate causal preflight and strict post-freeze temporal guard into one fail-closed batch admission decision so callers cannot accidentally run only one of the two checks.

## Files
- `prospective_shadow_admission_gate.py`
- `test_prospective_shadow_admission_gate.py`

## Required admission conditions
A batch is admitted only when both are true:
1. `shadow_preflight.validate_shadow_export_rows()` passes for the full batch.
2. `prospective_shadow_postfreeze_guard.evaluate_postfreeze_rows()` returns `postfreeze_valid=true` for the full batch.

Any failure blocks the entire batch with `BLOCK_PROSPECTIVE_SHADOW_BATCH`.

## Verification
Local equivalent execution: **8/8 PASS**.
Covered cases:
- valid causal post-freeze batch admitted;
- noncausal source tag blocked;
- pre-freeze cutoff blocked;
- empty batch blocked;
- duplicate candidate key blocked;
- unexpected bin cutoff blocked;
- freeze identity mismatch blocked;
- integrity metadata confirms atomic dual-gate and no production modification.

## Parallel-lane reconciliation
During verification the shared research branch advanced by two commits after the admission-gate test commit. GitHub compare from `cc223ad5aeeaffaef008f1ec2e4dd03a4c8846d9` to `42352c72323f2436e7b1562a92f3df89c23fbc0f` returned `ahead_by=2`, `behind_by=0`; the intervening files were V20 workflow files only. Therefore this admission-gate work does not overlap the active V20 event experiment.

## Decision
`UNIFIED_SHADOW_ADMISSION_GATE_VERIFIED`

This is evidence-collection infrastructure only and does not authorize production promotion.
