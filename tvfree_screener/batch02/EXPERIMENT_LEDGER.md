# TV-Free batch02 experiment ledger

All results are RETROSPECTIVE_PROVISIONAL unless a genuinely unviewed future period is later recorded. No production edits.

## CORE-TREND-COMPRESSION-20260913-01 — REGISTERED

- Freeze timestamp UTC and spec digest: see `FAMILY_SPEC.json` and `FAMILY_SPEC.sha256`.
- Mechanism: positive 20-session and nonnegative 5-session return; five-session realized volatility below its 20-session realized-volatility baseline; rank by the ratio ascending.
- Period: discovery 2022H2–2023 only; 2024 gated/retrospective confirmation only; 2025/2026 closed.
- Outcome status: **NOT OPENED** at preregistration time.
- Decision: pending frozen discovery execution.
## TVFREE-ANNUAL-CANDIDATE-AUDIT-20260913-01 — frozen, outcomes not yet replayed

- User-directed year-by-year report for the existing leading Monster and Core references; exact contract is ANNUAL_CANDIDATE_AUDIT_SPEC.json (hash pinned in sidecar).
- Monster: frozen weak+early+volr20-low pool, all detections/day, no Top-N cap, one-prior-XTKS-session same-symbol cooldown. V7 signal feature cache has years 2023-2025 only. 2025 is opened for report-only once, no tuning or selection. Do not use cached outcome columns.
- Core: V29 fixed_min98_both only; exact annual replay unavailable because raw 4h results and dated watchlist/teacher rows are absent. Do not substitute daily-derived indicators.
- V29/Monster prior target/population definitions differ; no direct composite comparison.
- Decision pending annual Monster replay.


## TVFREE-ANNUAL-CANDIDATE-2022-2026-EXT-20260913-03 — REPORT_ONLY / NO_PROMOTION

- User-requested extension of the frozen weak+early+volr20-low Monster annual report. Frozen extension spec: tvfree_screener/batch02/ANNUAL_CANDIDATE_2022_2026_EXTENSION_SPEC_V3.json; SHA-256 67d0cfd5fdb2bac4780dde5581123e721f0e3aaf7c82284710e5745af095c175.
- Runtime: local research venv, XGBoost 3.4.1. Feature scoring uses the original V7/V9 source recipe and monthly causal training (matured labels before month start; minimum 30,000 rows); user-facing output remains report-only.
- Cache reproduction check: 2024-06 generated 30 tail-gate rows versus 37 in the preserved cache; tail-p maximum absolute difference 0.03175835206146238. The historical cache does not record its XGBoost runtime. Do not search versions or tune thresholds to force a match. 2022/2026 values are runtime-sensitive source reconstructions, not exact preserved-cache replays.
- 2022: 24 detections / 16 symbols; 23 resolved and one year-boundary purge. Net after assumed 0.5% round-trip cost: mean +4.40%, median -5.36%, win 43.48%, +10/+20/+50 rates 26.09/13.04/4.35%, -10/-20 rates 26.09/4.35%, best-one/best-three exclusion means -0.74/-5.01%. Only June-December scored; January-May did not meet the frozen 30,000-row training minimum.
- 2026 through 2026-09-11: 49 detections / 28 symbols; 47 resolved and two beyond available OHLCV. Net after assumed 0.5% cost: mean +0.08%, median -5.46%, win 38.30%, +10/+20/+50 rates 27.66/14.89/4.26%, -10/-20 rates 40.43/12.77%, best-one/best-three exclusion means -1.52/-3.67%. Partial-year, previously exposed, report only.
- 2022/2026 are not used to promote, reject, or tune the candidate. These rows should not be pooled as a single exact-runtime series with 2023-2025 cache results.
- Core V29 annual results remain unavailable: preserved dated symbols, teacher rows, and historical hourly/four-hour inputs are absent. Do not approximate them from daily OHLCV.
- Outputs: reports/annual_candidate_evaluation_2022_2026_extended.md, matching JSON, all-year detected-symbol CSV, and all-pool CSV.
- Frozen extension registrations V1/V2 were superseded before requested-year outcome evaluation; they produced no 2022/2026 return summaries. V3 is the authoritative extension and report.


