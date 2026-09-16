# Core24 handoff — 2026-09-16 21:24 JST

## P0 progress
The prior `daily raw not established` blocker is resolved. Existing immutable Actions artifact `tvfree-frozen-dataset-run80-preserved` (run 34599959356, artifact 10264205130) contains `tse_daily.csv`, SHA-256 `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`, 4,061,361 data rows covering 2022-01-04 through 2026-09-11.

Observed field nulls are O/H/L/C/V = 0/0/0/0/0 and nonpositive O/C = 0/0. This does NOT establish endpoint completeness because required symbol-date rows may be absent.

A concrete integrity issue exists: 797 rows violate OHLC ordering, concentrated on 2022-05-17 (272), 2024-04-04 (1), 2024-06-05 (16), 2024-11-15 (10), 2025-05-23 (9), 2026-09-11 (489). Do not silently repair/drop these rows. Candidate endpoint intersection must report whether any frozen trade entry/exit lands on them.

Machine-readable receipt: `CORE_DAILY_RAW_CORPUS_RECEIPT_20260916_2124.json`.

## Next P0
Recover exact rows for the first available frozen primary candidate (`body_pct LOW`, `volr20 LOW`, `mean-rank`, `DUAL_TOP1_AGREEMENT`, or `DUAL+G3`), derive next-XTKS-open/fifth-XTKS-close, and intersect required O/C keys against the pinned corpus. Then repeat across all five. Exact-hour/activity remains SEALED and does not block daily endpoint work.

No production/main changes. No retune. No costed calculation.
