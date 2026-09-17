# Alternate-family exact forensic receipt — 2026-09-17 17:46 JST

## Scope
P0 exact/deterministic recovery only. 2026 outcomes remain SEALED. No production/main/workflow/Discord/Spreadsheet/Stable/Sniper/Mega/TradingView/watchlist changes.

## strict_3pt
Status: `NOT_REPRODUCIBLE_YET / REFERENCE_ONLY`.

No source artifact, trade rows, receipt, code definition, or SHA chain identifying `strict_3pt` has been recovered. No nearby rule was substituted and no performance was generated.

## Eliminated false lineage: legacy optimizer/scoring scripts
The recovered `codex/data-driven-entry-strategy` lineage is not accepted as an exact source for `strict_3pt`:
- `_list_candidate_a.py` blob `fa19886a77f272ab48cdcc33974db8896d92bc3f` defines Candidate A as `vol12+body2+atr5+stoch75+rsi4060+gap_up` and reports 40BD/other legacy perf fields.
- `analyze_compare_two.py` blob `8d9435f1af00cdb68032b50cfbbbf5ecf2222418` compares explicit six-condition A/B/current logic across legacy 5BD/10BD/20BD modules.
- `explore_scoring_logic.py` blob `f3b018fb9c22e03fab407db8a2b73f68d019a36a` is a broad N-of-K/weighted/threshold explorer over Mega validation data.

None provides evidence tying its candidate identity to `strict_3pt`, and their evaluation contracts are not the required canonical `signal T -> next XTKS open -> fifth XTKS close`. Treating any as `strict_3pt` would be prohibited inference.

Decision: this lineage is `EXCLUDED_AS_STRICT_3PT_SOURCE` unless a future immutable artifact/receipt explicitly links the identity.

## Newly recovered alternate-family evidence chain
`core_bollinger_reclaim` has an immutable outcome-blind pool reproduction receipt at blob `c5b47f1380f8c9ee31db4588b15d8eb826b57e90` (`CORE-BOLLINGER-RECLAIM-20260913-01`). It records exact decision hashes for pool/ranked/selected, `reproduced_exactly=true`, `outcome_values_opened=false`, and `2024_plus_numeric_ohlcv_opened=false`.

This is genuine deterministic source/pool provenance, but it is NOT admitted to the common comparison ranking yet: there is not yet a recovered normalized 2022-computable/2023/2024/2025 trade-row chain under the common endpoint contract. Status: `SOURCE_POOL_EXACT / PERFORMANCE_COMPARISON_NOT_ELIGIBLE_YET`.

## Next forensic action
Continue from alternate-family artifacts that already contain `*_pool_receipt.json`, `*_pool_reproduction.json`, spec SHA and code, prioritizing candidates with historical outcome evidence through 2025. Do not open 2026. Cloud Monster remains last and reference-only unless exact evidence is recovered.
