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

### Historical +5.42% Short reference and recovery status
The old non-reproducible 2026 Mar-Aug reference remains:
- n=29
- mean +5.42%
- median +2.06%
- win 65.5%
- +10% rate 13.8%
- -10% rate 6.9%

Exact old thresholds were never committed. A targeted TEST-only recovery workflow was added at `28ab0492ab1dee59e255b459f8543278cad1a9af` and run successfully as `34558192262`; artifact `10183354156`.

The recovery preserved the known architecture and did not tune to 2026:
- relative-ranking Core;
- recent-40 confirmed-outcome Meta with four fixed rules (`r40_win50`, `r40_win55`, `r40_mean0_win50`, `r40_mean0_win55`);
- fixed Attack families `lowvol_ignition_A/B` and `bounded_breakout_A/B`;
- fixed Deep Reversal families `capitulation_reversal_A/B`;
- one-business-day same-symbol cooldown;
- 2024 development first, only qualifying candidates allowed to open 2025, and 2026 only after validation.

Result: **all fixed combinations failed the 2024 development utility gate**. The artifact records `development_ranked=[]`, `validation_opened=[]`, `locked_candidate=null`. Therefore 2025 and 2026 were deliberately not opened. Reject this approximate recovery family; do not tune it to the known 2026 headline. The historical +5.42% result remains unrecovered, not disproved. Future recovery must come from exact archived parameters or materially different hypotheses selected from pre-2026 evidence.

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
5. The first causal approximation of the legacy +5.42% architecture failed 2024 development; exact old parameters remain unrecovered.

## Next concrete tasks
1. Confirm manifest-v4/fixed-baseline guard on a non-cancelled TEST run.
2. When `STOOQ_APIKEY` is available, run the deterministic 24-event pre-2026 coverage probe and expand to all 460 only if evidence supports it.
3. If Stooq stays blocked/unusable, add a TEST-only J-Quants Free overlapping-window coverage/sanity probe without pretending it solves 2022-2023 backfill.
4. For legacy +5.42%, search for exact archived parameters or test materially different pre-2026-derived families; never rescue the rejected recovery family by fitting to 2026.
5. Production integration remains blocked until explicit user Go.


## V5 right-tail winner research — DIRECT ABSOLUTE-TAIL MODEL REJECTED
User explicitly accepts a positively skewed model where a small number of very large winners lift the mean, provided the same pattern is detectable prospectively. Therefore large winners are no longer penalized merely for making the mean tail-driven.

TEST-only implementation:
- `508e9200413b2fe98c36a2aefaba9d50d27daffa`: causal +20%/+50%/-10% right-tail model.
- `560debea19e9251469ee8306dda4190ab54b40b8`: calibrate final tail gates only from causal training-score distributions.
- `ca169e64822cd4afa0f1fd2a3fb0807d7676c1fc`: enforce staged blind opening: score 2024 only -> top2 -> score 2025 only if qualified -> score 2026 only after validation pass.
- isolated workflow: `.github/workflows/tvfree-tail-winner-test.yml`.

Authoritative run: `34560020106`, artifact `10183988857`, head `ca169e64822cd4afa0f1fd2a3fb0807d7676c1fc`.
Input: retained fixed run-80 `tse_daily.csv`. Opportunity rows: 477,031; audit label counts across full available rows: +20% 6,874, +50% 1,037, -10% 18,390.

All four predeclared variants failed 2024 development:
- `tail20_q999`: 2024 pooled n=70, mean -0.93%, win 31.4%, +20% 0%.
- `tail50_q999`: n=71, mean -0.44%, win 38.0%, +20% 0%.
- `blend_q999`: n=70, mean -0.10%, win 27.1%, +20% 1.43%; one +48.3% winner existed but 2024H2 mean was negative.
- `blend_q9995`: n=34, mean -0.80%, win 23.5%, +20% 0%.
Thus `development_ranked=[]`, `validation_opened=[]`, `locked_candidate=null`; 2025 and 2026 were not scored by the final staged implementation.

Decision: reject **absolute +20/+50 classification with extreme training-CDF gates** as this V5 family. This does NOT reject positive-skew/tail capture as a goal. Next tail hypothesis should be materially different and should restore the historical V3 clue of cross-sectional/relative ranking, e.g. daily relative extreme-winner labels rather than absolute +20/+50 labels.


