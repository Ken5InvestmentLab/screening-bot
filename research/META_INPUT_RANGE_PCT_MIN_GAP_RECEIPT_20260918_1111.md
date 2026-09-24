# Meta range_pct minimum-gap receipt — 2026-09-18 11:11 JST

Status: `MIN_GAP_ARTIFACT_IDENTIFIED_RANGE_PCT`

Scope: research-only provenance. No performance/outcome values inspected or recomputed. 2022 `SUMMARY_ONLY` is excluded from Meta. 2026 remains prohibited. No production/main/workflow files changed.

## Axis selection

Per `research/META_INPUT_RANK_COUNT_PARK_RECEIPT_20260918_1009.md`, rank-pre candidate_count is PARKED after two narrow passes. This run switches only to `range_pct`; breadth and rank-count are not re-searched.

## Exact source-side chain already pinned

- feature code path: `tvfree_screener/run.py`, `build_features()`
- source code blob SHA from controlling Meta manifest: `b639a6f6f33c643c2dcf09383ccf7dbfc7790cfa`
- raw OHLCV columns required: `date`, `symbol`, `high`, `low`, `close`
- exact formula: `range_pct = (high - low) / close`
- row identity / primary-row join key if selected-symbol semantics is confirmed: `signal_date/date + symbol`
- causal label boundary: signal-T raw value may be joined, but 33/67 percentile thresholds must use only the 120 XTKS sessions strictly before signal T; T cannot enter its own threshold history.
- preserved OHLCV artifact previously pinned by the breadth provenance work: Actions artifact `tvfree-frozen-dataset-run80-preserved`, artifact ID `10264205130`; internal daily file `tse_daily.csv`; content SHA256 `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`.

## Single minimum unresolved object

`MISSING_RANGE_PCT_SEMANTICS_RECEIPT`

The controlling manifest explicitly leaves unresolved whether preregistered Meta `range_pct` means:

1. the selected primary signal symbol's symbol-date `range_pct`, or
2. a date-level market aggregate derived from symbol-date `range_pct`.

No existing receipt/code evidence inspected in this narrow pass resolves that semantic choice. It is therefore prohibited to guess an aggregation or to generate Meta labels yet.

This is now the minimum missing artifact/evidence object for the range_pct axis. Once a prereg/receipt/path+SHA fixes the intended semantics, the already-pinned OHLCV path/SHA and `run.py` formula are sufficient to define the source columns and causal lag; a final explicit primary-5 input binding edge may still be required before `META_INPUT_CHAIN_COMPLETE` promotion.

No return calculation was performed.