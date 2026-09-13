# Prospective shadow evidence reporter verification — 2026-09-14 JST

## Purpose

Provide a model-agnostic, research-only summary step for genuinely prospective shadow evidence after candidates mature to 5BD. This does not choose models, thresholds, ranks, or candidates.

## Added

- `prospective_shadow_report.py`
  - reads resolved shadow JSONL;
  - preserves explicit pending/unresolved counts;
  - computes metrics only from rows with `status=RESOLVED`;
  - errors if a row claims `RESOLVED` without numeric `ret5bd_gross`;
  - summarizes overall, by `experiment_id|model_freeze_id`, and by signal month;
  - default assumed round-trip cost is 0.5%, configurable but nonnegative;
  - reports mean, median, win rate, +10/+20/+50 gross rates, -10/-20 gross rates, and Top1/Top3-removed net means;
  - output explicitly states that selection/threshold tuning is not allowed.

- `test_prospective_shadow_report.py`
  - resolved-only metric isolation;
  - invalid resolved-row rejection;
  - freeze/month grouping;
  - Top1/Top3 removed mean checks.

## Verification

Local functional verification: **4/4 PASS**.

## Integrity

This reporter must only consume prospective shadow evidence created after a model freeze. It is not a retrospective optimizer and must not be used to tune V15/V16 on already-viewed historical periods.

## Production impact

None. No production workflow, TradingView, Discord, Sheets, Stable, Sniper, or Mega changes.
