# Core + Cloud forensic log — 2026-09-16 02:24 JST

## Scope / guardrails
Research-only. No production/main/Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist-builder/updater changes. No reject-family retune. No new performance opened. Transaction-cost policy remains 0% for any future performance.

## Coordination start state
Coordination STATE v100 marks `research/tentei-cloud-mtf` HEAD `eaabfde1501e695907c25207a95e51302b0bed9a` processed and assigns P0: byte-pin JPX transfer current/2025/2024, build transfer ledger, audit 375-vs-395 listing/delisting delta, then conflict-checked reverse replay and PIT receipt.

## New forensic finding: transfer archive mapping verified independently
Official JPX English pages resolve the segment-transfer archive family as:
- current: `https://www.jpx.co.jp/english/listing/stocks/transfers/`
- 2025: `https://www.jpx.co.jp/english/listing/stocks/transfers/00-archives-01.html`
- 2024: `https://www.jpx.co.jp/english/listing/stocks/transfers/00-archives-02.html`

Rendered official evidence confirms the schema required by the frozen transfer contract: Date, Issue Name, Code, Market Segment, Previous Market Segment, Underwriter. It also independently confirms `277A Globe-ing Inc.` transferred Growth -> Prime on 2026-04-30. The 2024 archive contains post-target-start transfers including 3993 Standard -> Prime (2024-09-27), 3663 Standard -> Prime (2024-09-25), and 9341 Growth -> Prime (2024-09-20), proving transfer replay is required immediately after the 2024-09-17 target date.

## Decision
The transfer source family is now URL/schema-provenance-resolved, but PIT remains FAIL-CLOSED until exact bytes and SHA-256 for all three transfer pages are captured by the research byte-preserving workflow. Rendered/search text is not promoted to byte-pinned evidence.

## Next P0
1. Extend/run the existing research-only JPX byte capture workflow for the three verified transfer URLs.
2. Freeze source URL, byte size, SHA-256, retrieval timestamp.
3. Build deterministic transfer ledger from those exact bytes.
4. Audit the legacy 375-event vs forensic 395-event listing/delisting delta row-by-row before combining ledgers.
5. Reverse replay anchor + listing + delisting + transfer events; quarantine impossible transitions; only then freeze PIT membership count/SHA/receipt.

Cloud exact forensic remains `HISTORICAL_EXACT_REPRO_UNAVAILABLE`; do not resume model-family guessing without new exact evidence.
