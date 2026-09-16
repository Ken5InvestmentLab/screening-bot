# Core + Cloud handoff — 2026-09-16 09:24 JST

## New P0
Empirical OHLCV completeness audit, not provider-option speculation.

## State
- Daily: `DAILY_RAW_EVIDENCE_NOT_YET_ESTABLISHED_FOR_EXHAUSTIVE_AUDIT` in this run. Do not claim zero missing.
- Exact-hour/activity: `SEALED_INDEPENDENT_RAW_ACTIVITY_NOT_ACQUIRED`.
- PIT/XTKS/source-provenance contracts remain authoritative.
- Unknown absence stays fail-closed; pre-listing/post-delisting/no-activity are normal only with evidence.
- Source completion credit requires acquired/pinned raw evidence. Google/Alpha/J-Quants/FLEX are not automatically credited.

## Required next output
`daily_expected`, `daily_observed`, `daily_missing(symbol,date,field,class)`, monthly/yearly summaries, source matrix, `trade_impact`, DUAL+G3 2022-2026 endpoint impact, plus receipt hashes. Hourly ledgers only after independent activity evidence.

Cloud Monster remains `HISTORICAL_EXACT_REPRO_UNAVAILABLE`. Cost policy remains 0% for any future new performance calculation.
