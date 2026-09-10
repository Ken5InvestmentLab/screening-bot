# TV-Free Screener — Next Actions

TEST ONLY. Execute top-to-bottom unless new evidence invalidates the next item. Keep `HANDOFF.md` synchronized.

## 1. Resolve/observe GitHub Actions runner-start blocker

Current fixed-start verification is still blocked before workflow steps begin. Latest observed PR-triggered run `34539341326` again failed before executable steps and does not demonstrate a Python/model exception.

Next run:
- inspect whether the newest job reaches `actions/checkout`,
- if it still fails pre-step/no-runner, keep production untouched and record the blocker,
- if GitHub exposes a concrete runner/account/quota error, fix only test plumbing if safe and justified,
- do not alter model semantics to address runner allocation failure.

## 2. Require both synthetic safety checks first

Reproducibility guard:
- `reproducibility_selftest.py`: `0a0f94894d79ec600c7cae1cc87b55d499ccc685`
- workflow integration: `f60df68db3172e3417eb32861cef0d342cc6b595`

Causality guard:
- `causality_selftest.py`: `9543975185767c4985e6afe1cee52a350cc00bc5`
- included in research-contract hash: `79fb0af83a04c53281ee77c0b5bb36c7122f45e7`
- workflow integration before heavy research: `de498ea0e4a808ec56f01067606285034a2e264b`

The causal self-check uses fabricated 2024/2025 data only. It verifies:
1. historical `run.py` feature values are prefix-invariant when later rows are appended,
2. 5BD evaluation enters at the next trading session open and exits at the 5BD close,
3. Short monthly training excludes labels whose `target_end_date` is on/after the prediction month start,
4. Swing semiannual training excludes labels whose `target10_end` is on/after the prediction period start.

Once Actions starts, both safety checks must pass before treating the run as valid. Do not bypass them to obtain attractive research numbers.

## 3. Confirm fixed-start history in a successfully started job

Fixed-start acquisition is test-only:
- `bootstrap.py`: `063a73b3...`
- workflow: `458be814...`
- default start: `2022-01-01`
- normal production-adjacent `run.py` period behavior remains untouched outside the bootstrap path.

When a job starts:
- confirm `Yahoo history mode: fixed start 2022-01-01 -> current`,
- confirm cache coverage and all Short/Swing/comparison steps succeed,
- build and retain `reproducibility_manifest.json`,
- record total runtime and artifact size.

Do not change any model threshold based on 2026 output.

## 4. Freeze stable numeric baselines and manifest-v2 contract

After fixed-start succeeds:
- record exact Short Core / defensive lane for 2025H1, 2025H2, contaminated 2026 Mar-Aug,
- record frozen Swing S at `score_R >= 0.20`,
- keep Short Attack = none and Swing A = none,
- keep Stable★6 / old Short rows historical/non-reproducible,
- record manifest-v2 `research_contract_sha256`, coverage SHA-256, OHLCV SHA-256, and Short/Swing output hashes at cutoff `2026-08-31`.

The prior rolling-3y run `34519284035` is a valid snapshot only, not the durable baseline.

## 5. Verify append-only reproducibility

Important manifest commits:
- initial manifest: `797a8578...`
- workflow integration: `418c42b7...`
- historical OHLCV-value hashing: `49ac8088a8160b6e8f4571374613b5d0343981d0`
- research-contract fingerprint: `dcf669a502763a934a0f5aa6c226ab0a2d4bd4de`
- reproducibility synthetic invariant test: `0a0f94894d79ec600c7cae1cc87b55d499ccc685`
- causal safety synthetic test: `9543975185767c4985e6afe1cee52a350cc00bc5`

On a later run after new market data arrives:
1. require matching `research_contract_sha256`; if it differs, do not interpret the run as a pure append-only comparison,
2. compare historical date/symbol coverage hash,
3. compare historical OHLCV hash,
4. compare Short Core / defensive / Swing S output hashes,
5. unchanged hashes support append-only reproducibility,
6. changed OHLCV with unchanged contract/coverage suggests source-data revision,
7. changed coverage with unchanged contract suggests listing/calendar/universe drift,
8. any mismatch requires investigation before accepting a new baseline.

## 6. Operational-cost validation

Prior rolling-3y run `34519284035` took about 23m15s and produced ~33.55 MB under a 90-minute timeout. Fixed-start 2022 will be larger. Measure and optimize only batching/checkpoints/job layout if needed; do not weaken causal/model semantics.

## 7. Production integration — BLOCKED until user Go

Never automatically:
- merge PR #13 to main,
- change production screening-bot,
- send production Discord,
- write production Spreadsheet,
- replace Stable★6/Sniper/Mega,
- disable TradingView/watchlist builder/updater.

Only prepare test outputs and implementation plans until explicit user Go approval.
