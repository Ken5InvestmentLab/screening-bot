# TradingView-Free Screener — Autonomous Handoff

TEST ONLY. Canonical handoff for scheduled runs and new chats.

## Safety guardrails
- Repository: `Ken5InvestmentLab/screening-bot`
- Working branch: `test/tvfree-screener-v1`
- Draft PR: #13
- NEVER merge to `main` without explicit user Go approval.
- NEVER modify production Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater, or production workflows without explicit user Go approval.
- Evaluate next-session-open -> horizon close.
- Training/selection must be causal.
- 2026 is contaminated and must not be used for threshold/model tuning.

## Goal
Replace TradingView/Pine watchlist dependency with a free Yahoo-daily-OHLCV TSE common-stock system without creating a visibly inferior Stable★6 replacement.

## Infrastructure / reproducibility
- TSE domestic common-stock universe: about 3,700 symbols.
- Last fully successful research pipeline remains Actions run `34519284035` on rolling `period=3y`; runtime about 23m15s, artifact about 33.55 MB.
- Rolling `period=3y` is not a durable baseline because old training rows disappear as wall-clock time advances.
- Test-only fixed-start acquisition uses `2022-01-01 -> current` via `bootstrap.py`; normal `run.py` behavior is unchanged outside this bootstrap.
- Fixed-start verification remains blocked by GitHub Actions hosted-runner allocation. Recent PR-triggered jobs, including `34541399127`, `34541906076`, and `34542011745`, fail before executable steps; job metadata exposes no usable steps/logs.

## Safety checks
- `reproducibility_manifest.py` tracks research contract, current universe, historical coverage/OHLCV/output SHA-256 fingerprints.
- `reproducibility_selftest.py` checks historical-revision detection and post-cutoff append invariance.
- `causality_selftest.py` uses fabricated 2024/2025 data only and checks feature prefix invariance, next-session-open -> 5BD semantics, Short monthly purge, and Swing semiannual purge.
- `point_in_time_universe_selftest.py` now checks reverse membership reconstruction, including a code-reuse episode and fail-closed same-day collision detection.
- These are test-only and do not write to production.

## Universe validity
- Commit `9e1bb3473ebbb2ccb3f768e7bf144b9969927f47` persists the exact run-date JPX universe as `jpx_universe_snapshot.csv`.
- Commit `d50cb1eca97734acb4f4d5ed2f1ab97acd6c267b` added universe hashing to manifest v3.
- Accepted finding: fixed-start Yahoo prices alone are insufficient because the old research path applies today's listed universe to all historical dates.
- Official JPX provides year-specific stock new-listing and delisting archives for 2022 onward, so point-in-time TSE membership is reconstructable without silently using only today's survivors.
- Commit `d2e66370d237edd94880fd9f8a6e740ed9332d5a` adds `point_in_time_universe.py`, a TEST-ONLY prototype that anchors on the current JPX domestic-common snapshot and reverses official JPX listing/delisting events back to a requested historical date.
- Commit `bea62cb1d1847409e84d1e63b2c08038db435765` adds synthetic membership reconstruction tests.
- Commit `7632a4cd6aa3c77153413251a6d4cdfdb6973c5b` runs the point-in-time synthetic test before heavy research once a runner is available.
- Commit `b88b04ebdc7e15c27eb7c6ae0ca34b3ed27a83a8` includes the point-in-time code/tests in the research-contract fingerprint.
- The prototype is intentionally fail-closed: unknown market classification or same-code same-day listing/delisting collisions block acceptance instead of being guessed.
- IMPORTANT: the prototype is not yet wired into Short/Swing backtest filtering. First validate the live JPX parser and measure whether Yahoo still supplies OHLCV for delisted symbols.

## Stable★6 historical reference
2026 Mar-Aug 5BD historical reference: n=55, mean about +6.59%, median +1.50%, win 56.4%, +10% 18.2%, -10% 10.9%. 10BD mean about +7.64%, win about 57.4%.

## V3 Short 5BD reconstruction
- Reproducible runner: same 45 `run.py` features, monthly causal 180-tree XGBoost, prediction-day percentile normalization, Core `r_top10 - 2*r_loss10`, one-selection-day same-symbol cooldown, next-open -> 5BD.
- Recent-outcome Meta: rejected/inactive.
- Attack: none/unaccepted.
- Last successful rolling-3y snapshot: 2025H1 n=119 mean +0.46%; 2025H2 n=124 mean +0.35%; contaminated 2026 Mar-Aug n=124 mean -0.56%.
- Durable fixed-start numeric baseline is still pending a started Actions job.

## V3 Swing 10BD
- Frozen architecture: MomCross -> causal semiannual quality model -> training empirical-CDF normalization -> Breadth Meta -> `score_R >= 0.20`.
- Do not retune from contaminated 2026 or from the rolling-window threshold sweep.
- Last successful rolling-3y snapshot: 2025H1 n=37 mean +6.36%; 2025H2 n=23 mean +5.89%; contaminated 2026 Mar-Aug n=31 mean +1.00%.
- Swing A: none/unaccepted.
- Durable fixed-start numeric baseline is still pending a started Actions job.

## Completed in latest run
- Re-read `HANDOFF.md`, `NEXT_ACTIONS.md`, and `V3_STATUS.md`; inspected Draft PR #13 and confirmed it remains open, Draft, unmerged, head `test/tvfree-screener-v1`.
- Re-checked Actions. Runs `34541399127`, `34541906076`, and `34542011745` failed before executable steps; no Python/model failure is demonstrated.
- Researched official JPX archives. Confirmed year-specific stock new-listing and delisting pages exist for 2022, 2023, 2024, 2025, plus current 2026 pages.
- Implemented TEST-ONLY point-in-time membership reconstruction prototype at `d2e66370...`.
- Added synthetic self-check at `bea62cb1...`, workflow safety-check integration at `7632a4cd...`, and research-contract coverage at `b88b04eb...`.
- Accepted: reverse official JPX membership events is causally defensible in principle and avoids silently applying today's survivor set to every historical date.
- Not yet accepted for model evaluation: live JPX parsing and delisted-symbol Yahoo coverage have not been validated on a running hosted runner.
- No thresholds, features, model parameters, production workflows, Discord/Spreadsheet writes, Stable★6/Sniper/Mega, TradingView/watchlist tooling, or `main` were changed.

## Blockers
1. GitHub hosted runner is not being assigned, preventing live fixed-start and parser validation.
2. Yahoo historical coverage for JPX-delisted codes is unknown; membership reconstruction alone cannot recover prices Yahoo no longer serves.

## Next concrete task
1. Re-check runner allocation. If it starts, require all three synthetic safety checks to pass first.
2. Run `point_in_time_universe.py` against the live JPX current snapshot and require zero unknown-market rows and zero same-day code collisions before using it for backtests.
3. Measure Yahoo OHLCV availability for reconstructed delisted members. Missing historical prices must be reported, not silently dropped.
4. Only if 2-3 pass, add point-in-time membership filtering to a separate test comparison and compare pre-2026 results without tuning thresholds.
5. Then run fixed `2022-01-01 -> current` Short/Swing/comparison/manifest and freeze numeric baselines/hashes.
6. Production integration remains blocked until explicit user Go.
