# V16 alternate-family 2025 canonical rows receipt

CANDIDATE_ADMISSIBILITY=GO
SCOPE=REFERENCE_FAMILY_ONLY_NOT_PRIMARY
TRADE_ROWS_2025=70
MISSING_ENDPOINT_2025=0
ROWS_SHA256=d7dc0fa5716e9abdcb64b347bcd1762af16e13b7e889c4b6ae8355d6c1580169
ROWS_BLOB_SHA=789b5eca741af0224843c67b69f08cf9801352d6
ROWS_COMMIT=710b948c6a4a8d1bc88da70c33449e7637474131

Candidate/source lock: commit bcc2b9f1ce2a2b8ce6bc02e21be72c48899690d5; selection blob 13fd0e87e81034757ca6b6f0a0b57abecae35109. Inputs: daily corpus artifact 10264205130 digest sha256:095e58986d45bda0092be1767e1b44a4791bf3c617179791d0c99c6d7d01bcb0; causal Tail cache artifact 10264251140 digest sha256:2f67833af2881754336c8f92cbf463ddf1cb995bd0fc808a962479d1bfd44198.

Generation: filter causal Tail cache to 2025; frozen V16 select; signal T -> next XTKS open -> fifth XTKS close; cost 0%; win iff gross_return > 0. Generated 70 selected rows and normalized 70/70 endpoints; missing=0. The same local generation procedure reproduced the already-pinned 2023 canonical CSV SHA256 exactly (1b304bb2a3c417967e0d94e263c8c4cc6acb5afb44fba43324928fb018810a1f), providing a cross-year implementation check. No tuning or performance-based selection.

The first create commit for this path contained a one-row placeholder and is superseded by ROWS_COMMIT above; only ROWS_COMMIT/ROWS_BLOB_SHA/ROWS_SHA256 in this receipt are canonical.

Guards: 2022 n=31 remains separate from primary. No 2026. strict_3pt parked. No production/main/workflow/Discord/Spreadsheet/Stable/Sniper/Mega/TradingView/watchlist-builder/updater changes.
