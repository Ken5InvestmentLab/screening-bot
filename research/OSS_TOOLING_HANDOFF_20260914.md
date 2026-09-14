# OSS research tooling handoff — 2026-09-14

Supporting branch: `research/oss-validation-tooling`

Original integrated head: `050f5dc833f156fd3041c386082126487ab6d30e` (CI `34796460950` SUCCESS).

Supervisor audit correction applied afterward:
- custom issued-share priority fix: `e701196f812d969902ec805c9ad7b09dfa328878`
- OSS raw-fact priority alignment: `d7c2d539708d6613757a081ee2592a35ea76e257`
- regression tests: `9e568d7cf51a4ad05b358d08827a94f99410820c`

Use the corrected branch head, not the original 050f5dc implementation, for future EDINET research.

## Available tools

### purgedcv audit layer
Files:
- `tvfree_screener/oss_validation.py`
- `tvfree_screener/oss_validation_requirements.txt`

Use for independent temporal-overlap audit and PSR/DSR/effective-trial-count
sensitivity. It supplements, not replaces, the repository's temporal policy.

### Optuna discovery-only harness
Files:
- `tvfree_screener/optuna_discovery.py`
- `research/OPTUNA_DISCOVERY_CONTRACT_20260914.json`

Rules:
- genuinely new family only;
- 2022-07-01..2023-12-31 candidate dates only;
- labels must resolve by 2023-12-31;
- 2024/2025/2026 are forbidden as selection inputs;
- feature set/candidate universe/target/top-N/cost fixed outside Optuna;
- first version tunes only LogisticRegression C;
- date-grouped purged walk-forward objective;
- every completed trial retained for DSR sensitivity;
- no automatic promotion.

Do not use this harness to rescue any family already rejected or whose later
outcomes have already been opened.

### EDINET independent cross-check
Files:
- `tvfree_screener/edinet_oss_crosscheck.py`
- research-branch adjustment to `edinet_fundamental_collector.py`
- `research/EDINET_OSS_CROSSCHECK_CONTRACT_20260914.json`

Finding:
The prior custom issued-share extractor generically accepted only
`CurrentYear...` contexts, while real EDINET filings commonly expose
`NumberOfIssuedSharesAsOfFiscalYearEnd...` under
`FilingDateInstant_OrdinaryShareMember`.

Research-branch priority is now frozen as:
1. `TotalNumberOfIssuedSharesSummaryOfBusinessResults` at CurrentYear;
2. fiscal-year-end issued shares at CurrentYear;
3. fiscal-year-end issued shares at FilingDateInstant fallback.

Parser disagreements are audit findings only. Never pick the parser/value that
improves performance. Existing submit/available timestamps remain the PIT
authority.

## Coordination rule

This is support infrastructure, not a fifth competing strategy lane. Existing
Canonical/Event, Core and Consensus workers should not detour into retuning
their rejected/opened families. The next genuinely new low-DOF family may start
from or selectively port this tooling before outcomes are opened.

Production/main and production integrations remain untouched.


### Supervisor correction to issued-share priority

The first implementation used element-first generic ranking and could allow a
summary-table `FilingDateInstant...` fact to outrank a fiscal-year-end
`CurrentYear...` fact. That contradicted the frozen contract even though both
custom and OSS parsers could agree on the same wrong choice.

Correct frozen priority is enforced explicitly:
1. summary-table issued shares at CurrentYear only;
2. either fiscal-year-end issued-share alias at CurrentYear;
3. either fiscal-year-end issued-share alias at FilingDateInstant.

Conflicting values inside one priority fail closed. Do not port the pre-fix
selection code to other research branches.
