# TV-Free Screener — Next Actions

TEST ONLY. Execute top-to-bottom unless new evidence invalidates the next item. Keep `HANDOFF.md` synchronized.

## 1. Preserve durable fixed-start baseline
Actions run `34545440155` is the first accepted fixed-start baseline and completed successfully with `2022-01-01 -> current` Yahoo history.

Do not retune from 2026. Run #80 remains the comparison baseline even though later research-contract hashes change as test-only validation code is added.

Key result:
- Short Core remains weak: 2025H1 +0.69%, 2025H2 +0.26% (5BD).
- Swing S old rolling advantage did not reproduce: 2025H1 -0.14%, 2025H2 +2.68% (10BD).
- therefore neither lane is accepted as a Stable★6 replacement yet.

## 2. Inspect replacement TEST run #98
Run #97 (`34549403943`) finished FAILURE only because live JPX parsing called `pandas.read_html()` without optional dependency `lxml`. The fixed-start backtest and all synthetic checks before that point had succeeded.

Fixes:
- `dcf6bef99e5ec113dcf8419801015b9a86c16e69`: add `lxml>=5,<7` to TEST requirements.
- `cda2a6c4090587dd1e0a37211bf62af02f35ab71`: preserve V4 cooldown state across development/validation/reporting stage boundaries.
- `7944d9ac0fbcb667924ac1b9924fc0093be9741a`: add synthetic 2024->2025 boundary regression test.
- `5f6207c93ca5fe464e90b9c69b8a8bb174924c82`: run V4 self-test and first blind V4 research in TEST workflow.

Replacement run #98:
- Actions run `34550900449`
- head `5f6207c93ca5fe464e90b9c69b8a8bb174924c82`
- currently in progress
- dependency installation including lxml PASS
- reproducibility, causality, point-in-time universe, delisted Yahoo coverage, fundamental/dilution, EDINET collector, EDINET dilution audit, and V4 cooldown self-tests PASS
- at last inspection: fixed-start Purged walk-forward backtest in progress

After completion inspect:
- `jpx_point_in_time_report.json`
- `jpx_membership_events.csv`
- `yahoo_delisted_price_coverage_report.json`
- `yahoo_delisted_price_coverage.csv`
- independent 2024 extension outputs
- `v4_event_quality_report.json`
- reproducibility manifest

Require zero unknown-market rows and zero same-day listing/delisting collisions before using reconstructed membership. Quarantine code-reuse identity ambiguity rather than joining it to Yahoo ticker history.

## 3. Missing-data safety — implemented, keep enforced
The fundamental overlay requires explicit coverage flags:
- `dilution_known`,
- `financial_known`,
- `combined_known`.

Unknown/invalid observations cannot pass filtered lanes. Every filter has a coverage-matched known baseline, and risk count/exclusion stays nullable when required facts are missing.

Never revert to `missing = healthy` semantics.

## 4. EDINET dilution audit — evidence only
`edinet_dilution_audit.py` extracts evidence from exact known dilution-related EDINET text blocks and records share-count candidates, source excerpts/hashes, and moving-strike/MS evidence.

Hard rule:
- every extracted number remains `accepted_remaining_potential_shares=False` until real historical filing table semantics are validated;
- do not use balance-sheet monetary `SubscriptionRightsToShares` as residual share count;
- do not infer financing/MS classification without source evidence.

The collector emits `edinet_dilution_evidence.csv` in addition to financial snapshots.

## 5. V4 stage-boundary cooldown — corrected before first performance run
The blind research order remains:
1. expose 2024 development metrics for all four predeclared variants,
2. lock exactly one variant from 2024 only,
3. evaluate only that locked variant on 2025,
4. compute 2026 only if the locked variant passes the predeclared 2025 gate.

The half-year training purge remains causal (`target5_end < prediction_period_start`).

Resolved implementation inconsistency:
- cooldown state now uses the global trading-calendar index and is carried from 2024 development into 2025 validation and, only after validation pass, into 2026 reporting;
- a dedicated synthetic test spans the 2024/2025 boundary and proves the reset failure mode would select a different symbol;
- V4 self-test is now required before heavy research in TEST workflow.

No event threshold, score weight, gate, model hyperparameter, or validation threshold changed. Do not expose 2025 metrics for variants rejected by the 2024 lock and never use 2026 to choose V4 settings.

## 6. Measure Yahoo delisted-symbol coverage
Use the TEST-only coverage probe from official delisting events:
- candidate universe = TSE domestic delistings since 2022,
- quarantine codes reused by a later issuer/listing episode,
- download historical daily data for remaining delisted tickers,
- record first/last Yahoo date, rows, whether prices exist near the official delisting date,
- report missing/partial/usable counts.

Do not claim survivorship-bias-free results until this coverage is measured and inspected.

## 7. Extend frozen technical reporting to 2024
Without changing thresholds/features/model hyperparameters or looking at 2026 for selection:
- use the independent 2024 extension to report 2024H1 and 2024H2 where causal training volume is sufficient,
- verify 2025 frozen outputs remain unchanged,
- compare 2024H1/H2 + 2025H1/H2 as four pre-2026 regimes.

If a period lacks enough causal training data, report it as unavailable rather than weakening the minimum-training rule.

## 8. Live EDINET validation and overlay comparison
Once `EDINET_API_KEY` is available:
- start with a small 2024/2025 sample,
- validate exact accounting element IDs/contexts and dilution text-block evidence,
- measure missing/ambiguous coverage,
- only promote warrant candidate numbers after manual/source-semantic validation,
- then compare coverage-matched baseline vs dilution/financial/combined overlays across 2024H1/H2 and 2025H1/H2.

Reject one-regime gains, severe sample shrinkage, missing-data artifacts, or unstable extraction.

## 9. Production integration — BLOCKED until user Go
Never automatically:
- merge PR #13 to `main`,
- change production screening-bot workflows,
- send production Discord,
- write production Spreadsheet,
- replace Stable★6/Sniper/Mega,
- disable or change production TradingView/watchlist builder/updater.
