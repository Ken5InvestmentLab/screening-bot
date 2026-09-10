# TV-Free Screener — Next Actions

TEST ONLY. Execute top-to-bottom unless new evidence invalidates the next item. Keep `HANDOFF.md` synchronized.

## 1. Resolve/observe GitHub Actions runner-start blocker

Current fixed-start verification is blocked before workflow steps begin:
- run `34525453744`: failed before any step; no usable step logs.
- run `34530881770`: failed before any step; empty steps list.
- run `34530963918`: failed before any step with `steps=[]`, `runner_id=0`, blank runner name.
- run `34531004386`: same pre-step failure.
- runs `34536163042`, `34536183995`, and `34536324032`: same pre-step/no-runner failure.

This is strong evidence that no hosted runner is being assigned. It is not evidence of a Python/model failure. Do not alter model semantics to address it.

Next run:
- inspect whether the newest job reaches `actions/checkout`,
- if it still fails pre-step, keep production untouched and record the blocker,
- if GitHub exposes a concrete runner/account/quota error, fix only test plumbing if safe and justified.

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

## 3. Freeze stable numeric baselines and manifest-v2 contract

After fixed-start succeeds:
- record exact Short Core / defensive lane for 2025H1, 2025H2, contaminated 2026 Mar-Aug,
- record frozen Swing S at `score_R >= 0.20`,
- keep Short Attack = none and Swing A = none,
- keep Stable★6 / old Short rows historical/non-reproducible,
- record manifest-v2 `research_contract_sha256`, coverage SHA-256, OHLCV SHA-256, and Short/Swing output hashes at cutoff `2026-08-31`.

The prior rolling-3y run `34519284035` is a valid snapshot only, not the durable baseline.

## 4. Verify append-only reproducibility

`reproducibility_manifest.py` was added at `797a8578...` and workflow integration at `418c42b7...`.

Important fixes:
- commit `49ac8088a8160b6e8f4571374613b5d0343981d0`: cache fingerprint now includes historical OHLCV values, not just date/symbol coverage.
- commit `dcf669a502763a934a0f5aa6c226ab0a2d4bd4de`: manifest v2 adds a research-contract fingerprint covering relevant test research code/workflow/requirements and explicit non-secret `TVFREE_*` inputs.

On a later run after new market data arrives:
1. require matching `research_contract_sha256`; if it differs, do not interpret the run as a pure append-only comparison,
2. compare historical date/symbol coverage hash,
3. compare historical OHLCV hash,
4. compare Short Core / defensive / Swing S output hashes,
5. unchanged hashes support append-only reproducibility,
6. changed OHLCV with unchanged contract/coverage suggests source-data revision,
7. changed coverage with unchanged contract suggests listing/calendar/universe drift,
8. any mismatch requires investigation before accepting a new baseline.

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
