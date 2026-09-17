# P0 Alt-family historical rows forensic — 2026-09-17 20:49 JST

Scope: research-only. Production/main/workflows/Discord/Spreadsheet/Stable/Sniper/Mega/TradingView/watchlist components untouched.

## Candidate: core_bollinger_reclaim

Status: SOURCE_POOL_EXACT; HISTORICAL_OUTCOME_CHAIN_NOT_ESTABLISHED; REFERENCE_ONLY for cross-candidate ranking until canonical rows are recovered/generated from the exact family.

Exact source/pool chain recovered from commit/tree snapshot `929e4fc625d3402f1ae6d4531c98d99630a0068f`:

- experiment_id: `CORE-BOLLINGER-RECLAIM-20260913-01`
- spec sha256: `ed3e053d81ab20b8f999bc44b1d3960f686f3df134eb09e93dc7702108f856b4`
- candidate_and_policy implementation sha256: `6b61dd9286344e4b5def77aa8f79976cf83d904bba0d59c23df20dcd082bcec5`
- pool receipt blob SHA: `9238fded8be258d68cc861ea4c89745dcecb7740`
- pool reproduction blob SHA: `c5b47f1380f8c9ee31db4588b15d8eb826b57e90`
- reproduction: `reproduced_exactly=true`
- decision hashes: pool `d16c61111cb17588c8e087edbb6c2c17b1f608999fddc2ca87b809cdb65360bc`; ranked `cf65884039d3526fd8c34cedc4e787fbe446a10e97baf2f657f44902a27821d9`; selected `c6433cc205d50c225c235c451afc65d41dc77995bffaa0e32804cb77bab9e54a`.

The frozen spec defines the intended endpoint as signal date -> next official XTKS session open -> fifth official XTKS session close. The present comparison contract uses cost 0%, so any historical evaluation using the spec's 0.5% primary cost cannot be copied as canonical performance.

## Historical rows candidate rejected

A historical trade-row artifact inspected during lineage tracing (blob `06bf7736cdedf16f6c50f4e4ba0d715394c31588`) is **not** accepted as `core_bollinger_reclaim` historical outcome evidence. Its schema/feature columns identify a different volr20/tail-CDF ranking family (`volr20_first_daily_rank`, `ret1_signal_time`, `ret10_signal_time`, `volr20_signal_time`, `tail_cdf_signal_time`, etc.) and therefore cannot be substituted for Bollinger-reclaim rows. Near-logic substitution is prohibited.

No performance values from that artifact are used here. It is recorded only as a lineage mismatch.

### MISMATCH receipt

- expected family: `core_prior20_lower_bollinger_reclaim_v1`
- observed historical artifact family indicators: volr20 / tail-CDF rank pipeline
- decision: `MISMATCH_FAMILY_DO_NOT_NORMALIZE`
- comparison eligibility: `REFERENCE_ONLY`
- reason: exact source/pool provenance exists, but exact historical signal-row identity connecting the Bollinger selected decision hash to 2022-computable/2023/2024/2025 outcomes has not yet been established.

## Next admissibility step

Do not repeat broad repo search. Continue from the exact Bollinger chain above and locate either (a) selected signal rows whose decision hash is `c6433cc205d50c225c235c451afc65d41dc77995bffaa0e32804cb77bab9e54a`, or (b) the exact generator/input artifacts sufficient to regenerate those selected rows for 2022-computable/2023/2024/2025 without opening 2026 outcomes. Only then build canonical cost-0 trade rows and machine-audit `entry_date > signal_date` plus fifth-XTKS-session endpoint.