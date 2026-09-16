# EDINET same-ZIP findings taxonomy — 2026-09-16

Research-only, outcome-blind disposition ledger. Strategy returns/performance are not used to select parser values or dispositions.

## Frozen contract

The same source ZIP bytes must be parsed by both implementations. Every mismatch or one-sided missing value is an audit finding; neither parser becomes authoritative because of strategy performance. Unresolved findings remain fail-closed.

## Frozen row-ledger recovery

Recovered the still-live artifact `edinet-same-zip-crosscheck-v1` from same-ZIP run `34944902155` (artifact `10386890723`, digest `sha256:2affc141851b7701490866be5ddfd35b740ac15e3a0bd48670d2aba3127f96a7`). The artifact contains 44 comparable document JSON receipts plus `crosscheck_summary.json`.

The frozen denominator is preserved exactly: 48 primary sample documents, 4 source-unavailable, 44 parser-comparable, 17 documents with all compared fields agreeing, and **27 documents with parser findings**. There are 33 one-sided field finding rows across those 27 documents; `BOTH_MISSING` is not counted as a one-sided parser disagreement.

Recovered one-sided row counts:

| Frozen row class | Rows | Documents |
|---|---:|---:|
| `net_income:OSS_MISSING_CUSTOM_VALUE` | 24 | 24 |
| `assets:CUSTOM_MISSING_OSS_VALUE` | 3 | 3 |
| `equity:CUSTOM_MISSING_OSS_VALUE` | 3 | 3 |
| `operating_income:CUSTOM_MISSING_OSS_VALUE` | 3 | 3 |
| **Total** | **33** | **27 unique docs** |

The three custom-missing documents are `S100QF0X`, `S100RWZI`, and `S100UXL5`; each contributes the same three one-sided fields (assets/equity/operating_income). The 24 net-income findings occur on 24 other documents, so the two groups partition the frozen 27-document denominator.

## Source-grounded taxonomy progress

### Class A — explicit revenue concept alias missing in custom parser

**Disposition: SOURCE-GROUNDED / FIXED NARROWLY / REGRESSION EVIDENCE PRESENT.**

Frozen real fixture `S100TYEA` (doc type 120) contains `jppfs_cor:OperatingRevenue1` at `CurrentYearDuration`, value `49,687,000,000`, in the frozen ZIP SHA-256 `8ee13034a170adf00e760406cabfe3e025888f7f8ac66beda6097f436138c1ee`. The OSS side mapped the same fact to `net_sales=49,687,000,000`; the prior cross-check status was `CUSTOM_MISSING_OSS_VALUE`.

The accepted repair is deliberately narrow: add only `jppfs_cor:OperatingRevenue1` to the custom revenue element aliases. Do not broaden contexts, resolve multi-member ambiguity, or alter net-income semantics. Commit `dcbb7c8726cb02edd3e59c260354a8e7f1f63044` implements exactly that one alias. The subsequent same-ZIP cross-check run `34944902155` completed successfully and emitted the frozen artifact above.

This class is therefore not an outcome-selected parser preference; it is a source-XBRL semantic mapping correction backed by a frozen real filing fact and same-ZIP rerun. It is already absent from the post-fix one-sided finding rows; the 27-document denominator below is the post-fix frozen audit denominator and is not rewritten.

### Class B — explicit custom ambiguity / context-selection disagreement

**Disposition: SOURCE-GROUNDED CLASSIFIED / UNRESOLVED_FAIL_CLOSED.**

The recovered receipts show exactly three documents (`S100QF0X`, `S100RWZI`, `S100UXL5`) where the custom parser explicitly reports `custom_status=ambiguous` and therefore emits no value, while OSS emits values for assets, equity and operating_income. This produces 9 one-sided rows (3 documents × 3 fields).

This is not an alias omission: the custom side did not report `missing`; it reported `ambiguous`. Therefore these rows are classified as **context/member selection ambiguity**. No OSS value is accepted merely because it is present. Resolution requires inspecting the same-ZIP XBRL contexts/members and preregistering a deterministic context-selection rule or retaining ambiguity. Until then all 9 rows remain fail-closed.

#### Class B1 — document-level correlated ambiguity signature

