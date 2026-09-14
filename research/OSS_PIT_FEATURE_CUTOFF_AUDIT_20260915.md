# OSS PIT feature-cutoff audit — 2026-09-15

Branch: `research/oss-validation-tooling`

## Finding

Outcome-blind inspection of `tvfree_screener/optuna_discovery.py` found a point-in-time fail-open boundary after the completed-trial receipt/DSR binding was verified.

`validate_discovery_frame()` accepts `feature_cutoff_column: str | None = None`. When callers omit the argument, the harness still validates candidate/label dates and finite feature values, but it does **not** prove that each feature row was available no later than its candidate/prediction date. `run_study()` exposes the same optional default and forwards it unchanged.

This does not show that any existing research outcome is leaked. It shows that the generic Optuna harness can currently be invoked without the PIT timestamp evidence needed to fail closed.

## Severity / status

- classification: `P0_VALIDATION_CONTRACT_GAP`
- outcome opened by this audit: `false`
- strategy/model thresholds changed: `false`
- transaction cost policy changed: `false` (`0%` remains frozen)
- later-period selection opened: `false`
- production/main touched: `false`

## Required fail-closed fix

Before this harness is used for a new discovery run:

1. Require an explicit feature-availability/cutoff timestamp column at the `run_study()` boundary, or require an equally strong preregistered immutable PIT provenance receipt that is validated there.
2. Reject missing/null/non-finite/unparseable cutoff evidence.
3. Reject any row where feature availability is later than the candidate/prediction timestamp.
4. Add regression tests proving omission and future-dated availability fail closed.
5. Keep Discovery window `2022-07-01..2023-12-31`, cost `0%`, receipt-bound DSR, and later-period selection exclusions unchanged.
6. Do not open 2024/2025/2026 performance to choose between PIT implementations.

## Parallel cross-check note

The previously observed SHA `74ab2aaf...` belonged to a separately saved `xtks_sessions.csv` representation that included a different serialization/schema. It must not be compared as if it were the pinned Parallel artifact bytes. The authoritative Parallel Wave-1 receipt binds `research/PARALLEL_WAVE1_XTKS_CALENDAR_2022_2026.csv` (single `session` column, 1,220 sessions) to SHA-256 `58e67bd20be08d04c143fa7e8f707bb3b82c21c2de2af9dfd7c2a05a406de71b`, source commit `cd667f598bcdd980cb186350f4ecb49f1e57661e`, receipt commit `69f49c879fec2eded3dfd84d7bf1f8f249b865aa`. Therefore the earlier cross-file SHA mismatch is **not** evidence of drift in the pinned artifact; it was a hash-domain/artifact-identity mismatch. Parallel remains fail-closed until its causal pick ledger and endpoint completeness receipt are produced.

## Next OSS action

Implement the smallest PIT-boundary fail-closed patch + tests, then run isolated OSS validation CI. Do not repeat the already-verified completed-trial receipt/DSR binding task.
