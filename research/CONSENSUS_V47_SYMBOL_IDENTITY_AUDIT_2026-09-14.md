# V47 point-in-time symbol identity audit — 2026-09-14

Research-only, outcome-free data-integrity audit. No strategy returns/model scores used.

## Finding

Comparing:
- accepted JPX PIT membership listing events, and
- frozen run80 current-symbol daily history,

found **24 listing-event codes from 2024-10 onward whose frozen current-code history contains rows before the official listing date**.

This is expected for some corporate reorganizations / holding-company transitions / code-history stitching by Yahoo, but it means current-code historical rows cannot be treated as point-in-time symbol identity.

Examples include:
- 253A / 254A / 255A / 256A — official listing 2024-10-01 while frozen history extends before that date;
- 463A / 464A — official listing 2025-12-01 while frozen history extends earlier;
- 543A / 547A — official listing 2026-04-01 while frozen history extends earlier;
- additional codes where a current/relisted code has pre-listing frozen history.

## Contract consequence

V47 must obey PIT membership identity:
1. a successor/current code is **not eligible before its official listing date**, even if Yahoo exposes older history under that code;
2. the historical predecessor/delisted code must be restored as the point-in-time member when JPX membership events say so;
3. if the predecessor historical code is unavailable directly from Yahoo, a query alias may be used only after official identity continuity/date mapping is verified;
4. aliasing is a data-repair operation only — never chosen from returns;
5. no duplicate economic security may be present under both predecessor and successor codes on the same PIT date.

This audit reinforces the 100% restored/delisted daily-coverage requirement in the authoritative V47 daily materializer.

## Known cross-lane examples already identified

Other research has independently identified examples such as:
- 463A successor history associated with predecessor 8940;
- 464A successor history associated with predecessor 5595;
- 547A successor history associated with predecessor 8515;
- 543A involves a 2026 reorganization and requires explicit predecessor mapping verification before any alias use.

These examples are data-identity evidence only and are not strategy signals.

## Decision

Do not use run80 current-code pre-listing rows directly in clean V47 candidate membership.

The authoritative path remains:
PIT membership -> historical/predecessor code data -> verified alias only if necessary -> coverage receipt -> model materialization.

Production modified: false.
