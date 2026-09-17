# Phase 2 historical comparison coverage manifest — 2026-09-18

Research-only. No production changes. 2026 outcomes are SEALED and excluded.

## Contract

Primary candidates: `body_pct LOW`, `volr20 LOW`, `mean-rank`, `DUAL_TOP1`, `DUAL+G3`.
Years: 2022-computable, 2023, 2024, 2025.
Canonical endpoint: next official XTKS open -> fifth official XTKS close; cost 0%; win = gross > 0.

This manifest does **not** regenerate or re-audit the already-exact 2023-2025 primary rows. It only inventories evidence that is actually present on the pinned research branch. Values from another family are never substituted.

## Pinned branch evidence

- branch/tree HEAD: `9fde775bac3449c5f5cf0cbbfc7babf9dc38ecfc`
- Batch02 ledger blob SHA: `ed9855303f102eb74c4f73d29435b0bba8bda48c`
- annual extension detections SHA: `06bf7736cdedf16f6c50f4e4ba0d715394c31588` — **NOT primary-5 rows; excluded from primary cells**
- annual extension evaluation SHA: `e9045afa5d74f11974cec07c132ec2ea6074fc03` — **different/extension family; excluded from primary cells**
- annual extension pool SHA: `a65d7b8a3d216e347ed3d8ff290fc6a678303cfd` — **different/extension family; excluded from primary cells**
- V16 volr20 implementation SHA: `13fd0e87e81034757ca6b6f0a0b57abecae35109`
- V18 consensus implementation SHA: `9cfa6b852ff3b3f4937dc6cc624b6dadc445c168`

## Cell-state vocabulary

- `CONFIRMED_SUMMARY`: exact comparable value is explicitly present in an admissible pinned summary/receipt.
- `SUMMARY_ONLY`: opened frozen summary exists but exact primary trade rows are not pinned here; keep separate from exact-row layer.
- `PENDING_ROWS`: metric requires the exact primary trade rows and cannot be inferred from summaries.
- `PENDING_SOURCE`: no admissible pinned primary summary/receipt was found on this branch for that candidate/year.
- `SEALED`: 2026; prohibited.

## Primary 5 × year coverage

The required metric schema is: `n, mean, median, win, +10, +20, -10, -20, max_up, max_down, Top1-ex, Top3-ex, buy100, sell100, pnl100` (15 cells per candidate-year).

| candidate | 2022 | 2023 | 2024 | 2025 | primary source state |
|---|---|---|---|---|---|
| body_pct LOW | PENDING_SOURCE | PENDING_SOURCE | PENDING_SOURCE | PENDING_SOURCE | exact-row/summary SHA not present in pinned tree |
| volr20 LOW | PENDING_SOURCE | PENDING_SOURCE | PENDING_SOURCE | PENDING_SOURCE | implementation pinned (`13fd0e87...`), but implementation is not a substitute for exact summary/rows |
| mean-rank | PENDING_SOURCE | PENDING_SOURCE | PENDING_SOURCE | PENDING_SOURCE | exact-row/summary SHA not present in pinned tree |
| DUAL_TOP1 | PENDING_SOURCE | PENDING_SOURCE | PENDING_SOURCE | PENDING_SOURCE | exact-row/summary SHA not present in pinned tree |
| DUAL+G3 | PENDING_SOURCE | PENDING_SOURCE | PENDING_SOURCE | PENDING_SOURCE | V18 implementation pinned (`9cfa6b85...`), but implementation is not a substitute for exact summary/rows |

### Metric coverage accounting

- Candidate-year blocks: 5 × 4 = **20**.
- Required cells: 20 × 15 = **300**.
- Exact primary cells provably recoverable from admissible pinned summary/receipt on this branch in this run: **0 / 300 = 0.0%**.
- Cells deliberately not filled from extension-family artifacts: **300 / 300** remain protected from family mixing.
- 2023-2025 primary exact-row regeneration/re-audit: **not performed**, by supervisor instruction.
- 2022: `PENDING_SOURCE`; if an already-opened frozen primary summary is later pinned, record it as `SUMMARY_ONLY` until exact rows become admissible.

This 0.0% is an **evidence-manifest coverage rate**, not a statement that prior research had no results. It means the current pinned branch does not contain an admissible source SHA tying the named primary candidate/year cells to the requested comparison contract. Prior chat claims are not promoted into GitHub evidence without a pinned receipt.

## Rows-required metrics

For every primary candidate/year, the following remain `PENDING_ROWS` once an admissible primary summary source is identified but does not carry them: `+20`, `-20`, `max_up`, `max_down`, `buy100`, `sell100`, `pnl100`, and symbol/date concentration. Any other metric absent from its pinned summary also remains `PENDING_ROWS`; no derivation from another family is allowed.

## Explicit mismatch / exclusion receipt

`tvfree_screener/batch02/reports/annual_candidate_detections_2022_2026.csv` (SHA `06bf7736...`) and its annual evaluation/pool are extension-family artifacts. They are not accepted as rows for the named primary 5 candidates. Their presence therefore does not increase primary coverage.

## Progress rule going forward

Progress is now counted only by populated admissible cells out of the 300 historical primary cells above. A future source can increase coverage only when its candidate identity, year, endpoint, and source SHA are pinned and compatible. Rows-dependent cells must remain `PENDING_ROWS` until exact rows are pinned. No 2026 performance may be added here.

## Missing-input receipt

`P0_MISSING_SOURCE_SHA: admissible_primary5_historical_summary_or_exact_rows_2022_2025 = NOT_PRESENT_ON_PINNED_HEAD_9fde775bac3449c5f5cf0cbbfc7babf9dc38ecfc`
