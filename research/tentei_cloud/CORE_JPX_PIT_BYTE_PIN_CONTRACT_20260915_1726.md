# Core24 JPX PIT byte-pin acquisition contract — 2026-09-15 17:26 JST

## Status
ACTIVE_PROVENANCE / PERFORMANCE UNOPENED.

The incoming Core HEAD `97106b9f9489f01545285481ba25ce87aad7fae2` is already marked processed in coordination STATE v81, so no prior SHA work was repeated. This run advances only the next declared provenance action.

## Fresh official-source verification
The official JPX listed-issues page currently states that its month-end listed-issues file is replaced monthly and should be downloaded/saved when needed. It also states that JPxData Portal all-issues CSV exposes TSE listing dates and includes delisted issues from the latest one year. The official New Listings page exposes listing date/code/segment, and the official Delisted Companies page exposes delisting events. These are source-route evidence, not yet the byte-pinned PIT dataset.

## Frozen acquisition contract
For the recovered raw1H interval `2024-09-17..2026-09-10`, PIT membership may become PASS only after all of the following are frozen without outcome/return inspection:

1. **Anchor snapshot** — exact downloaded JPX/JPxData all-issues bytes, SHA-256, byte count, retrieval timestamp, source URL, and parser version. The snapshot must carry listing-date/current identity fields and the documented latest-one-year delisted coverage.
2. **Historical event coverage** — official JPX New Listings and Delisted Companies archive inputs, or monthly `Changes in Listed Companies and Issues` inputs, covering the part of the interval not guaranteed by the anchor snapshot. Every exact input byte object must receive SHA-256 + size + source URL + retrieval timestamp.
3. **Deterministic normalization** — normalize code, listing date, delisting date, market segment and identity into a canonical event ledger sorted by `(effective_date, code, event_type, source_sha)`; hash the normalized ledger.
4. **Conflict quarantine** — code reuse, same-day contradictory events, missing effective dates, or segment/identity conflicts are fail-closed and excluded from formal expected-key generation until resolved from official evidence.
5. **Membership receipt** — emit source hashes, parser/contract version, normalized-ledger SHA, membership row count/date envelope, quarantine count/reasons, and a deterministic membership-output SHA.
6. **No Cartesian expected keys** — PIT membership plus XTKS calendar still does not prove a bar should exist in a specific hour. Formal missing inventory remains CLOSED until independent exact-hour activity evidence is frozen.

## Why this contract is necessary
The currently available JPX month-end page is a moving snapshot. Hashing only today's HTML or current Excel would not reconstruct the full historical membership interval. Conversely, Yahoo first/last observations cannot define listing boundaries because that would make provider availability part of the expected-universe definition. The PIT layer therefore needs an official anchor plus official historical event coverage.

## Cloud exact forensic
No new identity-critical primary evidence appeared. `HISTORICAL_EXACT_REPRO_UNAVAILABLE` remains binding. Old `n=63 / 5BD mean +9.86%` remains historical evidence only; no surrogate/model-family guessing was restarted.

## Guardrails
No backtest or performance statistic was computed. All future newly computed performance in this lane is cost 0%; win = gross return > 0; 2026 outcome is report-only. No production/main, production workflow, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater changes.
