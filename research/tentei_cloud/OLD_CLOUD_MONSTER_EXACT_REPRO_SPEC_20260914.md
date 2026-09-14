# Old Cloud Monster exact-reproduction forensic spec — FROZEN 2026-09-14 JST

Research-only. This does **not** reopen old Cloud Monster as a promotion candidate.

## Historical target to reproduce

The target is the saved historical Priority-A result, not a surrogate:

- matured selected rows: **n=63**
- historical 5BD mean: **+9.86%**
- historical median: **+3.33%**
- historical win rate: **57.1%**
- historical >=+20%: **30.2%**
- historical <=-10%: **22.2%**
- historical top-5-removed mean: **+4.03%**

These are historical evidence and must never be relabeled as a new replay result.

## Exact-match acceptance contract

A replay is `EXACT_REPRODUCED` only if all of the following are recovered from contemporaneous source evidence and replayed without outcome-driven substitution:

1. exact source universe / candidate pool and its row identity;
2. exact Watch seed implementation, including `pre_down3`, `gap_up`, recent 4H 3-bar return >= +6%, plus every additional filter/session/calendar/dedup treatment needed to recover the historical pool;
3. exact model class and objective;
4. exact feature list, feature transforms, missing-value treatment and preprocessing;
5. exact training period and label definition;
6. exact fitted parameters / serialized model, or deterministic training recipe including random seed sufficient to reproduce scores;
7. exact probability/calibration mapping;
8. exact Priority bands: A = top 10%, B = next 20%, including tie handling and grouping scope;
9. exact cooldown/dedup/candidate-selection ordering;
10. exact entry and 5BD exit definition used by the historical headline;
11. exact cost convention used by the historical headline;
12. exact 63 selected matured rows and their saved scores where contemporaneous scores survive;
13. replay on the original period yields n=63 and 5BD mean +9.86% to the historical reporting precision, with row-level identity reconciled.

Failure of any identity-critical item means `NOT_EXACT_REPRODUCED`. A nearby n/mean, high AUC, similar score rank, or good return is not exact reproduction.

## Evidence already recovered

Contemporaneous/saved evidence establishes:

- Watch seed family: daily `pre_down3`, daily `gap_up`, recent 4H 3-bar return >= +6%;
- historical Watch pool was recorded as **575** candidates after then-current filtering/calendar correction;
- Priority A = probability-score top 10%; Priority B = next 20%;
- model training era = **March-June 2026**; July-August 2026 = later evaluation block;
- surviving `cloud_two_lane_union_jpx.csv` contains the historical 63 Priority-A rows;
- surviving `cloud_priorityA_monsters_compare_teacher.csv` contains exact saved score values for 19 high-return Priority-A rows;
- surviving `teacher_ohlcv_4h_raw.csv` contains historical 4H/session OHLCV;
- broad Watch reconstruction recovers 62/63 historical A timestamps but produces **696** rows, not the recorded 575.

## Identity-critical missing evidence at freeze time

The surviving repository/history/artifacts do **not** establish:

- original model class;
- exact objective/target implementation;
- exact feature list;
- exact transforms/preprocessing;
- probability calibration;
- serialized fitted model;
- exact deterministic training recipe/seed;
- the missing Watch implementation detail(s) that reduce the forensic 696-row reconstruction to the recorded 575.

Therefore the status at freeze time is:

**SPEC_FROZEN / EXACT_REPRODUCTION_BLOCKED_BY_MISSING_IDENTITY_EVIDENCE**

No model-family guessing is authorized. Only genuinely new contemporaneous evidence (original script/notebook, serialized model, exact feature table, exact training manifest, or equivalent) may reopen the exact-replay step.

## Cost policy from this run forward

All **new** forensic/backtest/portability calculations in this lane use **transaction cost 0% only** and define win as gross return > 0. Historical costed outputs remain legacy evidence only and cannot drive current ranking or GO/NO-GO.

The historical +9.86% headline retains its original historical convention for identity checking; it is not recomputed under an invented cost convention. Any new bridge table, if exact reproduction ever becomes possible, must separately report gross cost-0% canonical next-XTKS-open -> fifth-close results and must not overwrite the historical endpoint result.

## Portability rule

Unused-period portability is forbidden unless `EXACT_REPRODUCED` is first achieved. If achieved, the exact frozen logic is applied once, unchanged, to periods not used in development/selection. 2026 outcomes are report-only for current research selection.

Required cost-0% portability metrics: period n, mean, median, win, +10/+20/+50, -10/-20, Top1/Top3 removed mean, month/week dependence, and—where data permit—a separate canonical next-XTKS-open -> fifth-close bridge table.

No threshold, feature, cooldown, probability band, ranker, or condition may be adjusted after portability outcomes are seen.

## Disposition vocabulary

- `HISTORICAL_REPRODUCIBLE_CANDIDATE`: exact original-period reproduction succeeded; unchanged portability may proceed.
- `HISTORICAL_NON_PORTABLE`: exact reproduction succeeded but unchanged unused-period portability failed.
- `HISTORICAL_EXACT_REPRO_UNAVAILABLE`: identity-critical source evidence is missing and exact reproduction cannot currently be executed.

Current frozen disposition: **HISTORICAL_EXACT_REPRO_UNAVAILABLE**.
