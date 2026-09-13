# Prospective shadow local CLI verification — 2026-09-14

Research-only parallel lane. This work intentionally avoided the concurrently advancing V14/V15 model/replay lane and did not change production code, production workflows, Discord, Sheets, Stable★6, Sniper, Mega, TradingView, watchlist-builder, or watchlist-updater behavior.

## Goal

Turn the previously frozen prospective-shadow evidence contract into an ordinary-Python, local-input-only workflow that can preserve genuinely post-freeze evidence without introducing network fetches or model tuning.

## Added

- `prospective_shadow_cli.py`
  - `ingest`: reads local CSV/JSONL candidate rows, verifies an immutable freeze manifest, rejects experiment/freeze identity overrides, and appends through the existing causal/idempotent recorder.
  - `resolve`: reads only a supplied local daily CSV, derives official-session labels from explicit dates, and resolves the existing next-session-open -> fifth-session-close endpoint without forward-fill or later-session substitution.
  - Every summary records SHA-256 values for the freeze manifest and local inputs.
- `PROSPECTIVE_SHADOW_FREEZE_MANIFEST_TEMPLATE.json`
  - requires a distinct immutable `model_freeze_id` and model-spec SHA before candidate collection.
- `test_prospective_shadow_cli.py`
  - dedicated guards for manifest SHA mismatch, freeze-identity override, CSV loading, and explicit-session derivation.

## Verification

Local ordinary-Python verification combined the original shadow behavior with the new CLI guards. Result: **7/7 PASS**.

Verified behaviors:

1. `POSTCLOSE_RECON_ONLY` is rejected from the prospective candidate stream.
2. Repeated candidate ingest is idempotent by the frozen candidate key.
3. Endpoint resolution remains next official session open to fifth official session close.
4. Freeze-manifest SHA mismatch fails closed.
5. Candidate rows cannot override `experiment_id` / `model_freeze_id` from the frozen manifest.
6. CSV candidate input is accepted without changing signal logic.
7. Daily session dates are taken only from explicit supplied rows; no forward fill or guessed sessions are introduced.

## Parallel-work collision check

Immediately before the verification/report step, branch HEAD had advanced from this lane's CLI test commit to `5f093c7e...`, message `research: add guarded fast-equivalent V14 replay evaluator`, from the other parallel chat. That work is in the V14 replay/model-evaluation lane. This shadow-evidence lane therefore did not modify V14/V15 evaluators or model logic and continued only with unique shadow files.

## Decision

The prospective evidence plumbing is ready for a future frozen candidate to begin genuine post-freeze shadow accumulation. It must remain disconnected from production until a model is explicitly frozen for shadow use. Historical 2026 outcomes are not to be used to select that model or tune its thresholds.

Production modified: **false**.
