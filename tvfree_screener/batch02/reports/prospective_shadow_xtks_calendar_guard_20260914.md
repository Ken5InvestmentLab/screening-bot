# Prospective shadow pinned XTKS session calendar — 2026-09-14

Research-only Shadow/Data integrity work. No strategy return was opened for tuning and no production path was modified.

## Gap

Prospective-shadow 5BD resolution previously derived the session sequence from dates present in the supplied daily CSV. A globally missing market-data date could therefore shift the apparent "fifth session" on the first resolution write.

## Existing frozen source reused

No new calendar was invented. The resolver now reuses the already frozen Batch01 XTKS reference:

- `tvfree_screener/batch01/reference/xtks_sessions.csv`
- `tvfree_screener/batch01/reference/xtks_sessions.manifest.json`
- calendar_id: `XTKS`
- generator: `exchange_calendars 4.13.2`
- covered range: 2022-01-04 through 2026-12-30
- session_count: 1,220
- frozen CSV SHA256: `74ab2aaf72a0c055af31b461dd1b5776cf83eebc9576830954248aa03f518f68`

The manifest records reviewed JPX source URLs and was generated before the current prospective period.

## Guard

`prospective_shadow_session_calendar_guard.py` now fails closed unless:

- calendar_id is XTKS;
- the CSV SHA matches the frozen manifest;
- session dates are unique and strictly sorted;
- session_index is zero-based and contiguous;
- count, first session, and last session match the manifest;
- every candidate signal_date exists in the calendar;
- every candidate signal_date has at least five later XTKS sessions available.

## Resolver integration

`prospective_shadow_cli.py resolve` no longer uses the daily CSV's date union as the authoritative 5BD calendar. It validates and uses the frozen XTKS session sequence before calling the continuity-safe verified resolver.

The old `read_daily_csv()` helper remains for daily-row normalization/backward test coverage, but its derived date list is not used as the canonical resolver calendar.

## Commits

- `283c55139617451dec937e8ae8bb7f86f0927f27` — XTKS session calendar guard.
- `2f363b893e9a43654c4affeb50919a30f7522d88` — calendar guard tests.
- `48087d412e20a76825eedaec1aebb2d8213eca73` — CLI resolve pinned to frozen XTKS calendar.
- `dcbbbc490823d89e9a979df5ca1201475f176688` — CLI regression test aligned to actual 2026-09 XTKS sessions.
- `2818fe55edeb3343caffe0a2f2f5a203bbf5920c` — CI coverage extended to the calendar guard and reference artifacts.

## Verification

GitHub Actions run `34795620704` completed successfully:

- 26 tests run;
- 26 passed;
- continuity guard, staged verified resolver, pinned-calendar guard, and CLI-level enforcement all passed together.

This specifically verifies the 2026-09 holiday sequence around the synthetic test: after 2026-09-15, the frozen XTKS sessions are 09-16, 09-17, 09-18, 09-24, and 09-25; 09-21 through 09-23 are not incorrectly counted as trading sessions.

## Isolation

This change does not alter Event/V20 logic, Core, Consensus V47, candidate ranking, thresholds, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater, production workflows, or main.
