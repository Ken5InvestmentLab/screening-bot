# Core exact-hour activity source spec — 2026-09-16 07:24 JST

## Purpose
Freeze the acceptance contract for the final Core24 endpoint-universe blocker without manufacturing expected hourly keys from PIT membership or the audited Yahoo raw1H bundle.

## Required witness semantics
An acceptable independent activity witness must identify actual TSE cash-equity trade activity at timestamp resolution sufficient to map each execution to an exact `(symbol, XTKS session_date, raw_hour)` key. Quote-only/order-book presence, daily OHLCV, morning-session OHLCV, membership, calendar membership, and the audited Yahoo raw1H source are insufficient by themselves.

## Official-source finding
JPX Market Innovation & Research documents **Historical Real-Time Market Data (Including Tick Data)** / FLEX Historical. The official service states that JPXI stores TSE real-time market data daily and provides historical Tick data; TSE listed cash equities are covered by FLEX Standard/FLEX MBO, data after 2021-05-24 are PCAP with reception timestamps, and all-period historical access is available by contract. This is semantically sufficient as an independent execution/activity witness if acquired and pinned.

Official source URL: `https://www.jpx.co.jp/english/markets/paid-info-equities/historical/01.html`

## Adoption status
`SEMANTIC_SOURCE_IDENTIFIED_ACCESS_NOT_ACQUIRED`

No FLEX Historical bytes are currently present in the research evidence chain, and the service is contract/paid access. Therefore formal expected-key generation remains **SEALED**. Do not substitute Yahoo raw1H, PIT membership × XTKS × hour, daily data, or synthesized intraday rows.

## Exact adoption procedure
If FLEX Historical access/data is obtained:
1. preserve source/service identity, acquisition timestamp, contract/service classification, raw file names, byte sizes and SHA-256 before parsing;
2. preserve the relevant FLEX specification/version and decoding procedure;
3. extract only actual cash-equity executions, normalize issue code and JST execution/reception timestamp, and map executions to the already-frozen raw-hour semantics;
4. deduplicate to sorted unique `(symbol, session_date, raw_hour)` activity keys;
5. SHA-pin the activity-key CSV and a machine-readable receipt binding raw FLEX source hashes, parser version, XTKS calendar receipt and PIT membership receipt;
6. only then generate the formal expected endpoint CSV and run `missing_inventory_runner.py` exactly once.

Any ambiguous message type, symbol mapping, timestamp/session mapping, or source gap fails closed and is quarantined rather than inferred.

## Guardrails
No performance opened. New performance remains cost 0% only, win = gross return > 0, 2026 report-only. No rejected-family retune. No production/main or production integration changes.

Cloud Monster remains `HISTORICAL_EXACT_REPRO_UNAVAILABLE`; no model-family guessing is reopened.
