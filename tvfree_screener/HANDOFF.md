# TradingView-Free Screener — Autonomous Handoff

TEST ONLY. Canonical handoff for scheduled runs and new chats.

## Safety guardrails
- Repository: `Ken5InvestmentLab/screening-bot`
- Working branch: `test/tvfree-screener-v1`
- Draft PR: #13
- NEVER merge to `main` without explicit user Go approval.
- NEVER modify production Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater, or production workflows without explicit user Go approval.
- Evaluate next-session-open -> horizon close.
- Training/selection must be causal.
- 2026 is contaminated/reporting-only and must not be used for threshold/model tuning.

## Goal
Replace the TradingView/Pine watchlist dependency with a free daily-OHLCV TSE common-stock system while remaining competitive with Stable★6. Weak or unstable methods must be rejected rather than tuned to look good.

## Durable fixed-start baseline
Actions run `34545440155` (run #80), head `5461eef6f35ea2cea2b4bc38ca7177c681681783`, remains the first accepted fixed-start baseline.

Verified contract:
- Yahoo history `2022-01-01 -> current`
- current JPX domestic common-stock universe 3,700 symbols
- OHLCV rows 4,061,361
- rows through frozen cutoff 2026-08-31: 4,031,154
- runtime about 27m03s
- artifact 51,126,879 bytes (~48.8 MiB)

Frozen source hashes:
- universe `271033ea30220e1731537a2b453d2f5bfffb9fbc29d7d43a46f8efd1f9f54cbe`
- historical coverage `2686163d4e4342198590d34a8708c5c142a11441befdd74da3475bafd3e9a935`
- historical OHLCV `475ae6166ed21220aaa7f9f98d5bfff6c2d221bf1e3571b59fc6656758f453ab`

### Output-hash policy corrected after run #114
Run #114 (`34554396869`, artifact `10182719509`) initially reported `ERROR_model_output_changed_with_identical_inputs`. Direct comparison with retained run #80 showed this was a false positive:
- Swing S selected exactly the same 101 `(date, symbol)` rows in both artifacts.
- Short Core and Short defensive were unchanged.
- Swing differences were only forward-reporting fields that matured after run #80: `target10_no`/`target10_end` for the 2026-08-28 pick, `target20_no` for 2026-08-14, and `target40_no` for 2026-07-15.
- No evidence of selection/model-score nondeterminism was found.

TEST-only fix:
- `4055d38fb15fbb5436a317b7306c70ded2ac53c8`: manifest v4 hashes signal-time/model-selection columns only and excludes `next_open` plus `target*` future labels.
- `901ed82ee17325229fec254707b532ad23fdc15d`: regression test proves future-label maturation does not change the frozen selection hash while a changed score or selected symbol still does.
- `7690c902b4f554ef78b3f9bfbd014855ea210515`: run #80 baseline migrated using hashes recomputed directly from the retained run #80 artifact; legacy hashes retained for audit.

New run-80 selection hashes:
- Short Core `5750fa35da7f344498bae65e6b270c437bd286ae23aa0e3c7d71367824b64bf4`
- Short defensive `4f057700a1152dbbd52281894b00468979cd7386781100106876dd0006fc3031`
- Swing S `1b4e987c5d062c0da5f6201c4a57922ca5ce26e6566b238e2abffec35987b1b1`

Do not treat the old run #114 full-row hash mismatch as model drift. Confirm manifest-v4/final guard in a non-cancelled TEST run.

## Frozen V3 status
Short Core uses the same 45 features, monthly causal XGBoost, prediction-day percentile normalization, Core `r_top10 - 2*r_loss10`, one-day same-symbol cooldown, next-open -> 5BD.
- 2025H1: n=119, mean +0.69%, median +0.45%, win 55.5%, +10% 3.36%, -10% 2.52%.
- 2025H2: n=124, mean +0.26%, median +0.58%, win 53.2%, +10% 0%, -10% 0%.
- 2026 Mar-Aug reporting-only: n=124, mean +0.015%, median -0.13%, win 47.6%, +10% 1.61%, -10% 0.81%.
Short Attack remains none/unaccepted.

Swing S frozen architecture: MomCross -> causal semiannual quality model -> training empirical CDF -> Breadth Meta -> `score_R >= 0.20`, next-open -> 10BD.
- 2025H1: n=36, mean -0.14%, median -1.96%, win 36.1%, +10% 11.1%, -10% 2.78%.
- 2025H2: n=24, mean +2.68%, median +0.90%, win 54.2%, +10% 12.5%, -10% 0%.
- 2026 Mar-Aug reporting-only: n=27, mean +0.017%, median 0%, win 48.1%, +10% 7.41%, -10% 7.41%.
Neither frozen V3 lane is accepted as a Stable★6 replacement.

### Historical +5.42% Short reference
The old non-reproducible 2026 Mar-Aug reference remains:
- n=29
- mean +5.42%
- median +2.06%
- win 65.5%
- +10% rate 13.8%
- -10% rate 6.9%
Exact old thresholds were never committed. Do not claim exact reproduction or tune directly to 2026. A separate TEST-only targeted legacy-recovery workflow was added at commit `28ab0492ab1dee59e255b459f8543278cad1a9af`; inspect its pre-2026-driven result when complete.

## Run #114 independent technical findings
These results are secondary until survivorship-aware delisted prices are available.

Independent 2024 frozen extension:
- Short 2024H1 Core n=120, mean about +0.72%; 2024H2 Core n=125, mean about +0.26%, median negative, win 42.4%. Weak/unstable; not accepted.
- Swing 2024H1 n=55, mean about +3.09%; 2024H2 n=39, mean about +1.94%, but median negative and -10% rate 12.8%. Mixed/unstable; not accepted.

Blind V4 protocol behaved correctly:
- all four predeclared variants were evaluated on 2024 development only;
- all failed the development utility requirement;
- `locked_variant=null`;
- 2025 was not opened;
- 2026 was not evaluated.
Decision: reject this V4 family as currently specified; do not retune it to obtain a good-looking 2026 result.

## JPX point-in-time membership — ACCEPTED
Run #112 (`34554140015`, retained artifact `10181998903`) established:
- anchor 2026-09-11
- current members 3,700
- official listing/delisting event rows 1,096
- `unknown_market_rows=0`
- `same_day_code_collisions=0`
- parsed/required years 2022-2026
- `missing_event_years=[]`
- `valid_for_membership_reconstruction=true`
- temporal code reuse: `3960`, `8303`; quarantine these identities.

This accepts membership reconstruction only, not survivorship-bias-free price history.

## Yahoo delisted-price coverage — REJECTED
Same run #112:
- official delisting events 463
- identity quarantined 3
- probed 460
- usable near delisting 11/460 = 2.39%
- probe errors 0
- missing 400
- missing before delisting 47
- partial old/sparse 2
- usable by delisting year: 2022 0/76, 2023 0/60, 2024 0/94, 2025 0/124, 2026 11/106.

Decision: Yahoo alone is insufficient for historical OHLCV of delisted TSE names. Never describe current-survivor-only Yahoo research as survivorship-bias-free.

## Stooq delisted-price coverage — IMPLEMENTED, LIVE MEASUREMENT PENDING
Stooq is the first free backfill candidate. Its 2026 CSV access requires an API key obtained manually; the key must remain env/secret-only.

TEST-only implementation:
- `d6b42eddf1c872f6be532d88cb5bb0b8072a600d`: coverage probe.
- `37ee3a4858b7e1a182dcee471e3da849b2fb93e6`: synthetic checks.
- `fc86c5412859f17dd2215becf5bd8b4516ccd4df`: workflow integration.

Probe semantics:
- reuse exact JPX official-delisting candidates and identity quarantine used for Yahoo;
- deterministic year-balanced 24-event sample from pre-2026 delistings; no returns used to sample;
- require complete OHLCV near official delisting, same 45-day near window and 14-day max last-price gap;
- distinguish true `No data` from auth, rate/quota, HTTP, transport, unexpected response, and parse errors;
- sanitize exception reporting so a URL containing the API key cannot leak into artifacts/logs;
- expand to all 460 only if the small sample proves retained history and workable request limits.

Run #119 (`34557956808`) confirmed `Delisted Stooq coverage synthetic self-check` PASS. The run was then cancelled by branch-update concurrency during Yahoo measurement, so the live Stooq step was skipped. **Skipped is not missing-history evidence.**

If `STOOQ_APIKEY` is unavailable or Stooq coverage is inadequate, J-Quants Free is only an official overlapping-window cross-check: its free two-year history with 12-week delay cannot fill the 2022-start contract in September 2026. JPX historical price files remain manual-only; do not automate scraping. Do not scrape Yahoo! JAPAN history pages.

## Fundamental / dilution research
TEST-only collectors/evaluators enforce causal availability and explicit unknown flags. Balance-sheet monetary `SubscriptionRightsToShares` is not accepted as residual potential-share count. Initial dilution thresholds remain predeclared at 20%, 35%, 50%, 100%; do not select using 2026.

Live EDINET remains blocked on `EDINET_API_KEY`; key stays env/secret-only. PER/PBR work remains deferred until point-in-time share-count/treasury-share/profit-period alignment is reliable.

## Current blockers
1. No accepted free 2022+ OHLCV backfill for delisted TSE names; Yahoo coverage is only 2.39% near delisting.
2. Stooq live coverage cannot be concluded until its deterministic pre-2026 probe actually runs with a manually obtained `STOOQ_APIKEY`.
3. Live EDINET validation requires `EDINET_API_KEY`.
4. Existing fixed-start Short/Swing performance remains materially below Stable★6 reference.
5. The legacy +5.42% V3 exact parameter set is still unrecovered; targeted TEST-only recovery is active, but 2026 must not be used for fitting.

## Next concrete tasks
1. Inspect the targeted legacy V3 recovery workflow started from commit `28ab0492ab1dee59e255b459f8543278cad1a9af`; accept/reject based on pre-2026 evidence, never by forcing the 2026 headline result.
2. Confirm manifest-v4/fixed-baseline guard on a non-cancelled TEST run.
3. When `STOOQ_APIKEY` is available, run the deterministic 24-event pre-2026 coverage probe and expand to all 460 only if evidence supports it.
4. If Stooq stays blocked/unusable, add a TEST-only J-Quants Free overlapping-window coverage/sanity probe without pretending it solves 2022-2023 backfill.
5. Production integration remains blocked until explicit user Go.
