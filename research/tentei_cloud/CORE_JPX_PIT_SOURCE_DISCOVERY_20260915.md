# Core24 official-JPX PIT source discovery — 2026-09-15 12:25 JST

## Status
SOURCE ROUTE IDENTIFIED / BYTES NOT YET CORE-PINNED / PERFORMANCE UNOPENED.

This is research-only provenance work. No production/main, production workflow, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater, candidate logic, or strategy performance was changed/read.

## Official source route verified
Fresh JPX web verification identified three official source families suitable for the point-in-time membership layer:

1. TSE listed-issues statistics page
   - `https://www.jpx.co.jp/markets/statistics-equities/misc/01.html`
   - JPX states that it publishes the TSE listed-issues list as of the latest month-end.
   - JPX also states that the JPxData Portal all-issues CSV exposes each issue's TSE listing date and includes delisted issues from the latest one year.

2. TSE New Listings archive
   - `https://www.jpx.co.jp/english/listing/stocks/new/`
   - archive exposes listing date, issue name, code and market segment.

3. TSE List of Delisted Companies archive
   - `https://www.jpx.co.jp/english/listing/stocks/delisted/`
   - archive exposes delisting date, issue name, code, market segment and reason.
   - JPX states data more than 11 years old is unavailable on that page, which is sufficient for the recovered 2024-09 through 2026-09 raw1H period.
   - JPX additionally points to Monthly Statistics Report / Changes in Listed Companies and Issues for historical monthly changes.

Official monthly Changes in Listed Companies and Issues PDFs were also found and expose New Listings / Delisting events by date and code, providing an independent official cross-check route.

## Adoption decision
These URLs establish that an official-JPX PIT reconstruction route exists, but **do not yet satisfy the Core byte-pin requirement**. Formal Core adoption remains CLOSED until the exact downloaded input bytes covering the recovered raw1H period are saved/hashed and a deterministic reconstruction receipt is produced.

Do not substitute current membership for historical membership. Do not infer listing/delisting boundaries from Yahoo first/last observations. Code reuse / same-day conflicts / ambiguous segment identity remain quarantine/fail-closed cases.

## Next action
Acquire and SHA-256 pin the exact official JPX inputs required for 2024-09-17 through 2026-09-10, preferably:
- a pinned JPxData Portal all-issues CSV snapshot for listing dates/current identity;
- official new-listing/delisting archive exports or monthly Changes PDFs for event coverage and cross-check;
- deterministic normalized PIT membership output + receipt.

Only after that layer PASSes should Core search/freeze independent exact-hour activity evidence. Cartesian `membership × session × hour` expected keys remain forbidden.

## Cloud exact forensic
Remains `HISTORICAL_EXACT_REPRO_UNAVAILABLE`. No new identity-critical primary evidence was found in this run; no model-family guessing or surrogate retune was performed.

## Cost/outcome guard
No backtest was run. Any later newly computed forensic/backtest/portability statistics use transaction cost 0% only; win = gross return > 0; 2026 outcome remains report-only.
