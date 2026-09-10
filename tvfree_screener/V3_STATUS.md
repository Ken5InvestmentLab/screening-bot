# TV-Free V3 research status (TEST ONLY)

## Guardrails
- Branch: `test/tvfree-screener-v1`
- Draft PR: #13
- No merge to `main` without explicit user Go approval.
- No production Discord/Spreadsheet writes.
- No production Stable★6/Sniper/Mega/TradingView changes.
- Realistic entry: next trading session open.
- 2026 is contaminated; never tune to it.

## Reproducibility status
The last fully successful research pipeline remains Actions run `34519284035`, which used rolling Yahoo `period=3y`. That run proved the full Short/Swing/comparison pipeline executes, but the rolling window allows old training rows to disappear as calendar time advances.

Test-only fixed-start acquisition was therefore added at commits `063a73b3...` and `458be814...`, using `2022-01-01 -> current`. No model architecture or threshold was changed.

Fixed-start verification has not yet produced a started job:
- run `34525453744` failed before any workflow step and exposed no step logs; a rerun was requested.
- run `34530881770` likewise failed before any step with an empty steps list.

These are runner/startup failures, not demonstrated Python/model failures. Do not modify model semantics in response.

A mechanical append-only check was added:
- `reproducibility_manifest.py`: commit `797a8578...`
- workflow integration: commit `418c42b7...`
- historical cutoff: `2026-08-31`
- hashes: raw OHLCV date/symbol coverage, Short Core, Short defensive lane, Swing S.

Future fixed-start runs can now prove whether historical outputs remain unchanged when only newer market sessions are appended.

## V3 Short (5BD)
Historical non-reproducible old reference: 2026 Mar-Aug n=29, mean +5.42%, median +2.06%, win 65.5%, +10% 13.8%, -10% 6.9%. Exact old parameters were never committed.

`v3_short_reconstruction.py` is executable and implements the same 45 `run.py` features, monthly causal 180-tree XGBoost, prediction-day percentile normalization, Core `r_top10 - 2*r_loss10`, one-day same-symbol cooldown, next-open -> 5BD, rejected/inactive recent-outcome Meta, and no accepted Attack.

Latest fully successful rolling-3y snapshot, run `34519284035`:
- Core 2025H1: n=119 mean +0.46%, median +0.45%, win 58.8%, +10% 4.2%, -10% 3.4%.
- Core 2025H2: n=124 mean +0.35%, median +0.28%, win 51.6%, +10% 1.6%, -10% 1.6%.
- Core 2026 Mar-Aug contaminated: n=124 mean -0.56%, median -0.42%, win 44.4%, +10% 0.8%, -10% 0.8%.
- Defensive `med_ret5 >= -1%` 2026 Mar-Aug: n=97 mean -0.11%, median 0%, win 48.5%, -10% 0%.

Attack:
- Whole-universe Attack heads rejected.
- Distinct event-family Attack: 10/10 variants failed pre-2026 robustness; 2026 was not opened for those candidates.
- Short Attack = none/unaccepted.

## V3 Swing (10BD)
Frozen architecture: `v3_swing_v2.py`, MomCross -> causal semiannual quality model -> training CDF -> Breadth Meta -> `score_R >= 0.20`.

Latest fully successful rolling-3y snapshot at unchanged 0.20:
- 2025H1: n=37 mean +6.36%, median -0.75%, win 45.9%, +10% 16.2%, -10% 5.4%.
- 2025H2: n=23 mean +5.89%, median -0.84%, win 43.5%, +10% 13.0%, -10% 0%.
- 2026 Mar-Aug contaminated: n=31 mean +1.00%, median +1.26%, win 54.8%, +10% 9.7%, -10% 3.2%.

The rolling-3y pre-2026 sweep currently favors 0.10 rather than 0.20. Do NOT retune. Establish the fixed-start data contract first. Swing A remains none/unaccepted.

## Operational snapshot
Last successful rolling-3y run `34519284035`:
- total runtime about 23m15s,
- artifact about 33.55 MB,
- job timeout 90 minutes.

Fixed-start cost remains unknown until a hosted runner actually starts the job.

## Current decision
- Short Core: code is reproducible; durable numeric baseline pending fixed-start run.
- Short defensive gate: supporting only.
- Short recent-outcome Meta: rejected.
- Short Attack: none.
- Swing S: architecture and threshold 0.20 frozen; durable numeric baseline pending fixed-start run.
- Swing A: none.
- Production migration: blocked pending explicit user Go.

## Next
1. Re-check GitHub Actions runner availability and obtain the first actually-started fixed-history job.
2. Confirm fixed history starts at 2022-01-01 where symbols existed and pipeline/manifest succeed.
3. Freeze fixed-start Short/Swing numeric values and historical hashes without retuning to 2026.
4. On a later appended session, compare cutoff hashes for historical stability.
5. Measure fixed-start runtime/artifact size.
