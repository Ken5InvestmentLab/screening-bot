# TradingView-Free Screener — Autonomous Handoff

TEST ONLY. This file is the canonical handoff for future ChatGPT scheduled runs and new chats.

## Safety guardrails

- Repository: `Ken5InvestmentLab/screening-bot`
- Working branch: `test/tvfree-screener-v1`
- Draft PR: #13
- NEVER merge to `main` without explicit user Go approval.
- NEVER modify production Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater, or production workflows without explicit user Go approval.
- All research remains isolated in the test branch / test workflow / artifacts.
- Evaluate realistic performance as next-session-open -> horizon close.
- Training rows must have their target outcome fully known before prediction period.
- 2026 has already been inspected and is not a pristine holdout. Never tune thresholds specifically to improve 2026.

## Project goal

Replace TradingView watchlist alerts/Pine dependency with a free daily-OHLCV system covering TSE domestic common stocks, without creating a visibly inferior replacement for the current Stable★6-centered workflow.

Target production flow after explicit user approval only:

JPX common-stock universe -> Yahoo daily OHLCV -> independent Short/Swing selection -> technical scoring -> fundamental analysis -> Discord -> HTML generation.

## Infrastructure

- Full TSE domestic common-stock universe: about 3,700 symbols.
- Yahoo daily history works in GitHub Actions in batches.
- About 3 years of daily data has been downloaded successfully.
- XGBoost / scikit-learn are available in the isolated test workflow.
- Test workflow artifacts are used for reports; production writes are disabled.
- Draft PR #13 is still open, draft, unmerged, and test-only.
- Latest inspected test workflow run on head `de9f7dfa...` completed successfully.

## Stable★6 reference

2026 Mar-Aug confirmed historical reference:

5BD: n=55, mean about +6.59%, median about +1.50%, win about 56.4%, +10% about 18.2%, -10% about 10.9%.

10BD: mean about +7.64%, win about 57.4%.

Stable★6 mean is boosted by a small number of very large winners. Judge replacements on mean, median, win rate, large-winner capture, large-loss rate, and month-to-month stability.

## V3 Short (5BD) — reconstruction status

Historical previous-session reference, NOT exactly reproducible because precise old parameters were never committed:

2026 Mar-Aug, one-business-day same-symbol cooldown: n=29, mean about +5.42%, median about +2.06%, win about 65.5%, +10% about 13.8%, -10% about 6.9%.

Known old architecture: monthly relative-ranking Core -> confirmed-outcome Meta -> Attack when Meta ON -> Deep Reversal when Meta OFF -> one-business-day same-symbol cooldown.

### Exact-feature reconstruction performed 2026-09-11

The reconstruction was rebuilt using the same 45 features and XGBoost shape as `run.py` (180 trees, depth 3, LR .04, min_child_weight 25, lambda 5, alpha .2). Candidate data covered roughly 681k eligible rows / 2,059 symbols through 2026-09-10. Monthly causal prediction files were generated and checkpointed.

Core was selected using 2025 only. Best robust 2025 rule was relative Top10 head percentile minus 2.0 x loss-risk percentile.

2025 Core development evidence:
- 2025H1 mean about +0.59%, median +0.58%, win 58.0%, -10% 2.5%.
- 2025H2 mean about +0.94%, median +0.57%, win 58.9%, -10% 0%.

A 2025-only confirmed-outcome Meta was then frozen as recent 30 Core outcomes, win >=55%, loss10 <=10%.

Frozen Meta results:
- 2025H1: n=48, mean +1.05%, median +0.79%, win 58.3%, -10% 4.2%.
- 2025H2: n=76, mean +1.14%, median +0.74%, win 63.2%, -10% 0%.
- 2026 Mar-Aug contaminated fixed check: n=26, mean -1.27%, median -0.46%, win 42.3%, +5% 0%, -10% 3.8%.

