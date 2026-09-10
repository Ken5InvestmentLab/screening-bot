# TV-Free V3 research status (TEST ONLY)

## Guardrails
- Branch: `test/tvfree-screener-v1`
- Draft PR: #13
- No merge to `main` without explicit user Go approval.
- No production Discord/Spreadsheet writes.
- No production Stable★6/Sniper/Mega/TradingView changes.
- Realistic entry: next trading session open.
- 2026 is contaminated; never tune to it.

## Reproducibility finding
GitHub Actions run `34519284035` successfully executed the full research pipeline. It also exposed that the previous Yahoo `period=3y` cache is rolling: as time advances, old rows fall out, changing historical training samples and therefore backtest numbers even when code is unchanged.

Test-only fixed-start acquisition was added at commits `063a73b3...` and `458be814...`, using `2022-01-01 -> current`. No model architecture or threshold was changed. Numeric baselines below are the latest successful rolling-3y snapshot until the fixed-start rerun completes.

## V3 Short (5BD)
Historical non-reproducible old reference: 2026 Mar-Aug n=29, mean +5.42%, median +2.06%, win 65.5%, +10% 13.8%, -10% 6.9%. Exact old parameters were never committed.

`v3_short_reconstruction.py` is now confirmed executable in Actions and implements the same 45 `run.py` features, monthly causal 180-tree XGBoost, prediction-day percentile normalization, Core `r_top10 - 2*r_loss10`, one-day same-symbol cooldown, next-open -> 5BD, inactive/rejected recent-outcome Meta, and no accepted Attack.

Latest successful snapshot, run `34519284035`:
- Core 2025H1: n=119 mean +0.46%, median +0.45%, win 58.8%, +10% 4.2%, -10% 3.4%.
- Core 2025H2: n=124 mean +0.35%, median +0.28%, win 51.6%, +10% 1.6%, -10% 1.6%.
- Core 2026 Mar-Aug contaminated: n=124 mean -0.56%, median -0.42%, win 44.4%, +10% 0.8%, -10% 0.8%.
- Defensive `med_ret5 >= -1%` 2026 Mar-Aug: n=97 mean -0.11%, median 0%, win 48.5%, -10% 0%.

Earlier research-note figures are not used as exact reproduction claims; the runner artifact is authoritative for its stated input snapshot. Await fixed-start rerun before freezing a durable numeric baseline.

### Attack
- Whole-universe Attack heads: rejected.
- Distinct event-family Attack: 10/10 variants failed pre-2026 robustness; no 2026 candidate opened.
- Short Attack = **none/unaccepted**.

## V3 Swing (10BD)
Frozen architecture: `v3_swing_v2.py`, MomCross -> causal semiannual quality model -> training CDF -> Breadth Meta -> `score_R >= 0.20`.

Latest successful rolling-3y snapshot, run `34519284035`, at unchanged 0.20:
- 2025H1: n=37 mean +6.36%, median -0.75%, win 45.9%, +10% 16.2%, -10% 5.4%.
- 2025H2: n=23 mean +5.89%, median -0.84%, win 43.5%, +10% 13.0%, -10% 0%.
- 2026 Mar-Aug contaminated: n=31 mean +1.00%, median +1.26%, win 54.8%, +10% 9.7%, -10% 3.2%.

The same run's current pre-2026 sweep selects 0.10 rather than 0.20, producing `locked_threshold_matches_best_pre2026=false`. **Do not retune.** The training-history drift invalidates direct comparison with the earlier threshold-selection snapshot. First establish the fixed-start history contract, then report the frozen 0.20 result consistently. Swing A remains none/unaccepted.

## Unified comparison
`unified_comparison.py` succeeded in run `34519284035`, correctly distinguishing historical references from reproducible-runner outputs and leaving unavailable metrics blank.

## Operational snapshot
Run `34519284035`:
- total runtime about 23m15s,
- rolling-3y artifact about 33.55 MB,
- current job timeout 90 minutes.

## Current architecture decision
- Short Core: executable/reproducible code but weak; numeric baseline pending fixed-start rerun.
- Short defensive gate: supporting only.
- Short recent-outcome Meta: rejected.
- Short Attack: none.
- Swing S: architecture and threshold 0.20 frozen; numeric baseline pending fixed-start rerun.
- Swing A: none.
- Production migration: blocked pending explicit user Go.

## Next
1. Inspect the fixed-start Actions rerun and artifact.
2. Confirm history starts at 2022-01-01 where symbols existed and pipeline succeeds.
3. Record/freeze fixed-start Short/Swing/unified numbers without retuning to 2026.
4. Later verify append-only historical stability as new sessions arrive.
5. Reassess runtime/artifact size with the longer fixed-start cache.
