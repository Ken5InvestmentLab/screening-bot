# Invalid evaluation notice

`core_trend_compression_fixed_policy_diagnostic.json` and `.md` are retained as an audit trail only. Do not use their Top-N resolved-only results to judge or tune this scoring family.

The label table used by that report was scoped to a different model's feature-eligible rows. It omitted valid frozen trend-compression choices, which were consequently counted as `LABEL_ROW_MISSING`. That status indicates absent evaluation coverage, not a demonstrated trading failure. The missing joins invalidate the report's policy return summaries.

The candidate pool, rankings, and selections remain frozen. The separately registered label-recovery diagnostic rebuilds the same target for every frozen pool row from the bounded 2022-2023 daily OHLCV panel. No thresholds or policy choices may be changed in response to the invalid report.
