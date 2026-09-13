# Prospective shadow causal preflight — 2026-09-14

## Scope

Research-only infrastructure. No production workflow, Discord, Sheets, Stable/Sniper/Mega, TradingView, ranking threshold, or model logic is changed.

Parallel-lane check before this work showed the shared branch advancing V14 into regime-normalized V15. This lane therefore stayed outside V14/V15 model construction and only hardened the prospective-shadow ingestion boundary.

## Added

- `shadow_preflight.py`
- `test_shadow_preflight.py`

## Enforced invariants

A candidate export is rejected unless all of the following are true:

1. required identity/provenance fields exist: `experiment_id`, `model_freeze_id`, `symbol`, `signal_date`, `bin_name`, `feature_cutoff`, `source_tag`;
2. `source_tag == RAW_CAUSAL_INTRADAY`;
3. only the frozen causal bins are accepted: `AM_09_13`, `PM_13_CLOSE`;
4. `feature_cutoff` is timezone-aware and normalizes to the same XTKS/JST calendar day as `signal_date`;
5. AM completion is exactly 13:00 JST;
6. PM completion is exactly 15:00 JST before the 2024-11-05 XTKS close extension and 15:30 JST from 2024-11-05 onward;
7. optional rank, when supplied, is >= 1;
8. duplicate prospective candidate keys are rejected within one export batch.

The purpose is to prevent a future frozen V15/V16/etc. candidate exporter from accidentally passing post-close or wrong-bin information into the forward-evidence store.

## Verification

Eight focused unit cases were executed locally and passed:

- valid AM candidate accepted;
- `POSTCLOSE_RECON_ONLY` rejected;
- cutoff on the wrong signal date rejected;
- wrong AM cutoff rejected;
- pre/post 2024-11-05 PM close boundary enforced;
- duplicate candidate key rejected;
- rank <= 0 rejected;
- UTC timestamp representing the exact JST cutoff accepted after timezone normalization.

Result: **8/8 PASS**.

## Concurrency / lane isolation

While this work was being completed, the branch advanced to a separate commit preregistering an outcome-free V15 normalized representation. No V15 files, thresholds, features, outcome gates, score calibration, or evaluator logic were edited by this lane.

## Next safe use

When another lane freezes a forward-test candidate model, its selected candidate rows can be exported under the already-frozen shadow export contract, run through this preflight, and only then appended to the prospective evidence JSONL. This does not authorize opening 2026 historical outcomes or using forward evidence to mutate an unfrozen model.
