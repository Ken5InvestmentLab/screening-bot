# V16 alternate-family 2024 canonical rows receipt

CANDIDATE_ADMISSIBILITY=GO
SCOPE=REFERENCE_FAMILY_ONLY_NOT_PRIMARY
TRADE_ROWS_2024=102
MISSING_ENDPOINT_2024=0
ROWS_SHA256=f19ce66789c12191fc909391cf7135e7f0f80ac9dc1cdd2705659a7a9ea9d887

Candidate/source lock: commit bcc2b9f1ce2a2b8ce6bc02e21be72c48899690d5; selection blob 13fd0e87e81034757ca6b6f0a0b57abecae35109. Inputs: daily corpus artifact 10264205130 digest sha256:095e58986d45bda0092be1767e1b44a4791bf3c617179791d0c99c6d7d01bcb0; causal Tail cache artifact 10264251140 digest sha256:2f67833af2881754336c8f92cbf463ddf1cb995bd0fc808a962479d1bfd44198.

Generation: filter causal Tail cache to 2024; frozen V16 select; signal T -> next XTKS open -> fifth XTKS close; cost 0%; win iff gross_return > 0. Generated 102 selected rows and normalized 102/102 endpoints; missing=0. No tuning or performance-based selection.

The canonical CSV bytes were generated in-run and SHA-pinned above. This receipt is the durable provenance checkpoint; next target is 2025 generation under the identical lock.

Guards: 2022 n=31 remains separate from primary. No 2026. strict_3pt parked. No production/main/workflow/Discord/Spreadsheet/Stable/Sniper/Mega/TradingView/watchlist-builder/updater changes.