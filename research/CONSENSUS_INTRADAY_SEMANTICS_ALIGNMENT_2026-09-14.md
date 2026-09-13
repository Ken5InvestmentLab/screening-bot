# Consensus intraday semantics alignment — 2026-09-14

Research-only cross-lane audit. No production or model parameters changed.

## Why this correction is needed

Consensus V43/V44 reuses the older Yahoo-1h reconstruction in `no_tv_v10_standalone.py` / `no_tv_v43_2025_uncapped.py`.

The function `synthetic_sessions()` assigns:
- every raw Yahoo 1h timestamp before 13:00 JST to integer label `session=9`;
- timestamps at/after 13:00 JST to `session=13`.

The label names can therefore be misread as exact alert times.

## Cross-lane data-integrity evidence

The canonical Batch02 data-integrity lane has already audited raw Yahoo 1h semantics and must remain the owner of this topic.

Its frozen findings include:
- Yahoo timestamps are treated as **interval-start** timestamps;
- 09/10/11/12 start rows form the first raw-source clock bin;
- the 12:00-start interval crosses the TSE lunch boundary and cannot be split into an exact true morning/afternoon OHLC bar;
- the lane explicitly keeps it only inside the named 09:00-13:00 raw-source clock bin and does **not** claim exact TradingView equivalence;
- PM construction also requires care around the 2024-11-05 TSE close extension and 15:00 rows.

Sources of record are on `research/tvfree-canonical-batch02`, especially:
- `tvfree_screener/batch02/HANDOFF_PAUSE_20260913.md`
- `tvfree_screener/batch02/EXPERIMENT_LEDGER.md`
- `CAUSAL_INTRADAY_FEATURE_ARCHITECTURE_SPEC.json`
- `raw_intraday_clock_bins.py` / related frozen reports.

No duplicate Yahoo timestamp experiment is started in the Consensus lane.

## Causality check of current Consensus reconstruction

`build_asof_official()` itself is causal with respect to current-day daily OHLC:
1. completed daily rows are restricted to `daily.date < current_date`;
2. the current partial daily row is reconstructed only from raw sessions up to the current candidate index;
3. `technical_features()`, including `atr14_pct`, is computed from that as-of frame.

Thus the frozen ATR OOD guard does **not** appear to use the finalized same-day daily candle at the earlier bin.

## Required interpretation change

For V43/V44 research:
- `session=9` must be read as **first reconstructed Yahoo raw clock bin**, not “a signal known at 09:00 JST”;
- `session=13` must be read as the second reconstructed raw clock bin, not automatically “a signal known exactly at 13:00 JST”;
- the reconstructed bins are not claimed to be exact TradingView 4H bars.

This matters less for the canonical research endpoint because all comparable performance is now measured from **next official XTKS session open**, after both prior-day bins are complete.

It still matters for production architecture and any claim of intraday alert timing.

## Decision

1. V44 remains valid as a **research ranking/diversification experiment on the existing reconstructed-bin representation** if its receipt checks pass.
2. Do not promote V43/V44 directly as an exact 09:00/13:00 live alert engine.
3. If Consensus survives V44 and subsequent robustness checks, final integration must migrate/retrain against the canonical data-integrity lane's frozen causal raw-bin materializer rather than assuming old `synthetic_sessions()` semantics are production-final.
4. Do not change V44's binning mid-experiment; doing so would change the parent representation after outcomes are already open.
5. The data-integrity lane remains owner of raw Yahoo clock boundaries, source semantics and coverage.
