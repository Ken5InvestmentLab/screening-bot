# TradingView-Free Screener — Autonomous Handoff

TEST ONLY. Canonical handoff for future scheduled runs and new chats.

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
- Test-only GitHub Actions / artifacts function successfully.
- Run `34519284035` completed successfully on head `e7dc6476...`; every research/comparison step passed.
- That run took about 23m15s end-to-end; its artifact was about 33.55 MB, comfortably below the current 90-minute job cap.
- Critical reproducibility issue found: the workflow used Yahoo `period=3y`, so the oldest history disappeared as calendar time advanced. Historical training samples therefore drifted between runs even with unchanged code/causal semantics.
- Fixed-start acquisition was added in `bootstrap.py` at commit `063a73b3...` and enabled in the test workflow at commit `458be814...`, defaulting to `2022-01-01 -> current`. This is plumbing only; model architecture/thresholds were not changed.
- Until the fixed-start Actions rerun succeeds, treat run-31 outputs below as the latest reproducible *snapshot*, not the final stable baseline.

## Stable★6 historical reference
2026 Mar-Aug 5BD: n=55, mean about +6.59%, median +1.50%, win 56.4%, +10% 18.2%, -10% 10.9%.
10BD mean about +7.64%, win about 57.4%.

## V3 Short 5BD reconstruction
Historical non-reproducible old reference: 2026 Mar-Aug n=29, mean +5.42%, median +2.06%, win 65.5%, +10% 13.8%, -10% 6.9%. Exact old parameters were never committed; do not claim reproduction.

`v3_short_reconstruction.py` implements same 45 `run.py` features, monthly causal 180-tree XGBoost, prediction-day percentile normalization, Core `r_top10 - 2*r_loss10`, one-selection-day same-symbol cooldown, next-open -> 5BD, recent-outcome Meta inactive/rejected, Attack none/unaccepted, and JSON/CSV-only outputs.

### Latest successful Actions snapshot (run 34519284035; rolling-3y input)
Core:
- 2025H1: n=119, mean +0.46%, median +0.45%, win 58.8%, +10% 4.2%, -10% 3.4%.
- 2025H2: n=124, mean +0.35%, median +0.28%, win 51.6%, +10% 1.6%, -10% 1.6%.
- 2026 Mar-Aug contaminated: n=124, mean -0.56%, median -0.42%, win 44.4%, +10% 0.8%, -10% 0.8%.

Defensive `med_ret5 >= -1%` supporting lane:
- 2025H1: n=102, mean +0.77%, median +0.39%, win 58.8%, -10% 0%.
- 2025H2: n=106, mean +0.09%, median +0.06%, win 50.0%, -10% 1.9%.
- 2026 Mar-Aug contaminated: n=97, mean -0.11%, median 0.00%, win 48.5%, +10% 1.0%, -10% 0%.

These supersede earlier non-runner research notes for this rolling-3y snapshot. Do not tune them using 2026. Recheck after fixed-start history is active.

### Attack status
- Whole-universe +10/+20-style heads: rejected after pre-2026 selection failed to survive fixed 2026.
- Distinct event-family experiment (compression-expansion, capitulation-reversal, gap-volume, low-vol ignition, bounded breakout; 10 variants): 0/10 passed the pre-2026 robustness gate; 2026 was not opened for those candidates.
- Current Short Attack: **NONE / unaccepted**.

## V3 Swing 10BD
Frozen architecture remains `v3_swing_v2.py`: MomCross -> causal semiannual quality model -> training empirical-CDF normalization -> Breadth Meta -> `score_R >= 0.20`.

### Latest successful Actions snapshot (run 34519284035; rolling-3y input)
At the still-frozen 0.20 threshold:
- 2025H1: n=37, mean +6.36%, median -0.75%, win 45.9%, +10% 16.2%, -10% 5.4%.
- 2025H2: n=23, mean +5.89%, median -0.84%, win 43.5%, +10% 13.0%, -10% 0%.
- 2026 Mar-Aug contaminated: n=31, mean +1.00%, median +1.26%, win 54.8%, +10% 9.7%, -10% 3.2%.

Important: the current rolling-3y threshold sweep reports 0.10 as its best eligible pre-2026 threshold, so `locked_threshold_matches_best_pre2026=false`. **Do not retune 0.20 to 0.10.** The input-history window drift was identified after this run and can change pre-2026 training samples. First rerun with fixed-start history and reconcile. Prior handoff figures (~+2.68%/+1.95%/+1.42%) also came from different rolling-history snapshots and are no longer treated as immutable truth.

Swing A remains none/unaccepted.

## Unified comparison
`unified_comparison.py` succeeded in run 34519284035. It correctly labels Stable★6/old Short figures as historical/non-reproducible, marks Short and Swing runner rows reproducible for that input snapshot, leaves unavailable metrics blank, and keeps Short Attack/Swing A as none.

## Current architecture decision
- Short Core: reproducible code, weak latest snapshot; awaiting stable fixed-start rerun.
- Short defensive market gate: supporting lane only.
- Short recent-outcome Meta: rejected.
- Short Attack: none.
- Swing S: frozen architecture/threshold 0.20; awaiting fixed-start rerun before freezing numeric baseline.
- Swing A: none.

## Next concrete task
1. Inspect the Actions run triggered by fixed-start commits `063a73b3...` / `458be814...`.
2. Verify the cache starts at 2022-01-01 (subject to each symbol's listing date) and that all Short/Swing/comparison steps succeed.
3. Freeze the resulting fixed-start snapshot; on a subsequent run, verify old historical rows remain unchanged when only new market days are appended.
4. If fixed-start runtime remains practical, keep this acquisition contract; optimize batching/jobs only if needed, without changing model semantics.
5. Production migration remains blocked until explicit user Go.
