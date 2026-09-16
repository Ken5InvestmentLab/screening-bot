# EDINET same-ZIP findings taxonomy — 2026-09-16

Research-only, outcome-blind disposition ledger. Strategy returns/performance are not used to select parser values or dispositions.

## Frozen contract

The same source ZIP bytes must be parsed by both implementations. Every mismatch or one-sided missing value is an audit finding; neither parser becomes authoritative because of strategy performance. Unresolved findings remain fail-closed.

## Source-grounded taxonomy progress

### Class A — explicit revenue concept alias missing in custom parser

**Disposition: SOURCE-GROUNDED / FIXED NARROWLY / REGRESSION EVIDENCE PRESENT.**

Frozen real fixture `S100TYEA` (doc type 120) contains `jppfs_cor:OperatingRevenue1` at `CurrentYearDuration`, value `49,687,000,000`, in the frozen ZIP SHA-256 `8ee13034a170adf00e760406cabfe3e025888f7f8ac66beda6097f436138c1ee`. The OSS side mapped the same fact to `net_sales=49,687,000,000`; the prior cross-check status was `CUSTOM_MISSING_OSS_VALUE`.

The accepted repair is deliberately narrow: add only `jppfs_cor:OperatingRevenue1` to the custom revenue element aliases. Do not broaden contexts, resolve multi-member ambiguity, or alter net-income semantics. Commit `dcbb7c8726cb02edd3e59c260354a8e7f1f63044` implements exactly that one alias. The subsequent same-ZIP cross-check run `34944902155` completed successfully and emitted artifact `edinet-same-zip-crosscheck-v1` (artifact `10386890723`, digest `sha256:2affc141851b7701490866be5ddfd35b740ac15e3a0bd48670d2aba3127f96a7`).

This class is therefore not an outcome-selected parser preference; it is a source-XBRL semantic mapping correction backed by a frozen real filing fact and same-ZIP rerun.

### Remaining findings

All other findings remain **UNRESOLVED_FAIL_CLOSED** until each is assigned a source-grounded class such as concept-alias omission, context-selection mismatch, dimensional/member ambiguity, issued-share priority/context issue, parser normalization/rendering issue, or genuine semantic disagreement. Do not bulk-resolve by whichever parser has fewer missing values or better downstream research performance.

## Next action

Recover the frozen same-ZIP cross-check row ledger/artifact and count findings by the above source-grounded classes. Preserve the original 27-finding denominator from the frozen run; do not resample documents. Each newly resolved class must cite exact doc_id/field/source fact and, where code changes, a regression fixture plus same-ZIP rerun.
