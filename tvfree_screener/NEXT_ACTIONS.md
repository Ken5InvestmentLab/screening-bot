# TV-Free Screener — Next Actions

TEST ONLY. Execute top-to-bottom unless new evidence invalidates the next item. Keep `HANDOFF.md` synchronized.

## 1. Resolve/observe GitHub Actions runner-start blocker

Latest observed PR-triggered runs `34541399127` and `34541906076` both failed before executable steps. Job metadata still shows no usable steps/logs. This is not evidence of a Python/model failure.

Next run:
- inspect whether the newest job reaches `actions/checkout`,
- inspect job/check metadata for a usable account/quota/runner reason,
- if still pre-step/no-runner, record the blocker and continue only test-safe research,
- never touch production workflows as a workaround,
- never alter model semantics to address runner allocation failure.

## 2. Require all synthetic safety checks before heavy research

The test workflow must first pass:
- `reproducibility_selftest.py`: historical-source revision and append-only invariants,
- `causality_selftest.py`: fabricated 2024/2025-only checks for feature prefix invariance, next-session-open -> 5BD semantics, Short monthly purge, and Swing semiannual purge,
- `point_in_time_universe_selftest.py`: reverse membership reconstruction, code-reuse chronology, and fail-closed same-day event collision detection.

Do not bypass these checks to obtain performance output.

## 3. Validate official JPX point-in-time membership reconstruction

Official JPX stock pages expose year-specific new-listing and delisting archives for 2022 onward. TEST-only implementation:
- `point_in_time_universe.py`: commit `d2e66370d237edd94880fd9f8a6e740ed9332d5a`
- synthetic test: `bea62cb1d1847409e84d1e63b2c08038db435765`
- workflow self-check integration: `7632a4cd6aa3c77153413251a6d4cdfdb6973c5b`
- research-contract inclusion: `b88b04ebdc7e15c27eb7c6ae0ca34b3ed27a83a8`

Method:
1. anchor on the current JPX domestic-common snapshot,
2. collect official JPX listing/delisting events from 2022 through the anchor date,
3. reverse events to reconstruct membership on historical dates,
4. reject, rather than guess, unknown market classifications or same-code same-day event collisions.

Acceptance gate before any backtest use:
- live parser succeeds,
- `unknown_market_rows == 0`,
- `same_day_code_collisions == 0`,
- archive years 2022 through current are represented,
- no future-dated listing/delisting event is applied before its event date.

Do NOT wire this prototype into Short/Swing until those checks pass.

## 4. Measure Yahoo coverage for reconstructed delisted members

Membership reconstruction does not guarantee historical OHLCV exists in Yahoo.

Before accepting point-in-time results:
- enumerate reconstructed members that are absent from the current universe,
- query/download their historical Yahoo OHLCV only in the test path,
- report requested vs usable symbol counts and missing/error codes,
- never silently exclude missing delisted symbols and then call the result survivorship-bias-free.

If coverage is materially incomplete, document the limitation and investigate another free historical-price source before changing model semantics.

## 5. Compare point-in-time vs current-survivor universe pre-2026

Only after sections 3-4 pass:
- keep all Short/Swing thresholds and architecture frozen,
- run a separate test comparison using point-in-time membership,
- evaluate 2024/2025 robustness and next-session-open outcomes,
- treat 2026 only as contaminated fixed-side reporting, never threshold/model selection,
- reject the point-in-time implementation if event/price coverage is unstable or not reproducible.

## 6. Confirm fixed-start history and freeze durable baseline

When a hosted runner actually starts:
- require `Yahoo history mode: fixed start 2022-01-01 -> current`,
- retain current-universe snapshot, point-in-time diagnostics, all model outputs, and `reproducibility_manifest.json`,
- record Short Core / defensive lane for 2025H1, 2025H2, contaminated 2026 Mar-Aug,
- record frozen Swing S at `score_R >= 0.20`,
- keep Short Attack = none; Swing A = none,
- record research-contract, universe, coverage, OHLCV, and Short/Swing output hashes,
- record total runtime and artifact size.

The old rolling-3y run `34519284035` remains a snapshot only, not the durable baseline.

## 7. Production integration — BLOCKED until user Go

Never automatically:
- merge PR #13 to main,
- change production screening-bot,
- send production Discord,
- write production Spreadsheet,
- replace Stable★6/Sniper/Mega,
- disable TradingView/watchlist builder/updater.

Only prepare test outputs and implementation plans until explicit user Go approval.
