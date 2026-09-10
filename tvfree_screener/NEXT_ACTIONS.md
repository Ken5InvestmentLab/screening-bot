# TV-Free Screener — Next Actions

TEST ONLY. Execute top-to-bottom unless new evidence invalidates the next item. Keep `HANDOFF.md` synchronized.

## 1. Observe runner blocker without changing model semantics
Recent PR-triggered jobs still fail before executable steps. Re-check only opportunistically. Never touch production workflows or model thresholds as a workaround.

## 2. Require all synthetic safety checks before heavy research
The test workflow must first pass:
- `reproducibility_selftest.py`,
- `causality_selftest.py`,
- `point_in_time_universe_selftest.py`,
- `fundamental_overlay_selftest.py`.

## 3. Build point-in-time EDINET snapshot ingestion
Goal: normalized historical snapshots keyed by `symbol` + `available_date`, where `available_date` is the filing/public date visible to the market.

Initial standardized fields:
- shares outstanding,
- assets,
- equity,
- revenue,
- operating income,
- net income,
- operating cash flow.

Requirements:
- use EDINET API v2 only in TEST path,
- require `EDINET_API_KEY` from environment/secrets; never commit the key,
- retain document id, filing date, period end, and source provenance,
- never backfill later filings into earlier signal dates,
- emit requested/usable/missing-field coverage diagnostics.

## 4. Prototype historical dilution extraction separately
Target normalized fields:
- remaining warrant/new-share-option potential shares,
- instrument type,
- MS-warrant / exercise-price-reset flag where deterministically identifiable,
- source filing/document id,
- public availability date,
- extraction confidence/coverage status.

Do not call a company dilution-safe when the source is missing. Missing must remain missing.

Predeclared dilution comparison grid in `fundamental_overlay.py`:
- 20%, 35%, 50%, 100% remaining potential shares / shares outstanding.
Do not select a threshold using 2026.

## 5. Validate financial-risk overlay before valuation scoring
Transparent first-pass risk flags:
- equity ratio < 10%,
- operating loss,
- net loss,
- negative operating CF,
- exclusion candidate when at least two risk flags are present.

These are research lanes only, not accepted production rules. Missing values must not be silently treated as healthy.

## 6. Add valuation only after point-in-time accounting is reliable
Potential later metrics:
- PBR from signal-date market cap / latest publicly available equity,
- PER only for positive earnings and causally available earnings,
- cash/market-cap or EV-style measures if field coverage is stable.
Avoid current-day valuation data in historical rows.

## 7. Backtest overlays only after coverage gates pass
Keep Short/Swing technical architecture frozen. Compare separately on 2024H1, 2024H2, 2025H1, 2025H2:
- technical baseline,
- dilution filter,
- financial-risk filter,
- combined dilution + financial risk,
- later valuation score if data quality is adequate.

Acceptance must consider mean, median, win rate, +10% rate, -10% rate, and retained sample size. Reject one-regime improvements, severe sample shrinkage, and gains caused by missing-data filtering. 2026 is reporting-only.

## 8. Point-in-time universe and delisted-price validation
Continue existing work:
- validate official JPX listing/delisting parser,
- require zero unresolved market rows/collisions before use,
- measure Yahoo historical coverage for reconstructed delisted members,
- never claim survivorship-bias-free results if delisted prices are materially missing.

## 9. Confirm fixed-start history and freeze durable baseline
When a hosted runner actually starts:
- require `Yahoo history mode: fixed start 2022-01-01 -> current`,
- retain all diagnostics/artifacts,
- freeze Short Core / defensive / frozen Swing S metrics and manifest hashes,
- keep Short Attack = none and Swing A = none unless separate pre-2026 evidence later supports them.

## 10. Production integration — BLOCKED until user Go
Never automatically merge PR #13, change main, send production Discord, write production Sheets, replace Stable★6/Sniper/Mega, or disable TradingView/watchlist tooling.
