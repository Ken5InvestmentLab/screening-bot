# TV-Free Screener — Next Actions

TEST ONLY. Execute top-to-bottom unless new evidence invalidates the next item. Keep `HANDOFF.md` synchronized.

## 1. Preserve durable fixed-start baseline
Actions run `34545440155` is the first accepted fixed-start baseline and completed successfully with `2022-01-01 -> current` Yahoo history.

Do not retune from 2026. Run #80 remains the comparison baseline even though later research-contract hashes change as test-only validation code is added.

Key result:
- Short Core remains weak: 2025H1 +0.69%, 2025H2 +0.26% (5BD).
- Swing S old rolling advantage did not reproduce: 2025H1 -0.14%, 2025H2 +2.68% (10BD).
- therefore neither lane is accepted as a Stable★6 replacement yet.

## 2. Inspect current live TEST run #97 before changing workflow
Actions run `34549403943` (run #97), head `80a42fc9d98796e1e0f17becaff5df825a71542f`, is currently in progress.

Already PASS in that run:
- reproducibility self-test,
- causality self-test,
- point-in-time universe self-test,
- delisted Yahoo coverage self-test,
- fundamental/dilution overlay self-test,
- EDINET collector self-test,
- EDINET dilution-audit self-test.

At last inspection it was executing the fixed-start `Purged walk-forward backtest`. Do not cancel or supersede this run. When it completes, inspect:
- `jpx_point_in_time_report.json`,
- `jpx_membership_events.csv`,
- `yahoo_delisted_price_coverage_report.json`,
- `yahoo_delisted_price_coverage.csv`,
- independent 2024 extension outputs,
- reproducibility manifest.

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

## 5. Correct V4 stage-boundary cooldown before first performance run
`v4_event_quality_research.py` passed static causal review for its blind research order:
1. expose 2024 development metrics for all four predeclared variants,
2. lock exactly one variant from 2024 only,
3. evaluate only that locked variant on 2025,
4. compute 2026 only if the locked variant passes the predeclared 2025 gate.

Its half-year training purge is causal (`target5_end < prediction_period_start`). Existing `v4_event_quality_selftest.py` checks purge and ordinary cooldown semantics.

However `select_variant()` is invoked independently for development, validation, and reporting stages, resetting same-symbol cooldown at the 2024/2025 and 2025/2026 boundaries. This is an execution-rule inconsistency, not future leakage.

Before first V4 performance interpretation:
- preserve cooldown state across stage boundaries, or select the locked variant over concatenated chronological scored stages after the lock is established;
- add a synthetic test specifically spanning a half-year/year boundary;
- change no event thresholds, variant score weights, gates, or validation thresholds based on 2025/2026 outcomes.

After the active run #97 finishes, add the V4 self-test to the TEST workflow and only then add the V4 research step. Do not expose 2025 metrics for variants rejected by the 2024 lock.

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
