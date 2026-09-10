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
Replace TradingView/Pine watchlist dependency with a free daily-OHLCV TSE common-stock system while remaining competitive with Stable★6, and test transparent non-technical overlays only when causally valid.

## Infrastructure / reproducibility
- Last fully successful research pipeline remains Actions run `34519284035` on rolling `period=3y`; runtime about 23m15s, artifact about 33.55 MB.
- Rolling `period=3y` is not a durable baseline. Test-only fixed-start acquisition uses `2022-01-01 -> current` via `bootstrap.py`.
- GitHub hosted-runner allocation remains blocked; recent PR-triggered jobs through `34543020376` fail before executable steps (`steps=null`). Do not alter model semantics because of this infrastructure failure.
- Manifest v3 fingerprints research code/config, current JPX universe, historical coverage/OHLCV, and Short/Swing outputs.
- Synthetic checks cover append-only reproducibility, causal feature/label boundaries, point-in-time universe reconstruction, fundamental overlay behavior, and EDINET collector parsing/key safety.

## Universe validity
- Current-universe snapshot: `9e1bb3473ebbb2ccb3f768e7bf144b9969927f47`.
- Manifest universe hash: `d50cb1eca97734acb4f4d5ed2f1ab97acd6c267b`.
- Point-in-time universe prototype: `d2e66370d237edd94880fd9f8a6e740ed9332d5a`; synthetic test: `bea62cb1d1847409e84d1e63b2c08038db435765`.
- Official JPX listing/delisting archives make historical membership reconstruction plausible, but live parser validation and Yahoo delisted-symbol price coverage are still pending.

## Stable★6 historical reference
2026 Mar-Aug 5BD historical reference: n=55, mean about +6.59%, median +1.50%, win 56.4%, +10% 18.2%, -10% 10.9%. 10BD mean about +7.64%, win about 57.4%. 2026 is reporting-only and must not drive tuning.

## V3 Short
- Same 45 features, monthly causal XGBoost, prediction-day percentile normalization, Core `r_top10 - 2*r_loss10`, next-open -> 5BD.
- Recent-outcome Meta rejected; Attack none/unaccepted.
- Last successful rolling-3y: 2025H1 mean +0.46%; 2025H2 +0.35%; contaminated 2026 Mar-Aug -0.56%.
- Durable fixed-start numeric baseline pending runner recovery.

## V3 Swing
- Frozen architecture: MomCross -> causal semiannual quality model -> training empirical CDF -> Breadth Meta -> `score_R >= 0.20`.
- Do not retune from 2026 or rolling-window sweep.
- Last successful rolling-3y: 2025H1 +6.36%; 2025H2 +5.89%; contaminated 2026 Mar-Aug +1.00%.
- Swing A none/unaccepted. Durable fixed-start baseline pending.

## Dilution / fundamental overlay research
User requested testing whether large outstanding stock-acquisition-right dilution and weak/expensive fundamentals can explain differences among otherwise similar technical signals.

Accepted feasibility findings:
- AI is not required. The overlay can be deterministic and reproducible.
- EDINET API v2 is an official route to historical filings; API use requires registration/API key. A TEST-only ingestion implementation now exists, but live historical coverage has not yet been validated.
- Any fundamental/dilution value must carry `available_date` and may affect only signals on/after that public date. Current values must never be backfilled into earlier signals.

TEST-only implementation completed in this run:
- `fundamental_overlay.py` commit `a5dbe1ca4398903327a9c84fb5a1cbee19c6459c`.
  - deterministic point-in-time as-of join,
  - dilution ratio = remaining warrant shares / shares outstanding,
  - predeclared dilution research grid 20%, 35%, 50%, 100%,
  - transparent financial-risk flags: thin equity ratio, operating loss, net loss, negative operating CF,
  - separate baseline / dilution / financial-risk / combined lanes,
  - missing fundamental/dilution observations remain explicitly missing rather than being silently scored safe.
- `fundamental_overlay_selftest.py` commit `860eed55ba8c47427f46ede4cf205fef3b80916f` verifies future disclosures do not affect earlier signals and verifies dilution/risk-lane behavior on fabricated data.
- Test workflow self-check integration: `ce5ebe9b226474222978aaa4f470f900431de3bf`.
- Research-contract inclusion: `42bd9e29dbfca27b02aaa0fd03bbc9c9018dd442`.
- `edinet_fundamental_collector.py` commit `5fc14fb5f238da7cd8284e2ee251f5db94fb107d`.
  - requires `EDINET_API_KEY` from environment and redacts it from object representation,
  - reads EDINET v2 document lists and type=5 XBRL-to-CSV ZIPs,
  - stores `doc_id`, source file date, filing period, `submit_datetime`, `available_at`, and `available_date`,
  - extracts an intentionally small auditable alias set for shares outstanding, assets, equity, revenue, operating income, net income, and operating CF,
  - conflicting same-priority facts fail closed as `ambiguous`,
  - emits per-field coverage/status diagnostics,
  - does not implement dilution/warrant extraction yet.
- EDINET synthetic self-test commit `34a44f006f67c26cecb63eaeefa1dff37a7e4cfc`; local synthetic execution passed.
- Test workflow integration: `0ff63844ba0d8914c08eb0ed8b68e869f93037da`.
- Research-contract fingerprint integration: `9591e19ac26c245518eea86f4cbf175ad2917ea8`.

Not yet accepted for performance use:
- No EDINET live historical dataset has been built yet and the initial element-id alias coverage is not live-validated.
- No 2024/2025 comparative backtest has been run yet.
- Valuation metrics such as PER/PBR require point-in-time market price and correctly aligned shares/equity/earnings; do not infer them from present-day values.
- Warrant classification (especially MS warrants versus ordinary options/SO) still needs a robust historical extractor; do not pretend simple XBRL totals fully capture all dilution risk until validated.

## Blockers
1. GitHub hosted runner allocation prevents fixed-start pipeline execution.
2. EDINET API requires an API key for programmatic live document acquisition.
3. Historical warrant residual shares may require extracting filing-specific XBRL/text tables beyond simple standardized financial facts.
4. Delisted-symbol historical price coverage remains unknown.

## Next concrete task
1. Keep model thresholds frozen and re-check hosted runner only opportunistically.
2. Live-validate the new TEST-only EDINET collector on a small pre-2026 sample once `EDINET_API_KEY` is available; inspect document selection, ZIP parsing, exact element-id coverage, and missing/ambiguous rates before broad collection.
3. Before any performance backtest, define a strict same-day availability rule using retained `available_at` so a filing published after the signal decision time cannot leak into that day's signal.
4. Separately prototype warrant/new-share-option extraction with confidence/coverage diagnostics; distinguish MS warrants where source disclosures allow it.
5. Only after acceptable historical coverage, apply overlay to frozen Short/Swing picks and compare baseline vs dilution-only vs financial-risk-only vs combined on 2024H1/H2 and 2025H1/H2. Use 2026 reporting-only.
6. Reject overlays that improve only one period, drastically reduce sample size, or rely on missing-data selection effects.
7. Production integration remains blocked until explicit user Go.
