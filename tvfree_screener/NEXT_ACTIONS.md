# TV-Free Screener — Next Actions

TEST ONLY. Execute top-to-bottom unless new evidence invalidates the next item. Keep `HANDOFF.md` synchronized.

## Guardrails
- Branch: `test/tvfree-screener-v1`; Draft PR #13 only.
- Never merge or modify `main` without explicit user Go.
- Never change production Discord/Spreadsheet writes, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater, or production workflows.
- Evaluation remains next-session-open -> horizon close and all model selection must be causal.
- 2026 is contaminated/reporting-only and must never be used for threshold/model tuning.

## 1. Re-run and inspect JPX live acceptance gate
Run #98 (`34550900449`, head `5f6207c93ca5fe464e90b9c69b8a8bb174924c82`) completed FAILURE. All synthetic checks, the fixed-start backtest, and latest scoring passed; the failure was isolated to `Live-validate JPX point-in-time membership reconstruction`, so all downstream live coverage / V3 / 2024 extension / V4 steps were skipped.

Post-#98 TEST-only fixes now on the branch:
- `ca93b8849d454aba775f91092b2a67ecaaf425e2`: deterministic UTF-8 decode plus required yearly archive URLs.
- `160adc5d2aa7a8fb659915a2fe5c7cc1948f7c6b`: handle JPX two-row listing markup without misreading four-character offer prices as security codes.
- `48210fb6b3e3e81d6e5b9ef348d086d7e535fa4a`: fail-closed live acceptance gate requiring no unknown-market rows, no same-day code collisions, and no missing event years.
- `1404952a30437a2651d80a29c61499defbd5da5f`: synthetic regressions for deterministic 2022+ archive generation and UTF-8/CP932 decoding.
- `b3be1f8fea2609e367b646c130d19219de396e79`: explicit/testable missing-event-year fail-closed helper and acceptance-rule text.
- `ef3e08221154b1c3b2b8e0d1a80ed8920be0615b`: regression for missing-year rejection and complete-year acceptance.
- `7518dc0af0e0027caa452b5221230e7faeb6c6c1`: TEST CI ignores Markdown-only research documentation updates, preventing mandatory handoff writes from cancelling the heavy validation run.

Current-head revalidation is run #110 (`34554098082`, head `7518dc0af0e0027caa452b5221230e7faeb6c6c1`). Runs #105-#108 were superseded/cancelled by later commits. Do not infer a JPX pass/fail until #110 produces the acceptance report.

Next run must verify all of the following before any survivorship-bias claim:
- `jpx_point_in_time_report.json` reports `valid_for_membership_reconstruction=true`;
- `unknown_market_rows == 0`;
- `same_day_code_collisions == 0`;
- `missing_event_years == []` for every required year from 2022 through the anchor year;
- temporal code reuse remains quarantined for Yahoo ticker identity.

If the gate fails, treat that as a data/parser blocker and do not weaken the gate to make the run green.

## 2. Measure Yahoo delisted-symbol coverage
Only after the JPX gate passes, inspect `yahoo_delisted_price_coverage_report.json` / CSV. Candidate universe is official TSE domestic delistings since 2022, with later code-reuse episodes quarantined. Keep transport/probe errors separate from genuine missing price history. Do not call results survivorship-bias-free until usable/partial/missing counts are measured.

## 3. Inspect independent 2024 extension and frozen 2025 invariance
Without changing thresholds/features/model hyperparameters, inspect 2024H1/H2 where causal training volume is sufficient and verify frozen 2025 outputs remain unchanged. Report unavailable periods rather than weakening minimum-training rules.

## 4. Inspect first blind V4 result
V4 protocol remains predeclared and blind:
1. expose 2024 development metrics for all four variants;
2. lock exactly one variant from 2024 only;
3. evaluate only that locked variant on 2025;
4. compute 2026 only if the locked variant passes the predeclared 2025 gate.

The global trading-calendar cooldown continuity fix and year-boundary synthetic test are already in place. Reject weak or one-regime methods rather than retuning.

## 5. Fundamental / dilution overlay
Live EDINET work remains blocked until `EDINET_API_KEY` is available as an environment/secret value. Never commit or log the key. Extracted warrant/share-count candidates remain audit evidence only until filing-table semantics are manually/live validated. Missing observations must remain explicit unknowns with coverage-matched baselines; never treat missing as healthy.

Initial dilution thresholds remain predeclared at 20%, 35%, 50%, and 100% potential shares / shares outstanding. Selection may use only 2024H1/H2 and 2025H1/H2; 2026 stays reporting-only. Valuation/PER-PBR remains deferred until point-in-time treasury-share and period-profit alignment is reliable.

## 6. Production integration — BLOCKED until user Go
Never automatically merge PR #13, alter production workflows, send production Discord, write production Spreadsheet, replace Stable★6/Sniper/Mega, or disable/change production TradingView/watchlist components.
