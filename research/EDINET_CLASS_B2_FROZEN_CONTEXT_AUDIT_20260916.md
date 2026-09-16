# EDINET Class B2 — frozen context audit (2026-09-16)

Outcome-blind/source-grounded inspection of the exact pre-parser frozen artifact from run `34943585921`, artifact `10385897929`. No strategy returns/performance were opened and no accounting fact was selected.

## Result
The prior Class B1 `document-level correlated ambiguity` is narrowed to **Class B2: multiple embedded report CSVs reuse the same canonical context labels while carrying distinct current-period values**.

For all four mapped fields (`assets`, `equity`, `operating_income`, `net_income`), each affected document contains multiple current-period candidates with the same semantic context family (`CurrentYearInstant_NonConsolidatedMember` for instant fields; `CurrentYearDuration_NonConsolidatedMember` for duration fields), spread across multiple `jpsps070000-asr-001_G...` CSVs. The current-period values are distinct across those files; values themselves are intentionally not recorded here.

| doc_id | frozen ZIP sha256 | mapped report CSVs | current candidates per mapped field | distinct current values per mapped field |
|---|---|---:|---:|---:|
| S100QF0X | `9f057056fc91b2c74ea52592a913a629a66dd3c6d5d6d4f0f3db3fd0a5e4fef8` | 3 | 3 | 3 |
| S100RWZI | `ecf2938f893ea9faccc0b0caf49a4e463020997402e239480cda0cad6754416b` | 4 | 4 | 4 |
| S100UXL5 | `4685a2f36de9174984d374dad7decaeb9dcca152581998a3f30c279f8c7c2a31` | 3 | 3 | 3 |

The same pattern spans instant and duration fields, so a field-specific alias change cannot solve it. A context-id-only rule also cannot solve it because the competing embedded CSVs reuse the same CurrentYear context ids.

## Disposition
**FAIL_CLOSED remains required.** Do not choose the first/last CSV, largest/smallest value, or the OSS parser value. A deterministic source-semantic mapping from the filing/document identity to exactly one embedded `G...` report would be required before these facts can be admitted. Until that mapping is independently established, the 3 documents / 9 one-sided Class-B finding rows remain unresolved.

## Reproducibility
`tvfree_screener/edinet_context_member_audit.py` enumerates candidate source CSV/context metadata from the frozen ZIPs without emitting accounting values or strategy outcomes. `.github/workflows/edinet-same-zip-crosscheck-research.yml` now invokes this audit after verifying the existing freeze lock. Connector-originated commits did not automatically create a new Actions run in this cycle, so the committed audit is ready for the next normal/dispatch execution; the classification above was independently reproduced directly from the downloaded frozen artifact bytes.
