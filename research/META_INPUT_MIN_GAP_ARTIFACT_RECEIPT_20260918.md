# Meta input minimum-gap artifact receipt — 2026-09-18

Scope: research-only provenance. No performance/outcome values inspected or recomputed. 2026 prohibited. Production/main unchanged.

## Selected axis

`breadth_ma20` is selected as the minimum-gap axis from `research/META_REGIME_INPUT_MANIFEST_20260918.md` at commit `b3d17a0b33070d03bbf7c4c16cc2d9b067160c9d`.

Known code/formula chain from the manifest:
- source code: `tvfree_screener/run.py` / `build_features()`
- source blob SHA: `b639a6f6f33c643c2dcf09383ccf7dbfc7790cfa`
- raw column: `breadth_ma20`
- definition: signal-date fraction of symbols with `ma20_gap > 0`, where `ma20_gap = close / rolling20(close) - 1`
- causal Meta lag: percentile/threshold history must use only the 120 XTKS sessions strictly before signal T; signal T raw value may be joined only after thresholds are formed.

## Newly pinned minimum missing artifact

GitHub Actions run `34599959356` on branch `test/tvfree-screener-v1`, head SHA `d03cdff1f27628f44f78d3787b0cc55bfa4bd271`, has exactly one preserved dataset artifact:

- artifact id: `10264205130`
- artifact name/path-level identity: `tvfree-frozen-dataset-run80-preserved`
- artifact archive digest: `sha256:095e58986d45bda0092be1767e1b44a4791bf3c617179791d0c99c6d7d01bcb0`
- size: `49,866,286` bytes
- expired: false

The existing manifest already identifies preserved dataset run `34599959356` as the frozen dataset source referenced by the 2023-2025 V16 chain. This receipt upgrades that run reference to an exact artifact ID/name/archive SHA.

## Status

`MIN_GAP_ARTIFACT_IDENTIFIED` for `breadth_ma20`.

This does **not** yet claim `META_INPUT_CHAIN_COMPLETE`: the archive-internal daily OHLCV file path/content SHA and an explicit proof that the same bytes underlie every pinned primary-5 2023-2025 row set remain to be tied down. Therefore Meta label generation remains fail-closed. 2022 SUMMARY_ONLY is excluded.
