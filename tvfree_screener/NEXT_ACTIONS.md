# TV-Free Screener — Next Actions

TEST ONLY. Execute top-to-bottom unless new evidence invalidates the next item. Keep `HANDOFF.md` synchronized.

## 1. Resolve/observe GitHub Actions runner-start blocker

Latest observed PR-triggered runs `34541092751` and `34541347039` both failed before executable steps. Earlier failed jobs exposed no assigned hosted runner (`runner_id=0`, blank runner name, no steps). The latest check-run contains one annotation, but the connected API cannot retrieve the annotation body.

GitHub public/Japan status reported Actions operational during the latest check. Treat the repeated failure as likely repo/account/quota-specific until GitHub exposes stronger evidence. Do not alter model semantics to address runner allocation failure.

Next run:
- inspect whether the newest job reaches `actions/checkout`,
- inspect job/check metadata for a usable account/quota/runner reason,
- if still pre-step/no-runner, record the blocker and continue only test-safe research,
- never touch production workflows as a workaround.

## 2. Require synthetic safety checks before heavy research

The test workflow must first pass:
- `reproducibility_selftest.py`: historical-source revision and append-only invariants,
- `causality_selftest.py`: fabricated 2024/2025-only checks for feature prefix invariance, next-session-open -> 5BD semantics, Short monthly purge, and Swing semiannual purge.

Do not bypass these checks to obtain attractive performance output.

## 3. Confirm fixed-start history

When a hosted runner actually starts:
- require `Yahoo history mode: fixed start 2022-01-01 -> current`,
- confirm cache coverage and all Short/Swing/comparison steps succeed,
- retain `jpx_universe_snapshot.csv`, `reproducibility_manifest.json`, and all model outputs,
- record total runtime and artifact size.

No model threshold may be changed based on 2026 output.

## 4. Freeze numeric baselines and manifest-v3 contract

After fixed-start succeeds, record:
- Short Core / defensive lane for 2025H1, 2025H2, and contaminated 2026 Mar-Aug,
- frozen Swing S at `score_R >= 0.20`,
- Short Attack = none; Swing A = none,
- `research_contract_sha256`,
- JPX universe SHA-256,
- historical date/symbol coverage SHA-256,
- historical OHLCV SHA-256,
- Short/Swing output hashes through cutoff `2026-08-31`.

The old rolling-3y run remains a snapshot only, not the durable baseline.

## 5. Address point-in-time universe validity

New guardrails:
- commit `9e1bb3473ebbb2ccb3f768e7bf144b9969927f47`: persist exact run-date JPX universe as `tvfree_screener/out/jpx_universe_snapshot.csv`.
- commit `d50cb1eca97734acb4f4d5ed2f1ab97acd6c267b`: manifest v3 fingerprints the universe and requires matching universe + research-contract hashes before interpreting append-only stability.

Important research limitation:
- current backtests use the run-date JPX listed universe,
- listings/delistings can therefore alter historical membership,
- this creates survivorship/membership bias even with a fixed Yahoo start date,
- snapshot hashing detects the problem but does not solve point-in-time membership.

Next safe research task while Actions is blocked:
- investigate a free, reproducible source/method for point-in-time TSE domestic common-stock membership from 2022 onward,
- prefer official JPX listing/delisting history if reconstructable,
- reject approaches that silently use only current survivors or introduce future membership knowledge.

## 6. Append-only reproducibility interpretation

On a later run after new market data arrives:
1. require matching `research_contract_sha256`,
2. require matching JPX universe SHA-256 for a pure append-only comparison,
3. compare historical date/symbol coverage hash,
4. compare historical OHLCV hash,
5. compare Short Core / defensive / Swing S output hashes,
6. universe mismatch means membership drift, not pure price append,
7. matching contract/universe/coverage but changed OHLCV suggests source-history revision,
8. any unexplained mismatch blocks acceptance of a new baseline.

## 7. Operational-cost validation

Prior rolling-3y run `34519284035` took about 23m15s and produced ~33.55 MB under a 90-minute timeout. Measure fixed-start cost only after a runner starts. Optimize batching/checkpoint/plumbing only; do not weaken causal/model semantics.

## 8. Production integration — BLOCKED until user Go

Never automatically:
- merge PR #13 to main,
- change production screening-bot,
- send production Discord,
- write production Spreadsheet,
- replace Stable★6/Sniper/Mega,
- disable TradingView/watchlist builder/updater.

Only prepare test outputs and implementation plans until explicit user Go approval.
