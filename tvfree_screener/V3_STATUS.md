# TV-Free V3 research status (TEST ONLY)

This document records the handoff state without pretending that unrecovered parameters are known.

## Guardrails

- Branch: `test/tvfree-screener-v1`
- Draft PR: #13
- No merge to `main` without explicit user Go approval.
- No production Discord or Spreadsheet writes.
- No modification of production Stable★6 / Sniper / Mega / TradingView flows.
- Primary realistic entry is next trading session open.
- 2026 has already been inspected during research, so it is not a pristine holdout.

## V3 Short (5BD)

Historical previous-session reference with one-business-day cooldown:
- n=29
- next-open -> 5BD mean +5.42%
- median +2.06%
- win 65.5%
- +10% 13.8%
- -10% 6.9%

The exact prior Short V3 parameters were never committed, so this remains a historical non-reproducible reference.

### Exact-feature reconstruction

A new reconstruction used the same 45 `run.py` features and the same XGBoost model shape (180 trees, depth 3, learning rate .04, min_child_weight 25, reg_lambda 5, reg_alpha .2). Monthly models were trained causally using only outcomes completed before each prediction month.

Core rule selected on 2025 only:
`r_top10 - 2.0 * r_loss10`.

2025 Core evidence:
- H1 mean about +0.59%, median +0.58%, win 58.0%, -10% 2.5%.
- H2 mean about +0.94%, median +0.57%, win 58.9%, -10% 0%.

Confirmed-outcome Meta selected on 2025 only:
recent 30 Core outcomes, win >=55%, loss10 <=10%.

Meta evidence:
- 2025H1 n=48, mean +1.05%, median +0.79%, win 58.3%, -10% 4.2%.
- 2025H2 n=76, mean +1.14%, median +0.74%, win 63.2%, -10% 0%.
- frozen 2026 Mar-Aug n=26, mean -1.27%, median -0.46%, win 42.3%, +5% 0%, -10% 3.8%.

Conclusion: the earlier defensive reconstruction result could not be reproduced under the exact `run.py` feature/model setup. The exact reconstructed recent-outcome Meta is rejected rather than retuned to 2026.

A 2025-selected contemporaneous market gate `med_ret5 >= -1%` improved the frozen 2026 Core side to roughly n=97 / mean +0.17% / -10% 1.0%, but median stayed negative. This is at most a defensive supporting observation.

### Dedicated Short Attack heads

Dedicated monthly +10% and +20% heads were trained causally with the same feature/model shape. Scores were converted to daily cross-sectional percentiles rather than using raw retrained probabilities.

Best eligible 2025 frontier candidate:
- score `r_hit20 - r_loss10`
- `med_ret5 >= -1%`
- `r_hit10 >= .85`
- daily best candidate
- one-selection-day same-symbol cooldown.

2025:
- H1 n=102, mean +1.93%, median 0%, win 47.1%, +10% 8.8%, +20% 2.9%, -10% 0%.
- H2 n=106, mean +2.10%, median 0%, win 44.3%, +10% 11.3%, +20% 3.8%, -10% 3.8%.

Frozen 2026 Mar-Aug:
- n=97
- mean +0.06%
- median -0.97%
- win 42.3%
- +10% 9.3%
- +20% 3.1%
- -10% 7.2%
- max +34.0%, min -18.2%.

May 2026 alone was about -2.89% mean. This Attack candidate is REJECTED. Do not keep tuning its thresholds/weights to already-seen 2026 data.

Next Short direction: test genuinely different event families using pre-2026 evidence, such as compression->expansion, capitulation->confirmed reversal, controlled gap/volume shocks, volatility contraction->ignition, or bounded-volatility breakout. If none survives, explicitly accept `Short Attack = none` rather than forcing one.

## V3 Swing (10BD)

Current reproducible candidate remains `v3_swing_v2.py`.

Architecture:
1. MomCross event filter.
2. Semiannual event-quality model using only fully known prior 10BD outcomes.
3. Return and loss model outputs normalized with training empirical CDFs.
4. `score_R = cdf_return - cdf_loss10`.
5. Breadth Meta >40% above MA20.
6. Daily best MomCross event with one-selection-day same-symbol cooldown.
7. Locked Swing S gate `score_R >= 0.20`, selected pre-2026.

Observed next-open -> 10BD:
- 2025H1 n=33, mean +2.68%, median +2.12%, win 57.6%, +10% 15.2%, -10% 6.1%.
- 2025H2 n=31, mean +1.95%, median -0.70%, win 45.2%, +10% 16.1%, -10% 6.5%.
- 2026 Mar-Aug contaminated check n=30, mean +1.42%, median +1.63%, win 60%, +10% 10%, -10% 3.3%, max about +17.5%.

Swing S remains the most credible current defensive 10BD research candidate. Swing A is unaccepted; prior big-winner, Surge, Breakout and Deep-Reversal approaches were unstable.

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
- Exact-feature Short recent-outcome Meta reconstructed above.
- Short whole-universe percentile +20% Attack reconstructed above.

## Next research direction

- Search for a distinct event-driven Short Attack family using 2024/2025 where possible; lock before viewing fixed 2026 evidence.
- If no robust Short Attack survives, record that explicitly instead of overfitting.
- Keep `v3_swing_v2.py` frozen as current Swing S and do not tune it from 2026.
- Final promotion remains blocked until explicit user Go approval and preferably a genuinely new forward period.
