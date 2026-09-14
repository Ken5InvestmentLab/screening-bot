# EDINET metadata acquisition spec — 2026-09-14

Status: **research-only / outcome-blind / pre-parser**.

## Purpose

Materialize the exact daily EDINET document-list JSON bytes needed by the frozen 2023-01-01..2025-12-31 metadata snapshot contract. This acquisition layer is upstream of `edinet_metadata_snapshot.py` and is not allowed to select filings or inspect parser/accounting/strategy outcomes.

## Official API contract

Use EDINET API v2 `https://api.edinet-fsa.go.jp/api/v2/documents.json` with required query parameters:

- `date=YYYY-MM-DD`
- `type=2`
- `Subscription-Key=<API key>`

The API key must come from an external environment variable. It must not be committed, logged, embedded in artifacts, or copied into research receipts.

## Frozen acquisition behavior

- one raw response file per calendar day, named `YYYY-MM-DD.json`;
- atomic temp-file replacement for newly fetched files;
- existing day files are skipped by default so interrupted runs resume without silent byte replacement;
- malformed JSON/object shape, missing `results` list, or EDINET metadata status other than 200 fails closed;
- no parser facts, accounting values, selected doc IDs, strategy labels/returns/scores, or 2026 outcomes may influence acquisition;
- acquisition completion alone is **not** acceptance. All 2023-2025 calendar days must subsequently pass `edinet_metadata_snapshot.py` full-period coverage and hash-chain freezing before the frozen selector can run.

## Implementation

- `tvfree_screener/edinet_metadata_acquire.py`
- `tvfree_screener/test_edinet_metadata_acquire.py`
- isolated CI: `OSS validation tooling TEST`

## Next boundary

After the full raw daily set exists, freeze the metadata snapshot receipt and normalized CSV first. Only then run the preregistered selector once, freeze selected doc IDs, fetch identical XBRL-to-CSV ZIP bytes, freeze ZIP SHA256 values, and open the custom-vs-edinet-tools same-ZIP comparison.
