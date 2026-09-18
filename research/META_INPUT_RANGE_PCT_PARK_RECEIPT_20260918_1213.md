# Meta range_pct park receipt — 2026-09-18 12:13 JST

Status: `RANGE_PCT_PARKED_AFTER_2_NARROW_PASSES`

Scope: research-only provenance. No performance/outcome values inspected or recomputed. 2022 `SUMMARY_ONLY` is excluded from Meta. 2026 remains prohibited. No production/main/workflow files changed.

## Narrow-pass result

This pass followed only the single unresolved object fixed by `research/META_INPUT_RANGE_PCT_MIN_GAP_RECEIPT_20260918_1111.md`: `MISSING_RANGE_PCT_SEMANTICS_RECEIPT`.

A repository code search for the preregistered `range_pct` Meta semantics did not surface an existing receipt/code edge that resolves whether Meta `range_pct` is (a) the selected primary signal symbol's signal-date value or (b) a signal-date market aggregate. No aggregation semantics are inferred or invented.

## Preserved exact source-side chain

- feature code: `tvfree_screener/run.py` / `build_features()`
- controlling source blob SHA: `b639a6f6f33c643c2dcf09383ccf7dbfc7790cfa`
- formula: `range_pct = (high - low) / close`
- required source columns: `date`, `symbol`, `high`, `low`, `close`
- preserved daily source: Actions artifact `tvfree-frozen-dataset-run80-preserved`, artifact ID `10264205130`, internal `tse_daily.csv`
- daily content SHA256: `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`
- causal boundary already fixed: signal-T raw value may be used only after semantics are fixed; 33/67 thresholds must use the 120 XTKS sessions strictly before T, excluding T from its own threshold history.

## Decision

This is the second narrow pass on `range_pct` without closing `MISSING_RANGE_PCT_SEMANTICS_RECEIPT`. Per Supervisor rule, do not broaden search and do not continue repeating this axis. `range_pct` is therefore PARKED fail-closed.

`META_INPUT_CHAIN_COMPLETE` is NOT claimed. Breadth and rank-count remain separately parked at their previously recorded minimum missing binding edges. Further progress requires a new exact provenance/semantics artifact, not another broad repository search.
