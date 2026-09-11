# TradingView-Free Screener — Autonomous Handoff

TEST ONLY. Canonical handoff for scheduled runs and new chats.

## Safety guardrails
- Repository: `Ken5InvestmentLab/screening-bot`
- Working branch: `test/tvfree-screener-v1`
- Draft PR: #13
- NEVER merge to `main` without explicit user Go approval.
- NEVER modify production Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater, or production workflows without explicit user Go approval.
- Evaluate next-session-open -> horizon close.
- Training/selection must be causal.
- 2026 is contaminated/reporting-only and must not be used for threshold/model tuning.

## Goal
Replace the TradingView/Pine watchlist dependency with a free daily-OHLCV TSE common-stock system while remaining competitive with Stable★6. Weak or unstable methods must be rejected rather than tuned to look good.

## Durable fixed-start baseline
Actions run `34545440155` (run #80), head `5461eef6f35ea2cea2b4bc38ca7177c681681783`, remains the first accepted fixed-start baseline.

Verified contract:
- Yahoo history: `2022-01-01 -> current`
- current JPX domestic common-stock universe: 3,700 symbols
- OHLCV rows: 4,061,361
- rows through frozen cutoff 2026-08-31: 4,031,154
- runtime about 27m03s
- artifact 51,126,879 bytes (~48.8 MiB)

Frozen run-80 manifest hashes:
- universe `271033ea30220e1731537a2b453d2f5bfffb9fbc29d7d43a46f8efd1f9f54cbe`
- historical coverage `2686163d4e4342198590d34a8708c5c142a11441befdd74da3475bafd3e9a935`
- historical OHLCV `475ae6166ed21220aaa7f9f98d5bfff6c2d221bf1e3571b59fc6656758f453ab`
- Short Core `5fbb16417b3cd87afcbba824ada77d912124c9c623aba470a1f1fa849a9df757`
- Short defensive `063b9c63bda60c298feb84e8e3d0d5f935f46da9dbc5900ba297bac21fbc723d`
- Swing S `0907e351e914a278e9a41f57f627c7fdb6f10ca43301139c1ba14154b070ceac`
- research contract `63b40267f9cdc6018aab701f36f79b1e675b35350a0ac5e6c35532f4c6046058`

Later TEST-only validator/audit changes can change the research-contract hash; that is not market-data drift.

## Frozen V3 status
Short Core uses the same 45 features, monthly causal XGBoost, prediction-day percentile normalization, Core `r_top10 - 2*r_loss10`, and next-open -> 5BD.
- 2025H1: n=119, mean +0.69%, median +0.45%, win 55.5%, +10% 3.36%, -10% 2.52%.
- 2025H2: n=124, mean +0.26%, median +0.58%, win 53.2%, +10% 0%, -10% 0%.
- 2026 Mar-Aug reporting-only: n=124, mean +0.015%, median -0.13%, win 47.6%, +10% 1.61%, -10% 0.81%.
Short Attack remains none/unaccepted.

Swing S frozen architecture is MomCross -> causal semiannual quality model -> training empirical CDF -> Breadth Meta -> `score_R >= 0.20`, next-open -> 10BD.
- 2025H1: n=36, mean -0.14%, median -1.96%, win 36.1%, +10% 11.1%, -10% 2.78%.
- 2025H2: n=24, mean +2.68%, median +0.90%, win 54.2%, +10% 12.5%, -10% 0%.
- 2026 Mar-Aug reporting-only: n=27, mean +0.017%, median 0%, win 48.1%, +10% 7.41%, -10% 7.41%.
The old rolling Swing advantage did not reproduce under the fixed-start contract, so neither V3 lane is accepted as a Stable★6 replacement.

## Fundamental / dilution research
TEST-only collectors/evaluators exist with strict causal availability fields (`available_at` / `available_date`, `doc_id`) and missing-data flags (`dilution_known`, `financial_known`, `combined_known`). Unknown rows cannot pass filtered lanes; every filter must be compared with a coverage-matched known baseline.

Historical dilution extraction is audit-first. Balance-sheet monetary `SubscriptionRightsToShares` is NOT the residual potential-share count needed for dilution filtering. Extracted warrant/share-count candidates remain `accepted_remaining_potential_shares=False` until real filing-table semantics are validated. Initial dilution thresholds remain predeclared at 20%, 35%, 50%, 100%; do not select among them using 2026.

Live EDINET acquisition is blocked on `EDINET_API_KEY`; the key must stay env/secret-only and never be committed/logged. Valuation/PER-PBR remains deferred until point-in-time treasury-share/share-count alignment and duration-period profit semantics are reliable.

## V4 event-quality protocol
`v4_event_quality_research.py` is TEST-only: broad OHLCV event union -> causal 3-head half-year models -> train-CDF normalization -> four predeclared score/gate variants.

Blind order is fixed:
1. expose 2024 development metrics for all four variants;
2. lock exactly one variant from 2024 only;
3. evaluate only that locked variant on 2025;
4. score 2026 only if the locked variant passes the predeclared 2025 gate.

Training purge requires `target5_end < prediction_period_start`. Global trading-calendar cooldown state now carries across 2024 -> 2025 -> conditional 2026, with a synthetic year-boundary regression test. Never inspect rejected variants' 2025 results or use 2026 to tune V4.

## Run #98 result and JPX blocker
Replacement Actions run `34550900449` (run #98), head `5f6207c93ca5fe464e90b9c69b8a8bb174924c82`, completed FAILURE.

Confirmed PASS before failure:
- dependency install including lxml
- reproducibility / causal-entry / point-in-time synthetic checks
- Yahoo delisted-coverage synthetic check
- fundamental/dilution and EDINET synthetic checks
- V4 cooldown self-test
- fixed-start Purged walk-forward backtest
- latest-session scoring

Failure was isolated to `Live-validate JPX point-in-time membership reconstruction`; downstream Yahoo delisted coverage, V3 reruns, 2024 extension, and blind V4 were skipped. Therefore no new model-performance conclusion was accepted from #98.

Post-#98 TEST-only fixes now on the branch:
- `ca93b8849d454aba775f91092b2a67ecaaf425e2`: deterministic UTF-8 decode and deterministic yearly archive URL generation.
- `160adc5d2aa7a8fb659915a2fe5c7cc1948f7c6b`: support JPX two-row issuer markup; do not mistake four-character offer prices for security codes.
- `48210fb6b3e3e81d6e5b9ef348d086d7e535fa4a`: fail closed unless unknown-market rows=0, same-day code collisions=0, and every required event year is present.
- `1404952a30437a2651d80a29c61499defbd5da5f`: add synthetic regressions for deterministic 2022+ archive generation and UTF-8/CP932 decoding.
- `edaf96d05455352c27aa657f3f7d410e2fcfac18`: synchronize next-action documentation.

These fixes do not change event thresholds, score weights, model hyperparameters, 2026 selection rules, production code, or production writes.

## Acceptance gate before survivorship claims
A future TEST run must show all of the following before reconstructed membership is trusted:
- `valid_for_membership_reconstruction=true`
- `unknown_market_rows == 0`
- `same_day_code_collisions == 0`
- `missing_event_years == []` from 2022 through the anchor year
- temporal code reuse identified and quarantined for Yahoo ticker identity

Do not weaken this gate to obtain a green run. Never call results survivorship-bias-free until official delisting events are reconstructed and Yahoo usable/partial/missing historical-price coverage is measured.

## Current blockers
1. JPX live parser/acceptance gate has not yet been revalidated after the post-#98 fixes.
2. Yahoo delisted-symbol price coverage remains pending until the JPX gate passes.
3. First independent 2024 extension and first blind V4 performance result remain pending because #98 stopped upstream.
4. Live EDINET validation requires `EDINET_API_KEY`.
5. Existing fixed-start Short/Swing performance remains materially below Stable★6 historical reference.

## Next concrete task
Re-run the TEST workflow on the current branch and inspect the JPX acceptance report first. If and only if it passes, inspect Yahoo delisted-price coverage, independent 2024 extension, and the first blind V4 report. Reject weak/unstable findings; never retune from 2026. Production integration remains blocked until explicit user Go.