## Legacy event-quality rank recovery — REJECTED
Run `34560020086`, artifact `10184003302`, head `ca169e64822cd4afa0f1fd2a3fb0807d7676c1fc` completed successfully.
Hypothesis: event-specific monthly causal ML -> training-score CDF -> recent-40 Meta -> Attack when ON / Deep Reversal when OFF.
All 8 fixed combinations failed the 2024 development gate; `development_ranked=[]`, `validation_opened=[]`, `locked_candidate=null`. Typical 2024 pooled means ranged roughly -0.18% to +0.17%; no candidate captured a +20% winner. 2025/2026 remained unopened.
Decision: reject this event-constrained relative-ranking reconstruction. The next relative-tail test removes the fixed event-lane restriction and predicts daily future top-1% / top-0.25% ranks across the broad eligible universe.


## V6 cross-sectional relative-tail research — REJECTED
Implementation `0271a508d2b98849df65d0953a03006fcaadfc19`; isolated workflow `87233fe0217b945ff7f1b802c5e751f23df2ec30`.
Authoritative run `34560206590`, artifact `10184090465`, fixed run-80 input.

Hypothesis: monthly causal models predict which eligible names will finish in the same-day future 5BD top 1% / top 0.25%, with training-CDF sparse gates. This restored the historical clue of monthly relative ranking but used the lighter 26-feature candidate set.

All four variants failed 2024 development; `development_ranked=[]`, `validation_opened=[]`, `locked_candidate=null`; 2025/2026 remained unopened.
- rel1_q999: 2024 pooled n=143, mean -1.05%, +20% 0%.
- rel025_q999: n=156, mean -0.12%, +20% 0%.
- relblend_q999: n=152, mean -0.72%, +20% 0%.
- relblend_q9995: n=107, mean -0.78%, +20% 0%.

Decision: reject this light-feature relative-tail family. The positive-skew objective remains valid. Next materially different test should use the full historical 45-feature set and avoid suppressing Attack candidates with a loss-probability penalty; risk should be enforced as a validation gate rather than directly subtracting explosive high-volatility candidates from the ranking.


## Legacy rolling-3y cache forensics — CACHE DIFFERENCE NOT THE MISSING EDGE
Run `34560223482`, artifact `10184124215`, head `6509764acb761fdc1a1bfd0eed657a44d3a9afa1` successfully re-ran the reproducible 45-feature Short reconstruction on the actual rolling-3y `tse_daily.csv` retained from early run #7 (`34496517500`).

Results:
- 2025H1 Core n=119, mean +0.46%, win 58.8%.
- 2025H2 Core n=124, mean +0.35%, win 51.6%.
- 2026 Mar-Aug Core n=124, mean -0.56%, median -0.42%, win 44.4%.
- 2026 Mar-Aug defensive n=97, mean -0.11%, win 48.5%.

Decision: the historical +5.42% result is not explained by the old rolling-3y cache alone. The missing edge must be in the unrecovered logic/labels/ranking/Meta/Attack construction, not merely the later fixed-start data contract.


## V7 full-feature pure relative-tail research — TAIL DETECTION CONFIRMED, FINAL LANE REJECTED
Implementation `5fd8cdb00cd4deb617b7d3edfc42ee6385a00891`; isolated workflow `cddceaf066c8870a00a9a80d66f06dc44c9f358c`.
Authoritative run `34560510106`, artifact `10184212775`, fixed run-80 input.

Hypothesis: restore the historical Short ingredients most directly: all 45 `run.py` signal-time features, monthly causal retraining, future same-day top-1% / top-0.25% relative labels, pure positive-tail ranking with no loss penalty in the Attack score, one-business-day same-symbol cooldown, next-open -> 5BD.

All final variants failed the 2024 acceptance gate, so 2025 and 2026 remained unopened. However unlike V5/V6, V7 materially recovered **prospective right-tail concentration**:
- `full_top025_q999`: 2024 pooled n=192, mean +0.12%, win 38.5%, +20% 15.1%, +50% 5.73%, +100% 1.04%, max +173.6%, -10% 40.6%.
- `full_top1_q999`: n=186, mean -0.39%, +20% 14.5%, +50% 7.53%, +100% 1.08%, max +105.4%, -10% 40.3%.
- `full_blend_q9995`: n=138, mean -0.62%, +20% 17.4%, +50% 5.07%, +100% 1.45%, max +173.6%, -10% 45.7%.

