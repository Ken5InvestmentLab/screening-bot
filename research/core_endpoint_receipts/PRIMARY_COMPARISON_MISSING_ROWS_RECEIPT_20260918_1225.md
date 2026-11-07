# Primary comparison missing-rows receipt — 2026-09-18 12:25 JST

Scope: research-only. No production/main/Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist-builder/updater changes. 2026 excluded. Meta excluded.

## Requested operation
Fill previously-uncomputed row-required comparison metrics (+20/-10/-20/max up/max down/100-share P/L) for the already-audited 2023-2025 primary five candidates, without regenerating or re-auditing their exact trade rows and without recomputing completed n/mean/median/win/+10/Top3-ex metrics.

## Single blocking artifact
MISSING: the committed canonical exact-trade-rows artifact for the 2023-2025 primary five candidates (or a receipt that names its repository path and immutable blob SHA).

Current branch snapshot checked: `test/tvfree-screener-v1` HEAD `682ba96034a17504cb941647e8b213f7fe5c0eff`, tree `b88ea09b0801f447205e245453be5df7daf4582d`.

The tree contains selector code/workflows and research receipts, but no committed primary-five canonical trade-row CSV/JSON artifact whose rows can be consumed directly under the no-regeneration contract. Therefore no COMPARISON_CELL is asserted in this run; doing so would require reconstructing rows, which Supervisor explicitly prohibited.

2022 row-required metrics remain `PENDING_2022_ROWS` and were not recalculated.

## Unblock condition
Provide/fix exactly one immutable reference: `PRIMARY_5_EXACT_ROWS_2023_2025 = <repo path>@<blob SHA>` containing the already-certified exact rows. Once present, this lane can calculate only the missing metrics directly from those existing rows.