## CORE-TREND-COMPRESSION-TOPN-DIAGNOSTIC-20260913 — INVALID LABEL-COVERAGE READOUT

- User-directed methodology deviation, registered after the original full-pool outcome summary was read. The original experiment's Top1/2/3/5 membership and ranking had been frozen and hashed before any labels.
- Reason: the frozen full-pool gate is INCONCLUSIVE because every active date contains at least one unresolved row. The all-universe pool is a reference population rather than an implementable score; requiring every stock on every date to resolve prevents assessment of the already-fixed daily policies.
- A first Top1/2/3/5 readout was generated, but label joins were incomplete: labels were built only for another model's eligible candidates. `LABEL_ROW_MISSING` therefore means missing evaluation coverage, not a proven non-tradable outcome. All policy-level resolved-only metrics in that readout are invalid for strategy judgment; the original artifacts are preserved with an adjacent invalidation notice.
- No N selection, thresholds, feature/rank/cooldown changes, later-period access, or promotion occurred. The prior diagnostic spec and output remain audit evidence only.
- Candidate-pool, ranked-pool, and combined Top1/2/3/5 selection hashes are pinned in the companion spec. The first failed evaluation attempt and subsequent join-key recovery are preserved in the recovery receipt; the original 2022H2-2023 results are retrospective/exploratory, not OOS.
- Current Bot comparison is context only: the local 2026-09-09 report lists Stable ★6 n=55, mean +6.6%, median +1.5%, win 56.4%. Its BOTTOM-signal population and signal-close target differ from this all-TSE/next-session-open target, so direct score claims are prohibited.
- Status: SUPERSEDED_INVALID_LABEL_COVERAGE; correction is registered separately before rebuilding labels.

## CORE-TREND-COMPRESSION-LABEL-RECOVERY-20260913 — CORRECTION IN PROGRESS

- The frozen Top1/2/3/5 candidate decisions remain unchanged. Rebuild canonical labels for every one of the 278,783 candidate-pool rows using the saved decision-only daily OHLCV panel ending 2023-12-29.
- Target and actionability checks reuse the pinned five-session label builder: next XTKS open to fifth XTKS close, positive-volume/valid OHLCV checks, and unresolved labels retained.
- The original label parquet scoped to Core Moderate Ridge is expressly excluded as the corrected source. No numeric outcomes after 2023 may be opened.
- Corrected report is exploratory/retrospective only; it cannot promote a policy. Any later-period test needs its own frozen spec.
- First pre-outcome spec write exposed a Windows newline/hash mismatch; no outcomes were opened. The runner now hashes the exact bytes written and the spec was re-frozen.
- Frozen correction spec: `reports/core_trend_compression_label_recovery_spec.json`; SHA-256 `a4e3cc0ce6122cced22c9042a5b874c656ce2d14b804ceb780fe90e5a220b1b2`.
- Status: `REJECT_FROZEN_POLICIES`; full-pool canonical label rows rebuilt and hashed. Corrected report: `reports/core_trend_compression_label_recovery.md` / `.json`.
- All unchanged Top1/2/3/5 policies had negative 0.5%-cost means (-0.14/-0.09/-0.08/-0.08%), -0.50% medians, and 39.1/40.7/40.8/40.6% wins. Resolved counts were 276/600/916/1,582 of 365/730/1,095/1,825 selected. Every Top3-excluded mean stayed negative; no policy passed the frozen retrospective gates.
- The broad full-pool reference had 272,151/278,783 resolved labels; all 365 daily cohorts were partial because the entire TSE pool includes future zero-volume/unactionable bars. This does not block judging selected policies, but it prevents a full-pool complete-day comparison.
- Decision: reject trend compression as a Core policy family. Do not adjust its thresholds or ranking. The corrected numbers are retrospective repair evidence, not OOS and not production parity.
- Verification: 69 batch01 tests plus all four batch02 trend-compression/recovery tests pass under package-qualified unittest discovery; the runner and frozen hashes reproduce.

