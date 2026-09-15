# EDINET real same-ZIP OSS cross-check audit — 2026-09-15

Status: **AUDIT COMPLETE WITH FINDINGS / OUTCOME-BLIND / NO PARSER CHOSEN**

## Frozen provenance

- Primary preregistered real sample: **48 documents**
- Full metadata/sample freeze run: `34940882530` — SUCCESS
- Frozen metadata rows: **216,094**
- Frozen selected sample: **48**
- Full-sample type=5 acquisition run: `34943233640` — FAIL at first source-unavailable selected filing after 22 successful downloads
- Frozen metadata source-availability audit: **44/48 parser-comparable, 4/48 source-unavailable**
- Source-unavailable IDs: `S100T45P`, `S100UGOG`, `S100W9BM`, `S100WSHJ`
  - all four are docTypeCode=130
  - all four advertise `csvFlag=0`, `xbrlFlag=0`, `pdfFlag=1`
  - no parent/later document substitution is allowed
- Parser-comparable ZIP freeze run: `34943585921` — SUCCESS
- Frozen ZIP artifact: `10385897929`
- Artifact digest: `sha256:3b63996b8cd1d49aadaabbd1b5456e80b24fd68727dd3141f8d724b7d277fe81`
- Embedded freeze-receipt SHA-256: `bdc3be943ffd51446068789e49628c8eaa5d0e91b22ea40626d7a0283d01cead`
- Aggregate 44-ZIP SHA chain: `146c82a288fc0df63851d6f4eaf4954687f89c75bcd862320ce5f8a647cd44bf`
- Same-ZIP cross-check run: `34944052995` — SUCCESS
- Cross-check artifact: `10385469806`
- Cross-check artifact digest: `sha256:a9eb68e9f2086adac69916e1e948b4f009805c9c2642b90ea8c3d75727da1d56`
- Cross-check summary SHA-256: `93fb6db6d9a2b7a9e047ce3a7cdd1ed5c8ad98af6928d556b5d1e972c4cb26e7`

No strategy return, 2026 outcome, candidate score, or backtest performance was read or used.

## Cross-check result

- parser-comparable selected documents: **44**
- completed cross-checks: **44**
- parser exceptions: **0**
- all compared fields agree: **16 documents**
- one or more audit findings: **28 documents**

Field-level statuses:

| Field | MATCH | BOTH_MISSING | CUSTOM_MISSING_OSS_VALUE | OSS_MISSING_CUSTOM_VALUE |
|---|---:|---:|---:|---:|
| assets | 41 | 0 | 3 | 0 |
| equity | 41 | 0 | 3 | 0 |
| revenue | 21 | 22 | 1 | 0 |
| operating_income | 41 | 0 | 3 | 0 |
| net_income | 17 | 3 | 0 | 24 |
| operating_cf | 23 | 21 | 0 | 0 |
| shares_outstanding | 22 | 22 | 0 | 0 |

## Finding classes

### F1 — net-income semantic scope mismatch, not parser winner/loser

All **24** `OSS_MISSING_CUSTOM_VALUE` net-income findings share the same shape:

- custom element = `jppfs_cor:ProfitLoss`
- custom context = `CurrentYearDuration_NonConsolidatedMember`
- OSS comparison field = `net_income_owners`
- OSS value = missing

The remaining 17 matched net-income documents use `jppfs_cor:ProfitLossAttributableToOwnersOfParent`; 3 are missing in both.

Therefore the current cross-check maps a broader custom `ProfitLoss` fallback to the narrower OSS `net_income_owners` metric. Those 24 rows must be treated as **semantic non-equivalence findings**, not evidence that either parser is correct. Do not delete the custom value or impute the OSS value based on this comparison.

### F2 — three multi-member context collisions correctly fail closed in custom parser

`S100QF0X`, `S100RWZI`, and `S100UXL5` are custom-`ambiguous` for assets/equity/operating_income while OSS emits one value.

Raw frozen ZIP inspection shows the same element ID and same `CurrentYear...NonConsolidatedMember` context repeated across multiple `XBRL_TO_CSV` members with **different numeric values**. Examples include multiple fund/member CSVs such as `...-001`, `...-002`, etc.

The custom parser's ambiguity stop is therefore a real identity/data-integrity guard. The OSS-emitted value must **not** be adopted automatically. A separate member-identity contract would be required before resolving these filings.

### F3 — one concrete custom revenue alias coverage gap candidate

`S100TYEA` is custom-missing / OSS-valued for revenue. The exact frozen ZIP contains:

- `jppfs_cor:OperatingRevenue1`
- context `CurrentYearDuration`
- value **49,687,000,000**

This equals the OSS `net_sales` extraction for the document. The current custom revenue alias list does not include `jppfs_cor:OperatingRevenue1`.

This is a legitimate **outcome-blind alias candidate**, but it is not yet accepted. Before changing the parser, freeze a targeted fixture from the exact ZIP and verify that adding the alias does not silently resolve unrelated multi-member ambiguity.

## Decision

- Do not choose custom or OSS globally.
- Keep the 4 source-unavailable primary-sample documents as explicit findings; no replacement.
- Keep the 3 multi-member ambiguous documents fail-closed.
- Reclassify the 24 `ProfitLoss` vs `net_income_owners` cases as semantic-scope findings in the next audit schema.
- Next safe parser change candidate: targeted `OperatingRevenue1` revenue-alias fixture/test only, followed by the same frozen 44-ZIP cross-check.
- Strategy/backtest use of EDINET fields remains blocked until the audit semantics are resolved.

Current decision: **NO-GO / validation continues**.
