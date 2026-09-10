# TV-Free Screener — Next Actions

TEST ONLY. Execute top-to-bottom unless new evidence invalidates the next item. Keep `HANDOFF.md` synchronized.

## 1. Confirm reproducible V3 Short runner in GitHub Actions

`tvfree_screener/v3_short_reconstruction.py` is implemented and integrated into the test workflow.

Current frozen representation:
- causal monthly exact-feature Core using `r_top10 - 2*r_loss10`, selected on 2025,
- contemporaneous `med_ret5 >= -1%` defensive market gate as a supporting lane,
- recent-outcome Meta = rejected/inactive,
- Attack = none/unaccepted,
- one-selection-day same-symbol cooldown,
- next-session-open -> 5BD evaluation,
- JSON/CSV reports with 2025H1/H2 and contaminated fixed 2026 Mar-Aug clearly labeled.

Current verification state:
- a workflow run containing the new Short step is in progress,
- the existing Purged walk-forward backtest is still ahead of it in the sequential job,
- do not call the Short runner validated until its step completes and its artifact is inspected.

If successful: preserve/report its artifact and reconcile exact numbers with prior research notes.
If it fails or times out: fix checkpoint/runtime plumbing only; do not reduce model semantics or tune to 2026.

## 2. Reproduce/freeze Swing S in GitHub Actions

Keep `v3_swing_v2.py` unchanged with `score_R >= 0.20`; do not tune it from 2026. Preserve the test artifact and confirm the report remains consistent.

## 3. Inspect unified Short/Swing comparison

`tvfree_screener/unified_comparison.py` is implemented and integrated into the workflow. It generates CSV/JSON from available runner reports and clearly labels historical references.

After the current research run completes:
- verify Short Core and defensive lane rows,
- verify Swing S 5/10/20/40BD rows,
- verify Stable★6 and old Short references remain labelled historical/non-reproducible,
- inspect monthly breakdowns,
- leave genuinely unavailable metrics blank rather than filling assumptions.

## 4. Operational-cost validation

After runner outputs are confirmed:
- measure full-universe Actions runtime,
- artifact/cache size,
- GitHub free-usage practicality,
- specifically assess whether the sequential all-research workflow approaches/exceeds the 90-minute job limit,
- optimize batching/checkpoints/job layout without changing model semantics.

## 5. Production integration — BLOCKED until user Go

Never automatically:
- merge PR #13 to main,
- change production screening-bot,
- send production Discord,
- write production Spreadsheet,
- replace Stable★6/Sniper/Mega,
- disable TradingView/watchlist builder/updater.

Only prepare test outputs and implementation plans until explicit user Go approval.
