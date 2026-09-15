# Core + Cloud handoff — 2026-09-15 19:24 JST

## New state
- Incoming Core HEAD `9506c2a6c96e6be9342cf1f7ab534f1ee959ab5a` was already processed in coordination STATE v85 and was not reprocessed.
- Official JPX archive page URLs are now resolved rather than guessed:
  - New Listings: current `/english/listing/stocks/new/`, 2025 `new/00-archives-01.html`, 2024 `new/00-archives-02.html`.
  - Delisted: current `/english/listing/stocks/delisted/`, 2025 `delisted/archives-01.html`, 2024 `delisted/archives-02.html`.
- The former blocker `archive selector target URL unknown` is therefore cleared.
- Exact byte capture is still pending. Container direct retrieval failed at network/DNS transport, so PIT remains NOT PASS and no SHA receipt was invented.
- Cloud exact remains CLOSED: `HISTORICAL_EXACT_REPRO_UNAVAILABLE`.

## Next action
Use the resolved six official JPX sources to obtain exact source bytes through an allowed byte-preserving transport; freeze SHA-256, byte size, retrieval timestamp and source URL. Then build deterministic normalized listing/delisting event ledger + conflict quarantine + membership receipt for `2024-09-17..2026-09-10`.

Only after PIT PASS, freeze independent exact-hour activity evidence before formal hourly missing inventory. No family retune; all eventual new performance is cost 0%, win = gross return > 0, and 2026 is report-only. Production/main and integrations remain untouched.
