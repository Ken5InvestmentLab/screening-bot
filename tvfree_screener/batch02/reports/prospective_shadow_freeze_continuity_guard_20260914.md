# Prospective shadow freeze continuity guard verification — 2026-09-14

## Scope

Research-only prospective-shadow infrastructure. No model, feature, threshold, ranking, cooldown, eligibility, Discord, Sheets, TradingView, watchlist, or production workflow changes.

## Parallel-lane check

Before this work, the other research lane had advanced to preregistering a distinct V20 session-impulse-continuation hypothesis. This lane therefore did not touch V17/V20 model logic or outcome evaluation.

## Added

- `prospective_shadow_freeze_continuity_guard.py`
- `test_prospective_shadow_freeze_continuity_guard.py`

## Guard behavior

The guard compares the originally pinned prospective-shadow baseline receipt with the current freeze manifest and current model-spec bytes. Shadow collection may continue only when all of the following remain unchanged:

1. experiment_id
2. model_freeze_id
3. freeze-manifest SHA-256
4. model-spec SHA-256
5. the model-spec SHA declared inside the freeze manifest

Any mismatch returns `STOP_AND_ROTATE_FREEZE_ID`. Existing prospective rows must remain attached to the old freeze and must never be relabeled under the changed model.

## Verification

7 focused cases passed:

1. intact identity passes
2. changed experiment_id stops
3. changed model_freeze_id stops
4. changed freeze-manifest SHA stops
5. changed current model-spec SHA stops
6. changed manifest-declared model-spec SHA stops
7. incomplete baseline receipt is rejected

Result: **7/7 PASS**.

## Integrity statement

- strategy returns used: false
- model scores used: false
- model tuning performed: false
- 2026 outcomes opened: false
- production modified: false
- network fetches added to runtime: false
