# Causal intraday relative-volume quality audit — 2026-09-13

Research-only. No strategy outcomes were opened.

## Definition

For each symbol and raw clock bin, use only prior completed bins from the same source:

`volume_rel20 = current_bin_volume / median(previous 20 same-bin volumes)`

Then transform with `log1p(volume_rel20)`.

AM history is continuous. PM history is split at the 2024-11-05 TSE close-extension regime boundary. Current-day finalized daily volume is never used.

## Broad raw audit

Input: the existing 1,315-symbol / 4,019,524-row raw 1h dataset from run 34592896202.

- complete AM/PM clock bins: **1,017,531**
- bins with 20 prior comparable volumes and a valid ratio: **941,126**
- coverage: **92.491%**

Raw ratio distribution:
- median 0.962x
- p95 5.171x
- p99 22.846x
- p99.9 188.629x
- max 3,969.28x

The raw ratio is extremely heavy-tailed. Therefore absolute clipping is not introduced; the preregistered representation is `log1p`.

Log-transformed distribution:
- median **0.674**
- p95 **1.820**
- p99 **3.172**
- p99.9 **5.245**
- max **8.287**

Regime medians are close:
- AM_STABLE 0.670
- PM_PRE_20241105 0.676
- PM_POST_20241105 0.678

Monthly median stability is also acceptable for a source-internal feature:
- 2025 monthly medians: 0.550 to 0.746
- 2026 through 2026-09-10: 0.609 to 0.736

## Decision

**DATA-QUALITY PASS for an experimental causal feature.**

This does not mean Yahoo/raw absolute volume is exchange-truth volume. The feature is allowed only as a same-source, same-symbol, same-bin relative ratio (and optionally a same-cohort cross-sectional rank). It must not be described as repaired absolute volume.

The next outcome experiment may add `log_volume_rel20` and its same-date+bin percentile rank to the causal 4H feature panel. No 2026 strategy outcome may be used.
