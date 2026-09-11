# TV-Free Screener — Next Actions

TEST ONLY. Execute top-to-bottom unless new evidence invalidates the next item. Keep `HANDOFF.md` synchronized.

## Guardrails
- Branch: `test/tvfree-screener-v1`; Draft PR #13 only.
- Never merge or modify `main` without explicit user Go.
- Never change production Discord/Spreadsheet writes, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater, or production workflows.
- Evaluation remains next-session-open -> horizon close and all model selection must be causal.
- 2026 is contaminated/reporting-only and must never be used for threshold/model tuning.

## 1. JPX point-in-time membership — ACCEPTED
Run #112 (`34554140015`, retained artifact `10181998903`) passed the live gate: 1,096 official event rows, unknown-market rows 0, same-day code collisions 0, all required years 2022-2026 present, `valid_for_membership_reconstruction=true`. Reused codes `3960` and `8303` remain identity-quarantined.

## 2. Yahoo delisted-symbol coverage — REJECTED AS SUFFICIENT SOURCE
The same run measured 463 official delistings. Three were identity-quarantined; among 460 probed events only 11 (2.39%) had usable Yahoo prices near delisting, with zero transport errors. Status: missing 400, missing-before-delist 47, partial-old-or-sparse 2, usable 11. Do not weaken the gate or describe current-survivor Yahoo backtests as survivorship-bias-free.

## 3. Stooq delisted-price probe — IMPLEMENTED, LIVE COVERAGE STILL PENDING
Highest data-source priority.

TEST-only implementation commits:
- `d6b42eddf1c872f6be532d88cb5bb0b8072a600d`: `stooq_delisted_price_coverage.py`.
- `37ee3a4858b7e1a182dcee471e3da849b2fb93e6`: synthetic regression checks.
- `fc86c5412859f17dd2215becf5bd8b4516ccd4df`: wire synthetic check and optional live probe into the TEST workflow.

The probe reuses the exact JPX delisting-candidate construction and identity quarantine used for Yahoo. It selects a deterministic year-balanced 24-event sample from pre-2026 delistings without using returns. It distinguishes true `No data` from auth, HTTP, transport, parse, and rate/quota errors; requires complete OHLCV near the official delisting date; and never writes/logs the API key.

Run #119 (`34557956808`) confirmed the new Stooq synthetic self-check PASS. That run was later cancelled by branch-update concurrency while Yahoo measurement was still running, so its Stooq live step was skipped. A skipped step is not evidence of missing Stooq history.

Live Stooq acquisition requires a manually obtained free `STOOQ_APIKEY`; keep it only in environment/GitHub Secret. When available, run the fixed 24-event pre-2026 sample first. Expand to all 460 non-quarantined official delistings only if the sample shows actual retained OHLCV and workable auth/rate limits.

If Stooq cannot provide adequate automated backfill, next provider checks remain:
1. J-Quants Free as an official overlapping-window cross-check only; its two-year history delayed 12 weeks cannot fill the full 2022-start contract in September 2026.
2. JPX historical stock-price files as manual fallback only; do not automate scraping.
3. Do not scrape Yahoo! JAPAN quote/history pages.

## 4. Reproducibility guard — FALSE POSITIVE FOUND AND FIXED
Run #114 (`34554396869`, artifact `10182719509`) failed only at the final fixed-run-80 output guard even though universe, historical date/symbol coverage, and historical OHLCV hashes were identical to run #80.

Direct artifact comparison established:
- Short Core and Short defensive output hashes were unchanged.
- Swing S had exactly the same 101 selected `(date, symbol)` rows in run #80 and #114.
- Only four forward-reporting cells differed because later sessions had matured: `target10_no`/`target10_end` for 2026-08-28, `target20_no` for 2026-08-14, and `target40_no` for 2026-07-15.
- Therefore the failure was not model-selection drift.

TEST-only fix commits:
- `4055d38fb15fbb5436a317b7306c70ded2ac53c8`: manifest v4 hashes signal-time/model-selection columns while excluding `next_open` and `target*` future labels.
- `901ed82ee17325229fec254707b532ad23fdc15d`: synthetic regression proving future-label maturation leaves the frozen selection hash unchanged while score/symbol changes still fail.
- `7690c902b4f554ef78b3f9bfbd014855ea210515`: migrate run #80 baseline to selection-only hashes, retaining legacy full-row hashes for audit.

New run-80 selection hashes, recomputed directly from the retained run #80 artifact:
- Short Core `5750fa35da7f344498bae65e6b270c437bd286ae23aa0e3c7d71367824b64bf4`
- Short defensive `4f057700a1152dbbd52281894b00468979cd7386781100106876dd0006fc3031`
- Swing S `1b4e987c5d062c0da5f6201c4a57922ca5ce26e6566b238e2abffec35987b1b1`

Next: confirm these self-checks and the final guard on a non-cancelled TEST run. Do not interpret run #114 as model nondeterminism.

## 5. 2024 extension / V4 conclusions from run #114 — REJECT WEAK PATHS
These are secondary while delisted-price survivorship coverage is unresolved and must not be promoted to production claims.

Independent 2024 extension, unchanged frozen logic:
- Short 2024H1 Core: n=120, mean about +0.72%; 2024H2 Core: n=125, mean about +0.26%, median negative, win 42.4%. Not strong/stable enough.
- Swing 2024H1: n=55, mean about +3.09%; 2024H2: n=39, mean about +1.94% but median negative and -10% rate 12.8%. Mixed and unstable.

Blind V4 behaved correctly: all four predeclared 2024 development variants failed the development utility requirement, so `locked_variant=null`; 2025 was not opened and 2026 was not evaluated. **Reject this V4 family as currently specified rather than retuning it.**

## 6. Legacy +5.42% V3 recovery — KEEP ISOLATED
The historical 2026 Mar-Aug reference remains n=29, mean +5.42%, median +2.06%, win 65.5%, but exact old thresholds were never committed. A separate TEST-only targeted legacy-recovery workflow was added on the branch at `28ab0492ab1dee59e255b459f8543278cad1a9af`. Let that recovery use pre-2026 evidence and archived/fixed data; do not tune thresholds to 2026 just to reproduce the headline number.

## 7. Fundamental / dilution overlay
Live EDINET work remains blocked until `EDINET_API_KEY` is available as an environment/secret value. Never commit/log it. Extracted warrant/share-count candidates remain audit evidence only until filing-table semantics are validated. Missing observations remain explicit unknowns with coverage-matched baselines. Initial dilution thresholds stay predeclared at 20%, 35%, 50%, and 100%; selection may use only pre-2026 evidence.

## 8. Production integration — BLOCKED until user Go
Never automatically merge PR #13, alter production workflows, send production Discord, write production Spreadsheet, replace Stable★6/Sniper/Mega, or disable/change production TradingView/watchlist components.

## Immediate next concrete tasks
1. Allow the targeted legacy V3 recovery run to finish and inspect it without tuning to 2026.
2. Confirm manifest-v4/fixed-baseline self-checks on a non-cancelled TEST run.
3. When `STOOQ_APIKEY` is available, execute the deterministic 24-event pre-2026 Stooq probe; expand only on adequate evidence.
4. If Stooq remains blocked/unusable, implement a TEST-only J-Quants Free overlapping-window coverage/sanity probe while explicitly retaining the full-2022 backfill blocker.
