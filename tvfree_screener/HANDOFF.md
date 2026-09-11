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
- Last fully successful research pipeline before runner recovery was Actions run `34519284035` on rolling `period=3y`; runtime about 23m15s, artifact about 33.55 MB.
- Rolling `period=3y` is not a durable baseline. Test-only fixed-start acquisition uses `2022-01-01 -> current` via `bootstrap.py`; normal production behavior is unchanged.
- IMPORTANT NEW STATUS: hosted runner allocation recovered on 2026-09-11. Actions run `34545440155` (head SHA `5461eef6f35ea2cea2b4bc38ca7177c681681783`) reached checkout and is genuinely executing.
- In run `34545440155`, all five synthetic safety checks passed before heavy research: reproducibility, causality, point-in-time universe, fundamental/dilution overlay, and EDINET collector.
- At the latest observation in this research turn, step `Purged walk-forward backtest` was still `in_progress`; no fixed-start numeric baseline or artifact hash has yet been accepted from that run. Do not claim completion until the run finishes.
- The repo is public and commit `5461eef6...` restored normal TEST-only PR triggers for `tvfree_screener/**`; concurrency still cancels obsolete duplicate runs. This change affects only the test workflow, not production.

## Reproducibility / universe
- Manifest v3 fingerprints research code/config, current JPX universe, historical date/symbol coverage, historical OHLCV, and Short/Swing outputs.
- Point-in-time universe prototype: `d2e66370d237edd94880fd9f8a6e740ed9332d5a`; synthetic test: `bea62cb1d1847409e84d1e63b2c08038db435765`.
- Official JPX listing/delisting archives make historical membership reconstruction plausible, but live parser validation and Yahoo delisted-symbol price coverage are still pending.
- Never call results survivorship-bias-free until delisted historical price coverage is measured.

## V3 Short
- Same 45 features, monthly causal XGBoost, prediction-day percentile normalization, Core `r_top10 - 2*r_loss10`, next-open -> 5BD.
- Recent-outcome Meta rejected; Attack none/unaccepted.
- Last successful rolling-3y snapshot: 2025H1 mean +0.46%; 2025H2 +0.35%; contaminated 2026 Mar-Aug -0.56%.
- Durable fixed-start numeric baseline pending completion of run `34545440155` or a later equivalent run.

## V3 Swing
- Frozen architecture: MomCross -> causal semiannual quality model -> training empirical CDF -> Breadth Meta -> `score_R >= 0.20`.
- Do not retune from 2026 or the old rolling-window threshold sweep.
- Last successful rolling-3y snapshot: 2025H1 +6.36%; 2025H2 +5.89%; contaminated 2026 Mar-Aug +1.00%.
- Swing A none/unaccepted. Durable fixed-start baseline pending.

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

### Newly found data-quality issue
A code review during the active fixed-start run found a real issue in `fundamental_overlay.py` that must be corrected BEFORE performance testing:
- missing financial values compare False against risk thresholds;
- current `financial_risk_count = ...fillna(False).sum()` can therefore assign a fully missing row a risk count of 0;
- `financial_risk_filter` then effectively lets that row pass as if healthy;
- the existing self-test checks that missing values stay NaN but does not yet test the downstream lane semantics.

This contradicts the research rule `missing != healthy`. It is a data-quality bug, not a model-performance finding.

Required fix after preserving the currently running fixed-start job:
1. add explicit `dilution_known`, `financial_known`, and `combined_known` coverage flags;
2. make `financial_risk_count` / `financial_risk_exclude` nullable/unknown when required financial facts are missing;
3. keep unknown observations explicit rather than silently classifying them healthy;
4. add coverage-matched baseline lanes (`*_known_baseline`) so apparent gains cannot come merely from dropping missing-data names;
5. extend the synthetic self-test to require these semantics.

No threshold should change as part of this fix.

## Historical dilution extraction design
Research this turn confirmed that balance-sheet `新株予約権` / `SubscriptionRightsToShares` is a monetary equity account and is NOT the residual potential-share count needed for dilution filtering.

Historical dilution therefore needs a separate deterministic collector for the EDINET section/table `新株予約権等の状況`, preserving source evidence. At minimum store separately:
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

## Current blockers
1. Fixed-start run `34545440155` is still executing; numeric baseline/artifacts cannot yet be frozen.
2. Live EDINET acquisition needs `EDINET_API_KEY`; the key must remain env/secret-only and never be committed/logged.
3. Historical residual warrant shares require a dedicated table/text extractor beyond standardized financial facts.
4. Point-in-time universe live parser validation and delisted-symbol historical price coverage remain pending.

## Next concrete tasks
1. Re-check and complete analysis of Actions run `34545440155`. If successful, require fixed-start mode, extract artifact, freeze Short/Swing baseline metrics and manifest hashes, runtime, artifact size, without retuning from 2026.
2. Fix fundamental-overlay missing-data semantics and add coverage-matched baselines/self-tests before any fundamental performance comparison.
3. Live-validate EDINET financial collector on a small pre-2026 sample once an API key is available; measure exact field coverage/missing/ambiguous rates.
4. Prototype a separate deterministic EDINET dilution collector for `新株予約権等の状況`; distinguish financing/MS-type warrants only when source evidence supports it.
5. Validate point-in-time JPX membership and delisted-price coverage.
6. Only after coverage gates pass, run frozen technical baseline vs overlays on pre-2026 periods. Reject weak/unstable overlays.
7. Production integration remains blocked until explicit user Go.
