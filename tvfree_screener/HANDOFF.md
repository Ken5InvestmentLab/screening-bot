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
- 2026 is contaminated and must not be used for threshold/model tuning.

## Goal
Replace TradingView/Pine watchlist dependency with a free daily-OHLCV TSE common-stock system while remaining competitive with Stable★6. Fundamental/dilution overlays are research-only and may be accepted only if pre-2026 evidence is robust.

## Runner / fixed-start status
- GitHub Actions runner allocation recovered after the repository was made public. TEST workflow commit `5461eef6...` restored normal research PR triggers; concurrency cancels obsolete duplicate runs.
- First durable fixed-start pipeline: Actions run `34545440155`, head `5461eef6f35ea2cea2b4bc38ca7177c681681783`, overall SUCCESS.
- Fixed Yahoo contract was verified as `2022-01-01 -> current`; 3,700 current JPX domestic common stocks produced 4,061,361 OHLCV rows, with 4,031,154 rows through the frozen 2026-08-31 historical cutoff.
- Runtime was about 27m03s; artifact size 51,126,879 bytes (~48.8 MiB).
- Manifest v3 fixed-start hashes from run #80:
  - universe: `271033ea30220e1731537a2b453d2f5bfffb9fbc29d7d43a46f8efd1f9f54cbe`
  - historical date/symbol coverage: `2686163d4e4342198590d34a8708c5c142a11441befdd74da3475bafd3e9a935`
  - historical OHLCV: `475ae6166ed21220aaa7f9f98d5bfff6c2d221bf1e3571b59fc6656758f453ab`
  - Short Core: `5fbb16417b3cd87afcbba824ada77d912124c9c623aba470a1f1fa849a9df757`
  - Short defensive: `063b9c63bda60c298feb84e8e3d0d5f935f46da9dbc5900ba297bac21fbc723d`
  - Swing S: `0907e351e914a278e9a41f57f627c7fdb6f10ca43301139c1ba14154b070ceac`
  - research contract: `63b40267f9cdc6018aab701f36f79b1e675b35350a0ac5e6c35532f4c6046058`
- These hashes belong to the frozen run-#80 research contract. Later overlay/audit changes intentionally change the research-contract hash and must not be mistaken for market-data drift.

## Reproducibility / universe
- Manifest v3 fingerprints research code/config, current JPX universe, historical date/symbol coverage, historical OHLCV, and Short/Swing outputs.
- Point-in-time universe prototype: `d2e66370d237edd94880fd9f8a6e740ed9332d5a`; synthetic test: `bea62cb1d1847409e84d1e63b2c08038db435765`.
- Official JPX listing/delisting archives make historical membership reconstruction plausible, but live parser validation and Yahoo delisted-symbol price coverage are still pending.
- Never call results survivorship-bias-free until delisted historical price coverage is measured.

## V3 Short
- Same 45 features, monthly causal XGBoost, prediction-day percentile normalization, Core `r_top10 - 2*r_loss10`, next-open -> 5BD.
- Recent-outcome Meta rejected; Attack none/unaccepted.
- Durable fixed-start run #80: 2025H1 n=119 mean +0.69%, median +0.45%, win 55.5%, +10% 3.36%, -10% 2.52%; 2025H2 n=124 mean +0.26%, median +0.58%, win 53.2%, +10% 0%, -10% 0%.
- 2026 Mar-Aug reporting-only side report: n=124 mean +0.015%, median -0.13%, win 47.6%, +10% 1.61%, -10% 0.81%.
- The old rolling-3y snapshot (+0.46% / +0.35%) remains historical context only; fixed-start run #80 is the durable numeric baseline.

## V3 Swing
- Frozen architecture: MomCross -> causal semiannual quality model -> training empirical CDF -> Breadth Meta -> `score_R >= 0.20`.
- Do not retune from 2026 or the old rolling-window threshold sweep.
- Durable fixed-start run #80 at the unchanged frozen threshold 0.20: 2025H1 10BD n=36 mean -0.14%, median -1.96%, win 36.1%, +10% 11.1%, -10% 2.78%; 2025H2 n=24 mean +2.68%, median +0.90%, win 54.2%, +10% 12.5%, -10% 0%.
- 2026 Mar-Aug reporting-only 10BD: n=27 mean +0.017%, median 0%, win 48.1%, +10% 7.41%, -10% 7.41%.
- The old rolling +6% regime did not reproduce under the fixed-start contract. Swing S is therefore NOT accepted as durable Stable★6 replacement evidence. Do not retune from 2026.
- Swing A remains none/unaccepted.

## Dilution / fundamental overlay
User requested testing whether large outstanding stock-acquisition-right dilution and weak/expensive fundamentals explain differences among otherwise similar technical signals.

Implemented TEST-only:
- `fundamental_overlay.py` `a5dbe1ca4398903327a9c84fb5a1cbee19c6459c`
- `fundamental_overlay_selftest.py` `860eed55ba8c47427f46ede4cf205fef3b80916f`
- `edinet_fundamental_collector.py` `5fc14fb5f238da7cd8284e2ee251f5db94fb107d`
- EDINET collector self-test `34a44f006f67c26cecb63eaeefa1dff37a7e4cfc`
- workflow / research-contract integrations already present.

Causal policy:
- every accounting/dilution observation must retain `available_at` / `available_date` and source `doc_id`;
- conservative default is `prior_day_only` when signals have dates only;
- same-day filing data may be used only with an explicit signal `decision_at` and filing `available_at`;
- current data must never be backfilled into earlier signals.

