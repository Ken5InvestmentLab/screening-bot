# EDINET document-list inert-row audit — 2026-09-15

Research-only, outcome-blind data-integrity note.

## Source receipt

- Workflow run: `34922234308`
- Artifact: `edinet-metadata-2023`
- Artifact ID: `10378661856`
- Artifact digest reported by GitHub Actions: `sha256:ed838ba08104d6e1c379db0c45673ffd31359068c1c082cb9f1e68806993d496`
- Raw daily file inspected: `2023-01-10.json`
- Raw daily SHA-256: `a2dd6ebd77d4aa5819e267eec072575e050d2d6c60eea7dfc5bdd8873668039c`
- Failing row: result index 292 / seqNumber 293 / docID `S100PXGH`

## Exact second null shape

The second failure is not a normal filing row. It has:

- `docTypeCode = null`
- `submitDateTime = "2023-01-10 15:30"` (timestamp retained)
- `withdrawalStatus = "1"`
- `parentDocID = "S100PV94"`
- `disclosureStatus = "0"`
- `xbrlFlag/pdfFlag/attachDocFlag/englishDocFlag/csvFlag/legalStatus = "0"`
- filing identity fields such as edinetCode/secCode/filerName/formCode are null

This means the first repair was too narrow because it required `submitDateTime=null`.

## Outcome-blind 2023 shape scan

Across the frozen 2023 metadata artifact, rows with `docTypeCode=null` or `submitDateTime=null` are distributed as:

- 32,852 rows: docType null, submitDateTime null, withdrawalStatus 0, disclosureStatus 0, all content/legal flags 0
- 52 rows: docType null, submitDateTime null, withdrawalStatus 2, disclosureStatus 0, all content/legal flags 0
- 31 rows: docType null, submitDateTime present, withdrawalStatus 1, disclosureStatus 0, all content/legal flags 0

Total: **32,935 inert document-list rows** in the inspected 2023 artifact.

No strategy returns, labels, or performance outcomes were opened for this audit.

## Narrow repair

The skip predicate is widened only to rows where:

1. `docTypeCode is null`
2. `disclosureStatus == "0"`
3. every content/legal flag is `"0"`

`submitDateTime` may be null or retained. All other malformed rows remain fail-closed.

Implementation commit: `819d63bbad4c995d8f6345280ce67df0e455effb`

Exact regression fixture commit: `90265c5ecc0b2e3d96d1c85f39eb665e9d4535fc`

OSS validation test run `34936903249`: **PASS**.

Full 2023-2025 metadata freeze retry `34936903153` is running. Do not loosen the predicate further without inspecting and freezing any new exact failing raw shape first.
