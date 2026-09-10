# TV-Free Screener — Next Actions

TEST ONLY. Execute top-to-bottom unless new evidence invalidates the next item. Keep `HANDOFF.md` synchronized.

## 1. Confirm fixed-start history in GitHub Actions

The previous successful run `34519284035` proved all Short/Swing/comparison steps execute, but exposed a reproducibility flaw: Yahoo `period=3y` is a rolling window, so old training rows disappear over time and unchanged historical backtests drift.

Fixed-start acquisition is now test-only:
- `bootstrap.py` commit `063a73b3...`
- workflow commit `458be814...`
- default start: `2022-01-01`
- end: current market data
- normal `run.py` period behavior is left untouched outside the test bootstrap.

Next:
- inspect the triggered Actions run,
- confirm logs say `Yahoo history mode: fixed start 2022-01-01 -> current`,
- confirm all steps succeed,
- inspect Short, Swing S and unified comparison artifacts,
- record runtime and artifact size.

Do not change any model threshold based on the new 2026 numbers.

## 2. Freeze stable numeric baselines

Latest successful rolling-3y snapshot (run `34519284035`) is valid for that data snapshot but not a long-term reproducibility anchor.

After fixed-start succeeds:
- record exact Short Core / defensive lane 2025H1, 2025H2, contaminated 2026 Mar-Aug,
- record frozen Swing S at `score_R >= 0.20`,
- keep Short Attack = none and Swing A = none,
- keep Stable★6 / old Short rows historical/non-reproducible.

Important: rolling-3y run 31 says the pre-2026 Swing threshold sweep currently favors 0.10 and `locked_threshold_matches_best_pre2026=false`. Do NOT retune from 0.20. Resolve the data-history contract first.

## 3. Verify append-only reproducibility

On a later run after at least one new market session is added, verify historical fixed-start predictions/statistics do not change unexpectedly. New future rows may appear, but old training history must no longer disappear due to a rolling-window boundary.

## 4. Operational-cost validation

Run 34519284035 took about 23m15s total and produced a ~33.55 MB artifact with 3y input. Fixed-start 2022 will be larger; measure:
- total Actions runtime,
- download/backtest runtime,
- Short reconstruction runtime,
- artifact/cache size,
- margin versus 90-minute job limit.

Optimize batching/checkpoints/job layout only if needed; do not weaken causal/model semantics.

## 5. Production integration — BLOCKED until user Go

Never automatically:
- merge PR #13 to main,
- change production screening-bot,
- send production Discord,
- write production Spreadsheet,
- replace Stable★6/Sniper/Mega,
- disable TradingView/watchlist builder/updater.

Only prepare test outputs and implementation plans until explicit user Go approval.
