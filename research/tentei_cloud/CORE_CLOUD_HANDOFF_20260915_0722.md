# Core + Cloud handoff — 2026-09-15 07:22 JST

## Frozen status
- Cloud exact: **CLOSED / HISTORICAL_EXACT_REPRO_UNAVAILABLE**. Reopen only on genuinely new contemporaneous identity-critical evidence.
- Old Cloud Monster `n=63 / 5BD mean +9.86%`: historical evidence only, never a reproduced result.
- current fixed Core, Failed-Breakdown Reclaim, Prior-Close Reclaim, Precision 3-family and other rejected families: closed; no retune/rescue.
- performance unopened; all future new performance cost 0% only; win = gross return > 0; 2026 report-only.

## Material advance this run
The expected-endpoint gate was tightened before opening the missing inventory.

Existing research evidence was located for:
- official-JPX point-in-time membership reconstruction;
- frozen XTKS sessions (`exchange_calendars 4.13.2`, 1,220 sessions, CSV SHA-256 `74ab2aaf72a0c055af31b461dd1b5776cf83eebc9576830954248aa03f518f68`);
- audited Yahoo/XTKS raw-hour semantics: AM 09/10/11/12; PM 13/14 pre-2024-11-05, 13/14/15 thereafter.

However, membership + session + clock does **not** prove that a thinly traded stock had a trade in every hour. A full Cartesian expansion would convert legitimate no-trade intervals into fake missing-data rows. The audited Yahoo file itself also cannot define its own expected activity without circularity.

`CORE_EXPECTED_ENDPOINT_UNIVERSE_SPEC_20260915.md` now freezes the required fourth evidence layer: **independent exact-hour activity evidence** for every endpoint asserted as expected. Daily OHLCV, Google Finance snapshots, observed Yahoo presence, interpolation and daily-to-intraday synthesis are explicitly insufficient.

## Current gate disposition
- exact observed Yahoo raw1H 8-shard bytes: **PASS / pinned**;
- PIT membership implementation: identified, but exact official source receipts still need Core pinning;
- XTKS calendar: identified, but adopted CSV/manifest bytes still need Core pinning;
- raw-hour semantic rule: identified;
- independent exact-hour activity evidence: **NOT YET PINNED**;
- formal missing inventory: **CLOSED**;
- formal supplemented dataset adoption: **CLOSED**;
- performance recomputation: **CLOSED**.

This is a provenance finding, not a strategy/performance result.

## Exact continuation
1. Freeze official-JPX PIT input/source receipts on Core.
2. Freeze adopted XTKS CSV + manifest bytes on Core.
3. Search for an independent intraday activity source that can establish exact `(symbol, session_date, hour)` activity across the recovered period. Preserve source/raw SHA and semantics.
4. If exact-hour activity evidence passes, generate and SHA-pin the expected CSV and run `missing_inventory_runner.py` exactly once.
5. Apply fallbacks only to declared gaps; record accepted/rejected/conflicted + coverage delta.
6. If activity evidence cannot be obtained, do **not** manufacture a formal expected universe. Keep only clearly labeled session/symbol coverage diagnostics and leave formal adoption/performance closed.

No production assets or integrations were modified. No new strategy outcomes or costed calculations were opened this run.
