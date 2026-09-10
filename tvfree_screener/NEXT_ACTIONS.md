# TV-Free Screener — Next Actions

TEST ONLY. Execute top-to-bottom unless new evidence invalidates the next item. Keep `HANDOFF.md` synchronized.

## 1. Build reproducible V3 Short reconstruction runner

Current decision: `Short Attack = none / unaccepted`.

Why:
- exact-feature recent-outcome Meta failed frozen 2026,
- whole-universe +10/+20 Attack selected on 2025 failed frozen 2026,
- 5 distinct event families x 2 fixed variants all failed the 2024-2025 robustness gate before 2026 evaluation.

Create `tvfree_screener/v3_short_reconstruction.py` with only defensible, reproducible test-only components. Do not recreate the historical +5.42% result by inventing missing parameters.

Recommended representation:
- causal monthly exact-feature Core using `r_top10 - 2*r_loss10`, selected on 2025,
- optionally report the contemporaneous `med_ret5 >= -1%` defensive market gate as a supporting lane,
- recent-outcome Meta = rejected/not active,
- Attack = none,
- one-selection-day same-symbol cooldown,
- next-session-open -> 5BD evaluation,
- JSON/CSV reports with 2025H1/H2 and contaminated fixed 2026 Mar-Aug clearly labeled.

If implementing the monthly XGBoost runner in Actions is too expensive, first preserve a reproducible checkpoint/report path and document the runtime blocker rather than weakening causal rules.

## 2. Reproduce/freeze Swing S in GitHub Actions

Keep `v3_swing_v2.py` unchanged with `score_R >= 0.20`; do not tune it from 2026. Preserve the test artifact and confirm the report remains consistent.

## 3. Unified Short/Swing comparison

Generate a test-only comparison covering 5BD, 10BD, 20BD, 40BD, n, mean, median, win rate, +10%, -10%, max/min, monthly breakdown.

Rows:
- Stable★6 historical reference,
- Short Core,
- Short defensive market-gated lane if retained,
- Short Attack = none,
- Swing S,
- Swing A = none unless a future pre-2026-stable hypothesis is found.

Label the old Short +5.42% figures as historical non-reproducible reference.

## 4. Operational-cost validation

After the reproducible runners are stable:
- measure full-universe Actions runtime,
- artifact/cache size,
- GitHub free-usage practicality,
- optimize symbol batches/checkpoints without changing model semantics.

## 5. Production integration — BLOCKED until user Go

Never automatically:
- merge PR #13 to main,
- change production screening-bot,
- send production Discord,
- write production Spreadsheet,
- replace Stable★6/Sniper/Mega,
- disable TradingView/watchlist builder/updater.

Only prepare test outputs and implementation plans until explicit user Go approval.
