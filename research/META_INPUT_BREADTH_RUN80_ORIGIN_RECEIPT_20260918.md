# Meta input breadth run-80 origin receipt — 2026-09-18

Scope: research-only provenance. No return/performance values inspected or recomputed. 2026 prohibited. 2022 SUMMARY_ONLY excluded from Meta. Production/main unchanged.

## Axis

`breadth_ma20` only.

## Newly pinned origin edge

The preserved OHLCV bytes already pinned in `research/META_INPUT_BREADTH_OHLCV_CONTENT_RECEIPT_20260918.md` originate from the exact run-80 TEST artifact, not from a later download or reconstructed dataset.

- original TEST run: `34545440155`
- original TEST run head SHA: `5461eef6f35ea2cea2b4bc38ca7177c681681783`
- original workflow: `.github/workflows/tvfree-screener-test.yml`
- original workflow blob SHA: `c60ef3888037e3b0fc5cc460558b2ae21c27fd8a`
- original artifact name: `tvfree-screener-test-34545440155`
- original cache path created/consumed by the TEST workflow: `tvfree_screener/out/tse_daily.csv`
- preserve run: `34599959356`
- preserve run head SHA: `d03cdff1f27628f44f78d3787b0cc55bfa4bd271`
- preserve workflow: `.github/workflows/tvfree-preserve-dataset.yml`
- preserve workflow blob SHA: `266f440bd9db79e729a58b1817dd3c5022ccdfca`
- preserved artifact id/name: `10264205130` / `tvfree-frozen-dataset-run80-preserved`
- preserved archive-internal path: `tse_daily.csv` (workflow preservation path `preserved/tse_daily.csv`)
- preserved content SHA256: `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`

The preservation workflow explicitly downloads artifact name `tvfree-screener-test-34545440155` from run-id `34545440155` into `preserved`, verifies `preserved/tse_daily.csv`, computes its SHA256, and uploads those exact bytes as `tvfree-frozen-dataset-run80-preserved`. Therefore the preserved content SHA is now pinned to the original run-80 `tvfree_screener/out/tse_daily.csv` origin.

## Causal Tail-cache corroborating edge

A separate causal Tail-cache workflow at head SHA `ef8754d835ccb39faf783092f969417a3ea74ce9` independently downloads the same original run-80 artifact name `tvfree-screener-test-34545440155` from run-id `34545440155` directly into `tvfree_screener/out`, then runs:

`python tvfree_screener/build_tail_research_cache.py --cache tvfree_screener/out/tse_daily.csv`

This pins the causal research-cache lineage to the same original run-80 cache origin without inspecting outcomes.

## breadth_ma20 join contract retained

- feature code: `tvfree_screener/run.py` / `build_features()`
- source blob SHA: `b639a6f6f33c643c2dcf09383ccf7dbfc7790cfa`
- OHLCV columns: `date,open,high,low,close,volume,symbol`
- intermediate: `ma20_gap = close / rolling20(close) - 1`
- raw signal-date feature: `breadth_ma20` = fraction of symbols on `date` with `ma20_gap > 0`
- join key: primary row `signal_date` -> feature/OHLCV `date`
- causal lag: percentile thresholds for signal T use only the 120 XTKS sessions strictly before T; signal-T raw breadth is joined after threshold formation.

## Status

`RUN80_OHLCV_ORIGIN_CHAIN_PINNED`.

This is a new provenance edge beyond the prior archive-content receipt: `original run-80 artifact -> original tse_daily.csv -> preservation workflow -> preserved content SHA`, with independent Tail-cache workflow corroboration.

Fail-closed remainder before `META_INPUT_CHAIN_COMPLETE`: an explicit provenance edge is still required from the pinned primary-5 2023-2025 exact-row generators/receipts to this run-80 cache origin (or its identical content SHA). This receipt does not infer that edge merely because the research workflows share the cache lineage.