Conclusion: the prior defensive Short result (+1.38% in 2026) was not reproducible under the exact `run.py` feature/model reconstruction. Core itself weakened in 2026 and the recent-outcome Meta worsened it further. Do not tune the Meta to 2026 to recover the old number.

A simple contemporaneous market gate chosen from 2025 only (`med_ret5 >= -1%`) improved the frozen 2026 Core side to about n=97 / mean +0.17% / -10% about 1.0%, but median remained negative (~-0.39%). Treat this only as a defensive observation, not an accepted primary Short engine.

### Short Attack research — rejected candidate

Dedicated monthly causal +10% and +20% heads were trained with the same exact-feature model. Raw probabilities were converted to daily cross-sectional percentiles.

2025 frontier search included +10%, +20%, relative Top10 and explicit loss-risk combinations. Best eligible pre-2026 candidate was:
- Attack score = `r_hit20 - r_loss10`
- contemporaneous market gate `med_ret5 >= -1%`
- require `r_hit10 >= 0.85`
- daily best candidate with one-selection-day same-symbol cooldown.

Pre-2026 evidence:
- 2025H1: n=102, mean +1.93%, median 0.0%, win 47.1%, +10% 8.8%, +20% 2.9%, -10% 0%.
- 2025H2: n=106, mean +2.10%, median 0.0%, win 44.3%, +10% 11.3%, +20% 3.8%, -10% 3.8%.

Frozen 2026 Mar-Aug check:
- n=97
- mean +0.06%
- median -0.97%
- win 42.3%
- +10% 9.3%
- +20% 3.1%
- -10% 7.2%
- max about +34.0%, min about -18.2%.

Monthly 2026 behavior was unstable, including May mean about -2.89%. Conclusion: REJECT this Attack candidate. It was selected on 2025, not tuned on 2026, and did not retain sufficient quality on the fixed side.

Do not keep tuning thresholds around these same heads to the already-seen 2026 period. The next Short Attack hypothesis should be a genuinely different event family, not another small weight/gate change around the same whole-universe percentile heads.

## V3 Swing (10BD)

Current reproducible candidate remains `v3_swing_v2.py`.

Structure: MomCross event -> causal semiannual event-quality model -> training-distribution CDF score -> market Breadth Meta -> quality gate.

Frozen Swing S candidate 2026 Mar-Aug contaminated check: about n=30, mean +1.42%, median +1.63%, win 60%, -10% 3.3%, max about +17.5%.

Swing A remains unaccepted. Prior Surge/Breakout/+20%/Deep-Reversal variants did not remain stable across pre-2026 periods.

## Rejected approaches

Do not repeat without a materially new hypothesis:
- Pine / 天底極致 imitation V2.
- Initial absolute-return XGBoost score dominated by outliers.
- Multi-head models with absolute probability thresholds after retraining.
- XGBRanker direct daily ranking.
- Fixed Breakout-only logic.
- Static Attack rules based on surge/volume/RSI sweet spots.
- Long same-symbol cooldowns such as 20 days.
- Fixed 10BD relative-ranking model.
- Monthly-retrained Swing heads with absolute probability thresholds.
- Rank regression Swing.
- Static trend factor / simple breadth switch as standalone Swing solutions.
- Simple Low-Vol Core recent-performance Meta for Swing.
- Deep Reversal Swing fixed-rule variants tested so far.
- Exact-feature Short recent-outcome Meta as reconstructed above.
- Short whole-universe +20% percentile Attack (`r_hit20-r_loss10`, `r_hit10>=.85`, `med_ret5>=-1%`).

## Working principles

- Prefer daily/cross-sectional percentiles or training-distribution CDFs over absolute probabilities when models retrain.
- Evaluate next-open -> horizon close.
- Preserve genuine +100% to +400% winners; do not blanket-remove them as outliers.
- Reject methods with negative median / unstable months even if mean is inflated by one huge winner.
- Record failed experiments as first-class results.
- Update this file after each material research change.
