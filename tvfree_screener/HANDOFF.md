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
- Fixed-start verification remains blocked by GitHub Actions hosted-runner startup failure, not a model/test exception. Recent jobs continue to fail before any workflow step with no runner assigned.
- Commit `797a8578...` added `reproducibility_manifest.py`; commit `418c42b7...` added it to the test workflow.
- Commit `49ac8088...` added full historical OHLCV hashing through frozen cutoff `2026-08-31` in addition to date/symbol coverage hashing.
- Commit `dcf669a502763a934a0f5aa6c226ab0a2d4bd4de` upgraded the manifest to v2 with a `research_contract_sha256` over relevant test research code/workflow/requirements and explicit non-secret `TVFREE_*` inputs.
- Commit `0a0f94894d79ec600c7cae1cc87b55d499ccc685` added `reproducibility_selftest.py`, a synthetic no-network self-check for historical revision detection and append-only invariants.
- Commit `e1227f0e52cd8d736857227d758187120c61dc79` included that self-check in the research-contract fingerprint.
- Commit `f60df68db3172e3417eb32861cef0d342cc6b595` runs the self-check before the heavy research pipeline once a hosted runner is available.
- The synthetic self-check was also executed independently in-session and passed: value-only historical OHLCV revision changes only the OHLCV hash, post-cutoff append leaves historical hashes unchanged, and historical output revision changes the output hash.

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
- Re-read `HANDOFF.md`, `NEXT_ACTIONS.md`, and `V3_STATUS.md` from `test/tvfree-screener-v1` and inspected Draft PR #13.
- PR #13 remained open, Draft, unmerged, and isolated to `test/tvfree-screener-v1`; observed head before this run's changes was `049212fa6a1afb9a1dfd2fec7aefdd6f05646f4b`.
- Latest observed workflow run `34536429235` again failed before executable steps; no evidence of a Python/model failure.
- Added and independently executed the synthetic reproducibility self-check. PASS.
- No thresholds, features, model parameters, 2026 tuning, production workflows, Discord/Spreadsheet writes, Stable★6/Sniper/Mega, TradingView, or `main` were changed.

## Next concrete task
1. Re-check hosted-runner availability and inspect the newest PR-triggered workflow job.
2. Once a job reaches checkout, require the synthetic reproducibility self-check to pass first.
3. Confirm `Yahoo history mode: fixed start 2022-01-01 -> current`, then require all Short/Swing/comparison/manifest steps to succeed.
4. Freeze the resulting fixed-start Short/Swing numeric snapshot plus manifest-v2 contract/coverage/OHLCV/output hashes without retuning from 2026.
5. On a later market-session append, require matching `research_contract_sha256`, then compare historical hashes through `2026-08-31`.
6. Record fixed-start runtime/artifact size and optimize plumbing only if necessary.
