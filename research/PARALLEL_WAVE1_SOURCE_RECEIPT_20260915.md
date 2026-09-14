# Parallel Wave-1 preserved-source receipt — 2026-09-15

Status: **SOURCE_BYTES_BOUND / SCHEMA+XTKS ENDPOINT RECEIPT PENDING / PERFORMANCE UNOPENED**

This receipt is research-only. It does not change production/main, production workflows, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder, or updater.

## 1. Frozen source lineage

The preserved dataset used for Parallel Wave-1 is explicitly bound to two different run roles:

- **Original source-data run:** `34545440155`
  - artifact: `tvfree-screener-test-34545440155`
  - artifact ID: `10179500303`
  - source artifact ZIP SHA-256: `85cf79fea74f9a122bf0b6b5c1e94d1fda80d468e68ac0d8c774e1a69010bfc4`
- **Preservation/hosting run:** `34599959356`
  - artifact: `tvfree-frozen-dataset-run80-preserved`
  - artifact ID: `10264205130`
  - preserved artifact ZIP SHA-256: `095e58986d45bda0092be1767e1b44a4791bf3c617179791d0c99c6d7d01bcb0`
  - preserved artifact is not expired at audit time; retention expiry reported as 2026-12-10T12:38:23Z.

Important provenance clarification: `34599959356` is the preservation host run, while the actual dataset bytes originated from run `34545440155`. These must not be collapsed into one provenance field.

## 2. Preserved CSV byte receipt

Preservation job `103264559940` verified and hashed `preserved/tse_daily.csv` before re-upload:

- CSV SHA-256: `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`
- `wc -l`: `4,061,362` lines including header
- data rows: `4,061,361`

The original source run's reproducibility manifest independently reported:

- rows: `4,061,361`
- symbols: `3,700`
- min date: `2022-01-04`
- max date: `2026-09-11`
- historical cutoff: `2026-08-31`
- historical rows through cutoff: `4,031,154`
- historical date/symbol SHA-256: `2686163d4e4342198590d34a8708c5c142a11441befdd74da3475bafd3e9a935`
- historical OHLCV SHA-256: `475ae6166ed21220aaa7f9f98d5bfff6c2d221bf1e3571b59fc6656758f453ab`
- universe rows: `3,700`
- universe SHA-256: `271033ea30220e1731537a2b453d2f5bfffb9fbc29d7d43a46f8efd1f9f54cbe`
- fixed-start contract: `2022-01-01 -> current; symbols listed later naturally start later`

## 3. Selection-use guardrails

- 2026 outcomes are **report/robustness-only** and may not be used for selection/tuning.
- Weak+Early 2022 fresh outcomes are not tuning inputs for Parallel Wave-1.
- Transaction cost for every new Wave-1 performance comparison is **0%**.
- Win is strictly **gross return > 0**.
- Canonical comparison endpoint remains **next XTKS session open -> fifth XTKS session close**.
- Frozen A1/B1/E1 thresholds in `research/PARALLEL_WAVE1_FROZEN_MANIFEST_20260915.md` may not be changed after performance is opened.

## 4. What is still required before opening performance

This receipt binds immutable dataset bytes and source lineage, but it deliberately does **not** claim that the full schema/endpoint contract has been verified yet.

Before the one-shot A1/B1/E1 cost0 batch, implementation must fail closed unless all of the following are bound and verified:

1. exact required-column/schema receipt for the preserved CSV;
2. pinned XTKS session calendar / required endpoint-session mapping;
3. required entry and fifth-session-close rows are complete for every evaluated pick;
4. evaluation period and untouched confirmation block are fixed without using 2026 outcomes;
5. source CSV SHA-256 exactly matches the value above.

No Wave-1 performance was opened during this receipt audit.

## 5. Next state

`SOURCE_BYTES_BOUND_SCHEMA_ENDPOINT_RECEIPT_PENDING`

Next action: bind exact schema + pinned XTKS endpoint completeness receipt, implement frozen A1/B1/E1 fail-closed, then execute one cost0 batch only. No threshold grid, no post-hoc A2/B2/E2 rescue.
