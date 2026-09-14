# Core24 raw1H artifact pin spec — 2026-09-15 JST

## Scope
Research-only, outcome-blind provenance work. No strategy family is reopened or retuned. No production/main, production workflow, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder, or updater changes are allowed.

## Recovered authoritative fetch
The retained successful extended Yahoo 1H fetch is Actions run `34592896202`, workflow `Tentei Cloud 1H Research Fetch`, source HEAD `a331b96c8b7391a146ed3a8d28dd5e66d6ae0679`.

The run exposes exactly eight shard artifacts named `tentei-cloud-1h-shard-{0..7}`. Each contains `ohlcv_1h_shard_i.csv` plus `failures_i.json`. All eight artifacts were recovered while GitHub reported them unexpired. Their artifact IDs, ZIP digests, expiry timestamps, raw CSV SHA-256 values, byte sizes, row counts, symbol counts, timestamp spans, and deterministic bundle SHA are frozen in `RAW1H_ARTIFACT_PIN_20260915_0626.json`.

## Acceptance contract
The recovered observed input is accepted for provenance work only if all of the following hold:
1. exactly one `ohlcv_1h_shard_i.csv` exists for every shard `i=0..7`;
2. required columns are `symbol,timestamp,open,high,low,close,volume`;
3. each raw CSV SHA-256 matches the frozen receipt;
4. the eight-shard deterministic bundle SHA-256 equals `de7710adaf52ba5a1fb783e7bde35feea9528294be557ef4e011dc4be7e8ed18`;
5. no return, label, rank, strategy outcome, or 2026 result is consulted when accepting/rejecting raw bytes.

Observed bundle facts: 4,019,524 rows; timestamp envelope `2024-09-17 09:00:00+0900` through `2026-09-10 15:00:00+0900`. Historical fetch failures remain 272 chunks across 61 symbols: HTTP400=153, HTTP404=119. Existing coverage forensic classifies 44 symbols as before-first-only and 17 as never observed, with no detected failure interval overlapping observed history.

## Artifact retention caveat
The GitHub artifacts expire on 2026-09-25 (per-artifact exact timestamps are in the receipt). The receipt permanently pins identity, but does **not** itself preserve the raw bytes after artifact expiry. Do not claim durable byte archival unless a separate storage receipt is created.

## Remaining formal gate: expected endpoint-key universe
Do not run the one-shot missing inventory until the expected endpoint-key CSV itself is independently frozen by SHA-256. The expected set must be generated without using returns/outcomes and must not silently erase:
- delisted tickers,
- pre-listing intervals,
- listing/delisting boundary effects,
- provider truncation,
- exchange holidays/session structure.

The existing `symbols_4h_universe.txt` or a Cartesian `symbol × timestamp` expansion is not by itself sufficient proof of the historical point-in-time endpoint universe. Exact listing eligibility and XTKS session keys must be evidenced. If that cannot be pinned, fail closed rather than fabricate expected keys.

After the expected CSV is pinned, run `missing_inventory_runner.py` exactly once against the pinned observed input. Only declared missing pairs may enter fallback acquisition. Any Stooq/other candidate must satisfy the frozen source policy; Alpha Vantage free is DAILY-only low-priority and cannot create 1H/4H bars; Google Finance snapshots are corroboration only. Conflicting formal sources fail closed.

## Performance gate
Performance remains unopened. New calculations, when eventually permitted, are transaction cost 0% only and win means gross return > 0. 2026 outcome remains report-only. Cloud Monster exact status remains `HISTORICAL_EXACT_REPRO_UNAVAILABLE`; no model-family guessing resumes without new contemporaneous identity-critical evidence.
