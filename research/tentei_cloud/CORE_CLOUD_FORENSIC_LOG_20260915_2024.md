# Core + Cloud forensic log — 2026-09-15 20:24 JST

## Intake / locking
- Coordination STATE v87 inspected first. Incoming Core HEAD `310569742343fca991fcf9fb8654a09b349b205a` equals `last_processed_sha`; no duplicate processing.
- Latest Core handoff confirmed official JPX current/2025/2024 New Listings + Delisted URL map resolved, exact-byte capture pending.
- Cloud exact forensic remains CLOSED as `HISTORICAL_EXACT_REPRO_UNAVAILABLE`; no model-family guessing resumed.

## New work
- Added research-only `research/tentei_cloud/scripts/capture_jpx_pit_sources.py`.
- Added research-only Actions workflow `.github/workflows/tentei-cloud-core-jpx-pit-source-capture.yml` on `research/tentei-cloud-mtf` only.
- The capture tool downloads the six frozen official JPX source URLs, writes the exact response bytes unchanged, and emits `receipt.json` containing source URL, final URL, HTTP status, byte size, SHA-256, and UTC capture timestamp.
- Workflow uploads the exact-byte directory as an immutable Actions artifact. It contains no strategy/performance logic and does not touch production/main or integrations.

## Status
This removes the prior dependency on the automation container's failing DNS transport by moving byte-preserving retrieval to a research-only GitHub Actions runner. PIT remains NOT PASS until a successful artifact is observed and its receipt is inspected. No membership ledger is generated yet; no Cartesian hourly expected universe is generated.

## Guardrails
- New performance calculations: none.
- Costed calculations: none.
- Reject-family retune: none.
- 2026 outcomes: unopened/report-only.
- Production/main/Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist-builder/updater: untouched.
