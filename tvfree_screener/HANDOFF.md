# TradingView-Free Screener — Autonomous Handoff

TEST ONLY. Canonical handoff for scheduled runs and new chats.

## Safety guardrails
- Repository: `Ken5InvestmentLab/screening-bot`
- Working branch: `test/tvfree-screener-v1`
- Draft PR: #13
- NEVER merge to `main` without explicit user Go approval.
- NEVER modify production Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater, or production workflows without explicit user Go approval.
- Evaluate next-session-open -> horizon close.
- Training/selection must be causal. 2026 is already contaminated and must not be used to tune thresholds.

## Goal
Replace TradingView/Pine watchlist dependency with a free Yahoo-daily-OHLCV TSE common-stock system without creating a visibly inferior Stable★6 replacement.

## Infrastructure / reproducibility
- TSE domestic common-stock universe: about 3,700 symbols.
- Last fully successful research pipeline: Actions run `34519284035` on rolling `period=3y`; all Short/Swing/comparison steps passed, runtime about 23m15s, artifact about 33.55 MB.
- Critical reproducibility flaw found: rolling `period=3y` drops old training rows as time advances.
- Test-only fixed-start acquisition was added in `bootstrap.py` (`063a73b3...`) and workflow (`458be814...`), defaulting to `2022-01-01 -> current`; no model architecture or threshold changed.
- Fixed-start verification remains blocked by GitHub Actions hosted-runner startup failure, not a model/test exception. Latest observed run `34539341326` again completed failure with no executable steps; earlier jobs exposed `runner_id=0` / blank runner.
- `reproducibility_manifest.py`: initial `797a8578...`; workflow integration `418c42b7...`; OHLCV-value hashing fix `49ac8088...`; manifest-v2 research-contract hash `dcf669a5...`.
- `reproducibility_selftest.py`: `0a0f9489...`; research-contract inclusion `e1227f0e...`; workflow integration `f60df68d...`.
- New causal-safety self-check `causality_selftest.py`: commit `9543975185767c4985e6afe1cee52a350cc00bc5`.
- Research contract now includes the causal self-check: `79fb0af83a04c53281ee77c0b5bb36c7122f45e7`.
- Test workflow runs it before heavy research: `de498ea0e4a808ec56f01067606285034a2e264b`.
- Causal self-check uses fabricated 2024/2025 data only and verifies: historical feature prefix invariance under future-row append, exact next-session-open -> 5BD target semantics, Short monthly training purge, and Swing semiannual training purge. It does not tune models or inspect 2026 performance.

## Stable★6 historical reference
2026 Mar-Aug 5BD: n=55, mean about +6.59%, median +1.50%, win 56.4%, +10% 18.2%, -10% 10.9%.
10BD mean about +7.64%, win about 57.4%.

## V3 Short 5BD reconstruction
Historical non-reproducible old reference: 2026 Mar-Aug n=29, mean +5.42%, median +2.06%, win 65.5%, +10% 13.8%, -10% 6.9%. Exact old parameters were never committed; do not claim reproduction.

`v3_short_reconstruction.py` implements the same 45 `run.py` features, monthly causal 180-tree XGBoost, prediction-day percentile normalization, Core `r_top10 - 2*r_loss10`, one-selection-day same-symbol cooldown, next-open -> 5BD, recent-outcome Meta inactive/rejected, Attack none/unaccepted, and JSON/CSV-only outputs.

Latest fully successful snapshot remains run `34519284035` on rolling-3y input:
- Core 2025H1: n=119, mean +0.46%, median +0.45%, win 58.8%, +10% 4.2%, -10% 3.4%.
- Core 2025H2: n=124, mean +0.35%, median +0.28%, win 51.6%, +10% 1.6%, -10% 1.6%.
- Core 2026 Mar-Aug contaminated: n=124, mean -0.56%, median -0.42%, win 44.4%, +10% 0.8%, -10% 0.8%.
- Defensive `med_ret5 >= -1%` supporting lane 2026 Mar-Aug: n=97, mean -0.11%, median 0%, win 48.5%, +10% 1.0%, -10% 0%.

Attack status:
- Whole-universe +10/+20-style heads: rejected after pre-2026 selection failed to survive fixed 2026.
- Distinct event-family experiment: 10/10 candidates failed the pre-2026 robustness gate; 2026 was not opened for them.
- Current Short Attack: NONE / unaccepted.

## V3 Swing 10BD
Frozen architecture remains `v3_swing_v2.py`: MomCross -> causal semiannual quality model -> training empirical-CDF normalization -> Breadth Meta -> `score_R >= 0.20`.

Latest fully successful rolling-3y snapshot at unchanged 0.20:
- 2025H1: n=37, mean +6.36%, median -0.75%, win 45.9%, +10% 16.2%, -10% 5.4%.
- 2025H2: n=23, mean +5.89%, median -0.84%, win 43.5%, +10% 13.0%, -10% 0%.
- 2026 Mar-Aug contaminated: n=31, mean +1.00%, median +1.26%, win 54.8%, +10% 9.7%, -10% 3.2%.
- Rolling-3y threshold sweep currently favors 0.10, but DO NOT retune from frozen 0.20; history-window drift was discovered afterward.
- Swing A remains none/unaccepted.

## Current architecture decision
- Short Core: reproducible code, weak latest snapshot; durable numeric baseline pending fixed-start Actions success.
- Short defensive market gate: supporting lane only.
- Short recent-outcome Meta: rejected.
- Short Attack: none.
- Swing S: frozen architecture/threshold 0.20; durable numeric baseline pending fixed-start Actions success.
- Swing A: none.
- Production migration: blocked pending explicit user Go.

## Completed in latest run
- Re-read `HANDOFF.md`, `NEXT_ACTIONS.md`, `V3_STATUS.md`, and inspected Draft PR #13.
- PR #13 remained open, Draft, unmerged, and on `test/tvfree-screener-v1`.
- Re-checked Actions: run `34539341326` still failed before executable steps; runner allocation remains the blocker.
- Added `causality_selftest.py` (`9543975185767c4985e6afe1cee52a350cc00bc5`).
- Added it to manifest-v2 research-contract hashing (`79fb0af83a04c53281ee77c0b5bb36c7122f45e7`).
- Added it before heavy research in the test-only workflow (`de498ea0e4a808ec56f01067606285034a2e264b`).
- Accepted finding: the explicit causal contracts represented by current Short/Swing code are now guarded by synthetic tests; no model-performance claim is made until Actions actually executes them and the fixed-start pipeline.
- Rejected action: no threshold/model retuning while runner infrastructure is unavailable and 2026 is contaminated.
- No production files/workflows, Discord/Spreadsheet writes, Stable★6/Sniper/Mega, TradingView, watchlist tooling, or `main` were touched.

## Next concrete task
1. Re-check hosted-runner availability and inspect the newest PR-triggered workflow job.
2. Once a job reaches checkout, require both `reproducibility_selftest.py` and `causality_selftest.py` to pass before accepting the run.
3. Confirm `Yahoo history mode: fixed start 2022-01-01 -> current`, then require all Short/Swing/comparison/manifest steps to succeed.
4. Freeze the resulting fixed-start Short/Swing numeric snapshot plus manifest-v2 contract/coverage/OHLCV/output hashes without retuning from 2026.
5. On a later market-session append, require matching `research_contract_sha256`, then compare historical hashes through `2026-08-31`.
6. Record fixed-start runtime/artifact size and optimize plumbing only if necessary.
