# TV-Free Screener — Next Actions

TEST ONLY. Execute top-to-bottom unless new evidence invalidates the next item. Keep `HANDOFF.md` synchronized.

## 1. Finish the first genuinely running fixed-start verification
Actions runner allocation recovered. Run `34545440155` on commit `5461eef6f35ea2cea2b4bc38ca7177c681681783` reached checkout and all five synthetic safety checks passed. At the latest observation, `Purged walk-forward backtest` was still in progress.

Do not disturb or reinterpret this run. When it completes:
- require overall success before freezing a durable baseline,
- verify `Yahoo history mode: fixed start 2022-01-01 -> current`,
- inspect Short/Swing/comparison outputs and `reproducibility_manifest.json`,
- record research-contract, universe, historical coverage, OHLCV, and output hashes,
- record runtime and artifact size,
- keep all model thresholds frozen and treat 2026 as reporting-only.

If it fails after executable steps, use the actual failing step/log as evidence; do not assume the old runner-allocation cause.

## 2. Correct missing-data semantics in fundamental overlay BEFORE performance tests
Current `fundamental_overlay.py` has an uncovered data-quality bug: missing financial facts can produce False risk flags, `financial_risk_count=0`, and pass `financial_risk_filter` as if healthy.

Required test-only correction:
- add explicit `dilution_known`, `financial_known`, `combined_known`,
- make risk count/exclusion unknown when required data is incomplete,
- never convert missing into healthy,
- retain an explicit unknown population rather than silently excluding it,
- add coverage-matched baselines for every filtered comparison,
- extend `fundamental_overlay_selftest.py` so fully missing rows cannot pass as known-safe.

This is a data-quality/causality fix only. Do not change thresholds based on performance.

## 3. Live-validate point-in-time EDINET accounting ingestion
Implementation exists in `edinet_fundamental_collector.py`. Use `EDINET_API_KEY` only from environment/secret; never commit or log it.

First use a small pre-2026 sample and measure:
- selected document IDs and form types,
- exact XBRL element IDs/contexts used,
- shares outstanding, assets, equity, revenue, operating income, net income, operating CF coverage,
- missing and ambiguous rates,
- `available_at`/`available_date` correctness.

Do not broaden aliases merely to improve backtest results. Conservative default remains `prior_day_only`; same-day data requires explicit `decision_at` and `available_at` timestamps.

## 4. Build historical dilution extraction as a separate collector
Do NOT use the balance-sheet monetary account `SubscriptionRightsToShares` as a proxy for residual dilution shares.

Target EDINET section/table: `新株予約権等の状況` and related exercise-price-reset disclosures.

Normalized outputs should retain:
- remaining potential shares across all relevant warrants/options,
- financing-type remaining potential shares when deterministically identifiable,
- MS/exercise-price-reset remaining potential shares when deterministically identifiable,
- warrant/instrument type,
- fiscal-year-end versus filing-preceding-month-end values when separately disclosed,
- source `doc_id`, member/table/evidence,
- `available_at`, `available_date`, extraction status/confidence.

Temporal rule: a newer value stated as filing-preceding-month-end is not market-available at that month-end unless separately disclosed then; when learned from the filing, it becomes usable only at the filing's public availability time.

Initial dilution threshold grid remains predeclared: 20%, 35%, 50%, 100% potential shares / shares outstanding. Never select a threshold using 2026.

## 5. Require coverage-matched overlay comparisons
Once accounting/dilution coverage is acceptable, keep Short/Swing technical architecture frozen and compare on 2024H1, 2024H2, 2025H1, 2025H2:
- technical baseline,
- dilution-known baseline vs dilution filter,
- financial-known baseline vs financial-risk filter,
- combined-known baseline vs combined filter,
- valuation only later if point-in-time accounting/share alignment is reliable.

Acceptance requires mean, median, win rate, +10% rate, -10% rate, and retained sample size. Reject:
- one-regime improvements,
- severe sample shrinkage,
- gains caused by excluding missing-data rows,
- unstable extraction coverage.

2026 is reporting-only.

## 6. Point-in-time universe and delisted-price validation
Continue existing work:
- validate official JPX listing/delisting parser,
- require zero unresolved market rows/collisions before use,
- measure Yahoo historical coverage for reconstructed delisted members,
- never claim survivorship-bias-free results if delisted prices are materially missing.

## 7. Valuation scoring only after reliable accounting
Potential later metrics:
- PBR from signal-date market cap / latest causally available equity,
- PER only for positive causally available earnings,
- cash/market-cap or EV-style measures if coverage is stable.

Never use present-day valuation values in historical rows.

## 8. Production integration — BLOCKED until user Go
Never automatically:
- merge PR #13 to `main`,
- change production screening-bot workflows,
- send production Discord,
- write production Spreadsheet,
- replace Stable★6/Sniper/Mega,
- disable or change production TradingView/watchlist builder/updater.
