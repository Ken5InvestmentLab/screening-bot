# Core24 JPX PIT transfer-ledger parser contract — 2026-09-16 04:24 JST

## Scope
Research-only PIT provenance. No production/main/workflow/Discord/Spreadsheet/TradingView/watchlist changes.

## Immutable inputs
Use only artifact `10411777912` (`jpx-transfer-source.zip`, artifact digest `sha256:2d1b761e51a8cd70ba8501a5c1ed0df8a09ad4b17fa5456483967108728df7e7`). Transfer source SHA-256 values:
- 2024: `dcd590122107f5632d4880b3d58ab38605f0b5bd11e6df51a90c9d56d3c35f71`
- 2025: `ade2457928577e98849ac23dfb5779ea14600d4bb7d89d5a87f377b121319145`
- current: `85be65e0669f7a54891de41616715a5cebcc6d291f000487720ac1d067d53a2a`

## Deterministic transfer parser
Read the first HTML table with columns `Date`, `Issue Name1`, `Code`, `Market Segment`, `Previous Market Segment`. Parse each `Date` independently with exact English `Mon. DD, YYYY` semantics; do not rely on pandas vectorized mixed-format inference. Normalize each row to `(date, code, issue_name, from_segment, to_segment, source_name, source_sha256)`. Sort ascending by `(date, code, issue_name)` before hashing/receipt generation.

For reverse replay from the official `2026-08-31` anchor to `2024-09-17`, retain transfer dates `2024-09-17 <= date <= 2026-08-31`. Exact parse yields **81** transfer events: 2024 archive 5, 2025 archive 35, current 41. `277A Globe-ing Inc.` is present on `2026-04-30`, `Growth -> Prime`.

## Critical parser guard
A previous exploratory count of 75 transfer rows was caused by vectorized `pd.to_datetime(series, errors="coerce")` format inference: the first row's month format was inferred and valid rows with other month abbreviations became `NaT`. This count is invalid and must not be used. Parse row dates independently or with an explicitly mixed/exact-safe parser and assert the source-family counts above.

## 375 vs 395 forensic correction
Reparse the pinned listing/delisting pages with exact row semantics. The New Listings HTML uses rowspan-expanded paired rows; deduplicate/pair by listing date + issue name, extracting one code and one eligible segment. For `2024-09-17..2026-09-10`, exact counts are **134 listings + 241 delistings = 375**, matching the original 375-event receipt exactly. Therefore the later exploratory `395 = 134 + 261` claim is not supported by the immutable artifact and is superseded. Do not treat 375 as disproven on count grounds.

The remaining PIT blocker is not the 375 count. It is segment-state completeness: listing/delisting alone cannot reverse market-segment changes. Integrate the 81 transfer events, then perform conflict-checked reverse replay from the `2026-08-31` listed-issues anchor. Fail closed on impossible transitions, duplicate contradictory transitions, unknown segment labels, or identity conflicts.

## Cost policy
No performance calculation is introduced here. Any later backtest/portability statistics in this lane remain cost 0% only; win = gross return > 0.