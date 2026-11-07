# Meta rank-pre candidate-count input-chain receipt — 2026-09-18 06:51 JST

Status: `RANK_COUNT_INPUT_CHAIN_BLOCKED_ONE_GAP`

Scope is research-only. This receipt inspects provenance/code only. No performance/outcome values were used, no return metrics were recomputed, 2022 SUMMARY_ONLY is excluded from Meta, and 2026 is prohibited. No production/main/workflow/Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist files are changed.

## KNOWN exact source chain

- Actions artifact: `tvfree-v7-causal-tail-cache-2023-2025`, artifact ID `10264251140`, artifact digest `sha256:2f67833af2881754336c8f92cbf463ddf1cb995bd0fc808a962479d1bfd44198`.
- Internal source path: `v7_causal_tail_cache_2023_2025.csv`.
- Internal file SHA256: `0398969e13cc4b79f64cf8ad3b300ab34c0270ac70d20367994979478b60849d`.
- Key columns available in the pinned cache: `date`, `symbol`, `volr20`, `med_ret5`, `tail_p`, `tail` (plus other feature columns). Join identity for signal rows is therefore mechanically `date + symbol`; same-day universe counting keys on `date`.
- Companion metadata SHA256: `7f992eaf8944c00018fd03311f92a1204fdf7df6d390b4a11ecabf028daf0a59`.
- Exact V16 selector source: `tvfree_screener/v16_pre2025_volr20_rank.py`, Git blob `13fd0e87e81034757ca6b6f0a0b57abecae35109`.
- The selector establishes ordering: start from Tail rows, apply same-signal-date market gate `med_ret5 <= 0`, sort same-day candidates by `volr20` ascending then Tail score descending, take same-day top 4, then apply one-XTKS-session same-symbol cooldown while choosing the final row. Thus a Meta `rank前candidate_count` must be counted on the applicable candidate universe at signal T before rank/selection/cooldown; it must not be counted from final picks.
- Meta category rule remains prereg-fixed: `SCARCE=1`, `MULTI=2+`. No outcome-dependent threshold is introduced here.

## Applicability boundary

The exact Tail-cache + V16 code chain proves the pre-rank universe semantics for the V16/volr20 lineage only. It does **not** prove that `body_pct LOW`, `mean-rank(volr20,body_pct)`, `DUAL_TOP1_AGREEMENT`, or `DUAL+G3` used this same pre-rank universe. Generalizing this V16 universe to those primary candidates would be a near-logic substitution and is forbidden.

## Single remaining provenance gap

`MISSING_PRIMARY5_RANK_UNIVERSE_BINDING_RECEIPT`

Exactly one evidence object is still required to complete the axis: a research receipt/artifact with an exact path + content SHA that binds each 2023-2025 primary-5 pinned signal-row artifact to the **lineage-specific pre-rank candidate-universe artifact used on that signal date**, and states the candidate-universe join/count key (`date`, and `symbol` where row identity is needed).

Until that one binding receipt exists, candidate-count remains fail-closed and `RANK_COUNT_INPUT_CHAIN_COMPLETE` must not be declared. The already pinned Tail-cache SHA `0398969e...` may satisfy the source side only for a primary lineage explicitly proven to use it.

## Next action

Do not rescan the repository broadly and do not regenerate primary trade rows. Search only existing primary-5 SOURCE_POOL_EXACT/pinned-row receipts for an explicit upstream pre-rank-universe artifact path/SHA binding. If none exists on the next productive run, this rank-count chain has reached the two-run no-progress threshold and should be PARKED/reallocated per supervisor rule.
