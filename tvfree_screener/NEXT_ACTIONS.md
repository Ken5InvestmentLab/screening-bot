# TV-Free Screener — Next Actions

TEST ONLY. Execute top-to-bottom unless new evidence invalidates the next item. Keep `HANDOFF.md` synchronized.

## Guardrails
- Branch: `test/tvfree-screener-v1`; Draft PR #13 only.
- Never merge or modify `main` without explicit user Go.
- Never change production Discord/Spreadsheet writes, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater, or production workflows.
- Evaluation remains next-session-open -> horizon close and all model selection must be causal.
- 2026 is contaminated/reporting-only and must never be used for threshold/model tuning.

## 1. JPX point-in-time membership — ACCEPTED
Run #112 (`34554140015`, retained artifact `10181998903`) passed the live gate:
- event rows 1,096;
- unknown-market rows 0;
- same-day code collisions 0;
- required/parsed years 2022-2026 with no missing years;
- `valid_for_membership_reconstruction=true`;
- reused codes `3960` and `8303` are identified for identity quarantine.

Use the reconstructed membership state only with price data whose issuer identity and historical coverage are independently valid.

## 2. Yahoo delisted-symbol coverage — REJECTED AS SUFFICIENT SOURCE
The same run measured 463 official delisting events. Three were identity-quarantined; among 460 probed events only 11 (2.39%) had usable Yahoo prices near delisting, with zero probe transport errors.

Status counts:
- missing 400;
- missing-before-delist 47;
- partial-old-or-sparse 2;
- usable-near-delist 11;
- identity-quarantined 3.

Usable/probed by year: 2022 0/76, 2023 0/60, 2024 0/94, 2025 0/124, 2026 11/106.

Do not weaken the near-delisting gate. Yahoo alone is rejected for survivorship-aware historical OHLCV of delisted TSE names.

## 3. Find and coverage-test a free delisted-price source
Highest priority. Reuse the exact official JPX delisting candidate set and identity quarantines from run #112. Implement only TEST-only probes. A candidate source must be evaluated by coverage before it is allowed into any historical backtest; transport failures and genuine missing data must remain separate.

Prefer sources/routes that can realistically cover 2022 onward without paid credentials. If none is adequate, record the blocker rather than substituting today's survivor universe.

## 4. Inspect independent 2024 extension and frozen 2025 invariance
Without changing thresholds/features/model hyperparameters, inspect 2024H1/H2 where causal training volume is sufficient and verify frozen 2025 outputs remain unchanged. Report unavailable periods rather than weakening minimum-training rules.

## 5. Inspect first blind V4 result
V4 protocol remains predeclared and blind:
1. expose 2024 development metrics for all four variants;
2. lock exactly one variant from 2024 only;
3. evaluate only that locked variant on 2025;
4. compute 2026 only if the locked variant passes the predeclared 2025 gate.

The global trading-calendar cooldown continuity fix and year-boundary synthetic test are already in place. Reject weak or one-regime methods rather than retuning.

## 6. Fundamental / dilution overlay
Live EDINET work remains blocked until `EDINET_API_KEY` is available as an environment/secret value. Never commit or log the key. Extracted warrant/share-count candidates remain audit evidence only until filing-table semantics are manually/live validated. Missing observations must remain explicit unknowns with coverage-matched baselines; never treat missing as healthy.

Initial dilution thresholds remain predeclared at 20%, 35%, 50%, and 100% potential shares / shares outstanding. Selection may use only 2024H1/H2 and 2025H1/H2; 2026 stays reporting-only. Valuation/PER-PBR remains deferred until point-in-time treasury-share and period-profit alignment is reliable.

## 7. Production integration — BLOCKED until user Go
Never automatically merge PR #13, alter production workflows, send production Discord, write production Spreadsheet, replace Stable★6/Sniper/Mega, or disable/change production TradingView/watchlist components.

## TEST-CI execution note
- `7518dc0af0e0027caa452b5221230e7faeb6c6c1`: insufficient path-only docs exclusion.
- `bbc7ed19ff46f98ef0beba9565e4071b6305bc94`: malformed intermediate edit, rejected/superseded.
- `8b8b46feaa14465180b740dba69a597de29b7660`: corrected per-update lightweight gate and job-level heavy concurrency; current accepted TEST-workflow structure.
- Run #114: `34554396869`; model-performance conclusions from it remain provisional while the delisted-price source blocker is unresolved.
