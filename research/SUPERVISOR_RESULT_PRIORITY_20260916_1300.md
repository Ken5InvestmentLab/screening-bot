# Supervisor result-priority checkpoint — 2026-09-16 13:00 JST

## P0 user-facing deliverables
1. Frozen `DUAL_TOP1_AGREEMENT + G3(NO_ACUTE_SELLOFF, med_ret1>=-1%)` 2026 reporting-only performance, only trades with confirmed fifth-XTKS-close exits.
2. Same frozen rows summarized by calendar year 2022/2023/2024/2025/2026 plus 2022-2026 aggregate: n, mean, median, win, +10, +20, -10, -20, max up, max down, Top3-ex. Include 2026 cutoff.
3. OHLCV endpoint-impact receipt first: true missing O/C rows intersecting DUAL+G3 next-XTKS-open / fifth-XTKS-close endpoints. Full-market O/H/L/C/V completeness comes after this endpoint-impact result.

## Concrete discovery this run
- The coordination branch contains an older `tvfree-v13-frozen-2026-test.yml` / `v13_frozen_preexhaust_range_2026.py`, but that runner is a different V13 Pre-Exhaustion+Range lane (`med_ret5<=0`, four-feature rank) and MUST NOT be substituted for frozen DUAL+G3.
- Frozen Phase-2 report confirms DUAL+G3 2023-25 totals: n117, mean +7.98%, median +1.74%, win 53.85%, +10 31.62%, +20 18.80%, -10 28.21%, -20 9.40%, Top3-ex +5.14%.
- Coordination state still lacks a SHA-pinned DUAL+G3 per-trade row artifact and therefore cannot safely derive 2026 or yearly max up/down yet.

## Stop wasting cycles
Until the three P0 deliverables above are fixed, do not spend Supervisor cycles on Canonical recovery expansion, Consensus formal-raw monitoring, new condition exploration, or additional provenance layers that do not unblock DUAL+G3 rows/OHLCV endpoints.

## Required next safe action
Search historical research branches/Actions artifacts for the exact DUAL+G3 row set that produced the frozen n117 2023-25 result and the fresh 2022 n17 block. Accept only an artifact whose recomputed 2023-25 summary exactly matches the frozen values. Pin row/source SHA. Then audit `entry_date > signal_date`, next XTKS open, fifth XTKS close, and append 2026 from the same frozen selection logic without retune. If exact rows cannot be recovered, create a research-only deterministic reproducer from the preregistered frozen definitions and preserved causal dataset, and require exact 2023-25 summary match before opening 2026.

Production/main and all production systems remain untouched.