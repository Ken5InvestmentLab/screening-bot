# Core + Cloud forensic log — 2026-09-15 19:24 JST

## Start-state / duplicate guard
- Coordination STATE v85 marked `9506c2a6c96e6be9342cf1f7ab534f1ee959ab5a` as both last-seen and last-processed for `research/tentei-cloud-mtf`; no duplicate processing was performed.
- Core HEAD at start was the same SHA.
- Cloud exact forensic remains CLOSED as `HISTORICAL_EXACT_REPRO_UNAVAILABLE`; no model-family guessing was reopened.

## New evidence: official JPX archive URL map resolved
Fresh official-JPX discovery resolved the previously unknown archive page paths without guessing:

### New Listings
- current / 2026: `https://www.jpx.co.jp/english/listing/stocks/new/`
- 2025 archive: `https://www.jpx.co.jp/english/listing/stocks/new/00-archives-01.html`
- 2024 archive: `https://www.jpx.co.jp/english/listing/stocks/new/00-archives-02.html`

The 2025 archive visibly contains 2025 listing events; the 2024 archive visibly contains 2024 listing events, including the target-window tail from 2024-09-17 onward.

### Delisted Companies
- current / 2026: `https://www.jpx.co.jp/english/listing/stocks/delisted/`
- 2025 archive: `https://www.jpx.co.jp/english/listing/stocks/delisted/archives-01.html`
- 2024 archive: `https://www.jpx.co.jp/english/listing/stocks/delisted/archives-02.html`

The 2025 and 2024 archive pages visibly expose delisting date, code, market segment and reason. This removes the prior `archive selector target URL unknown` blocker.

## Byte-pin status
- PIT is still **NOT PASS**. Rendered/search text is not promoted to exact-byte evidence.
- A direct runtime byte-download/hash attempt against the now-resolved JPX URL failed at DNS/network transport in the container, so no SHA-256/size receipt was fabricated.
- The remaining blocker is now narrower: capture exact official page/file bytes for the six resolved official sources (or an equivalent official downloadable object), record SHA-256 + byte size + retrieval timestamp + URL, then build the deterministic event ledger/quarantine/membership receipt.
- No Cartesian `membership × XTKS × hour` expected-key generation until independent exact-hour activity evidence is frozen after PIT PASS.

## Guardrails honored
- No new performance/backtest was run; no 0.5%/1% cost calculation was run.
- No rejected family retune.
- No production/main/workflow/Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist-builder/updater change.
- 2026 outcome remains report-only.
