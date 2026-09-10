# TradingView-Free Screener — Autonomous Handoff

TEST ONLY. This file is the canonical handoff for future ChatGPT scheduled runs and new chats.

## Safety guardrails

- Repository: `Ken5InvestmentLab/screening-bot`
- Working branch: `test/tvfree-screener-v1`
- Draft PR: #13
- NEVER merge to `main` without explicit user Go approval.
- NEVER modify production Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, or production workflows without explicit user Go approval.
- All research must remain isolated in the test branch / test workflow / artifacts.
- Use next-session-open entry for realistic performance evaluation.
- Do not use future information. Training rows must have their target outcome fully known before the prediction period.
- 2026 has already been inspected in prior research and is not a pristine holdout. Do not tune thresholds specifically to improve 2026.

## Project goal

Replace TradingView watchlist alerts and Pine dependency with a free daily-OHLCV system covering all TSE domestic common stocks, while retaining performance competitive enough with the current Stable★6 system to avoid a visibly inferior replacement.

Target production flow after explicit user approval only:

JPX common-stock universe -> Yahoo daily OHLCV -> independent Short/Swing selection -> technical scoring -> fundamental analysis -> Discord -> HTML generation.

## Current infrastructure state

- Full TSE domestic common-stock universe: about 3,700 symbols.
- Yahoo daily history download works in GitHub Actions in batches.
- About 3 years of daily data has been downloaded successfully.
- XGBoost / scikit-learn dependencies are installed in the isolated test workflow.
- Test workflow artifacts are used for CSV/JSON reports.
- Production writes are disabled.

## Stable★6 reference

2026 Mar-Aug confirmed reference:

5BD:
- n=55
- mean about +6.59%
- median about +1.50%
- win rate about 56.4%
- +10% rate about 18.2%
- -10% rate about 10.9%

10BD:
- mean about +7.64%
- win rate about 57.4%

Stable★6 mean is boosted by a small number of very large winners. A replacement should therefore be judged on mean, median, win rate, large-winner capture, large-loss rate, and stability, not mean alone.

## V3 Short (5BD)

Previous research reference, NOT exactly reproducible because the original precise parameters were not committed:

2026 Mar-Aug, one-business-day same-symbol cooldown:
- n=29
- mean about +5.42%
- median about +2.06%
- win rate about 65.5%
- +10% rate about 13.8%
- -10% rate about 6.9%

Known architecture:
1. Core: monthly-updated relative-ranking model.
2. Meta: only already-confirmed recent Core outcomes.
3. Attack: large-winner lane when Meta is ON.
4. Deep Reversal: fallback during Meta OFF.
5. One-business-day same-symbol cooldown.

Exact old thresholds were searched in GitHub, prior context, and Library and could not be recovered. Do not invent them. Current work is explicitly `Short V3 Reconstruction`.

Current reconstruction findings:
- Monthly causal Core using relative ranking and a loss penalty produced about 124 picks in 2026 Mar-Aug, mean about +1.16%, -10% rate about 0.81%.
- A 2025-selected Meta using confirmed recent Core results (recent 30, win rate >=52%, loss10 rate <=3%) produced a 2026 Mar-Aug contaminated fixed check of about 20 picks, mean +1.38%, median +1.02%, win rate 70%, -10% rate 0%.
- This defensive Core+Meta has no meaningful +10% capture, so an independent Attack lane is still required.
- Attack model exploration is the current highest-priority Short task.

## V3 Swing (10BD)

Current reproducible candidate is `v3_swing_v2.py`.

Structure:
MomCross event -> causal semiannual retraining inside MomCross -> model-output CDF/relative quality -> market Breadth Meta -> quality gate.

Current Swing S candidate, treated as frozen research candidate rather than something to keep tuning on 2026:
- 2026 Mar-Aug contaminated fixed check: about 30 picks
- 10BD mean about +1.42%
- median about +1.63%
- win rate about 60%
- -10% rate about 3.3%
- max about +17.5%

This does not match Stable★6's 10BD mean, but it is materially safer. 20BD/40BD extensions were worse, so this is a 10BD-specific candidate.

Swing Attack exploration using Surge, Breakout, +20% heads, and Deep Reversal did not remain stable across pre-2026 periods. Do not promote an Attack lane merely because it looks good in 2026. Current Swing A status: no accepted candidate.

## Rejected approaches

Do not repeat these without a materially new hypothesis:
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

## Working principles

- Prefer daily/cross-sectional percentiles and ranks over absolute predicted probabilities when models are retrained.
- Evaluate next-open -> horizon close.
- Preserve genuine +100% to +400% winners; do not blanket-remove them as outliers.
- Reject methods with negative median / unstable months even if mean is inflated by one huge winner.
- Record failed experiments as well as successes.
- Update this file whenever the architectural state materially changes.
