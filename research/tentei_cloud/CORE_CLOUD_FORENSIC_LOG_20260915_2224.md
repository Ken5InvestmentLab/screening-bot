# Core + Cloud forensic log — 2026-09-15 22:24 JST

## Start-state reconciliation
- Coordination STATE v92 marks Core HEAD `80bcd6c14cd3dcc7254f934af195eaf9d7e6d084` processed.
- Actual Core HEAD matched that SHA at run start, so no processed work was repeated.
- P0 remained official-JPX anchor universe bytes/SHA -> deterministic PIT membership receipt.
- Cloud exact forensic remains CLOSED: `HISTORICAL_EXACT_REPRO_UNAVAILABLE`; no model-family guessing reopened.

## Core24 advance
JPX official `List of TSE-listed Issues` page states that the previous-month-end issue list is published and the Excel file is sequentially updated. This gives a source-grounded current/end-of-month anchor route rather than inferring membership from Yahoo observations.

Updated `capture_jpx_pit_sources.py` to byte-pin the official listed-issues publication page itself in addition to the six already-pinned listing/delisting pages. Push commit `8c11ebfe1dc6122668acade4eea6480980f68af6` triggered Actions run `34974570085`; run was in progress when this log was written.

The next deterministic step is: collect the run artifact, parse the pinned page only to discover the workbook href, capture the workbook bytes/SHA, then use that official anchor plus the frozen event ledger. Prefer reverse replay from a later official anchor when it avoids inventing a window-start universe. Any workbook/date mismatch or event conflict remains fail-closed/quarantined.

## Guardrails
- No production/main/workflow/Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist-builder/updater changes.
- No new performance/backtest calculations; therefore no costed result was produced.
- Existing reject families were not retuned/reopened.
- 2026 outcome remains report-only.
