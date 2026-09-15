# Core24 JPX PIT segment-transfer repair contract — 2026-09-16

Status: FROZEN / outcome-blind / research-only.

## Finding
The current 2026-08-31 JPX anchor cannot be reverse-replayed to 2024-09-17 using listing/delisting events alone because market-segment transitions are state-changing PIT events. Concrete official-JPX example: code 277A (Globe-ing Inc.) transferred Growth -> Prime on 2026-04-30. The JPX transfer pages expose Date, Issue Name, Code, Market Segment, Previous Market Segment.

Official source family:
- current: https://www.jpx.co.jp/english/listing/stocks/transfers/
- 2025: https://www.jpx.co.jp/english/listing/stocks/transfers/00-archives-01.html
- 2024: https://www.jpx.co.jp/english/listing/stocks/transfers/00-archives-02.html

## Required repair before PIT PASS
1. Capture the three official pages as exact bytes with URL, byte count, SHA-256 and retrieval timestamp, using the same byte-preserving research-only route as the already frozen JPX listing/delisting sources.
2. Parse only rows with effective date in the replay interval and freeze normalized fields: effective_date, code, issue_name, previous_segment, new_segment, source_url, source_sha256.
3. Reverse replay from the 2026-08-31 anchor in descending effective-date order. For a transfer event, current state MUST equal new_segment before replacing it with previous_segment. Otherwise quarantine and fail closed.
4. Listing/delisting extraction must be re-audited because the previously frozen 375-event receipt conflicts with the later forensic recount (395 replay-eligible events). The 375 receipt is non-canonical until the exact row-set difference is explained and a corrected ledger receipt is frozen.
5. Do not construct hourly expected keys until corrected membership receipt has zero unresolved identity/state conflicts and its output SHA/count are frozen.

## Guardrails
No performance opening, no retune, no production/main changes, no Discord/Spreadsheet/TradingView/watchlist changes. All future performance remains cost 0% only; 2026 remains report-only. Cloud Monster exact forensic remains CLOSED / HISTORICAL_EXACT_REPRO_UNAVAILABLE unless genuinely new historical evidence appears.
