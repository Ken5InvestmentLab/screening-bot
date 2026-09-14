# OSS validation tooling review — 2026-09-14

## Decision

Adopt **purgedcv 0.1.6** as an independent research-audit dependency.

This does **not** replace the repository's frozen XTKS calendar, point-in-time
universe, label construction, temporal policy, or existing weekly block
bootstrap. The current code already has stronger project-specific controls
than a generic framework in several of those areas.

The immediate gap this fills is independent checking of:

1. temporal label overlap in research folds; and
2. selection bias after trying many candidate specifications.

The integration is isolated on branch research/oss-validation-tooling and must
not touch production/main, Discord, Spreadsheet, Stable★6, Sniper, Mega,
TradingView, watchlist-builder, or watchlist-updater.

## Added helper

tvfree_screener/oss_validation.py exposes:

- purged_kfold_audit: independent PurgedKFold + audit_splitter check;
- selection_bias_summary: PSR plus raw-trial and autocorrelation-adjusted
  effective-trial DSR sensitivity;
- CLI modes cv and dsr.

The DSR helper deliberately reports both raw and effective trial-count views.
Neither is an automatic GO/NO-GO gate. Effective trial count is heuristic, and
overlapping 5BD observations must not be treated as independent returns.

Isolated CI run 34795055091 passed on Python 3.12.

## Optuna

**Approved for a later discovery-only optimization harness**, not activated by
this branch.

Reason: Optuna can accelerate parameter search, but doing that before recording
trial counts / Sharpe dispersion would accelerate overfitting too. When added:

- objective input must remain inside the frozen discovery window;
- 2024/2025/2026 may not influence parameter selection;
- every completed trial must be logged;
- trial-level performance dispersion must be retained for DSR;
- the chosen specification must be frozen before locked validation opens.

## EDINET OSS cross-check

**edinet-tools is a high-priority cross-check candidate**, but it should not
silently replace the current point-in-time collector.

Why it is interesting: the current collector intentionally uses a small,
auditable alias set and the EDINET XBRL-to-CSV output. edinet-tools exposes
typed parsers across EDINET document types while retaining raw/unmapped facts.
That makes it useful for measuring whether our current financial coverage or
dilution-event coverage is leaving useful fields on the table.

Safe next experiment:

- run both parsers on the same preregistered historical document sample;
- compare extracted values and missingness without opening strategy outcomes;
- keep submit/availability timestamps from our point-in-time contract;
- admit a new field only after exact source semantics and PIT availability are
  reproducible;
- do not use parser disagreement as permission to choose whichever value makes
  a strategy look better.

## Other OSS reviewed

- exchange-calendars: already adopted in Batch01; keep the frozen,
  hash-checked XTKS materialization rather than replacing it.
- vectorbt: technically strong for large vectorized sweeps, but its
  Apache-2.0-with-Commons-Clause terms make it a poor default dependency for a
  project that may feed commercial tooling. Do not embed in core research.
- backtesting.py: useful API, but AGPL-3.0 and less aligned with our
  project-specific causal evaluation. Do not adopt.
- Microsoft qlib: capable MIT platform, but migration cost is high and it
  would duplicate the point-in-time pipeline we already built. Reference only.
- tsfresh: potentially useful for feature discovery, but creates a large
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
