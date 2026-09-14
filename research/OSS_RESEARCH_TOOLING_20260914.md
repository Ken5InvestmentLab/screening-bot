# OSS validation tooling review — 2026-09-14

## Decision

Adopt a small, isolated OSS research layer on branch
`research/oss-validation-tooling`:

- **purgedcv 0.1.6** for independent temporal-leakage and selection-bias audits;
- **Optuna 5.0.0** for guarded discovery-only low-DOF search;
- **edinet-tools 0.8.4** for outcome-blind EDINET parser cross-checks.

This does **not** replace the repository's frozen XTKS calendar, point-in-time
universe, label construction, temporal policy, or existing weekly block
bootstrap. It must not touch production/main, Discord, Spreadsheet, Stable★6,
Sniper, Mega, TradingView, watchlist-builder, or watchlist-updater.

Latest integrated CI: **run 34796460950 — SUCCESS** on Python 3.12 (8 pytest checks passed; existing EDINET collector self-test also passed).

## purgedcv

`tvfree_screener/oss_validation.py` exposes:

- `purged_kfold_audit`: independent PurgedKFold + audit_splitter check;
- `selection_bias_summary`: PSR plus raw-trial and autocorrelation-adjusted
  effective-trial DSR sensitivity;
- CLI modes `cv` and `dsr`.

The DSR helper reports both raw and effective trial-count views. Neither is an
automatic GO/NO-GO gate. Effective trial count is heuristic, and overlapping
5BD observations must not be treated as independent returns.

## Optuna

Optuna is now wired through `tvfree_screener/optuna_discovery.py`.

The first integration is deliberately low-DOF: the feature set, candidate
universe, target threshold, top-N and cost are fixed outside Optuna. Optuna
tunes only LogisticRegression `C`. Candidate dates and label-resolution dates
are hard-limited to 2022-07-01..2023-12-31; a 2024/2025/2026 row causes the
harness to fail closed.

Selection uses date-grouped expanding walk-forward folds audited by purgedcv.
Every completed trial retains its OOS active-date Sharpe so the selected trial
can be accompanied by PSR/DSR sensitivity instead of reporting only the best
backtest.

The frozen contract is:
`research/OPTUNA_DISCOVERY_CONTRACT_20260914.json`.

This infrastructure has passed synthetic CI. It has **not** been pointed at an
already rejected/outcome-opened family, because doing so would violate the
research contract. The next genuinely new family may use it from the start.

## EDINET OSS cross-check

`tvfree_screener/edinet_oss_crosscheck.py` parses the exact same
XBRL-to-CSV ZIP through:

1. the current custom point-in-time collector; and
2. edinet-tools' independent parser/raw-fact layer.

It compares accounting facts without reading strategy outcomes. Parser
disagreement is an audit finding only; no implementation is allowed to win
because its value improves a backtest.

The cross-check also exposed a concrete coverage defect in the custom issued
share extractor: real EDINET filings commonly put
`NumberOfIssuedSharesAsOfFiscalYearEnd...` at
`FilingDateInstant_OrdinaryShareMember`, while the previous generic context
rank accepted only `CurrentYear...`.

The research-branch fix now uses this frozen priority:

1. `TotalNumberOfIssuedSharesSummaryOfBusinessResults` at CurrentYear;
2. fiscal-year-end issued-share fact at CurrentYear;
3. the same fiscal-year-end fact at FilingDateInstant as an explicit fallback.

Conflicting values at the same priority remain unknown/ambiguous.

The frozen contract is:
`research/EDINET_OSS_CROSSCHECK_CONTRACT_20260914.json`.

Synthetic same-ZIP tests and the existing custom EDINET self-test both pass in
CI run 34796460950. Production behavior is unchanged because this work remains
on the isolated research branch.

## Other OSS reviewed

- `exchange-calendars`: already adopted in Batch01; keep the frozen,
  hash-checked XTKS materialization rather than replacing it.
- `vectorbt`: technically strong for large vectorized sweeps, but its
  Apache-2.0-with-Commons-Clause terms make it a poor default dependency for a
  project that may feed commercial tooling. Do not embed in core research.
- `backtesting.py`: useful API, but AGPL-3.0 and less aligned with our
  project-specific causal evaluation. Do not adopt.
- Microsoft `qlib`: capable MIT platform, but migration cost is high and it
  would duplicate the point-in-time pipeline we already built. Reference only.
- `tsfresh`: potentially useful for feature discovery, but creates a large
  multiple-testing surface. Reconsider only after the selection-bias audit is
  operational.
- DuckDB: MIT and a good fit for direct Parquet/CSV analytical joins. Keep it
  as a performance upgrade if pandas/Parquet aggregation becomes a measured
  bottleneck; do not add complexity before that.
- J-Quants client: official and useful for Japanese market data, but J-Quants
  API is a paid service. Keep as an optional future data-quality path, not a
  requirement for the free TV-Free design.

## Research guardrail

OSS is adopted only when it improves evidence quality or implementation
reliability. It is not permission to reopen rejected families, tune on 2026,
or silently change canonical endpoint semantics.


## Post-audit correction: issued-share priority

A supervisor audit found that the first implementation did not exactly enforce the
frozen three-level issued-share priority. Because the generic extractor sorted
element rank before context rank, a
`TotalNumberOfIssuedSharesSummaryOfBusinessResults` fact at
`FilingDateInstant...` could outrank a fiscal-year-end issued-share fact at
`CurrentYear...`, even though the frozen contract allows the summary-table fact
only at CurrentYear.

Research-only correction:
- custom extractor now evaluates explicit semantic priority groups;
- summary/FilingDateInstant is ineligible;
- both fiscal-year-end aliases share the same CurrentYear priority and conflicting
  numeric values at that priority fail closed;
- the edinet-tools raw-fact cross-check applies the same frozen semantic policy;
- regression tests cover the previously-missing conflict case.

No strategy outcomes were used and production remains unchanged.
