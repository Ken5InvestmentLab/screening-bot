# EDINET Class C ownership-basis disposition — 2026-09-16

## Scope / guardrail
Research-only, outcome-blind semantic audit of the already-frozen same-ZIP crosscheck. No strategy returns/performance were opened and no parser value is selected because of downstream performance.

Frozen crosscheck run `35081622646` (artifact `10440293333`, digest `sha256:147181ed5fd58df53d223f107d3539520a578c11055092705dc84db5f889cb55`) reproduces the existing 24 Class-C documents. In every Class-C row:

- custom element: `jppfs_cor:ProfitLoss`
- custom context: `CurrentYearDuration_NonConsolidatedMember`
- custom status: `ok`
- OSS field compared by our adapter: `net_income_owners`
- OSS value: `null`
- crosscheck status: `OSS_MISSING_CUSTOM_VALUE`

The 24-document partition is unchanged; values are intentionally not reproduced here.

## Source-grounded semantic cause
The crosscheck adapter maps custom `net_income` to OSS `net_income_owners`. That mapping is not semantically valid for `jppfs_cor:ProfitLoss`.

Pinned OSS dependency is `edinet-tools==0.8.4`. Upstream 0.8.0+ explicitly split net income by ownership basis:

- `net_income_owners`: profit attributable to owners of parent.
- `net_income_total`: total-basis profit including non-controlling interests.

Upstream `securities.py` is explicit that owners-basis sources fill only `net_income_owners`, while `jppfs_cor:ProfitLoss` fills only `net_income_total`; there is no cross-basis coalescing.

Therefore Class C is **not evidence that edinet-tools missed the same semantic fact**. It is a crosscheck-adapter basis mismatch: our adapter compared a total-basis custom fact to an owners-basis OSS field.

## Deterministic disposition
Class C is classified as:

`CLASS_C_CROSSCHECK_ADAPTER_OWNERSHIP_BASIS_MISMATCH`

For future research-only crosschecks, the comparison target must be selected from the custom element semantic basis before values are compared:

- `jppfs_cor:ProfitLoss` -> compare with `report.net_income_total`
- `jppfs_cor:ProfitLossAttributableToOwnersOfParent` -> compare with `report.net_income_owners`
- IFRS/US-GAAP owners-attributable elements -> owners basis
- unknown/unclassified net-income elements -> fail closed; do not guess or coalesce bases

This rule is source-semantic and fixed without strategy outcomes. It does **not** authorize replacing the custom collector's production semantics, changing scoring inputs, or choosing whichever basis yields a better backtest.

## Status
The **cause** of all 24 Class-C rows is resolved. Their old `OSS_MISSING_CUSTOM_VALUE` labels should be treated as invalid same-concept comparisons, not parser failures. A corrected research-only same-ZIP rerun may reclassify them only after the adapter implements the basis-aware mapping above. Any residual disagreement after that rerun remains fail-closed.

Class B2 remains separately unresolved: filing/document identity still must map to exactly one embedded `G...` report before any fact selection.
