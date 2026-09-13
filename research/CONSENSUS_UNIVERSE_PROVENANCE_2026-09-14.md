# Consensus universe provenance / survivorship limitation — 2026-09-14

Research-only provenance audit. No production writes and no strategy rules changed.

## Frozen daily source

Consensus V43/V44 uses the preserved artifact:
- `tvfree-frozen-dataset-run80-preserved`
- preservation run: 34599959356
- source research run: **34545440155**
- source commit: 5461eef6f35ea2cea2b4bc38ca7177c681681783

The source workflow ran `tvfree_screener/bootstrap.py`.

## How the historical universe was built

At the source commit, `dynamic_jpx_universe()`:
1. downloaded the official JPX listed-issues spreadsheet at run time;
2. filtered it to domestic common stocks;
3. produced a **run-date current-listed universe**;
4. then Yahoo daily history was fetched from a fixed start date for those symbols.

Source-run receipt:
- JPX domestic common-stock universe: **3,700 symbols**
- universe policy: `run-date JPX domestic common-stock universe`
- universe snapshot SHA-256: `271033ea30220e1731537a2b453d2f5bfffb9fbc29d7d43a46f8efd1f9f54cbe`
- daily cache rows: 4,061,361
- daily cache symbols: 3,700
- min date: 2022-01-04
- max date: 2026-09-11
- historical OHLCV SHA-256 in the source receipt: `475ae6166ed21220aaa7f9f98d5bfff6c2d221bf1e3571b59fc6656758f453ab`

The source code itself explicitly warns:

> Historical research currently uses the run-date listed universe. Listings/delistings can therefore change the backtest population even when model semantics are unchanged.

V43 later narrows this frozen dataset by historical price/volume eligibility. Its 2025 research build reported:
- 1,910 symbols were eligible at least once in the monitored window before Yahoo-1h reconstruction;
- this does not turn the universe into a point-in-time listing universe.

## Consequence

The frozen dataset is reproducible, but it is **not survivorship-neutral historical JPX membership**.

Possible bias:
- a stock that existed/traded in 2025 but was delisted before 2026-09-11 can be absent from the run-date 3,700-symbol universe;
- later listings naturally begin only after listing, but historical delistings are not restored by the current-list snapshot;
- therefore 2025 Consensus results may omit failed/delisted historical members.

The direction and size of this bias are not measured here. Do not assume it is negligible and do not invent a correction.

## What remains valid

V44 still answers a useful narrower question:

> Within one fixed, reproducible 2026-09-11 current-listed JPX universe, does Top-K cooldown replacement reduce repeated-symbol concentration without destroying the frozen-min95 Consensus edge?

All compared V44 policies use the same frozen universe, so the internal policy comparison is not invalidated by this provenance limitation.

## What is not justified

Until point-in-time membership is available:
- do not call V43/V44 a survivorship-free all-TSE historical backtest;
- do not declare superiority over Stable★6 from headline means;
- do not production-promote Consensus from this evidence alone;
- do not repair the issue by manually adding known delisted winners/losers after seeing outcomes.

## Required path before promotion

If Consensus survives V44:
1. obtain or reconstruct a point-in-time JPX common-stock membership source with listing/delisting effective dates;
2. freeze that universe independently of strategy outcomes;
3. rerun the candidate/data pipeline using only symbols eligible on each historical date;
4. report membership coverage and unresolved historical symbols;
5. only then treat historical breadth/generalization as a promotion-grade result.

Point-in-time universe and broader source-integrity work belongs with the shared data-integrity lane; the Consensus lane records this dependency rather than duplicating that work.
