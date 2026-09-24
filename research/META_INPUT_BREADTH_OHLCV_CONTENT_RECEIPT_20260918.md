# Meta input breadth OHLCV content receipt — 2026-09-18

Scope: research-only provenance. No performance/outcome values inspected or recomputed. 2026 prohibited. 2022 SUMMARY_ONLY excluded from Meta. Production/main unchanged.

## Axis

`breadth_ma20`, selected as the minimum-gap axis by `research/META_REGIME_INPUT_MANIFEST_20260918.md` at commit `b3d17a0b33070d03bbf7c4c16cc2d9b067160c9d`.

## Exact preserved OHLCV bytes recovered

The already-pinned GitHub Actions artifact was downloaded and inspected without calculating returns:

- source run: `34599959356`
- artifact id: `10264205130`
- artifact name: `tvfree-frozen-dataset-run80-preserved`
- artifact archive digest: `sha256:095e58986d45bda0092be1767e1b44a4791bf3c617179791d0c99c6d7d01bcb0`
- archive-internal OHLCV path: `tse_daily.csv`
- embedded provenance path recorded by `tse_daily.sha256`: `preserved/tse_daily.csv`
- OHLCV content SHA256: `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`
- key/source columns: `date,open,high,low,close,volume,symbol`

The archive's own `tse_daily.sha256` states the same content digest for `preserved/tse_daily.csv`; an independent SHA256 over the extracted `tse_daily.csv` reproduced it exactly.

## breadth_ma20 code/column/lag chain

From the controlling manifest:

- feature generator: `tvfree_screener/run.py` / `build_features()`
- source blob SHA: `b639a6f6f33c643c2dcf09383ccf7dbfc7790cfa`
- symbol-date intermediate: `ma20_gap = close / rolling20(close) - 1`
- signal-date raw Meta input: `breadth_ma20` = fraction of symbols on `date` with `ma20_gap > 0`
- join key to primary exact rows: `signal_date` -> OHLCV/feature `date`
- causal Meta lag: the 33/67 or percentile threshold for signal T must be formed only from the 120 XTKS sessions strictly before T; signal T raw `breadth_ma20` is joined only after that threshold is formed.

## Status / remaining proof

`OHLCV_CONTENT_CHAIN_PINNED`.

This closes the previously missing archive-internal path + content-SHA item for `breadth_ma20`. It does **not** yet promote the axis to `META_INPUT_CHAIN_COMPLETE`, because a single explicit provenance edge proving that this exact OHLCV content SHA underlies every pinned primary-5 2023-2025 exact-row set has not yet been established. No substitution or inference is made. Meta label generation remains fail-closed until that edge is pinned.
