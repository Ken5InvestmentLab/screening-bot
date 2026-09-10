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
- Fixed-start verification is currently blocked by GitHub Actions runner startup failure, not a model/test exception. Runs `34525453744`, `34530881770`, `34530963918`, `34531004386`, `34536163042`, `34536183995`, and `34536324032` all failed before any workflow step. Recent jobs expose `steps=[]`, `runner_id=0`, and blank runner name, confirming no hosted runner was assigned.
- Because jobs are not starting, do not treat these failures as evidence against fixed-start code or the models. Do not weaken model semantics to work around this blocker.
- Commit `797a8578...` added `reproducibility_manifest.py`; commit `418c42b7...` added it to the test workflow.
- Commit `49ac8088...` fixed an important manifest gap: cache history now records both date/symbol coverage SHA-256 and full historical OHLCV SHA-256 through frozen cutoff `2026-08-31`.
- Commit `dcf669a502763a934a0f5aa6c226ab0a2d4bd4de` upgraded the manifest to v2 and added a research-contract fingerprint. It hashes the relevant test research code/workflow/requirements plus explicit non-secret `TVFREE_*` inputs. This prevents a code/config change from being mistaken for append-only data drift.

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
- Re-read HANDOFF/NEXT_ACTIONS/V3_STATUS and inspected Draft PR #13; it remains Draft, open, unmerged, head branch `test/tvfree-screener-v1`.
- Re-checked fixed-start Actions. New run `34536324032` at research-contract commit `dcf669a...` again failed before any step with `steps=[]`, `runner_id=0`, blank runner name. Runner allocation remains the blocker.
- Highest-priority safe task completed: upgraded `reproducibility_manifest.py` to manifest v2 at commit `dcf669a502763a934a0f5aa6c226ab0a2d4bd4de`.
- Manifest v2 now fingerprints relevant research code, test workflow, requirements, and explicit non-secret `TVFREE_*` inputs as `research_contract_sha256` in addition to coverage/OHLCV/output hashes.
- Interpretation rule is now explicit: compare append-only historical hashes only when the research-contract hash matches. A contract mismatch means semantics/config changed; an OHLCV-only mismatch can indicate Yahoo history revision.
- No production files, workflows, Discord/Spreadsheet writes, Stable★6/Sniper/Mega, TradingView, or main branch were touched.

## Next concrete task
1. Re-check Actions runner availability. Do not change model semantics while `runner_id=0 / steps=[]` persists.
2. Once a fixed-start job actually starts, confirm `Yahoo history mode: fixed start 2022-01-01 -> current` and all Short/Swing/comparison/manifest steps succeed.
3. Freeze the resulting fixed-start Short/Swing numeric snapshot plus manifest-v2 contract/coverage/OHLCV/output hashes without retuning from 2026.
4. On a later market-session append, require matching `research_contract_sha256` before interpreting historical hash stability. Then compare cutoff `2026-08-31` coverage, OHLCV, Short Core, Short defensive, and Swing S hashes.
5. Record fixed-start runtime/artifact size and optimize plumbing only if needed.
