# Core + Cloud forensic log — 2026-09-15 18:24 JST

## Start-state reconciliation
- Coordination STATE v83 marks Core HEAD `402c2ebc00abd75f3f5305030cbef52028d482ea` as already processed; no prior SHA work was repeated.
- Latest Core handoff requires exact official JPX PIT bytes/SHA before deterministic membership construction.
- Cloud exact remains CLOSED as `HISTORICAL_EXACT_REPRO_UNAVAILABLE`; no model-family guessing restarted.
- Rejected Core/Reclaim/Precision families remain closed. No performance was opened.

## Official JPX acquisition probe
Fresh official JPX pages were rechecked outcome-blindly.

- `https://www.jpx.co.jp/english/listing/stocks/new/index.html` exposes current 2026 new-listing rows with listing date, code and market segment and advertises an Archives selector.
- `https://www.jpx.co.jp/english/listing/stocks/delisted/index.html` exposes current delisting rows with delisting date, code and market segment and advertises an Archives selector.
- The current pages therefore remain valid official event-source routes, but the non-interactive web representation does not expose the archive-selector target URLs directly.
- A direct raw-byte download attempt against the JPX new-listings HTML failed in the available download transport. Therefore no byte object was falsely declared pinned and PIT remains NOT PASS.

## Contract consequence
This run does **not** substitute search-engine rendered text, current-page tables, Yahoo first/last observations, or guessed archive URLs for the required exact official byte objects. The frozen PIT contract remains unchanged:
1. acquire exact official anchor/event bytes,
2. SHA-256 + byte-count every object,
3. deterministic normalized event ledger,
4. conflict quarantine,
5. deterministic membership receipt,
6. only after PIT PASS seek independent exact-hour activity evidence.

A useful route-level finding is retained: current official 2026 New Listings and Delisted Companies pages contain the needed event fields, so the remaining acquisition problem is transport/archive-byte capture rather than schema discovery.

## Guardrails
No backtest or performance statistic was computed. Future new performance remains transaction cost 0% only; win = gross return > 0; 2026 report-only. No production/main, production workflow, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater changes.