## CORE-GAP-DOWN-PARTIAL-RECLAIM-20260913-01 — REJECT_GAP_RECLAIM_DISCOVERY

- Independent hypothesis: after an opening gap down of at least 1%, a bullish daily candle that recovers at least half but less than all of the gap and closes in the top quarter of its range may show seller absorption before a five-session rebound. The close remains below the prior close, distinguishing it from First Reversal's positive-ret1 setup.
- Signal-time only: clean daily OHLCV, gap, and close location; no market-regime, volume, or fundamental filter. Score is the equal-weight mean of close-location and gap-reclaim fraction.
- Selection is every score at or above the within-day 80th percentile, all ties included, one official XTKS-session same-symbol cooldown, unlimited names/day, and no substitution on empty days.
- Target is next XTKS open to fifth XTKS session close with 0/0.5/1.0% round-trip cost sensitivities. Discovery is 2022H2 through 2023 only; those outcomes were viewed for other families, so this remains retrospective evidence. Later years require the registered staged gates; 2026 is report-only.
- Feature-only preparation completed from the bounded decision panel. There are 1,260,690 universe rows, 11,419 candidates across 3,102 symbols and all 365 active dates; q80/all-ties selection with one-session cooldown produced 2,361 rows (131.17 per calendar month), with multiple names allowed and zero empty selection days.
- Frozen decision hashes: pool `354b3de71b32a27f854e2855ad4a7d395b320dcdabf4b54a7e62d537fcff57b2`; ranked `df9a37a7d820bd29684c4813a3719d7be360f5ee051e28c1eabf8079f996d38b`; selected `3997f9d573cff0d18ade886b327b019207b20b56c13853ea3c7895cd62cd1d3c`. Candidate/rank/selection recomputation and artifact hashes reproduced exactly before any labels were opened.
- Verification: all seven focused batch02 unit tests pass. Preparation receipt says `outcome_values_opened=false` and `later_periods_opened=false`.
- Evaluation: `reports/core_gap_reclaim_discovery.json` / `.md`; 2,361 selected of 11,419 candidates, 2,146 resolved (90.9% coverage). At 0.5% assumed round-trip cost: mean -0.4685%, median -0.6095%, win 37.88%, +10/+20/+50 2.75/0.75/0.19%, -10/-20 2.14/0.14%, Top1/Top3-excluded mean -0.5291/-0.5863%. Cost-free mean was only +0.0315%, median -0.1095%, win 45.28%; the frozen ranking did not add value over the full candidate pool (costed pool mean -0.4550%, median -0.6181%, win 40.43%).
- Stability: only 6/18 months had positive net mean; removing the best month left -0.554%. Of 365 selected-date cohorts, 207 were complete and their costed mean/median/win were -0.222/-0.500/38.16%; 158 were partial because some selected rows could not be resolved. Weekly block-bootstrap 95% mean interval was -0.869% to +0.585%, with P(mean <= 0)=0.73. Top symbol contributed 1.12% of resolved rows and top five 4.57%, so poor results were not explained by single-symbol concentration.
- Decision: reject the gap-reclaim family as a broad Core selector. It failed signal-quality, monthly-robustness, and complete-cohort gates. Do not tune the gap, reclaim, close-location, quantile, or cooldown parameters against these outcomes; 2024+ outcomes remain unopened for this family.
- Fundamental V2 handoff is currently absent from this checkout; proceed independently and recheck at the next milestone.
- Frozen spec: `reports/core_gap_reclaim_spec.json`; SHA-256 `aee0f9e2f79af99149c1d2b1993772778a6d2c3ecc19f44d30075f611fbb7926`.
- Status: rejected after frozen discovery. Decision artifacts were recorded before outcome access in local commit `926f983`; evaluation and rejection summary are recorded afterward. Candidate/rank/selection/label Parquet artifacts remain local `.cache` audit evidence and excluded from Git. Weekly usage last observed 40% used / 60% remaining; pause latch remains false.

