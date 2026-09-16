# EDINET Class C corrected same-ZIP receipt — 2026-09-16

Research-only, outcome-blind validation receipt. No strategy returns/performance were opened.

## Frozen execution

- workflow: `EDINET same-ZIP OSS crosscheck research`
- run: `35092381577`
- head SHA: `700de43b199ace40920df441764af03ca9b59a64`
- conclusion: `success`
- artifact: `edinet-same-zip-crosscheck-v1`
- artifact id: `10444563724`
- artifact digest: `sha256:c207bce85ef2bf1dc8185a6ddf086cb0c4261e1655d060da478064af1613950c`

The run used the basis-aware research adapter fixed before the rerun:

- `jppfs_cor:ProfitLoss` -> `net_income_total`
- owners-attributable elements -> `net_income_owners`
- unknown ownership basis -> fail closed

## Corrected result

`crosscheck_summary.json` reports:

- primary sample documents: 48
- source unavailable: 4
- parser comparable: 44
- crosscheck exceptions: 0
- documents all compared fields agree: **41**
- documents with parser findings: **3**
- strategy outcomes opened: **false**

The previous 24 Class-C `ProfitLoss` vs `net_income_owners` one-sided findings are absent after the preregistered basis-aware correction. Net-income status is now:

- `net_income:MATCH` = **41**
- `net_income:BOTH_MISSING` = **3**
- no `net_income:OSS_MISSING_CUSTOM_VALUE` remains

Representative corrected receipts also show non-consolidated `jppfs_cor:ProfitLoss` compared to `net_income_total` with `MATCH`, while owners-attributable `jppfs_cor:ProfitLossAttributableToOwnersOfParent` compares to `net_income_owners` with `MATCH`.

Therefore Class C is closed as `CLASS_C_CROSSCHECK_ADAPTER_OWNERSHIP_BASIS_MISMATCH`, validated by same-ZIP rerun. This is not permission to alter production collector semantics or scoring logic.

## Residual findings

Only the previously isolated Class B2 documents remain:

- `S100QF0X`
- `S100RWZI`
- `S100UXL5`

For each, the remaining one-sided fields are assets/equity/operating_income, giving **3 documents / 9 one-sided rows** total. Net income is `BOTH_MISSING` in those three. These remain `UNRESOLVED_FAIL_CLOSED` pending an independent filing/document -> embedded `G...` report identity rule. No OSS value is accepted by presence alone.

## Disposition

- Class C: **RESOLVED_AND_VALIDATED_SAME_ZIP**
- Class B2: **UNRESOLVED_FAIL_CLOSED**
- performance: **SEALED / NOT OPENED**