### Missing-data safety correction
Implemented after freezing run #80:
- explicit `dilution_known`, `financial_known`, and `combined_known` flags;
- nullable financial risk flags/count/exclusion when required facts are incomplete;
- unknown rows are separated into explicit unknown lanes and cannot pass filtered lanes;
- every filter has a coverage-matched known baseline;
- invalid negative remaining-warrant shares fail closed;
- persisted MS-warrant boolean strings are parsed without turning unknown into False.
Synthetic coverage is included in the current CI run; no thresholds were changed.

No threshold should change as part of this fix.

## Historical dilution extraction design
Research confirmed that balance-sheet `新株予約権` / `SubscriptionRightsToShares` is a monetary equity account and is NOT the residual potential-share count needed for dilution filtering.

An audit-first deterministic extractor exists in `edinet_dilution_audit.py`. It scans only exact known EDINET dilution-related text blocks, extracts nearby share-count tokens with source excerpts/hashes, marks moving-strike/MS evidence, and deliberately sets `accepted_remaining_potential_shares=False` for every candidate until real filing table semantics are validated.

Historical dilution still needs promotion from audit evidence to accepted residual-share facts only after live validation. At minimum store separately:
- remaining potential shares, all warrant/options;
- financing-type potential shares where deterministically classifiable;
- exercise-price-reset / MS-warrant potential shares where deterministically identifiable;
- instrument type and source row/table evidence;
- fiscal-period-end value versus filing-preceding-month-end value when both are disclosed;
- `doc_id`, `available_at`, `available_date`, extraction status/confidence.

Important temporal rule: a filing may show both fiscal-year-end and filing-preceding-month-end warrant counts. The newer bracket/preceding-month-end value becomes usable by the model only when the filing itself becomes public; it must not be backdated to that month-end.

Initial dilution comparison grid remains predeclared at 20%, 35%, 50%, 100% remaining potential shares / shares outstanding. Do not select among them using 2026.

## Fundamental overlay acceptance protocol
Once historical coverage is acceptable, compare on 2024H1, 2024H2, 2025H1, 2025H2 only for selection:
- technical baseline;
- dilution filter;
- financial-risk filter;
- combined dilution + financial risk;
- valuation only later if point-in-time accounting/share alignment proves reliable.

Acceptance must include mean, median, win rate, +10%, -10%, and retained sample size. Reject one-regime improvement, severe sample shrinkage, and any gain caused by missing-data selection. 2026 remains reporting-only.

## V4 event-quality research audit
- `v4_event_quality_research.py` is a TEST-only stronger technical architecture: broad OHLCV event union -> causal 3-head half-year models -> train-CDF normalization -> one of four predeclared score/gate variants.
- Static audit in this run confirmed the intended blind order is implemented: only 2024 development predictions/metrics are exposed for all variants; one variant is locked from 2024; only that locked variant is evaluated on 2025; 2026 is not scored unless the locked variant passes the predeclared 2025 validation gate.
- Training purge is causal: each half-year uses only rows with `target5_end < prediction_period_start`.
- `v4_event_quality_selftest.py` already checks purge behavior, selection-day cooldown, missing-calendar fail-closed behavior, and deterministic 2025 gate logic; it is included in the research-contract hash.
- New static-audit finding: `select_variant()` is called separately for development, validation, and 2026 stages, so its in-memory same-symbol cooldown state resets at stage boundaries. This is NOT future leakage and should not materially drive broad results, but it is an execution-rule inconsistency at 2024/2025 and 2025/2026 boundaries. Fix/test this before first V4 performance run; do not use the fix to tune thresholds.
- Do not open/reject variants based on 2025 metrics other than the one locked from 2024, and never use 2026 to choose V4 settings.

## Current live TEST run
- Actions run `34549403943` (run #97), head `80a42fc9d98796e1e0f17becaff5df825a71542f`, is in progress.
- All currently scheduled synthetic checks through EDINET dilution audit have passed, including reproducibility, causality, point-in-time universe, delisted Yahoo coverage, fundamental/dilution overlay, EDINET collector, and dilution-audit tests.
- At last inspection, run #97 was in `Purged walk-forward backtest`; live JPX point-in-time parsing and Yahoo-delisted coverage steps were still pending.
- Do not modify the active test workflow in a way that cancels this run; wait for its live universe/coverage artifacts before interpreting survivorship-bias risk.

## Current blockers
1. Live EDINET acquisition still needs `EDINET_API_KEY`; the key must remain env/secret-only and never be committed/logged.
2. Audit evidence has not yet been live-validated enough to promote any warrant share-count candidate to accepted residual dilution.
3. Point-in-time JPX live parser validation and delisted-symbol Yahoo price coverage are being exercised by run #97 and must be inspected after completion.
4. Existing Short/Swing fixed-start results remain materially below Stable★6 historical reference; new research must improve pre-2026 robustness rather than tune to 2026.
5. V4 cooldown continuity across half-year stage boundaries must be corrected before first performance interpretation.

## Next concrete tasks
1. Inspect run #97 after completion. Require live JPX parser diagnostics and Yahoo delisted-price coverage results before any point-in-time backtest claim.
2. Correct V4 selection cooldown continuity across development/validation/reporting stage boundaries and extend its synthetic test before first V4 performance run.
3. Add V4 self-test and then V4 research execution to the TEST workflow only after the active run finishes, preserving blind 2024 -> locked-2025 -> conditional-2026 order.
4. Live-validate EDINET financial + dilution evidence on a small 2024/2025 sample once `EDINET_API_KEY` is available.
5. Extend/inspect 2024H1/H2 frozen technical reporting and compare four pre-2026 regimes without changing thresholds based on 2026.
6. Only after coverage gates pass, compare coverage-matched technical baseline vs dilution/financial/combined overlays. Reject weak/unstable effects.
7. Production integration remains blocked until explicit user Go.