**Disposition: SOURCE-RECEIPT-GROUNDED / NARROWED / STILL UNRESOLVED_FAIL_CLOSED.**

Direct inspection of the frozen per-document receipts shows an identical cross-field signature in all three Class B documents, not three independent field-specific failures:

| doc_id | assets | equity | operating_income | net_income | OSS values present for one-sided fields |
|---|---|---|---|---|---|
| `S100QF0X` | custom `ambiguous` | custom `ambiguous` | custom `ambiguous` | custom `ambiguous`, OSS null (`BOTH_MISSING`) | assets `8,028,504,889`; equity `7,978,470,707`; op income `-375,135,451` |
| `S100RWZI` | custom `ambiguous` | custom `ambiguous` | custom `ambiguous` | custom `ambiguous`, OSS null (`BOTH_MISSING`) | assets `2,274,610,761`; equity `2,187,481,293`; op income `-142,493,605` |
| `S100UXL5` | custom `ambiguous` | custom `ambiguous` | custom `ambiguous` | custom `ambiguous`, OSS null (`BOTH_MISSING`) | assets `3,684,568,452`; equity `3,676,944,688`; op income `236,382,778` |

In the same receipts, revenue and operating cash flow are reported by the custom parser as `missing`, not `ambiguous`. This distinction matters: the ambiguity spans both instant-type balance-sheet fields (assets/equity) and duration-type income fields (operating_income/net_income), while unrelated absent fields retain `missing` status. The safest current interpretation is therefore **document-level context/member collision affecting multiple mapped concepts**, rather than a missing concept alias or a single-field extractor defect.

This narrows the next source inspection: enumerate candidate contexts/members for these four ambiguous mapped concepts in each of the three frozen source ZIPs and test whether one deterministic context preference resolves all mapped concepts consistently. Do not accept the OSS values, and do not add a field-specific alias, until that source-XBRL check is complete. The 9 one-sided rows plus the three `BOTH_MISSING` net-income ambiguity observations remain fail-closed.

### Class C — ProfitLoss vs OSS net-income semantic coverage

**Disposition: SOURCE-GROUNDED CLASSIFIED / UNRESOLVED_FAIL_CLOSED.**

All remaining 24 one-sided rows have one identical structural pattern: field `net_income`, status `OSS_MISSING_CUSTOM_VALUE`, custom element `jppfs_cor:ProfitLoss`, context `CurrentYearDuration_NonConsolidatedMember`, and a concrete custom value. OSS `net_income_owners` is null in every one of these 24 receipts.

This is therefore not 24 unrelated missing-data events. It is one repeated **semantic/concept coverage disagreement** between the custom parser's non-consolidated `ProfitLoss` mapping and the OSS adapter's `net_income_owners` field. Do not map `ProfitLoss` into OSS `net_income_owners` automatically: `ProfitLoss` and profit attributable to owners can differ semantically depending on consolidation/context. Resolution requires source-XBRL inspection plus the OSS library's field semantics. Until that mapping is proven equivalent for the relevant non-consolidated contexts, all 24 rows remain fail-closed.

## Frozen accounting after recovery

The post-fix 27-document finding denominator is now completely partitioned at the structural/source-receipt level:

- **3 docs / 9 one-sided rows — Class B/B1 document-level correlated context/member ambiguity — unresolved fail-closed**
- **24 docs / 24 rows — Class C ProfitLoss/net_income_owners semantic coverage — unresolved fail-closed**
- **27 docs / 33 one-sided rows total**

This is a taxonomy completion and narrowing, not a semantic resolution. No finding has been cleared merely by grouping it, and no parser was selected using downstream strategy performance.

## Next action

For Class B/B1, acquire/inspect the actual same-ZIP source XBRL contexts and members for `S100QF0X`, `S100RWZI`, and `S100UXL5`; compare candidate contexts across assets/equity/operating_income/net_income and freeze a deterministic cross-field context-selection disposition or retain ambiguity. For Class C, inspect representative same-ZIP XBRL facts and the OSS `net_income_owners` mapping semantics to determine whether non-consolidated `ProfitLoss` is intentionally unsupported or safely equivalent in a constrained context. Any code change requires a regression fixture plus same-ZIP rerun. Unresolved remains fail-closed.
