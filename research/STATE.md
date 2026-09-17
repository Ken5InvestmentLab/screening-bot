# Research STATE

Updated: 2026-09-17 22:49 JST
Branch: `research/p0-alt-family-rows-normalization`

## P0 Meta prereg implementation

- Alternate-family historical normalization is PARKED after two runs without new canonical rows/receipt progress.
- `strict_3pt`: PARKED / REFERENCE_ONLY. Do not repeat name search unless new explicit evidence appears.
- Meta prereg source: `research/META_REGIME_SWITCHING_PREREG_20260917.md`, blob `9224a074a4ee19d3da9a69fe875c883c6f62c5af`.
- Added research-only causal label generator: `research/meta_regime_label_generator.py`.
  - generator blob SHA: `cf9053340b4ed7d8ca34d0cc2ebc689e4cd0e68a`
  - creation commit: `d49fe56ae352059ccc3e4bdb45514a9c83e26a6f`
  - axes only: breadth_ma20 causal percentile LOW/MID/HIGH; candidate_count_pre_rank SCARCE=1/MULTI=2+; range_pct causal percentile LOW/MID/HIGH.
  - breadth/range history: exactly 120 XTKS sessions strictly before signal T; quantiles 0.33/0.67.
  - fail-closed: insufficient 120 prior sessions, missing signal session/value, or missing candidate count.
  - 2026 rows rejected by code; only 2023-2025 accepted.
  - no outcome/return metrics are read or recomputed.
- Pinned primary rows have not yet been relabeled in this run because their exact artifact paths/input regime-series chain were not established from the current research branch. No substitute rows were used.

## Previous alt-family state

- `core_bollinger_reclaim`: SOURCE_POOL_EXACT; HISTORICAL_OUTCOME_CHAIN_NOT_ESTABLISHED; REFERENCE_ONLY for ranking.
  - experiment: `CORE-BOLLINGER-RECLAIM-20260913-01`
  - spec sha256: `ed3e053d81ab20b8f999bc44b1d3960f686f3df134eb09e93dc7702108f856b4`
  - candidate implementation sha256: `6b61dd9286344e4b5def77aa8f79976cf83d904bba0d59c23df20dcd082bcec5`
  - pool receipt blob: `9238fded8be258d68cc861ea4c89745dcecb7740`
  - pool reproduction blob: `c5b47f1380f8c9ee31db4588b15d8eb826b57e90`
  - selected decision hash: `c6433cc205d50c225c235c451afc65d41dc77995bffaa0e32804cb77bab9e54a`
  - reproduction exact: true
- Historical rows blob `06bf7736cdedf16f6c50f4e4ba0d715394c31588` rejected as `MISMATCH_FAMILY_DO_NOT_NORMALIZE`.
- Prior receipt: `research/P0_ALT_FAMILY_ROWS_FORENSIC_20260917_2049.md`, commit `54bf5cb7fc83b374f8c6f6a5190cad297447c0cc`.

## Guardrails

2026 outcomes excluded. No Meta performance cross-tab yet. No existing 2023-25 return metrics recalculated. No production/main/workflow/Discord/Spreadsheet/Stable/Sniper/Mega/TradingView/watchlist changes.

## Next

Locate the already-pinned primary-5 2023-2025 row artifacts and their causal daily breadth_ma20/range_pct + pre-rank candidate-count inputs by exact SHA/path, then apply the frozen generator without reading outcomes. Emit labeled-row artifact plus candidate×year coverage/fail-closed receipt. Do not regenerate trade returns.
