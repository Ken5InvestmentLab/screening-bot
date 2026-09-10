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

## Infrastructure
- TSE domestic common-stock universe: about 3,700 symbols.
- Yahoo 3y daily cache works in GitHub Actions.
- Test-only workflow and artifacts are functioning.
- XGBoost/scikit-learn available.
- Latest previously inspected test run on head `d3712601...` succeeded.
- Distinct Short event-family experiment added at commit `e8da88d8...`.
- Workflow integration added at commit `fc441e61...`.

## Stable★6 historical reference
2026 Mar-Aug 5BD: n=55, mean about +6.59%, median +1.50%, win 56.4%, +10% 18.2%, -10% 10.9%.
10BD mean about +7.64%, win about 57.4%.

## V3 Short 5BD reconstruction
Historical non-reproducible old reference: 2026 Mar-Aug n=29, mean +5.42%, median +2.06%, win 65.5%, +10% 13.8%, -10% 6.9%. Exact old parameters were never committed; do not claim reproduction.

Exact-feature reconstruction used the same 45 `run.py` features and XGBoost shape (180 trees, depth 3, LR .04, min_child_weight 25, lambda 5, alpha .2). About 681k eligible rows / 2,059 symbols through 2026-09-10 were used.

2025-only Core: `r_top10 - 2.0*r_loss10`.
- 2025H1 mean +0.59%, median +0.58%, win 58.0%, -10% 2.5%.
- 2025H2 mean +0.94%, median +0.57%, win 58.9%, -10% 0%.

2025-only recent-outcome Meta: recent 30 Core outcomes, win >=55%, loss10 <=10%.
- 2025H1 n=48, mean +1.05%.
- 2025H2 n=76, mean +1.14%.
- Frozen 2026 Mar-Aug n=26, mean -1.27%, median -0.46%, win 42.3%.
Rejected; do not retune to 2026.

A 2025-selected contemporaneous market gate `med_ret5 >= -1%` improved frozen 2026 Core to about n=97 / mean +0.17% / -10% 1.0%, but median remained negative (~-0.39%). At most a defensive supporting lane.

### Whole-universe Attack heads — rejected
2025-selected candidate `r_hit20-r_loss10`, `r_hit10>=.85`, `med_ret5>=-1%`:
- 2025H1 n=102 mean +1.93%.
- 2025H2 n=106 mean +2.10%.
- Frozen 2026 Mar-Aug n=97 mean +0.06%, median -0.97%, win 42.3%, -10% 7.2%.
Rejected. Do not tune the same heads around 2026.

### Distinct event-family Attack search — rejected before opening 2026
A separate `short_event_experiment.py` tested 5 materially different event families x 2 fixed variants, selected only from 2024-2025:
1. volatility compression -> expansion,
2. capitulation -> confirmed reversal,
3. gap + volume shock with controlled close,
4. low-volatility -> momentum ignition,
5. bounded-volatility breakout.

One-pick-per-day and one-selection-day same-symbol cooldown were preserved. Pre-2026 robustness required adequate samples in >=3 half-years, positive mean in >=3, nonnegative median in >=3, and no adequate half-year mean below -1%.

Result: all 10 variants failed the pre-2026 gate, so 2026 was deliberately not opened for candidate selection/evaluation. Representative findings:
- compression/expansion variants had negative mean/median in nearly every half-year and high -10% rates.
- capitulation/reversal was unstable and materially negative in 2025.
- gap/volume shock was strongly negative across all four half-years.
- low-vol ignition had lower loss rates but failed half-year mean/median stability.
- bounded breakout B was the closest defensive shape (2025H1 +0.54%, 2025H2 +0.46%) but 2024H1/H2 were both negative, so it failed robustness.

Current Short Attack decision: **NONE / unaccepted**. Do not force an Attack lane merely to emulate the old +5.42% reference.

## V3 Swing 10BD
Frozen current candidate: `v3_swing_v2.py`.
Architecture: MomCross -> causal semiannual quality model -> training CDF normalization -> Breadth Meta -> `score_R>=0.20`.
2026 Mar-Aug contaminated check: n~30, mean +1.42%, median +1.63%, win 60%, -10% 3.3%, max ~+17.5%.
Swing A remains unaccepted.

## Rejected families / methods
- Pine imitation V2.
- Absolute-return/outlier-dominated ML.
- Absolute probability thresholds across retrained models.
- XGBRanker direct ranking.
- Fixed Breakout-only and static surge/RSI sweet spots.
- Long cooldowns.
- Rejected Swing Attack/Deep Reversal variants.
- Exact Short recent-outcome Meta.
- Short whole-universe +10/+20 percentile Attack.
- Short compression-expansion, capitulation-reversal, gap-volume, lowvol-ignition, and bounded-breakout fixed event variants tested in `short_event_experiment.py`.

## Next concrete task
1. Treat `Short Attack = none` unless a materially new hypothesis appears.
2. Build one reproducible `v3_short_reconstruction.py` representing only the defensible Short lane(s), with no production writes.
3. Re-run/freeze Swing S in Actions.
4. Produce unified Short/Swing/Stable★6 historical comparison.
5. Then measure operational runtime/cost.