## CORE-ALL-MARKET-STATE-20260913-01 — REJECT_ALL_MARKET_STATE_FEATURES

- Rationale: the gap-reclaim ranking did not improve on its pool, and the existing First Reversal winner/loser audit was already rejected after its DD60 direction reversed in 2024. This audit expands the population to all actionable date/symbol rows in the preserved daily source and excludes DD60 rather than recycling that finding.
- Frozen spec: `reports/core_market_state_audit_spec.json`; SHA-256 `8d5efa0280715ae4c46f2b4a2580b11319cf901d59f4e86783a7ed26bb9255cb`.
- Candidate population: every valid positive-volume daily bar with a signal-day gap ratio from 0.60 through 1.40, no First Reversal prefilter, no ranking/cooldown/cap. Historical universe membership is limited to symbols present in the preserved Yahoo source; point-in-time delisting completeness is not guaranteed.
- Frozen features: 31 signal-time variables covering returns/acceleration, volatility, range/body/close location, volume/liquidity, drawdown/position, candle composition, dispersion, and lagged/cross-sectional market state. Inclusive same-day volume ratios, days-since-drop (ambiguous missingness), and previously rejected DD60 are excluded.
- Target and phases: next XTKS session open to fifth XTKS session close; winners >=+10% gross and losers <=-10%. Discovery uses separately purged 2022H2 and 2023; feature directions and discovery terciles freeze before 2024 direction-only confirmation. 2025 is closed for this audit; 2026 is report-only.
- Discovery rule: >=50 winners and losers per split, >=95% finite feature coverage among resolved rows, matching nonzero Cliff's delta and median-difference signs in both splits and pooled data, absolute pooled Cliff's delta >=0.10, and at most two features by the preregistered sort. Every selected feature must match both 2024 effect direction and frozen outer-tercile winner-share direction; no replacement search after failure.
- Data handling: feature panel ends 2024-12-30. The streaming source pass inspects only each row's date prefix for cutoff filtering; 2025+ OHLCV is never numerically parsed for this experiment. Discovery labels are built with a price frame ending 2023-12-29; 2024 labels cannot open until a discovery freeze exists.
- Before data access: 69 batch01 tests and 11 focused batch02 tests passed; spec, source/calendar hashes, and implementation hashes verify. No new feature panel or outcome labels have been read. Weekly usage last observed 41% used / 59% remaining.
- Feature-only panel: 2,554,987 rows / 3,612 symbols through 2024-12-30; SHA-256 `37dd48dbc1ac1b7e1128a6cfb990100333704720506d9cae18d8a74405d19682`; manifest SHA-256 `c3cf2f92214a8eaaceb5a0f706a1a02d2f7ee8f7473554d4b15ea5dd7b73dfd6`. The date-prefix filter discarded 1,506,374 out-of-range source rows before numeric OHLCV parsing; the panel manifest confirms `labels_included=false` and `2025_plus_numeric_ohlcv_parsed=false`.
- Candidate pool: 2,129,867 source rows in the signal period, 2,107,533 clean bars, 297 clean bars outside the registered gap-actionability range, 2,107,236 eligible rows across 3,604 symbols and 609 signal days. Candidate-row digest `7894e8b6673d95c9dcc748eba23adb2f33376cacc9983ed1c77e0cfa813e47e8`; Parquet SHA-256 `af2136ad0e54be39b58a48c415f12f5f4076622f0446ea045a94a83b67ec5100`.
- Candidate preparation recomputed from the panel and reproduced the same row hash and counts. Receipt records `outcome_values_opened=false`, `2024_outcome_values_opened=false`, and `2025_plus_features_or_outcomes_opened=false`.
- Discovery execution was run from frozen code commit `7739e4688bfb584e07f3ca21356919f3bada3079` after the pool commit. Only 2022H2 and 2023 labels were opened: 2022H2 398,118 eligible / 384,563 resolved, 9,046 winners and 5,937 losers; 2023 829,740 eligible / 810,940 resolved, 20,729 winners and 14,362 losers.
- The frozen selection rule retained `range_pct` and `dispersion20`, both `lower_for_winners`. `range_pct`: Cliff's delta -0.1587 / -0.1447 and median winner-minus-loser delta -0.00677 / -0.00552 in 2022H2 / 2023 (pooled -0.1462 / -0.00576). `dispersion20`: Cliff's delta -0.1522 / -0.1240 and median delta -0.00346 / -0.00318 (pooled -0.1301 / -0.00314). Finite coverage was 100% for range and >=99.76% for dispersion.
- Frozen discovery tercile edges: `range_pct` [0.013355592265725136, 0.02361111156642437]; `dispersion20` [0.011891510337591171, 0.01889415830373764]. These were calculated without labels under the registered procedure.
- Discovery JSON SHA-256 `eb85138b24f56afc8858ee5158f697899193b1c3bcd8df1613a9543cb6f68f33`; feature-freeze JSON SHA-256 `a51aa151da8ff6cde61e32b7dc3af49a15621aeff7f7b3fa6d3daaa1de9b18b3`. Reports: `reports/core_market_state_discovery.md` / `.json`; freeze: `reports/core_market_state_feature_freeze.json`.
- Both features passed the preregistered discovery gates, so the decision is `PROCEED_TO_2024_DIRECTION_CONFIRMATION` only. This is retrospective descriptive association, not an implementable score or promotion; repeated-symbol/time dependence means no independent-sample significance claim. The frozen 2024 test requires both effect directions and frozen outer-band winner-share direction, with minimum class counts, for each feature.
- Before confirmation, discovery/freeze/control/ledger were locally committed at `8d06c42`. The discovery report recorded `2024_outcome_values_opened=false` and `2025_plus_features_or_outcomes_opened=false`; the 2024 runner then loaded only 2024 outcome prices through the registered 2024-12-30 cutoff.
- 2024 confirmation: 844,820 signal rows / 828,077 resolved, 24,756 winners >=+10% and 22,529 losers <=-10%. Both frozen features reversed discovery direction: `range_pct` winner-minus-loser median +0.005156, Cliff +0.10374, frozen low-to-high outer-band extreme-winner share 44.21% vs 54.44%; `dispersion20` median +0.006531, Cliff +0.15879, share 36.33% vs 56.97%. Minimum class counts passed, but neither the effect-direction nor broad-band direction checks passed.
- Whole-universe context only (not a strategy result): gross mean +0.0443%, median 0%, win 48.80%; at assumed 0.5% round-trip cost mean -0.4557%, median -0.50%, win 41.43%. This does not represent the selected behavior of any deployable score.
- Decision: reject this fixed-direction all-market state feature family. Do not flip the signs, tune the tercile boundaries, or search replacement features within this family from 2024. No candidate was promoted. 2025+ features/outcomes remain unopened.
- Confirmation JSON SHA-256 `1e29d8fc98dfef9b57596944119bef0de2c55de53a5a9478c20e280da8f89fa6`; Markdown SHA-256 `b721c48b2851cfdce8f836770e97f718ec39f2d110b62f217794185822cd1e0f`; report paths `reports/core_market_state_confirmation_2024.json` / `.md`. Confirmation label Parquet SHA-256 is recorded in the JSON; `.cache` labels remain local and untracked.
- Next independent experiment: preregister a trend-pullback interaction (established medium-term uptrend plus a controlled short-term retracement) as a separate strategy hypothesis, with broad fixed conditions, unlimited qualifying names/day, canonical next-session-open to fifth-session-close target, and no threshold tuning from the failed state audit. Treat all historical findings as retrospective; 2025 remains closed until a separate frozen gate permits it. Fundamental V2 handoff is still absent here.
