# EXPERIMENT_LEDGER append — 2026-09-13

## DATA-QUALITY-DAILY-ANCHOR-MATERIALIZER-20260913-03 — FROZEN / IMPLEMENTED

- Resumed from `DATA-QUALITY-DAILY-ANCHOR-OPTIONS-20260913-02` before further 4H model tuning.
- No new Yahoo market-data request. No strategy-return file opened. No 2026 return used to choose thresholds, tiers, models, or correction rules.
- Prior cached eight-symbol quality evidence retained unchanged: 1,087 complete seven-slot sessions; raw all-OHLC-within-1% 494 (45.446%); common scale 574 (52.806%); open/close anchor 985 (90.616%); extrema anchor 1,074 (98.804%); compatible volume reconciliation 846 (77.829%); prior fully-corrected diagnostic 596.
- Frozen deterministic spec: `DAILY_ANCHOR_MATERIALIZER_SPEC.json`.
- Implementation: `daily_anchor_materializer.py`.
- Common scale: median daily/hourly O/H/L/C factor, eligible only when normalized max factor spread <=2%.
- Price anchors/extrema require complete seven-slot coverage and defensible common scale. Daily extrema are assigned to observed raw-extreme locations; no unobserved intraday time is fabricated.
- Volume proportional reconciliation requires complete coverage and factor 0.5..2.0. Otherwise price reconstruction may remain `B_PRICE_RECON_POSTCLOSE` with volume untrusted.
- Tier precedence frozen: A full post-close reconstruction; B price-only post-close reconstruction; C exactly one daily-resolution fallback; D unusable.
- Same-day finalized daily OHLCV is `POSTCLOSE_RECON_ONLY` unless feature cutoff is explicitly >= final-daily availability timestamp. Pre-close 4H/session features must not consume these repaired values.
- Focused local verification: 6 passed / 0 failed. Guards include raw immutability, no fake AM/PM fallback, inconsistent-scale fallback, volume compatibility, explicit cutoff causality, unusable-source handling.
- Decision: `FREEZE_MATERIALIZER_AND_RETURN_TO_CAUSAL_4H_FEATURES`. Daily fallback remains data-quality/fallback only and is not a final scoring candidate.
- Next: propagate tier/causal tags to the research feature boundary, measure usable bin/tier coverage, then resume causal 4H/intraday feature work. Relative-volume work may continue only after the boundary rejects post-close-only fields at pre-close cutoffs.
- Production Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist-builder/updater/workflows unchanged.
