# Meta input axis reallocation receipt — 2026-09-18 09:13 JST

Status: `BREADTH_BINDING_GAP_PARKED__RANK_COUNT_MIN_GAP_PINNED`

Scope: research-only provenance. No performance/outcome values inspected or recomputed. 2022 `SUMMARY_ONLY` is excluded from Meta. 2026 remains prohibited. No production/main/workflow files changed.

## Why breadth_ma20 is parked for now

The two preceding productive provenance passes pinned the preserved OHLCV bytes and their run-80 origin, but did not establish the final explicit provenance edge from every primary-5 pinned 2023-2025 exact-row lineage back to those exact OHLCV bytes. Repeating the same artifact/origin search is therefore prohibited by the Supervisor two-run rule.

Pinned source side remains valid and unchanged:
- preserved daily OHLCV internal path: `tse_daily.csv`
- content SHA256: `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`
- feature code: `tvfree_screener/run.py` / `build_features()`; blob `b639a6f6f33c643c2dcf09383ccf7dbfc7790cfa`
- `breadth_ma20` reconstruction: per signal date, fraction of eligible symbols with `ma20_gap > 0`, where `ma20_gap = close / rolling20(close) - 1`
- causal Meta threshold history: only the 120 XTKS sessions strictly before signal T; signal T must not enter its own percentile thresholds.

Single unresolved breadth evidence object: `MISSING_PRIMARY5_OHLCV_BINDING_RECEIPT` — an exact receipt/path+SHA that binds each primary-5 pinned 2023-2025 signal-row lineage to the preserved OHLCV content SHA above. Until present, `META_INPUT_CHAIN_COMPLETE` is not declared for breadth.

## Reallocated axis: rank-pre candidate_count

The narrow existing receipt `research/META_RANK_COUNT_INPUT_CHAIN_RECEIPT_20260918_0651.md` pins the nearest source artifact without broad repository search:
- Actions artifact: `tvfree-v7-causal-tail-cache-2023-2025`, artifact ID `10264251140`
- artifact digest: `sha256:2f67833af2881754336c8f92cbf463ddf1cb995bd0fc808a962479d1bfd44198`
- internal path: `v7_causal_tail_cache_2023_2025.csv`
- internal file SHA256: `0398969e13cc4b79f64cf8ad3b300ab34c0270ac70d20367994979478b60849d`
- key columns: `date`, `symbol`, `volr20`, `med_ret5`, `tail_p`, `tail`
- signal-row identity key: `date + symbol`; same-day count key: `date`
- exact V16 selector: `tvfree_screener/v16_pre2025_volr20_rank.py`, blob `13fd0e87e81034757ca6b6f0a0b57abecae35109`
- causal/ordering boundary: count on signal T after the lineage's signal-time eligibility/gate and before ranking/selection/cooldown; never count final picks.

The exact Tail-cache/V16 chain is admissible only for the V16/volr20 lineage. It must not be generalized to body_pct LOW, mean-rank, DUAL_TOP1, or DUAL+G3.

## One minimal missing object now targeted

`MISSING_PRIMARY5_RANK_UNIVERSE_BINDING_RECEIPT`

Required evidence is exactly one research receipt/artifact that binds each primary-5 2023-2025 pinned signal-row artifact to its lineage-specific pre-rank candidate-universe artifact with exact source path + content SHA and states the join/count keys. This is now the sole target for the reallocated axis. No regeneration of returns or rows is authorized.

No axis is promoted to `META_INPUT_CHAIN_COMPLETE` by this receipt; fail-closed status is preserved.