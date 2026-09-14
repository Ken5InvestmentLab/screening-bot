# OSS research tooling handoff — 2026-09-14

Supporting branch: `research/oss-validation-tooling`

Latest tested code head before this handoff: `050f5dc833f156fd3041c386082126487ab6d30e`
(latest branch also contains documentation-only follow-up).

CI run: `34796460950` — SUCCESS
- 8 isolated pytest checks passed
- existing EDINET fundamental collector self-test passed

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
