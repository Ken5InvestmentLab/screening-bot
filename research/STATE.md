# Research STATE

Updated: 2026-09-17 20:49 JST
Branch: `research/p0-alt-family-rows-normalization`

## P0 alt-family exact/historical normalization

- `strict_3pt`: PARKED / REFERENCE_ONLY. Do not repeat name search unless new explicit evidence appears.
- `core_bollinger_reclaim`: SOURCE_POOL_EXACT; HISTORICAL_OUTCOME_CHAIN_NOT_ESTABLISHED; REFERENCE_ONLY for ranking.
  - experiment: `CORE-BOLLINGER-RECLAIM-20260913-01`
  - spec sha256: `ed3e053d81ab20b8f999bc44b1d3960f686f3df134eb09e93dc7702108f856b4`
  - candidate implementation sha256: `6b61dd9286344e4b5def77aa8f79976cf83d904bba0d59c23df20dcd082bcec5`
  - pool receipt blob: `9238fded8be258d68cc861ea4c89745dcecb7740`
  - pool reproduction blob: `c5b47f1380f8c9ee31db4588b15d8eb826b57e90`
  - selected decision hash: `c6433cc205d50c225c235c451afc65d41dc77995bffaa0e32804cb77bab9e54a`
  - reproduction exact: true
- Historical rows blob `06bf7736cdedf16f6c50f4e4ba0d715394c31588` rejected as `MISMATCH_FAMILY_DO_NOT_NORMALIZE`: its volr20/tail-CDF schema is not Bollinger reclaim. No performance values from it are admitted.
- Receipt: `research/P0_ALT_FAMILY_ROWS_FORENSIC_20260917_2049.md`
- Receipt commit: `54bf5cb7fc83b374f8c6f6a5190cad297447c0cc`

## Guardrails

2026 outcomes excluded from research decisions. No production/main/workflow/Discord/Spreadsheet/Stable/Sniper/Mega/TradingView/watchlist changes.

## Next

Trace exact Bollinger selected rows by selected decision hash, or exact generator/input chain, then normalize only 2022-computable/2023/2024/2025 to signal T -> next XTKS open -> fifth XTKS close, cost0%, and machine-audit entry/endpoint. If this family cannot advance in the next run, switch to another existing SOURCE_POOL_EXACT family rather than repeating broad search.
