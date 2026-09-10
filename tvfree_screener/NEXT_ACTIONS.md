# TV-Free Screener — Next Actions

TEST ONLY. Execute top-to-bottom unless new evidence invalidates the next item. Keep `HANDOFF.md` synchronized.

## 1. Resolve/observe GitHub Actions runner-start blocker

Current fixed-start verification is blocked before workflow steps begin:
- run `34525453744`: failed before any step; no usable step logs; rerun requested.
- run `34530881770`: failed before any step; empty steps list again.

This failure mode is not evidence of a Python/model failure. Do not alter model semantics to address it.

Next run:
- inspect whether a job now reaches `actions/checkout`,
- if it still fails pre-step, keep production untouched and record the blocker,
- if GitHub exposes a concrete runner/account error, fix only test plumbing if safe and justified.

## 2. Confirm fixed-start history in a successfully started job

Fixed-start acquisition is test-only:
- `bootstrap.py` commit `063a73b3...`
- workflow commit `458be814...`
- default start: `2022-01-01`
- normal `run.py` period behavior remains untouched.

When a job starts:
- confirm `Yahoo history mode: fixed start 2022-01-01 -> current`,
- confirm cache coverage and all Short/Swing/comparison steps succeed,
- run `reproducibility_manifest.py` and retain `reproducibility_manifest.json`,
- record total runtime and artifact size.

Do not change any model threshold based on 2026 output.

## 3. Freeze stable numeric baselines and hashes

After fixed-start succeeds:
- record exact Short Core / defensive lane for 2025H1, 2025H2, contaminated 2026 Mar-Aug,
- record frozen Swing S at `score_R >= 0.20`,
- keep Short Attack = none and Swing A = none,
- keep Stable★6 / old Short rows historical/non-reproducible,
- record SHA-256 fingerprints at historical cutoff `2026-08-31` from the manifest.

The prior rolling-3y run `34519284035` is a valid snapshot only, not the durable baseline.

## 4. Verify append-only reproducibility

`reproducibility_manifest.py` was added at `797a8578...` and workflow integration at `418c42b7...`.

On a later run after new market data arrives:
- compare historical hashes through 2026-08-31,
- unchanged hashes support append-only reproducibility,
- changed hashes require investigation for Yahoo history revisions or intentional code/semantic changes before accepting new baselines.

## 5. Operational-cost validation

Prior rolling-3y run `34519284035` took about 23m15s and produced ~33.55 MB under a 90-minute timeout. Fixed-start 2022 will be larger. Measure and optimize only batching/checkpoints/job layout if needed; do not weaken causal/model semantics.

## 6. Production integration — BLOCKED until user Go

Never automatically:
- merge PR #13 to main,
- change production screening-bot,
- send production Discord,
- write production Spreadsheet,
- replace Stable★6/Sniper/Mega,
- disable TradingView/watchlist builder/updater.

Only prepare test outputs and implementation plans until explicit user Go approval.
