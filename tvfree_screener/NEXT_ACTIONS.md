# TV-Free Screener — Next Actions

TEST ONLY. Execute top-to-bottom unless new evidence invalidates the next item. Keep `HANDOFF.md` synchronized.

## 1. Preserve durable fixed-start baseline
Actions run `34545440155` is the first accepted fixed-start baseline and completed successfully with `2022-01-01 -> current` Yahoo history.

Do not retune from 2026. Run #80 remains the comparison baseline even though later research-contract hashes change as test-only validation code is added.

Key result:
- Short Core remains weak: 2025H1 +0.69%, 2025H2 +0.26% (5BD).
- Swing S old rolling advantage did not reproduce: 2025H1 -0.14%, 2025H2 +2.68% (10BD).
- therefore neither lane is accepted as a Stable★6 replacement yet.

## 2. Missing-data safety — implemented, keep enforced
The fundamental overlay now requires explicit coverage flags:
- `dilution_known`,
- `financial_known`,
- `combined_known`.

Unknown/invalid observations cannot pass filtered lanes. Every filter has a coverage-matched known baseline, and risk count/exclusion stays nullable when required facts are missing.

Current CI run #90 has already passed the synthetic fundamental/dilution self-test. Never revert to `missing = healthy` semantics.

## 3. EDINET dilution audit — evidence only
`edinet_dilution_audit.py` now extracts evidence from exact known dilution-related EDINET text blocks and records share-count candidates, source excerpts/hashes, and moving-strike/MS evidence.

Hard rule:
- every extracted number remains `accepted_remaining_potential_shares=False` until real historical filing table semantics are validated;
- do not use balance-sheet monetary `SubscriptionRightsToShares` as residual share count;
- do not infer financing/MS classification without source evidence.

The collector now emits `edinet_dilution_evidence.csv` in addition to financial snapshots. Current CI run #90 has passed both collector and dilution-audit synthetic tests.

## 4. Live-validate JPX point-in-time universe
Run #90 includes live parsing of official JPX listing/delisting archives after the fixed-history cache is built.

When it finishes:
- inspect `jpx_point_in_time_report.json`,
- require zero unknown-market rows and zero same-day collisions before using reconstructed membership,
- identify temporal code reuse separately; code identity reuse must be quarantined rather than silently joined to Yahoo ticker history.

## 5. Measure Yahoo delisted-symbol coverage
Build a TEST-only coverage probe from official delisting events:
- candidate universe = TSE domestic delistings since 2022,
- quarantine codes reused by a later issuer/listing episode,
- download historical daily data for remaining delisted tickers,
- record first/last Yahoo date, rows, whether prices exist near the official delisting date,
- report missing/partial/usable counts.

Do not claim survivorship-bias-free results until this coverage is measured.

## 6. Extend frozen technical reporting to 2024
Without changing thresholds/features/model hyperparameters or looking at 2026 for selection:
- add 2024H1 and 2024H2 prediction/report periods to Short Core and Swing S where causal training volume is sufficient,
- verify 2025 outputs remain unchanged under the same data contract,
- compare 2024H1/H2 + 2025H1/H2 as four pre-2026 regimes.

If a period lacks enough causal training data, report it as unavailable rather than weakening the minimum-training rule.

## 7. Live EDINET validation and overlay comparison
Once `EDINET_API_KEY` is available:
- start with a small 2024/2025 sample,
- validate exact accounting element IDs/contexts and dilution text-block evidence,
- measure missing/ambiguous coverage,
- only promote warrant candidate numbers after manual/source-semantic validation,
- then compare coverage-matched baseline vs dilution/financial/combined overlays across 2024H1/H2 and 2025H1/H2.

Reject one-regime gains, severe sample shrinkage, missing-data artifacts, or unstable extraction.

## 8. Production integration — BLOCKED until user Go
Never automatically:
- merge PR #13 to `main`,
- change production screening-bot workflows,
- send production Discord,
- write production Spreadsheet,
- replace Stable★6/Sniper/Mega,
- disable or change production TradingView/watchlist builder/updater.
