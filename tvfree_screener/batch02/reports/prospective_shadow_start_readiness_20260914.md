# Prospective Shadow Start-Readiness Gate Verification — 2026-09-14

## Scope

Research-only infrastructure. No production changes. No strategy-return opening. No model, threshold, ranking, cooldown, or eligibility changes.

Parallel-lane recheck before this work found the model-research lane had advanced past the V17 representation pass into V12 H2 trigger-path degradation diagnosis. This lane intentionally did not modify V12/V17 model logic.

## Added

- `prospective_shadow_start_readiness.py`
- `test_prospective_shadow_start_readiness.py`

## Required start conditions

Prospective shadow collection is blocked unless all of the following are explicitly true:

1. representation gate passed
2. supervised evaluation preregistered
3. H1 policy frozen
4. model freeze manifest valid
5. model spec SHA pinned
6. candidate export contract satisfied
7. causal preflight passed
8. append-only integrity enabled
9. production isolation confirmed
10. historical 2026 tuning forbidden

A representation pass by itself is therefore insufficient to start shadow collection.

## Verification

Focused local unit tests: **5/5 PASS**.

Covered cases:

- all requirements true -> allow prospective shadow start
- representation pass alone -> block
- missing freeze -> block
- missing causal preflight -> block
- gate cannot promote or modify a model

## Decision semantics

- `ALLOW_PROSPECTIVE_SHADOW_START`: authorizes evidence collection only.
- `BLOCK_PROSPECTIVE_SHADOW_START`: at least one prerequisite is missing.

Passing this gate never promotes a model and never authorizes production writes.
