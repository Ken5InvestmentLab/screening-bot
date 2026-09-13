# Prospective shadow branch ancestry guard — 2026-09-14

## Scope
Research-only integrity control for prospective-shadow authorization. This guard does not open strategy returns, alter any model, change thresholds/ranking/cooldown/eligibility, or modify production.

## Why this was added
The supervisor contract now requires all source-branch HEADs to be re-fetched immediately before any prospective-shadow authorization or cross-lane comparison. A simple SHA mismatch detects staleness but does not distinguish a normal fast-forward from a branch rewind or divergent history. This guard adds that distinction.

## Behavior
Given a snapshot branch/head and the current branch/head plus GitHub compare metadata, the guard classifies ancestry as:

- `IDENTICAL`: existing readiness snapshot may remain valid.
- `AHEAD`: normal fast-forward; readiness must be regenerated before authorization.
- `BEHIND`: branch rewind detected; block and reconcile history.
- `DIVERGED`: histories diverged; block and reconcile history.
- `UNKNOWN`: ancestry could not be verified; block.

Branch-name mismatch and missing HEAD identifiers are also blocking.

## Decisions
- `ALLOW_EXISTING_READINESS_SNAPSHOT`
- `REFRESH_READINESS_AFTER_FAST_FORWARD`
- `BLOCK_AND_RECONCILE_BRANCH_HISTORY`

## Verification
Seven behavior cases were executed against the implementation logic:

1. identical branch/head -> allow existing readiness
2. clean fast-forward -> refresh readiness
3. behind/rewind -> block
4. diverged history -> block
5. unknown relation -> block
6. branch identity mismatch -> block
7. ahead/behind counts infer divergence -> block

Result: **7/7 PASS**.

## Files
- `tvfree_screener/batch02/prospective_shadow_branch_ancestry_guard.py`
- `tvfree_screener/batch02/test_prospective_shadow_branch_ancestry_guard.py`

## Integrity constraints
- 2026 strategy outcomes opened: false
- production modified: false
- model/threshold/ranking/cooldown/eligibility changed: false
- purpose: provenance and authorization integrity only
