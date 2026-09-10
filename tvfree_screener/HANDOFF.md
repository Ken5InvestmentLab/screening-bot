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
- Rolling `period=3y` was rejected as a durable baseline because old training rows disappear as wall-clock time advances.
- Test-only fixed-start acquisition uses `2022-01-01 -> current` via `bootstrap.py`; normal `run.py` period behavior is unchanged outside this test bootstrap.
- Fixed-start verification is still blocked by GitHub Actions runner allocation. Run `34541092751` failed before executable steps. After the latest test-only changes, run `34541347039` briefly appeared queued but then also completed failure with no executable steps/job logs.
- Earlier jobs showed `runner_id=0`, blank runner name, and empty/no steps. The latest check-run exposes one annotation, but the connected API cannot retrieve the annotation body.
- GitHub public/Japan status reported Actions operational during this run, so repeated no-runner failures are more consistent with repo/account/quota-specific infrastructure than a public Actions outage.

## Safety checks
- `reproducibility_manifest.py` tracks historical coverage/OHLCV/output SHA-256 fingerprints.
- `reproducibility_selftest.py` checks historical-revision detection and post-cutoff append invariance.
- `causality_selftest.py` uses fabricated 2024/2025 data only and checks feature prefix invariance, next-session-open -> 5BD semantics, Short monthly purge, and Swing semiannual purge.
- Both self-checks are placed before the heavy research path in the test workflow.

## Universe-drift guard
- Commit `9e1bb3473ebbb2ccb3f768e7bf144b9969927f47` makes the test bootstrap persist the exact current JPX universe used by a run as `tvfree_screener/out/jpx_universe_snapshot.csv`.
- Commit `d50cb1eca97734acb4f4d5ed2f1ab97acd6c267b` upgrades the reproducibility manifest to v3 and fingerprints that universe snapshot.
- Accepted finding: fixed-start prices alone do NOT guarantee historical reproducibility because the backtest currently starts from the run-date JPX listed universe. Future listings/delistings can change historical membership.
- Important limitation: the new snapshot/hash detects this drift; it does NOT reconstruct point-in-time historical constituents and therefore does not remove survivorship/membership bias by itself.
- Append-only comparisons are valid only when both `research_contract_sha256` and universe SHA-256 match.

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
- Re-read `HANDOFF.md`, `NEXT_ACTIONS.md`, `V3_STATUS.md`, inspected Draft PR #13, and confirmed it remained open/Draft/unmerged on `test/tvfree-screener-v1` before changes.
- Re-checked Actions: run `34541092751` failed before executable steps. New run `34541347039` also ended in the same pre-step failure mode.
- Checked GitHub public/Japan status; Actions was operational, reducing the likelihood of a global outage.
- Identified current-listed-universe drift as a separate reproducibility risk.
- Added exact JPX universe snapshot artifact at commit `9e1bb3473ebbb2ccb3f768e7bf144b9969927f47`.
- Added universe SHA-256 and manifest-v3 interpretation rules at commit `d50cb1eca97734acb4f4d5ed2f1ab97acd6c267b`.
- Updated this handoff after the observed workflow result.
- Accepted: detect and block interpretation when run-date universe changes.
- Rejected: treating a fixed Yahoo start date alone as sufficient proof of historical reproducibility.
- No thresholds, features, model parameters, production workflows, Discord/Spreadsheet writes, Stable★6/Sniper/Mega, TradingView tooling, watchlist tooling, or `main` were changed.

## Blockers
1. GitHub hosted runner is not being assigned, preventing execution of the fixed-start pipeline and self-checks in Actions.
2. Point-in-time historical JPX membership is not yet reconstructed; current research backtests use the run-date listed universe, so survivorship/membership bias remains a documented research limitation.

## Next concrete task
1. Re-check runner allocation and inspect any newly exposed annotation/account/quota signal without changing model semantics.
2. If runner starts, require reproducibility and causality self-check PASS first, then fixed `2022-01-01 -> current`, Short/Swing/comparison/manifest-v3 success.
3. Freeze Short/Swing numeric baselines plus research-contract, universe, coverage, OHLCV, and output hashes without tuning from 2026.
4. While Actions remains blocked, research a free, causally defensible way to reconstruct point-in-time TSE common-stock membership for 2022+; reject any method that silently uses only today's survivors.
5. Production integration remains blocked until explicit user Go.
