# Primary historical comparison table — 2026-09-18 18:25 JST

Research-only. 2026 excluded. No Meta or production/main changes.

Canonical contract: signal T -> next XTKS open -> fifth XTKS close; cost 0%; win = gross > 0.

Source-of-truth handoff: `research/core_endpoint_receipts/PRIMARY_HISTORICAL_HANDOFF_20260918_1524.md` @ blob `e4f01619115a5b8e5a6e7cf32bc8ae5d94a15729`.

Current branch tree SHA checked: `05a3940ab250d2363617de16230cef093a8fbaf9`.

## Comparison-cell availability

| cohort | n | mean | median | win | +10 | +20 | -10 | -20 | max up | max down | Top3-ex | 100-share P/L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| primary5 / 2022 deterministic | PENDING_2022_ROWS | PENDING_2022_ROWS | PENDING_2022_ROWS | PENDING_2022_ROWS | PENDING_2022_ROWS | PENDING_2022_ROWS | PENDING_2022_ROWS | PENDING_2022_ROWS | PENDING_2022_ROWS | PENDING_2022_ROWS | PENDING_2022_ROWS | PENDING_2022_ROWS |
| primary5 / 2023 | COMPLETED_ELSEWHERE_DO_NOT_RECALC | COMPLETED_ELSEWHERE_DO_NOT_RECALC | COMPLETED_ELSEWHERE_DO_NOT_RECALC | COMPLETED_ELSEWHERE_DO_NOT_RECALC | COMPLETED_ELSEWHERE_DO_NOT_RECALC | PENDING_ROWS | PENDING_ROWS | PENDING_ROWS | PENDING_ROWS | PENDING_ROWS | COMPLETED_ELSEWHERE_DO_NOT_RECALC | PENDING_ROWS |
| primary5 / 2024 | COMPLETED_ELSEWHERE_DO_NOT_RECALC | COMPLETED_ELSEWHERE_DO_NOT_RECALC | COMPLETED_ELSEWHERE_DO_NOT_RECALC | COMPLETED_ELSEWHERE_DO_NOT_RECALC | COMPLETED_ELSEWHERE_DO_NOT_RECALC | PENDING_ROWS | PENDING_ROWS | PENDING_ROWS | PENDING_ROWS | PENDING_ROWS | COMPLETED_ELSEWHERE_DO_NOT_RECALC | PENDING_ROWS |
| primary5 / 2025 | COMPLETED_ELSEWHERE_DO_NOT_RECALC | COMPLETED_ELSEWHERE_DO_NOT_RECALC | COMPLETED_ELSEWHERE_DO_NOT_RECALC | COMPLETED_ELSEWHERE_DO_NOT_RECALC | COMPLETED_ELSEWHERE_DO_NOT_RECALC | PENDING_ROWS | PENDING_ROWS | PENDING_ROWS | PENDING_ROWS | PENDING_ROWS | COMPLETED_ELSEWHERE_DO_NOT_RECALC | PENDING_ROWS |
| primary5 / aggregate 2023-2025 | COMPLETED_ELSEWHERE_DO_NOT_RECALC | COMPLETED_ELSEWHERE_DO_NOT_RECALC | COMPLETED_ELSEWHERE_DO_NOT_RECALC | COMPLETED_ELSEWHERE_DO_NOT_RECALC | COMPLETED_ELSEWHERE_DO_NOT_RECALC | PENDING_ROWS | PENDING_ROWS | PENDING_ROWS | PENDING_ROWS | PENDING_ROWS | COMPLETED_ELSEWHERE_DO_NOT_RECALC | PENDING_ROWS |
| primary5 / aggregate 2022-2025 | PENDING_2022_ROWS | PENDING_2022_ROWS | PENDING_2022_ROWS | PENDING_2022_ROWS | PENDING_2022_ROWS | PENDING_2022_ROWS | PENDING_2022_ROWS | PENDING_2022_ROWS | PENDING_2022_ROWS | PENDING_2022_ROWS | PENDING_2022_ROWS | PENDING_2022_ROWS |

Important: the rows above are availability/status cells, not pooled performance values across the five candidates. Candidate-level numeric cells are intentionally not invented while immutable exact-row artifacts are absent.

## Gate

The checked tree contains neither a committed `primary_2022_weak_early_gated_rows.csv` nor a committed primary-five 2023-2025 canonical exact-row artifact/receipt naming immutable repo path + blob SHA. Therefore no row-derived numeric COMPARISON_CELL is admissible in this run without violating the no-regeneration/no-re-audit rule.

Next admissible update is mechanical only: when an immutable rows path+SHA appears, fill only currently PENDING row-required cells; do not recompute completed n/mean/median/win/+10/Top3-ex cells. Keep old 2022 summary identity separate from deterministic 2022 rows if identities differ.