Interpretation: daily OHLCV + the full 45-feature monthly relative model can materially concentrate future large winners, but raw tail ranking also admits too many large losers. Do **not** discard the Tail detector merely because its unfiltered mean is weak; preserve it as a research component. The next causal hypothesis is a separate downstream Quality/Meta layer that filters false positives while leaving Tail ranking itself untouched.

The user's accepted objective is positive skew: a small number of very large winners may legitimately lift average return if the pattern is prospectively detectable. Future evaluations should report mean, +20/+50/+100 capture, loss10, and regime stability; median is secondary rather than a reason by itself to reject positive skew.


## V9 conditional-on-Tail Quality — 2024 IMPROVED, 2025 REJECTED
Authoritative push run `34598346729`; artifact `10263352589`.

Hypothesis:
- preserve the V7 extreme top-0.25% Tail detector unchanged;
- train downstream Quality only on historical causal V7 Tail candidates;
- conditional targets: 5BD >= +20% and 5BD <= -10%;
- rank/filter by monster-vs-loss probability ratio;
- staged protocol: 2023 Tail warmup -> 2024 development -> top2 -> 2025 validation -> 2026 only after validation pass.

The strongest development variant was `ratio50`:
- 2024H1 n=42, mean +4.69%, +20% 19.0%, -10% 26.2%.
- 2024H2 n=61, mean +1.76%, +20% 18.0%, -10% 31.1%.
- 2024 pooled n=103, mean +2.95%, +20% 18.45%, +50% 3.88%, -10% 29.13%.

This was a real 2024 improvement versus raw V7: large-loss frequency fell materially while right-tail capture remained strong.

2025 validation then failed decisively:
- 2025H1 n=39, mean -0.40%, -10% 38.5%.
- 2025H2 n=52, mean -5.45%, -10% 51.9%.
- 2025 pooled n=91, mean -3.29%, +20% 9.89%, -10% 46.15%.
- `validation_pass=false`, `locked_candidate=null`; 2026 remained unopened.

Decision: reject the V9 learned conditional classifier as the final Quality layer. Keep the broader insight that **Quality must be learned/evaluated conditional on the Tail population**, not on all stocks.

## V10 historical-neighbor Quality — PROMISING 2024, STRICT GATE MISSED
Authoritative push run `34598608591`; artifact `10262863024`.

Hypothesis:
- preserve the same V7 extreme Tail detector;
- no outcome classifier;
- compare each current Tail candidate with previously completed causal Tail candidates in robust-standardized signal-time feature space;
- use neighbor future returns for Quality;
- fixed k=20/40 variants, with optional neighbor expected-return > 0 veto.

Best-looking development row was `knn40_pos`:
- 2024H1 n=28, mean +3.44%, +20% 21.4%, +50% 7.14%, -10% 32.14%.
- 2024H2 n=52, mean +5.03%, +20% 23.1%, +50% 7.69%, -10% 30.77%.
- 2024 pooled n=80, mean +4.47%, +20% 22.5%, +50% 7.5%, -10% 31.25%.

This missed the predeclared development gate only because pooled loss10 was above the fixed 30% ceiling. The gate was **not** loosened after inspection; therefore `development_ranked=[]`, 2025 was not opened, and V10 was not accepted.

Interpretation:
- historical-neighbor conditioning appears materially useful;
- ranking by neighbor **mean return** is vulnerable to right-tail outliers and is not the final formulation;
- next test V11 uses the same causal neighbors but ranks by a payoff-aware local probability utility:
  `2 * P(+20% or better) - P(-10% or worse)`.
  The 2:1 coefficient is fixed from the outcome magnitudes (+20 vs -10), not fit to future results.

## Frozen dataset preservation
Original fixed run-80 artifact `10179500303` expires 2026-09-14, so a TEST-only preservation workflow was added:
- workflow: `.github/workflows/tvfree-preserve-dataset.yml`
- source run: `34545440155`
- destination artifact name: `tvfree-frozen-dataset-run80-preserved`
- intended retention: 90 days
- trigger file: `tvfree_screener/RUN_PRESERVE_DATASET`

Use the preserved artifact for future research once the preservation run completes. Do not silently switch to a fresh Yahoo download when reproducibility against run #80 matters.
