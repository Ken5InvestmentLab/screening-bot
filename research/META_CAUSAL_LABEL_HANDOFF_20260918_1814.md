# META CAUSAL LABEL HANDOFF — 2026-09-18 18:14 JST

Status: RESEARCH ONLY / META PREPARATION RESUMED / NO RULE FREEZE. 2026 SEALED. No production writes.

Primary selector prerequisite is resolved for the computable historical set by `research/PRIMARY5_C5_G3_REFERENCE_ONLY_RECEIPT_20260918.md`: C1-C4 are computable; C5 is REFERENCE_ONLY, not PENDING. No G3 threshold is inferred.

This handoff resumes Meta preparation from the latest explicit Meta provenance only; no performance values, 2022 legacy 29/23 membership, or 2026 data are used.

## First META_LABEL axis: breadth_ma20

Use the already-pinned causal contract from `META_REGIME_INPUT_MANIFEST_20260918.md` and `META_INPUT_BREADTH_RUN80_ORIGIN_RECEIPT_20260918.md`:

- source artifact: `10264205130` / `tvfree-frozen-dataset-run80-preserved`
- archive path: `tse_daily.csv`
- source content SHA256: `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`
- origin: run `34545440155`, `tvfree_screener/out/tse_daily.csv`
- feature code: `tvfree_screener/run.py` `build_features()`
- feature-code blob SHA: `b639a6f6f33c643c2dcf09383ccf7dbfc7790cfa`
- required raw columns: `date,open,high,low,close,volume,symbol`
- intermediate: `ma20_gap = close / rolling20(close) - 1`
- raw feature: per-date fraction of symbols where `ma20_gap > 0`
- join key: primary exact row `signal_date` -> breadth series `date`
- causal threshold lag: 33/67 percentile thresholds for signal T are formed from the 120 XTKS sessions strictly before T; T is excluded from threshold formation; signal-T raw breadth is then labelled against those frozen-at-T thresholds.
- intended signal-date coverage: 2023-2025 exact C1-C4 primary rows. 2022 labels may be appended only after canonical 2022 rows exist, with this same definition. C5 remains excluded while REFERENCE_ONLY.

## Fail-closed boundary

Do not emit a joined `META_LABEL` yet unless the exact 2023-2025 primary-row generator/receipt supplies an explicit provenance edge to the above run-80 cache origin or identical SHA. Existing Meta receipts explicitly identify that binding as the final breadth-chain gap. Shared lineage alone is not sufficient.

Next substantive action is therefore narrowly defined: recover or produce the explicit `primary C1-C4 exact rows -> input cache SHA 6adfb626...` binding receipt. Once that edge exists, breadth_ma20 is the first axis eligible for signal-date META_LABEL materialization. Do not reopen rank-count or range_pct before this breadth binding attempt is resolved.

Meta rule final freeze remains prohibited until primary historical complete and alt historical complete are both available.