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
- The adjacent `CORE-ORDERLY-PULLBACK-20260913-01` slot has already tested the trend-pullback idea. Its recovered 2022H2–2023 broad-pool mean/median were -0.2134%/-0.3778% after 0.5% cost, with 0 complete daily cohorts; all three measurable signal gates failed. Do not rerun or threshold-tune that family.

## CORE-MULTI-EVENT-QUALITY-20260913-01 — REGISTERED, outcomes not opened

- Frozen specification: `reports/core_multi_event_quality_spec.json`; SHA-256 `02dea9242d7aec279fc0765d323c419bacd5b2c130b74fae426bfe57d9ccce8c`. Frozen input hashes cover the preserved daily source, preservation manifest, and official XTKS calendar; implementation/test/dependency hashes are pinned in the spec.
- Hypothesis: a union of six distinct signal-time setups can provide a useful daily Core candidate pool when return-quality, +10%-hit, and -10%-loss heads are combined, while allowing multiple names/day. This tests event-conditioned ranking rather than revisiting the rejected single-family pullback or market-state rules.
- Event pool and thresholds are fixed in the spec. Selection is up to five names/session, score gate first, score-descending/symbol-ascending tie-break, one-next-session same-symbol cooldown. An empty day remains an abstention.
- Scorer: deterministic NumPy ridge heads on causal features, training-only standardization, alpha=30, and same-day percentile conversion. This replaced the planned XGBoost dependency before any outcomes were opened because no local XGBoost/Parquet runtime was available; no dependency was downloaded. It uses the shared canonical feature and label builders.
- Target: next XTKS open to fifth XTKS close. Each training label must exit before the half-year prediction boundary. Primary net-cost comparison is 0.5%, with 0% and 1% reported.
- Development/selection: 2024H1 and 2024H2 are retrospective, previously exposed periods. Each half must pass every fixed sample, net mean/median, win, +10, -10, Top3-exclusion, and complete-day cohort gate. Any passing variant is only eligible for a separate committed 2025 freeze; 2025/2026 remain closed in this experiment.
- Data access is still gated: generate the signal-feature pool, commit its receipt, independently rebuild it and commit the matching reproduction report, then open only prices through 2024-12-30 for labels. 2025+ numeric OHLCV must be filtered by the raw date prefix before parsing.
- Focused tests: seven passed on the bundled local Python runtime, including multiple names/day, five-name cap, XTKS cooldown, signal-feature-only pool, purged training, deterministic model output, and net daily-cohort accounting. Full dataset results are pending; no candidate has been promoted.
- Feature-only pool built from frozen code commit `f5517bdf02dc8b72f3fdae2fc37565bea452a9fc`: 90,006 rows, 2,105 symbols, 609 signal days (2022: 18,679; 2023: 37,939; 2024: 33,388), maximum raw pool 890 names/day before score gating. It covers 2022-07-01 through 2024-12-20, has no outcome-like columns, and its CSV SHA-256 is `638167d7a2edb802d3de202a582585efb847cb6cb252591c5e0bea15dbe372db`. The outcome-free receipt SHA-256 is `d984b30766af6690fa3d1f77cbe97993a405a190fdd4fca4a6eb065792e65e2e`; it is committed separately before any label processing. Outcomes remain unopened.
- Independent feature-pool rebuild reproduced all 90,006 rows and the exact CSV SHA-256 `638167d7a2edb802d3de202a582585efb847cb6cb252591c5e0bea15dbe372db`. The outcome-free reproduction report SHA-256 is `401ac151663beca44a5c3f4e040ccd34410d810363d436d2c078f274b5d3e555`; its report is committed before outcome processing. No 2025+ numeric OHLCV or labels were opened.

## CORE-MULTI-EVENT-QUALITY-20260913-01 — REJECT_MULTI_EVENT_QUALITY

- Result: `reports/core_multi_event_quality_2024_development.json` SHA-256 `a0c0103f6c1ccd45d284701770ab6c8c619532c898cc6ea2c39ded5c3db8ae4f`; Markdown SHA-256 `8b4457e932df337f98c82280569da692bd3ae11ab99f580c0402b4912d328c3a`. All 4 frozen score variants failed the preregistered Core gates in both 2024 halves. `n` below is resolved selected signals; means/medians and daily cohort returns are net of the assumed 0.5% round-trip cost.
- 2024H1: balanced `n=597`, mean/median `-0.244/-0.368%`, win `46.7%`, +10 `2.2%`, -10 `1.7%`, Top3-excluded `-0.368%`; winner-aware `n=597`, `-0.239/-0.500%`, win `44.7%`, +10 `3.4%`, -10 `2.0%`, Top3-excluded `-0.383%`; defensive `n=597`, `-0.218/-0.500%`, win `45.4%`, +10 `2.7%`, -10 `1.8%`, Top3-excluded `-0.365%`. Balanced-high-gate matched balanced.
- 2024H2: balanced `n=589`, mean/median `-0.772/-0.741%`, win `39.0%`, +10 `1.5%`, -10 `3.2%`, Top3-excluded `-0.920%`; winner-aware `n=590`, `-0.675/-0.638%`, win `41.8%`, +10 `3.2%`, -10 `4.4%`, Top3-excluded `-0.871%`; defensive `n=589`, `-0.840/-0.686%`, win `39.2%`, +10 `1.5%`, -10 `3.9%`, Top3-excluded `-0.988%`; balanced-high-gate `n=584`, `-0.769/-0.719%`, win `39.0%`, +10 `1.4%`, -10 `3.1%`, Top3-excluded `-0.915%`.
- Daily cohort medians and means were negative in both halves for all variants; after removing the best month, mean stayed negative. H2 weekly-block confidence intervals were below zero for all four variants. Symbol concentration was low (top-ten symbol share `5.6–7.5%`), and removing top performers did not explain the failure. The 0.5% cost is a sensitivity assumption, not measured live execution cost.
- Sample and coverage were sufficient for the frozen selected-signal gates, but central tendency, win rate, +10 rate, and downside-adjusted criteria failed. Decision: reject this multi-event ridge family; do not fine-tune its score weights, gates, or six event thresholds against these retrospective 2024 outcomes. No variant locked. 2025/2026 features/outcomes were not opened; production was unchanged.
- Pool reproduction remains exact as recorded above. Seven focused tests passed before outcomes; label/data artifacts are local `.cache` only. Continue with a materially distinct hypothesis and preregister before opening that experiment's outcomes.

## CORE-SUPPORT-SWEEP-20260913-01 — FROZEN_BEFORE_DISCOVERY_OUTCOME_ACCESS

- Hypothesis: a daily bar undercuts the minimum low of the five immediately prior official XTKS sessions, then closes above that support in the top quartile of its range. This is a failed-breakdown/short-term demand setup, distinct from the rejected opening-gap reclaim.
- Frozen spec: `reports/core_support_sweep_spec.json`; SHA-256 `74ad269f4b53527b730f39eb337118d85d978d556b958eb9d5d60e8f98ca06c7`. Code and implementation hashes are pinned inside the spec. Target is next-session open to fifth-session close; rank by equal-weight close-location/support-reclaim quality; select up to five names per day; one-session same-symbol cooldown.
- Candidate cutoffs: discovery signals through 2022-12-23 (last exit 2022-12-30) and 2023-12-22 (last exit 2023-12-29), separately gated. 2024/2025 outcomes are closed and 2026 is report-only. Historical outcomes in discovery years were seen in other families, so any result is retrospective, not untouched OOS.
- Frozen gates require each discovery period to have at least 75 resolved picks, at least five picks/month, net mean and median above zero, win rate above 50%, positive top-three-excluded mean and complete-day cohort metrics, downside rates no worse than its full candidate pool, and at least half of resolved months positive. Any failed gate rejects the whole family without parameter replacement.
- Four focused tests pass for strong reclaim, weak/no reclaim rejection, missing XTKS-session handling, multi-name cap and symbol cooldown. Frozen feature-only pool: 43,931 candidates / 3,505 symbols / 365 dates; Top5 produced 1,825 selections, exactly five on each date. Candidate/rank/selection digests reproduced exactly. Receipt SHA-256 `62a7e28db55cb797d5cdde5dad36873c7a962432e2bafe10e26cb3b4de5c24c5`; reproduction report SHA-256 `6da19259c717dc999621d454d540d6129513831c55de89dee3a8a37d4b655c10`. Both are outcome-free; no 2024+ numeric OHLCV was opened. The frozen 2022H2/2023 labels remain unopened until these receipts are committed.

### Report-side join recovery — initial report invalidated

- The first evaluation report `reports/core_support_sweep_discovery.json` SHA-256 `0385737e936325a68db963114e3746ca43f3e7a8a2ebb3d3cbec1b981bcf14b1` is invalid: its selected-signal summary counted the full candidate label pool instead of joining the selected Top5 keys. Do not use its selected signal metrics or decision.
- The frozen candidate, rank, and selected artifacts remain unchanged; the selection digest remains `22878879cecf5cbd7d56112ec4d4a56ec554a456a9c27e938c270b73c6d6cfc0`. The label digest from the first pass is `54d2cc0c4a99f101c2baccb6988d7140532280e13bd903de5a133a3491ef552d`.
- A separate report-recovery script and two join tests now enforce exact one-to-one selection-key joins and fail closed on a missing label. This is evaluation plumbing recovery only; no signal definition, ranking, cooldown, sample, or gate is changing. The same 2022H2/2023 labels will be reprocessed, and the original report will be preserved with an invalidation notice. 2024+ remains closed.
- Corrected report: `reports/core_support_sweep_discovery_recovery.json`, SHA-256 `f1f7731d447f9b46ebf39242cb51031a1f49fadb3350bc94766b36c81534aff3`; Markdown SHA-256 `25c9e69aad9f45bd852a8b77ca6e98af8e542d4c98c496e5c5fdef21ce1259cb`. Canonical label digest matched the first pass exactly (`54d2cc0c4a99f101c2baccb6988d7140532280e13bd903de5a133a3491ef552d`), and frozen selection digest was unchanged.
- At assumed 0.5% round-trip cost, 2022H2 selected 515/595 resolved: mean `-0.802%`, median `-0.627%`, win `39.2%`, +10 `1.36%`, -10 `4.08%`, -20 `0.78%`, top-three-excluded mean `-0.916%`. There were 60 complete and 59 partial selected-day cohorts; complete-day mean/median were `-0.915/-0.313%`, and top-three-excluded mean `-1.171%`.
- 2023 selected 1,104/1,205 resolved: mean `-0.189%`, median `-0.500%`, win `41.3%`, +10 `3.08%`, -10 `2.81%`, -20 `0.72%`, top-three-excluded mean `-0.365%`. There were 158 complete and 83 partial selected-day cohorts; complete-day mean/median were `-0.136/-0.408%`, and top-three-excluded mean `-0.362%`.
- Selection concentration was low (highest period top-one share `0.78%`), yet both periods failed their fixed central-tendency/win/top-three gates, and complete-day cohort gates failed. In 2022H2 the selected -10/-20 rates were also worse than the full candidate pool. Decision: `REJECT_SUPPORT_SWEEP`; do not change sweep depth, close-location cutoff, rank, or daily cap based on these outcomes. No 2024+ data was opened.

## CORE-BOLLINGER-RECLAIM-20260913-01 — FROZEN_BEFORE_DISCOVERY_OUTCOME_ACCESS

- Hypothesis: intraday trade below the prior-close-only 20-session lower Bollinger band followed by a close back above it in the upper half of the day's range may be a volatility-normalized failed breakdown.
- Frozen spec: `reports/core_bollinger_reclaim_spec.json`; SHA-256 `ed3e053d81ab20b8f999bc44b1d3960f686f3df134eb09e93dc7702108f856b4`. It fixes population, band definition (prior 20 official sessions, population standard deviation, 2 sigma), event, equal-weight reclaim/close-location score, Top5/day, tie-break, cooldown, target, cutoffs, and all gates. Code and helper hashes are pinned inside.
- Discovery is separately purged 2022H2 and 2023 through 2023-12-22 with final exits by 2023-12-29. 2024/2025 remain closed; 2026 is report-only. Historical outcomes have been seen in other families, so results are retrospective.
- Four focused tests pass for band reclaim, close/undercut rejection, missing-session treatment, five-name cap, and symbol cooldown. Outcome-free pool: 43,763 candidates / 3,496 symbols / 365 dates; Top5 produced 1,825 selections, five on every date. Pool, rank, and selected rows reproduced exactly. Receipt SHA-256 `39714255d46b4fb22fcb310880578819c085fbfb84d8e4e2b4dfaff6da9562aa`; reproduction report SHA-256 `d9bcbb3c2bd8ad4a41ae7b0b3af7eb75383c82c46dc69e3fb7bf6d724e13fc28`. Both were committed before the result read.
- Correct evaluation: `reports/core_bollinger_reclaim_discovery.json`, SHA-256 `8bc081574136eb6f20232b8091e9f797409c71daee4e8212a16b05782c2a3225`; Markdown SHA-256 `daa6c592c3938945acfae4502888b3436e28d58652b608dc7600932e5df2869d`. One-to-one selected-key joins were used; no report recovery was needed.
- At assumed 0.5% round-trip cost, 2022H2 selected 545/595 resolved: mean `-0.453%`, median `-0.779%`, win `32.7%`, +10 `2.02%`, -10 `1.47%`, -20 `0%`, top-three-excluded mean `-0.719%`. There were 82 complete/37 partial selected-day cohorts; complete-day mean/median were `-0.358/-0.736%`.
- 2023 selected 1,113/1,205 resolved: mean `-0.668%`, median `-0.500%`, win `35.8%`, +10 `1.17%`, -10 `1.71%`, -20 `0.45%`, top-three-excluded mean `-0.817%`. There were 157 complete/84 partial selected-day cohorts; complete-day mean/median were `-0.704/-0.642%`; the weekly-block 95% interval was `-1.219%` to `-0.175%`.
- Best-symbol concentration stayed below `0.74%`, but both periods failed positive mean/median/win/top-three gates and daily-cohort gates. Downside rates were also worse than the full candidate pool. Decision: `REJECT_BOLLINGER_RECLAIM`; do not tune the 20-day/2-sigma boundary or candle cutoff. No 2024+ outcomes were opened.

## CORE-STOCHASTIC-CROSS-20260913-01 — FROZEN_BEFORE_THIS_EXPERIMENTS_OUTCOME_ACCESS

- Hypothesis: standard 14-session stochastic %K crosses above 3-session %D after prior-session %K <= 20, with signal-day close location >= 0.50; rank by current K-D strength.
- Frozen spec: `reports/core_stochastic_cross_spec.json`; SHA-256 `853d89bfa70cab2812e035ffcae30188e998d6cfb98b627acc602e82c240e5d7`. The shared `FAMILY_SPEC.json` remains unchanged and its SHA-256 `4303a8033dfdffbd97eed21fca1b92b1b4012c3a0d4548be1eb78051d0e26e1f` is verified before outcome access.
- Selection is up to five names per official XTKS session, score descending then close location descending and symbol ascending, with one-next-official-session same-symbol cooldown; empty days remain abstentions.
- Target is the canonical next-session open to fifth-session close including entry. Its source artifact, manifest, original target-spec identity `6f56fc4c0f914f6faec0285e915a393044003505bc5d71cabb52e4d7778dcfa7`, official calendar, and feature-only panel hashes are pinned. Missing canonical labels stay explicitly unresolved; duplicate date/symbol labels fail closed.
- Discovery is purge-safe 2022H2 and 2023 only, ending at signals 2022-12-23 / 2023-12-22 so the last exits remain inside each registered boundary. 2024+ are closed for selection; prior exposure makes results retrospective rather than true OOS. Fixed gates require positive net mean, median, win >50%, positive Top3-excluded mean, adequate sample/frequency/coverage, no worse -10/-20 rates than the same-date full candidate pool, and positive complete-day cohorts in both periods.
- Before outcome access, all 35 batch02 tests passed, including four stochastic tests for the oversold cross, weak close rejection, missing-session behavior, Top5 and cooldown. No forward-return label values have been opened. Weekly use at registration: 46% used / 54% remaining.
- Outcome-free pool preparation produced 1,260,690 source rows, 1,245,061 clean bars, 100,410 oversold-cross rows and 75,348 eligible candidates across 3,510 symbols and 365 candidate-bearing dates. Frozen Top5 selected 1,825 rows, five on each date; there were no empty selected days. Pool/rank/selection digests: `6fd7838bd57e62bc5ef5c9e00d156331b31166822a8c8a74daeb05c823758d4e` / `30cb14cd1e1b378392d6fbe5db405b319a1914eb0204ccefc501e392c067fe3e` / `958c977a5b466090ee853f544db986617ea06d39d06d86239e8e4da9dcfa013d`. Outcome-free receipt SHA-256 `24588dd6d7bd22cbab49fc3ca6a0280b191e7458ca237e130017195a230f850b`; Parquet receipts remain in ignored `.cache/`.
- Independent rebuild reproduced the pool, ranking, and selection digests exactly. Reproduction report SHA-256 `55f35bf382e87953c5b88fa0f7c54b9ea2dea9f16b9817385d3b735ea09d876e`; it confirms `outcome_values_opened=false` and `2024_plus_numeric_ohlcv_opened=false`. The outcome-free receipt was already committed as `55be7de`; this reproduction report must also be committed before evaluation.
- The first post-commit evaluation opened only the frozen canonical discovery labels, then stopped before writing a report because the runner queried a nonexistent `selected_count` inside `return_metrics`; the canonical key is `requested_count`. The corrective script changed only this report-side key, retained all selected keys/labels/gates, and recorded recovery code SHA-256 `f790aa925a86813259cb9332aaa90008d5a3628aa47eae294477bb163255b2d0`. Corrected JSON SHA-256 `a4a8bc2e80c02b41917b4b01bbd795472f7c1b50e99057bb1e1dbd720bb8d0bb`; Markdown SHA-256 `8ea5d337e9d16d435e5f869922848ecd1dd0aded8889c2418f4308e61e4f7de2`. Canonical label digest `aedb2f9aba326724093c6903f5929fa30257ba960944422b6eb225414db29a2c`. Label-source absences and unresolved zero-volume/invalid-price labels remain in the denominators; nothing was dropped or replaced.
- At 0.5% assumed round-trip cost, the frozen Top5 selected-signal results were:

| Period | Resolved / selected | Mean | Median | Win | +10 | +20 | +50 | -10 | -20 | Top1-excluded mean | Top3-excluded mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2022H2 | 507 / 595 | -1.333% | -0.985% | 28.80% | 2.96% | 1.38% | 0.20% | 6.51% | 1.58% | -1.464% | -1.577% |
| 2023 | 1,068 / 1,205 | -0.895% | -0.684% | 34.36% | 3.75% | 1.31% | 0.37% | 6.84% | 1.50% | -1.023% | -1.129% |

- The full event pool was also negative and ranking made it worse: mean `-0.317%` / `-0.147%` and median `-0.500%` / `-0.354%` in 2022H2 / 2023 versus selected means `-1.333%` / `-0.895%`. Selected-day complete cohorts were 54/119 and 130/241; their mean/median/Top3-excluded mean were `-1.718/-1.867/-2.168%` and `-0.895/-0.929/-1.192%`. Weekly-block 95% mean intervals were `[-2.419%, -0.965%]` and `[-1.494%, -0.320%]` with bootstrap `P(mean <= 0)` of `1.0000` and `0.9995`. Positive months were 0/6 and 2/12. Symbol concentration was low (top-one/top-five selected shares `1.97/5.92%` and `2.34/7.12%`), so concentration did not explain the loss.
- Decision: `REJECT_STOCHASTIC_CROSS`. It fails positive mean/median/win, coverage, downside-relative-to-pool, monthly robustness and complete-day gates in both periods. Do not tune 14/3/20, close-location, Top5, ranking or cooldown against these outcomes. 2024+ outcomes were not opened; no confirmation is authorized by the frozen rule. Production is unchanged.

## CORE-GAP-UP-ACCEPTANCE-20260913-01 — REJECT_GAP_UP_ACCEPTANCE

- Rationale: after the stochastic-reversal hypothesis failed, test a distinct continuation mechanism: a positive opening gap, signal-day volume expansion, a bullish candle, and a close near the session high. This is a fixed, heuristic rule; no threshold search or return-informed feature selection is authorized.
- Frozen spec: `reports/core_gap_up_continuation_spec.json`; SHA-256 `23f2b3a97d995fab44d5dfe283deccd6e52951a28c6ed68611657da86bb10c4f`. Shared `FAMILY_SPEC.json` remains unchanged at `4303a8033dfdffbd97eed21fca1b92b1b4012c3a0d4548be1eb78051d0e26e1f`.
- Candidate gates: prior-close-only gap >=1.5%; signal-day volume / prior 20-session average >=1.5; positive candle body; close location >=70%. Rank by the equal-weight mean of same-day percentile ranks for gap, volume ratio, and close location. Select up to five symbols/day; selected symbols cool down for the next official XTKS session. Empty days remain abstentions.
- Target: next official XTKS session open to fifth official XTKS session close including entry. Primary assumed round-trip cost 0.5%, with 0% / 1% sensitivity. This cost is not measured execution cost.
- Purge-safe discovery is limited to 2022H2 and 2023; latest signal dates are 2022-12-23 and 2023-12-22, respectively, so exits stay within each period. 2024 can be opened only for frozen confirmation if all discovery gates pass; 2025 is closed and 2026 remains report-only. Because earlier work has viewed these years, this is retrospective discovery, not untouched OOS.
- Required gates in both discovery periods: >=75 resolved selections, >=5 selections per calendar month, label coverage >=90%, positive net mean/median/win (>50%)/Top3-winner-excluded mean, -10%/-20% rates no worse than the full event pool on the same selected dates, at least half of resolved months positive, and >=20 complete selected-day cohorts with positive mean/median/Top3-excluded mean. No tuning or 2024 confirmation follows a failed gate.
- Data and implementation were pinned before label values were read. Feature panel SHA-256 `f66bf52ab73a4764c9b4c55857877970f536a6d96485d70282b00b6ee6a4bec4`; panel manifest SHA-256 `d40748bc303dbd801f876d08c1eee6c025d69da3129741170a34d87c370060e7`; source daily OHLCV SHA-256 `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`; official calendar SHA-256 `74ab2aaf72a0c055af31b461dd1b5776cf83eebc9576830954248aa03f518f68`.
- Universe limitation is explicit in the frozen spec: the historical panel is limited to symbols present in the preserved Yahoo source and point-in-time delisted-symbol completeness is not guaranteed. The discovery is not a full point-in-time TSE-universe claim.
- Before registration, all 39 batch02 tests passed, including four tests for the new event gates, deterministic rank score, multi-symbol Top5, and next-session cooldown. `audit.verify()` confirmed the frozen spec and all input/implementation hashes. No forward-return labels or 2024+ numeric OHLCV values were opened. Weekly use at registration was 47% (53% remaining).
- Outcome-free pool generation read 1,260,690 rows and retained 8,057 candidates across 2,734 symbols / 364 candidate-bearing days; Top5 selected 1,783 rows across 364 days with one abstention. Pool/rank/selection digests: `6dc62fa73be0e56a5a3af76993b232ff29b3003019a232e5391ce9b126b5ae2f` / `16ab99129fc45b48138ff8dc0bc4776eacad02419ecad53f4a1661afb6772d0f` / `bdd774d227bb5397e02007f626d4559d218df26de5177a80aaf16f57fee7d1b7`. Artifact SHA-256 values: `1bf860a7fb3b062d2877266fd6bf7125a441e6f3cf1a04a184263a7c9da4192c` / `cf17eddedb5782dcf811cfdaac693edc7c903ab2d55e6932659a95a4c677b6da` / `839afbd1705a4eb6596bd0b1e097f1e279f510eea0f32b20b7e96a7dcd36b8bb`; outcome-free receipt SHA-256 `38bf8b9a73f9f5960c0a3e0a0c492378ef49774c8c048155afb7265ef3918dc7`. No outcome labels or 2024+ numeric OHLCV were opened.
- Independent rebuild reproduced the pool, rank, and selection digests exactly. Reproduction report SHA-256 `6659a7cae3e4034400b90c6d80f954db14b682e885aaa2941636ddb03a85691d`; it confirms `outcome_values_opened=false` and `2024_plus_numeric_ohlcv_opened=false`. The outcome-free receipt is committed as `eabc747`; reproduction must be committed before label evaluation.
- Exact candidate/rank/selection reproduction passed in local commit `7728676`; the outcome-free receipt was committed in `eabc747`. Only purge-safe 2022H2 / 2023 labels were then evaluated. Canonical label digest `b0fcbb2a785590314de6dd115529ad0162cd01072b0ce507c9b053fd8b2031c7`; 77 candidate rows had no canonical source label and remained unresolved. Report SHA-256 `80404fd7e10dca552f7e1e52bbb58072a6908f36895b50e0aad37c1167e4f0e8`; Markdown SHA-256 `60c0fca3adf09169cecdda927b66727aae3852b8b5f3756aaa1b23f798df2916`.
- There were 1,783 frozen Top5 choices: 25 rows fell after the 2022H2 signal cutoff of 2022-12-23 and were retained only as purge rows. Evaluated selections were 583 / 1,175 in 2022H2 / 2023; resolved were 533 / 1,132. Label coverage passed, but the results failed decisively at every cost. At 0.5% assumed round-trip cost, signal metrics were:

| Period | Resolved / selected | Mean | Median | Win | +10 | +20 | +50 | -10 | -20 | Top1-excluded mean | Top3-excluded mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2022H2 | 533 / 583 | -2.733% | -2.514% | 36.77% | 8.07% | 3.19% | 0.75% | 21.20% | 9.01% | -2.986% | -3.289% |
| 2023 | 1,132 / 1,175 | -2.825% | -2.450% | 35.78% | 7.69% | 3.36% | 0.71% | 21.11% | 6.89% | -2.948% | -3.111% |

- The same-active-date full event pool was materially better: net mean `-1.359%` / `-1.270%`, -10 rates `9.85%` / `10.06%`, and -20 rates `2.84%` / `2.64%` for 2022H2 / 2023. The ranker increased losses and downside. Mean sensitivity at 0% / 1% cost was `-2.233% / -3.233%` in 2022H2 and `-2.325% / -3.325%` in 2023.
- Complete daily cohorts: 80 in 2022H2 (119 active days, 39 incomplete) and 203 in 2023. Net daily-cohort mean / median / Top3-excluded mean were `-2.871% / -2.547% / -3.748%` and `-3.016% / -2.870% / -3.328%`. Weekly-block 95% intervals were `[-4.822%, -1.000%]` and `[-3.975%, -2.132%]`, with bootstrap P(mean <= 0) `0.9995` / `1.0000` (2,000 repetitions). Positive months were 0/6 and 0/12. Symbol concentration was low: top-one/top-five shares `1.13%/3.94%` and `0.53%/2.12%`; failure was broad, not a single-name artifact.
- Decision: `REJECT_GAP_UP_ACCEPTANCE`. Both periods fail the positive return, win-rate, downside-relative-to-pool, positive-month, and complete-day gates. Do not alter the 1.5% gap, 1.5 volume ratio, 70% close position, ranking, cooldown, or Top5 after this result. 2024+ values remain unopened; production is unchanged.
- Next action: select a materially different technical mechanism from the remaining ledger, register it before labels, and continue only while weekly usage stays below 50%.

## DATA QUALITY — 5BDラベル欠損の扱いと再取得案 (2026-09-13)

- ユーザー指摘どおり、公式XTKSカレンダー上の評価5セッションに銘柄の日足が1日でも欠けると、そのシグナルの5BD評価は現状の入力から確定できない。batch01/evaluation.py::build_five_session_labels はシグナルごとに1行を残し、次営業日から5営業日目まで各バーを検査する。1日目欠損は MISSING_ENTRY_BAR、2〜4日目欠損は MISSING_HOLDING_SESSION_BAR、5日目欠損は MISSING_EXIT_BAR とし、リターンを計算せず未解決にする。日付を飛ばす、前値で補う、他銘柄や将来値で代用する処理はない。中間日欠損は端点価格だけの単純な比率なら計算できる場合もあるが、経路の価格・出来高・分割等を確認できないため、現在のactionability定義は保守的に未解決としている。
- 同ファイルは非数値/不正OHLCV、価格が範囲外、評価窓の出来高0も未解決扱いにする。既存の batch01/test_evaluation.py と batch01/test_core_moderate_ridge.py は entry/holding/exit の欠損を別ステータスにして、要求件数と未解決件数を保持するテストを含む。
- 保存済みソース監査では、Yahoo由来CSVの取引日集合はXTKSカレンダーの1,148日と一致する一方、日ごとの銘柄行数は646〜3,696、中央値3,555、ユニーク銘柄は3,700。これは市場全体の暦日欠落がないことを示すだけで、特定銘柄の日足欠落理由を示さない。監査マニフェスト自身も、現存銘柄中心の母集団、過去の上場/売買可能性、価格調整・コーポレートアクションの完全性が未証明と記録している。
- tvfree_screener/run.py::fetch_daily の確認では、Yahoo取得は例外またはバッチ全体が空のときにバッチ単位で最大3回試すが、非空バッチ内で特定tickerが無い/不完全な場合にそのtickerだけを照合・再取得する処理はない。これは研究プロトタイプの取得経路の所見であり、欠損が一時通信失敗だと断定する証拠ではない。データ行がない理由には取得欠落、上場前/上場廃止、売買停止、無約定等が残り、価格データ単体では区別できない。
- 改善案は二段階とする。第一に、公式取引日とpoint-in-time上場期間が得られるなら期待される銘柄×営業日を作り、内側の欠損だけを同一Yahooソースへticker単位・短い重複期間で限定再取得し、取得日時/ソース/原本ハッシュを残す。第二に、それでも欠ける行は、Codexを使わず通常のスケジュール処理から取得できる独立した公式またはライセンス済み日足ソースと照合する。価格調整・権利落ち・分割・銘柄コード変更を同じ基準に正規化でき、独立実行と再現性を確認できるまでバックテスト用の採用も本番実装もしない。
- 真の休場日以外の無約定/停止/上場状態不明は、執行できたと推定して埋めず未解決として残す。各実験は選出要求数・解決数・未解決数/理由・年/月/銘柄別偏りを併記し、解決済み部分集合だけの成績が欠損偏りに左右されないことを確認する。欠損を解決しないままのバックテスト数値は「解決ラベルの成績」であって全シグナル母集団の正確な成績とは呼ばない。
- 日足を1h/4hへ合成してproductionの欠損を埋める案は、ユーザーの既決指示どおり実装しない。上記の再取得/照合も、通常ジョブでCodexなしに動作し、認証・レート制限・データ利用条件を検証するまでは設計案に留める。

## CORE-CMF-FLOW-ACCELERATION-20260913-01 — FROZEN, OUTCOME-FREE POOL PREPARED

- 独立した仮説: 5日間の出来高加重終値位置が正で、20日状態より上向いている銘柄は、ギャップや単日の価格ブレイクに依存しない短期需要加速を示すか。
- 2026-09-13 07:11 UTC時点で条件を凍結。仕様SHA-256 a96bee2b91733d5978142da37d2fbc8c7d59e8d56f60cb8b32b6f95bfb08c32d。特徴量は cmf5, cmf20, cmf_delta=cmf5-cmf20。CMF5>0かつdelta>0、delta降順でTop5/日、選択銘柄は次の公式営業日だけ抑制、複数銘柄/日を許し候補なしは見送り。閾値探索なし。
- 評価は既存共通定義の次営業日始値から5営業日目終値。発見期間2022H2/2023、各期間75解決選出以上・90%ラベル解決率・正の平均/中央値/勝率50%超/Top3除外平均などの全ゲートを固定した。両期間を通過した場合のみ2024の方向確認を開く。2025は閉鎖、2026は報告のみ。2022H2/2023は他仮説で過去に見たため、未閲覧OOSではなく回顧的発見である。
- 共有family spec 4303a8033dfdffbd97eed21fca1b92b1b4012c3a0d4548be1eb78051d0e26e1f とdaily/calendar/label/code hashを登録済み。2024年以降のOHLCV数値も、新仮説の結果ラベルも未閲覧。CMF専用4テストと既存ラベル生成10テストを含む対象24テストを実行し全件PASS。次は凍結ファイルとledgerをcommitした後だけ、アウトカムを使わずfeature-only候補poolを作る。

- Feature-only preparation is complete. From 1,260,690 source rows, 1,224,060 passed daily OHLCV validation; 1,107,444 had complete consecutive 20-session flow windows; 446,974 rows met CMF5>0 and CMF5>CMF20 across 3,438 symbols and all 365 signal dates. Top5 plus one-session cooldown selected 1,825 rows on 365 days; no empty day. These counts do not use returns or labels.
- Frozen decision digests: pool fb882439ad18d8ac31787f8ce074f4312cef75ed6261aefd0178669b4fdf38c1; ranked cd28c9abe0da088734758783b09a85dca9b9625cf3c16da33ebe39d0af4bdbb5; selected c3c2240aa3346c5ccf1c20cdaa5b91457b0b6fcf478df8aeeb7b40a17395a2eb. Receipt SHA-256 0ed8ab75e94abf7f4ff7769336fa6746137a141bd6365bf189aff3aaa6034f72. The Parquet decision artifacts are local ignored audit files.
- No outcome labels or 2024+ numeric OHLCV were opened. Next: commit this receipt, independently recompute and compare all three decision digests, commit that reproduction receipt, then and only then open the preregistered 2022H2/2023 outcome labels.

- Independent reproduction completed after the preparation receipt commit. Pool/ranked/selected decision digests matched exactly; reproduction report SHA-256 bff85ed69c1ecb38a547859f6f5cfef076f9366e6a8dc07365ef70021e525210. It confirms outcome_values_opened=false and 2024_plus_numeric_ohlcv_opened=false. Commit this report before any outcome evaluation.

- The outcome-free preparation receipt was committed as 13fb02c and the exact reproduction report was committed as 729fe15. Both verify before the evaluator opens any label values. The frozen 2022H2/2023 discovery evaluation is now authorized by its staged gate; no 2024+ outcome values may be read unless both discovery periods pass every gate.

- Frozen discovery evaluation completed and rejected. At 0.5% assumed round-trip cost, 2022H2 had 587/595 resolved (98.7%), mean -0.934%, median -0.836%, win 32.8%, +10/+20/+50 1.5/0/0%, -10/-20 2.7/0%, Top1/Top3-excluded mean -0.966/-1.023%. 2023 had 1,181/1,205 resolved (98.0%), mean -0.286%, median -0.713%, win 33.8%, +10/+20/+50 2.0/0.85/0.34%, -10/-20 1.61/0.17%, Top1/Top3-excluded mean -0.413/-0.567%. Cost-free means were -0.434% and +0.214%, with negative medians in both periods.
- Unresolved selected-label status: 2022H2 = 5 ZERO_VOLUME_HOLDING_SESSION, 2 MISSING_CANONICAL_LABEL, 1 ENTRY_ZERO_OR_UNKNOWN_VOLUME; 2023 = 11, 11, 2 respectively. Total 32/1,800 unresolved. Missing canonical rows are not proof of missing market bars. They remain unresolved and were never imputed.
- Positive monthly mean share was 0/6 and 3/12. Complete-day cohort means were -0.920% and -0.269%; their weekly block-bootstrap 95% intervals were [-1.407%, -0.470%] and [-0.803%, +0.403%]. Top-five symbol shares were 5.11% and 4.06%; no symbol concentration explains the failure.
- Decision REJECT_CMF_FLOW_ACCELERATION: the frozen mean/median/win/Top3-exclusion gate failed in both periods, as did monthly majority and complete-day cohort gates. No 2024 confirmation or threshold adjustment was performed. Full JSON report SHA-256 c55b15bee70b08cb787e2cfa79d379d326126c3b4099d99878795c9b45f77805.

## DATA-QUALITY-5BD-MISSING-20260913-01 — SOURCE OPTION AUDIT

- User clarified that no paid contract may be considered; any remedy must be free and run in the normal Bot environment without Codex. Official-source review found no source verified to satisfy all these constraints and the Bot's current member-facing use.
- LINE Yahoo's official help prohibits programmatic collection of Yahoo Finance prices and reuse/redistribution/commercial use. Do not implement targeted Yahoo retries as an automated repair path.
- JPX's announced J-Quants Free tier is ¥0, daily OHLC, two years and 12-week delayed, but JPX classifies J-Quants API as individual use and disallows corporate use/redistribution. The Bot's member-facing use is not established as eligible private use, so do not wire this source into the Bot.
- JPX Daily Report contains issue-level OHLC and volume and a rolling 12-month archive. The separate historical stock price page says manual acquisition is the basis, automated acquisition is discouraged, and reprinting is prohibited; JPX site terms also restrict commercial collection/secondary use without permission or paid terms. Do not automate it for this Bot. Paid J-Quants Pro/DataCube are excluded by user instruction.
- Decision: no source-side repair implementation. Keep true price gaps unresolved, never infer a trade from a missing/zero-volume session, and report resolved-subset metrics. Rebuild `MISSING_CANONICAL_LABEL` only from already-local cached inputs where reproducible, because label-join gaps are not proof of missing prices. Keep endpoint-only calculations for interior gaps as a separate diagnostic, never mix them into the current complete-path/actionability metric.
- The 5BD target enters at the next official session open and exits at the fifth session close. Missing either endpoint prevents calculation; a missing interior bar may leave the endpoint ratio arithmetically calculable, but the current full-session actionability label remains unresolved.
- No API key, external market data, production file, or workflow was touched. The report at `tvfree_screener/batch02/reports/missing_5bd_data_remediation.md` contains official citations and the bounded local-only follow-up audit.

## DATA-QUALITY-CMF-LOCAL-LABEL-COVERAGE-20260913-01 — LOCAL REBUILD, 13 LABEL-JOIN GAPS RECOVERED

- Frozen CMF selections/spec were unchanged. Used only the existing label-free Yahoo-derived local daily panel through 2023-12-29; no network, 2024+ values, or production files were read or changed.
- All 13 `MISSING_CANONICAL_LABEL` joins (2 in 2022H2, 11 in 2023) rebuilt as `RESOLVED`. The other 1,768 rows that already had canonical labels matched the rebuild for status, entry/exit dates, entry/exit prices, and gross return.
- At 0.5% assumed round-trip cost, 2022H2 changed from 587/595 resolved, mean -0.934%, median -0.836%, win 32.8% to 589/595, mean -0.954%, median -0.856%, win 32.7%. 2023 changed from 1,181/1,205, mean -0.286%, median -0.713%, win 33.8% to 1,192/1,205, mean -0.250%, median -0.706%, win 34.1%.
- Overall unresolved fell from 32/1,800 to 19/1,800: 16 zero-volume holding sessions and 3 entry sessions with zero/unknown volume. Do not fabricate those bars. The change diagnoses label-cache coverage and does not alter the original `REJECT_CMF_FLOW_ACCELERATION` decision.
- The user now prefers Yahoo daily bars as a best-effort supplement and wants hourly-vs-daily quality checks. Use the already-local Yahoo-derived panel for research label repair. Yahoo's official help prohibits automated retrieval/commercial reuse; no new scraper or live API call was implemented. A Codex-free comparator is specified in `reports/missing_5bd_data_remediation.md`, but the worktree has no local 1h/4h panel to measure real discrepancies yet.
- Reproducible local audit: `audit_cmf_local_label_coverage.py`; JSON/Markdown outputs are in `reports/cmf_local_label_coverage_recovery.*`. All source/spec/selection hashes are in the JSON receipt.

## CORE-MONSTER-WEAK-EARLY-V20 — FINAL DISPOSITION (2026-09-13)

- Rechecked the frozen report `tvfree_screener/batch01/reports/monster_canonical_audit.json` read-only. The `ret10 <= 0.5735294117647058` threshold provenance matches the reconstructed 2023 V18 consensus median to 1e-12; this verifies lineage, not predictive value.
- The 2023 retrospective candidate pool contains 69 rows, 68 resolved. At the assumed 0.5% round-trip cost, mean was +2.20%, median -2.30%, win rate 39.7%, and Top3-excluded mean -2.08%.
- The registered Top1, Top2, Top3, and Top5 policy rows each have `status=FAIL`. The JSON's `SELECTION_COUNT_UNRESOLVED` means no selection count passed the frozen gate; it is not a missing-label or missing-price condition. Final family disposition: `REJECT_NO_TOPN_POLICY_PASSED`. Do not tune or re-sweep ret10, volr20, candidate gates, ranking, or cooldown on these exposed years.
- 2025/2026 remain unopened in this audit. The existing 2024 summary is retrospective evidence and does not rescue a failed 2023 selection gate. The candidate remains a historical Monster hypothesis, not a frozen production-ready scorer.
- This is a decision clarification from already-frozen artifacts; it does not alter candidate membership, labels, thresholds, or reported metrics.

## TARGET-DAILY-ENDPOINT-PATH-SEPARATION-20260913-01 — REGISTERED

- User approved one common daily endpoint for morning/afternoon signals: next XTKS session open to the fifth XTKS session close, with entry day counted as session one. The formula already exists in the strict batch01 labeler; this experiment adds a separately named endpoint-only result and keeps path/actionability completeness separate.
- Frozen spec: tvfree_screener/batch02/DAILY_ENDPOINT_TARGET_SPEC.json; SHA-256 1250b7fae5eab0137de5bc4d0a7057c4e0683a1e37446bf25b33c08d0bca9f51.
- Candidate membership/selection is frozen. Unit tests use synthetic daily bars. Any retrospective audit is limited to previously opened 2022H2-2023 CMF discovery artifacts; 2024-2026 stay closed. No daily-to-intraday synthesis or external data retrieval.
- Stop latch explicitly cleared by the user's resume instruction. New pause threshold: 45% weekly remaining (55% used); latest observed: 50% used / 50% remaining.
- Status: registered before endpoint-only result access; implementation and tests pending.

## DATA-QUALITY-INTRADAY-DAILY-COVERAGE-20260913-01 — COMPLETE / COVERAGE ONLY

- User requested a complete missing four-hour symbol/session inventory and same-key daily OHLCV check. A connected `ohlcv_4h` sheet was audited read-only against the local daily panel and frozen XTKS calendar; the sheet was not edited.
- Frozen spec: INTRADAY_DAILY_COVERAGE_AUDIT_SPEC.json. The audit script accepts local CSV exports, hashes each input, separates fully missing, one-slot missing, duplicate/unexpected, invalid 4-hour, and daily availability/validity statuses.
- Expected pairs use the daily file's symbol/session rows plus observed four-hour-only keys; pairs absent from both sources need a point-in-time security universe and cannot be inferred from these two files.
- Real-data coverage result (2025-12-23 to 2026-09-11): 645,187 daily symbol/session pairs; 205,630 complete 09:00/13:00 pairs and 439,557 missing/partial/duplicate/invalid pairs (434,693 no bars, 1,555 missing afternoon, 375 missing morning, 2,723 invalid OHLCV, 211 duplicate/unexpected). Same-day numerically valid daily OHLCV exists for 439,207/439,557 (99.920%), including 3,710 zero-volume rows; 350 daily rows are invalid/unavailable. Another 4,788 observed 4H keys across 1,064 symbols have no same-day daily key.
- `NO_4H_BARS` means absent from the stored 4H sheet, not proven provider failure; a point-in-time tracked universe is unavailable. This measured availability/basic validity only, not value accuracy, adjustment parity, target returns, or model performance. No 4H synthesis, 2025/2026 outcome review, or source write occurred.
- Full rows are ignored local artifacts only in `tvfree_screener/batch02/.cache/audits/4h_daily_coverage_20260913/`; report: `tvfree_screener/batch02/reports/intraday_daily_coverage_audit_20260913.md`.

## USER METHODOLOGY CLARIFICATION — FOUR-HOUR FEATURES REQUIRED

- The user clarified that the TV-Free score features/ranking must remain four-hour based because daily feature performance had already been judged inadequate. The daily-only batch02 experiments are retrospective rejected research and do not satisfy or qualify as four-hour candidates.
- Daily OHLCV in the newly registered endpoint work is for the common next-session-open/fifth-session-close evaluation target and same-day data-availability audit only. Any future feature fallback must be independently frozen and visibly source-tagged; no silent timeframe mixing.
- DAILY_ENDPOINT_TARGET_SPEC.json was superseded by DAILY_ENDPOINT_TARGET_SPEC_V2.json before endpoint-only result access. V2 SHA-256: cecb2d2647a3b042cb061d9019f2f239e8b1680b1f5cf7bd8d8d720a76624d86.
- Repository evidence: the preserved source artifact manifest contains a 4,061,361-row daily CSV but no raw four-hour export; the current batch02 feature panel and recent candidate experiments are daily-based. A full four-hour scoring audit cannot be claimed from those artifacts.

## DATA-QUALITY-4H-FEASIBILITY-20260913-01 — SOURCE REVIEW COMPLETE / RAW INPUTS MISSING

- User authorized changing timeframe/bar boundaries and suggested testing daily OHLCV as a validator or supplement for unreliable Yahoo hourly data. The feature representation is not frozen; compare TSE session bars, raw-rebuilt TradingView-compatible bins, intraday-plus-daily reconciliation, and a separate daily-feature family.
- Official JPX hours are 09:00-11:30 and 12:30-15:30; the afternoon close changed from 15:00 to 15:30 on 2024-11-05, with a 15:25-15:30 closing auction. Session bars are market-aligned but not equal-duration four-hour bars.
- Read-only source inspection found an existing ordinary-GAS route from Yahoo 1h to AM/PM values and documented 365-day legacy retention. It does not prove all-TSE multi-year coverage or data-source permission. The research worktree has a 4,061,361-row daily CSV but no raw hourly or legacy 4H export.
- A same-provider daily-vs-hourly comparison measures internal consistency, not which feed is true. Daily full-session OHLCV can validate an intraday aggregate; it cannot recover per-session extremes/volume or be used before close. Same-day daily values before close would leak future data.
- Free-source review: J-Quants Free is daily; JPX minute/tick is a paid add-on. Twelve Data documents 4h but Basic describes global trial symbols and 8 credits/min, 800/day; full TSE/delisted/multi-year free coverage is unestablished. Alpha Vantage marks intraday Premium. Yahoo terms prohibit automated data collection without express prior permission.
- Decision 4H_INFEASIBLE is scoped to all-TSE multi-year research under the no-contract constraints among official sources reviewed, not a universal claim. Daily-plus-recent-intraday hybrid remains UNPROVEN; neither daily-only nor legacy 4H is selected as final.
- V2 gap-audit and endpoint specs were superseded before real inputs/results by INTRADAY_DAILY_COVERAGE_AUDIT_SPEC_V2.json and DAILY_ENDPOINT_TARGET_SPEC_V3.json. HOURLY_DAILY_CONSISTENCY_AUDIT_SPEC.json registers per-field daily-vs-hourly source reconciliation.
- If intraday is used, rebuild from raw input into separate ignored research artifacts. Never mutate or score from legacy ohlcv_4h. Read-only legacy gap audit uses a local exported copy. No production file, Sheet, workflow, account, API key, or external market-data service was touched.
- Focused synthetic tests passed: 2 gap-audit tests, 5 endpoint/path-separation tests, and 6 hourly/daily consistency tests (13 total). The hourly/daily runner requires explicit bar interval and start/end timestamp semantics; lunch/close-crossing bars are included whole and flagged, never split. Missing symbol/session availability is now measured from the connected read-only 4H sheet; value-level Yahoo hourly-vs-daily accuracy still requires raw 1-hour bars.
- Reports/specs: reports/4h_data_feasibility_audit_20260913.md, 4H_DATA_FEASIBILITY_AUDIT_SPEC.json, HOURLY_DAILY_CONSISTENCY_AUDIT_SPEC.json, INTRADAY_BAR_DEFINITION_STUDY_SPEC.json, INTRADAY_DAILY_COVERAGE_AUDIT_SPEC_V2.json, DAILY_ENDPOINT_TARGET_SPEC_V3.json.

## USER-SUPPLIED TV-FREE PRIOR-RESEARCH HANDOFF — ACCEPTED AS HISTORY, NOT CANONICAL SCORES

- The independent end goal is a TradingView-free TSE screener that can compete with current Stable/Sniper/Mega performance; exact signal overlap is irrelevant. Keep Core and Monster as separate roles. Existing products/data/workflows remain unchanged.
- Old V29 headline metrics are not canonical. Its limited-universe result does not survive the later full-universe V40 audit (negative), so reject V29 as a current Core candidate while retaining consensus/three-head ranking as an architecture clue. Do not claim Stable dependence without tracing actual feature/label/filter/ranking use of `stable_score`.
- The pasted handoff calls Monster `weak market + early ret10 + low volr20` the leading historical hypothesis. A newer local canonical audit supersedes that status: in 2023 the frozen pool had 69 requested / 68 resolved rows over 51 dates and 41 symbols; gross mean was +2.70%, median -1.80%, win 40.9%, +20% 17.65%, -10% 33.82%, Top1-excluded +1.15%, Top3-excluded -1.58%. At 0.5% cost the leaderboard reports mean +2.20%, median -2.30%, and Top3-excluded -2.08%. All registered Top1/2/3/5 policies failed, the selected N remains unresolved, 2024 is pool-diagnostic-only, and 2025/2026 were not opened. Keep this pool exploratory; do not describe Monster as a passing candidate.
- The `ret10 <= 0.5735294117647058` provenance is already verified in `batch01/reports/monster_canonical_audit.json`: reconstructing the 2023 V18 consensus median from the source functions exactly matches V20 within 1e-12. This confirms provenance only; it does not create a pre-2023 sample. Prior one-pick/day numbers do not settle a multi-candidate pool.
- The V29 audit does trace actual model input use: `fit_attach` passes the derived `stable_score` (sum of six technical Boolean conditions) into V29 fitting. This does not prove identity with the production TradingView Stable★ label. V29 remains rejected as a full-universe candidate because the cap-removal countercheck collapses, and its signal-close-to-fifth-close target differs from the current next-session-open endpoint. The preserved run records 22 Yahoo 1-hour HTTP errors and one hourly parse failure among 350 requested symbols (327 succeeded), reinforcing the need for the hourly-vs-daily data-quality audit.
- Preserve every candidate-pool row and evaluate Top1/2/3/5 with independent chronological cooldown simulations plus candidate-pool equal-weight daily cohorts; these are not portfolio returns. Build a portfolio simulation only after a candidate survives these screens.
- Core is incomplete. The pasted handoff labels clipped-upside expected-return regression, point-in-time sector-lag, and orderly pullback as untested, but newer local reports supersede that: Ridge already regressed `min(gross return5, 0.30)` and every registered Top1/2/3/5 policy failed; sector-lag was inconclusive because historical industry membership is unavailable; orderly pullback has already been tested and its measurable signal checks failed (the broad-pool cohort gate was inconclusive because there were no complete cohorts). Do not repeat or rename these families. Keep First Reversal research-only unless it generalizes without 2025/2026 tuning.
- Connected read-only legacy 4H coverage is now measured for 2025-12-23 through 2026-09-11; 99.920% of noncomplete 4H symbol/session pairs have a numerically valid same-day daily bar. Raw Yahoo 1-hour bars are not preserved for a value-level comparison; V29 logs 22 Yahoo 1-hour HTTP errors and one parse failure among 350 requests (327 succeeded). Hourly-vs-daily price accuracy and adjustment parity remain INCONCLUSIVE. No daily-to-intraday synthesis or paid data-source fallback is acceptable.
- Historical 2025 is seen and is not blind OOS; 2026 is reporting-only. Only post-freeze forward data can establish true forward performance. Any old candidate score must be re-evaluated if universe, cooldown, selection count, calendar, entry/exit, or label definition changes.

## DATA-QUALITY-4H-PROVENANCE-20260913-01 — COMPLETE / VALUE ACCURACY INCONCLUSIVE

- Read-only review of weekly_report_gas/gas.txt found the legacy Yahoo 1h session mapping: interval-start 09/10/11/12 timestamps go into AM; 13/14/15/15:30/16:00 go into PM. A 12:00 hour crosses the TSE lunch boundary and is not splittable into true morning/afternoon values. A flat zero-volume 15:30/16:00 close snapshot can update PM close only.
- The GAS 1d fallback copies daily OHLC into both AM and PM rows and splits daily volume 50/50. This is a missing-row placeholder, not intraday recovery.
- Read-only marker count for the 429,033-row legacy sheet: 8,610 rows carry GAP_REPAIR. Source inspection shows that marker is shared by Yahoo 1h gap-refetch results and daily-derived fallback rows. new_session and MIDDAY_<date> are batch/update markers. Source accuracy cannot be stratified from the legacy sheet; no raw 1h export exists in the research worktree.
- Decision: INCONCLUSIVE_SOURCE_PROVENANCE_MIXED. No price accuracy comparison, signal scoring, synthetic bars, 2025/2026 return review, production edit, or source-sheet write was performed. Daily endpoint measurement stays separate from feature inputs.

Source receipt for DATA-QUALITY-4H-PROVENANCE-20260913-01: read-only weekly_report_gas HEAD f2fb9df22565e29890a91c16c5063acb2f5d4cb1; gas.txt SHA-256 0ab6326c0eeca1090fc9cbbc116794481982db0e5fdf45afccd6a138a1ee9b46; connected legacy 4H projection SHA-256 32c5e53f77487d17545abdbe80205289a53af532f37ae8f517c29c5f8b86402a; daily panel SHA-256 6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0.

Source receipt for DATA-QUALITY-4H-PROVENANCE-20260913-01: read-only weekly_report_gas HEAD f2fb9df22565e29890a91c16c5063acb2f5d4cb1; gas.txt SHA-256 0ab6326c0eeca1090fc9cbbc116794481982db0e5fdf45afccd6a138a1ee9b46; connected legacy 4H projection SHA-256 32c5e53f77487d17545abdbe80205289a53af532f37ae8f517c29c5f8b86402a; daily panel SHA-256 6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0.

## DATA-QUALITY-HOURLY-DAILY-SAMPLE-20260913-01 — COMPLETE / DIAGNOSTIC ONLY

- Existing research artifact run 34586861016 (head 1588cd1ff5911da3401a48cb8de1f4017c35dd27; created 2026-09-11; expires 2026-09-18) supplied 8,709 raw Yahoo 1h rows for 8 preselected Monster examples. Only cloud_1h_monsters.csv was read; cloud_1h_monster_precursors.csv was not opened. No action was dispatched or new Yahoo request made.
- Matched against cached daily rows from 2026-01-05 through 2026-09-11 using 60-minute interval-start aggregation and the frozen XTKS calendar. 1,324/1,360 symbol-session pairs were comparable; 36 were unassessable. Only 1,087/1,324 hourly sessions contained all seven expected hourly start slots. Eight 15:30 close snapshots were excluded from session aggregates by the generic runner; close-snapshot override was not applied.
- Within 1% of daily values: open 830/1,324; high 1,142/1,324; low 1,203/1,324; close 1,076/1,324. Median absolute percentage differences were open 0.41%, high 0%, low 0%, close 0.34%. These are internal consistency figures only; the daily panel is not ground truth.
- Volume: 2 exact matches, 76/1,324 within 5%, median absolute percentage difference 37.7%. Raw hourly coverage and volume semantics remain unresolved.
- Forty-seven 6085 sessions (2026-01-05 through 2026-03-31) show an approximately 10x close scale mismatch; 38 show a common 10x OHLC scale. The company disclosure says 1:10 split effective 2026-04-24, but available data do not establish that this fully explains the earlier adjustment mismatch. Do not post-hoc normalize or exclude.
- Decision: INCONCLUSIVE_ADJUSTMENT_AND_VOLUME_SEMANTICS. The sample is small and preselected; do not tune or promote a model. Daily values remain suitable for the approved endpoint measurement only after the entry/exit definition is applied, not as intraday-session reconstruction. 2026 strategy outcomes were not opened.
- Inputs: raw hourly SHA-256 cb33bb893291a31d57973d981a5db8f010ca34f2db80804a92e7be5ad5e7776b (8,709 rows); filtered daily SHA-256 e8a7225469217a1c496b8f83a0bc66325541bde48025956f01bdb30158780d67 (1,353 rows); cached daily source SHA-256 6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0; XTKS calendar SHA-256 74ab2aaf72a0c055af31b461dd1b5776cf83eebc9576830954248aa03f518f68. Reported rows are ignored local `.cache/` artifacts only.

## DATA-QUALITY-DAILY-ANCHOR-OPTIONS-20260913-01 — PARTIAL DIAGNOSTIC / REPAIR VARIANTS NOT RUN

- User clarification: the practical objective is an approximate daily-led correction/fallback for unreliable Yahoo 1h data; hourly is not the presumed truth and exact AM/PM reconstruction is not required.
- Hypothesis: daily OHLCV can help correct a common price scale mismatch, anchor the first/last hourly prices and full-day extrema, and reconcile total volume while retaining observed intraday shape when coverage and units are adequate. Incomplete days can fall back to a tagged single daily-resolution row.
- Planned variants: common OHLC scale correction; daily open/close anchoring; daily high/low anchoring to observed extrema only with complete expected slots; proportional volume reconciliation only with complete coverage and compatible share units; whole-day daily-resolution fallback.
- Guardrails: keep raw rows immutable; store corrected variants separately with method/factor/source tags; never split daily OHLCV into fake AM/PM rows or place a daily extreme in an unobserved hour; never use completed daily data before its close for an earlier signal; do not inspect strategy returns or alter 2026 rules.
- Evaluation scope: data quality and resolvable coverage only, on the already-cached, selected eight-symbol sample. It is small and selection-biased; it cannot establish broad source accuracy, strategy improvement, or Codex-independent runtime feasibility.
- Additional diagnostic on 1,087 complete symbol-sessions: OHLC daily/hourly ratios were within a 1% normalized common-factor spread on 478 (44.0%) and within 2% on 770 (70.8%). A median-of-four-OHLC ratio factor put all four daily/hourly aggregate fields within 1% on 574 (52.8%) and within 2% on 891 (82.0%). A close-only factor put open/high/low within 1% on 522 (48.0%; close exact by construction). Daily-volume/hourly-sum ratio median was 1.606 (p10 1.131, p90 2.541); 846 ratios were between 0.5 and 2. These selected same-provider data do not identify which feed is correct and do not validate intraday path accuracy.
- Sample availability: 1,352/1,360 daily rows were numerically valid; 1,087 hourly sessions had all seven expected starts. A daily-resolution fallback appears to improve full-day availability, but does not restore intraday timing.
- Status: coarse diagnostic complete; no correction variant actually applied. No 2026 returns or strategy outcomes were opened. Prior hourly/daily metrics remain diagnostics, not a decision against daily-led correction.


## DATA-QUALITY-DAILY-ANCHOR-OPTIONS-20260913-02 — KEEP REPAIR / CORRECT CAUSAL USE

- Scope: existing cached Yahoo-derived 1h sample only; 8 symbols, 1,325 observed symbol-sessions, 1,087 complete seven-slot sessions. No new Yahoo request and no strategy-return file opened.
- Raw complete-session quality: all OHLC within 1% of same-provider daily aggregate on 494/1,087 (45.446%); within 2% on 814/1,087 (74.885%). Median volume APE was 37.723%; only 65/1,087 (5.98%) were within 5%.
- Common OHLC scale repair improved all-OHLC-within-1% to 574/1,087 (52.806%) and within-2% to 838/1,087 (77.093%). Applied to 769 sessions; factor median 1.0, p10 0.995415, p90 1.005339, min 0.0986842, max 1.049973.
- Daily open/close anchoring improved all-OHLC-within-1% to 985/1,087 (90.616%); adding extrema anchoring improved it to 1,074/1,087 (98.804%). This is post-close reconstruction consistency, not proof of the true intraday path.
- Eligible proportional volume reconciliation improved median volume APE to 0 and volume-within-5% to 846/1,087 (77.829%). Median volume factor 1.605659; p10 1.131488; p90 2.530032.
- 596/1,087 complete sessions met the current fully-corrected diagnostic; 455 were partial-review. Do not infer mutually-exclusive fallback-tier counts until the materializer freezes exact status precedence.
- 6085 remains a stress/pathology case: raw all4<=1% 25.35%, scale 41.55%, fully-corrected 24.65%. Do not derive universal correction rules from this symbol.
- **Important correction to the previous handoff:** any repair that uses the current day's finalized daily high/low/close/volume is not causally eligible for an earlier pre-close 4H feature. Reconstruction quality and signal-time causal eligibility are now separate dimensions.
- Frozen policy: `INTRADAY_CAUSAL_QUALITY_TIER_SPEC.json`. Current-day final daily anchors are tagged `POSTCLOSE_RECON_ONLY` for earlier cutoffs. Only observations available by cutoff can carry `RAW_CAUSAL_INTRADAY`.
- Daily fallback remains one daily-resolution record only. Never synthesize two AM/PM or 4H bars from one daily candle.
- Decision: keep the repair ladder for archival/data-quality reconstruction; do not use its post-close consistency gain as evidence that pre-close scoring inputs are valid.
- Report: `reports/daily_anchor_repair_audit_20260913.md`.
- Next: implement deterministic materializer/source tags, then build cutoff-aware 4H/session features and measure coverage before any strategy-outcome test.


## CAUSAL-INTRADAY-FEATURE-AUDIT-20260913-03 — PIVOT TO RAW SCALE-INVARIANT 4H FEATURES

- No strategy outcomes opened. This is data-quality/causal-availability work only.
- Causal price calibration test on the 1,087 complete sessions: raw all4<=1% 45.45%; previous-session scale 44.21%; trailing-5 prior scale median 46.10%. At 2%: raw 74.89%; previous-session 73.40%; trailing-5 76.48%. Prior-only rescaling is not a meaningful v1 improvement.
- Scale factor day-to-day is usually stable (median absolute change 0.20%, p90 1.17%, p99 2.77%) but rare breaks remain. Prefer scale-invariant features rather than mandatory absolute-price repair.
- Causal volume calibration remains noisy: previous-session factor median APE 21.93%; trailing-5 prior median APE 19.53%; trailing-5 within-5% only 13.92%, p90 APE 50.72%. Do not treat this as exact absolute-volume repair.
- Raw row-type correction: 1,332 unique symbol/date keys exist across all row types, but 8 are 2026-09-11 closing-snapshot-only keys. The clock-bin denominator is therefore 1,324 normal intraday symbol-sessions. AM 09/10/11/12 complete 1,150 (86.86%); PM 13/14/15 complete 1,155 (87.24%); both complete 1,087 (82.10%). Gate AM/PM independently and never promote snapshot-only keys into fake 4H bars.
- Raw-vs-postclose-reconstructed normalized feature stability on 2,102 bin pairs: body_pct Spearman 0.901, range_pct 0.984, close_location 0.826. AM close_location was 0.981 but PM only 0.694. Uniform whole-day volume scaling leaves within-day share unchanged, but current-day full-day share is not causal for the AM cutoff.
- Architecture freeze: `CAUSAL_INTRADAY_FEATURE_ARCHITECTURE_SPEC.json`. Prefer returns, normalized range/ATR, normalized momentum/position, compression/realized-volatility and prior-bin-relative-volume features. Hold PM close-location and same-day-daily-rescaled absolute volume back.
- Implemented `intraday_causal_guard.py` and `raw_intraday_clock_bins.py` with tests. Isolated pre-commit checks passed 7/7 causal-guard cases and 5/5 clock-bin cases.
- PM 15:00 interval-start bar is conservatively assigned a 16:00 feature cutoff until provider availability latency is verified; do not assume 15:30 availability.
- 12:00 interval crosses the lunch break but is kept only as part of the named 09:00-13:00 raw-source clock bin; exact TradingView equivalence is explicitly not claimed.
- Next: implement causal scale-invariant feature extraction from these bins, using prior completed comparable bins for rolling features, then measure usable coverage before any outcome evaluation.


### CAUSAL-INTRADAY-FEATURE-IMPLEMENTATION-20260913-04

- Implemented `causal_intraday_features.py` on top of the raw clock-bin builder.
- Initial model-safe feature set is intentionally scale-invariant: body_pct, range_pct, body_to_range, upper/lower wick pct, plus rolling prior-shape/range baselines. These do not require current-day finalized daily anchors.
- PM close_location is calculated for diagnostics but explicitly marked model-ineligible because its raw-vs-postclose stability was materially weaker than AM.
- `volume_rel20` uses only prior 20 completed comparable bins, but remains tagged `EXPERIMENTAL_SOURCE_INTERNAL` until raw volume semantics are better understood.
- Same-bin 20-history features have coverage on 1,985/2,305 complete raw bins (86.12%) in the current 8-symbol sample. Prior-4 shape features cover 2,273/2,305 (98.61%).
- Cross-day absolute price-return/RSI features are deliberately deferred for now: the raw series contains several very large adjacent gaps, including the known 6085 adjustment/split pathology, and simple magnitude clipping would also remove genuine Monster-style gap moves.
- Isolated pre-commit feature checks passed 4/4 cases.
- Next research: run the feature extractor on the cached sample, inspect per-feature distributions/outliers and missingness without returns, then freeze the first causal 4H candidate-feature panel before any performance replay.


## CAUSAL-INTRADAY-FEATURE-PANEL-V1-20260913 — FROZEN BEFORE OUTCOMES

- Only `cloud_1h_monsters.csv` from Actions artifact run 34586861016 was read. The colocated precursor/outcome file was not opened.
- Count definition fixed: 1,332 all-row symbol/date keys = 1,324 normal-intraday keys + 8 closing-snapshot-only keys on 2026-09-11. The feature builder uses 1,324 as its denominator.
- Independent complete raw bins: AM 1,150; PM 1,155; total 2,305. Missing-required-hour attempts: 343.
- Frozen v1 candidate features: `bar_log_return`, `range_pct`, `upper_wick_pct`, `lower_wick_pct`, `prev4_log_return_mean`, `prev4_range_mean`, `log_range_vs_prior20`.
- All are scale-invariant or within-bin normalized and use no current-day finalized daily anchor. `bar_log_return` replaces raw body_pct for symmetry; `log_range_vs_prior20` log-compresses the heavy positive tail without clipping genuine expansions.
- Redundancy-only exclusions made without outcomes: body_pct vs body_to_range Spearman 0.928; prev4_abs_body_mean vs prev4_range_mean 0.872. The redundant alternatives are not in v1.
- `close_location` remains diagnostic-only because PM source stability was weak. `volume_rel20` remains diagnostic-only because volume semantics are unresolved and its sample max reached 335.45.
- No clipping and no imputation. Requiring 20 prior same-bin observations yields 1,985/2,305 v1-complete rows (86.12%); all 320 missing rows are the exact warmup cost across 8 symbols × 2 bins × 20 observations.
- Local materialized v1 panel SHA-256: `6fcc178be5d23d39126c053cc998a4cbca6ffedf07dc650c1c7875d22490b440`.
- Spec: `CAUSAL_INTRADAY_FEATURE_PANEL_V1_SPEC.json`. Report: `reports/causal_intraday_feature_panel_v1_20260913.md`. Reproducible runner: `audit_causal_intraday_feature_panel.py`.
- Important limitation: this eight-symbol Monster sample is selection-biased and is not an acceptable strategy-performance population. Next step is broader historical/universe raw-intraday source discovery before any outcome replay.


## BROAD-CAUSAL-INTRADAY-V1-20260913 — DATA QUALITY PASS / SESSION-CLOSE CORRECTION

- Recovered an existing raw 1h Actions dataset from run 34592896202; no new market-data request. Eight shards contain 4,019,524 rows, 1,315 usable symbols of a 1,332-symbol historical 4H comparison set, 2024-09-17 through 2026-09-10.
- The historical 1,332-symbol list is a broad same-universe comparison set, not proven full-TSE history; its derivation recipe is not preserved. Do not overclaim historical all-TSE coverage.
- Found and corrected a methodological bug in the old session reconstruction. Before the TSE close extension on 2024-11-05, 15:00-start rows are overwhelmingly close snapshots (93.43% flat + zero volume). After the extension, 83.92% are nonflat + nonzero. PM construction is now 13/14 pre-change and 13/14/15 post-change, with separate PM rolling regimes.
- Broad raw audit: 618,775 symbol-days; 1,237,550 attempted bins; 1,017,531 complete bins; 941,118 v1-complete rows. Frozen v1 coverage is 92.49% of complete bins and 76.05% of all attempts.
- V1 completeness among complete bins: 2024 50.08% (warmup + regime reset), 2025 99.24%, 2026 99.80%.
- Frozen v1 features remain unchanged: bar_log_return, range_pct, upper_wick_pct, lower_wick_pct, prev4_log_return_mean, prev4_range_mean, log_range_vs_prior20. No automatic clipping of extreme bars.
- Integrity note: while tracing the universe source, old research/tentei_cloud/RESEARCH_STATE.md exposed previously seen 2026 strategy summaries. This is recorded as source-discovery contamination. The v1 feature set was already frozen before that exposure; those summaries are forbidden from selecting features, thresholds, model architecture, cooldowns, or correction rules. 2026 remains report-only.
- Broad raw audit itself did not join outcome columns.
- Decision: data-quality pass. Move to a preregistered canonical feature-to-label scoring experiment using the batch02 next-session-open -> fifth-session-close endpoint, not the older candidate-close endpoint.
- Report: reports/broad_causal_intraday_v1_audit_20260913.md
- Receipt/spec: BROAD_CAUSAL_INTRADAY_V1_SPEC.json


## CAUSAL-4H-SCORING-V3-NONLINEAR-RISK-20260913 — REJECT / NO_PROMOTION

- Preregistered before V3 row-level H2 access. H2 aggregate V2 results were already known, so H2 is retrospective refutation only and cannot promote V3.
- Architecture: separate AM/PM HistGradientBoosting gain/loss heads, fixed shallow-tree parameters, and equal-weight risk score logit(p_gain)-logit(p_loss10). Same seven causal 4H features, candidate gates, Top1/2/3/5 and cooldown as V2.
- H1 fold1: every gate failed. Core Top1 mean -0.48%; Monster Top1 mean -0.51%, +20% rate 0%.
- H1 fold2: Core Top2 mean +0.32% but median -0.37%/win 41.5%; Monster Top1 mean +0.69% but +20% only 3.66%. Every gate failed.
- H2 retrospective: Core Top1 mean +0.21%, median -0.35%, win 45.6%, <=-10% 0%; all Core TopN failed. Monster Top1 mean -0.40%, +20% 2.42%, <=-10% 5.65%; Top2/3/5 +20% only 3.23/3.36/2.98%; all failed.
- Interpretation: V3 strongly reduced downside but suppressed the right tail too much. Reject the architecture; do not tune risk weight against H2.
- Report: `reports/causal_4h_scoring_v3_nonlinear_risk_20250913.md`.
- Reproduction hashes: H1 fold1 c7a2ce88331ce8fc65522abaad94b4fc6311b944ef1b467ece04ed0f11b77dc8; H1 fold2 508e71a5e960fe307763ce43d5d1eb4ac05969a437c04a05d55b0d517add3fde; H2 4e38d1a946b4eacfcafd6818a4b4a7e8e1cef6a4c1d96b2b40a1d279f61d9522.
- 2026 strategy outcomes opened: false. Production modified: false.
- Next: causal cross-sectional/regime 4H representation; tail-first Monster objective; prospective evidence required for any promotion.


## CAUSAL-4H-SCORING-V4-CROSSSECTIONAL-REGIME-20260913 — REJECT / NO_PROMOTION

- Preregistered before V4 row-level evaluation. Added same-cohort percentile ranks and intraday cohort context; Core remained risk-adjusted, Monster became tail-first p(+20).
- H1 fold1 Monster Top1 restored +20% rate to 10.98%, but mean -0.53% and Top1-excluded mean -1.43%; FAIL.
- H1 fold2 Monster Top3/Top5 had positive means (+0.60/+0.76%) and positive Top1-excluded means, but +20% rates only 8.54/7.32%; FAIL.
- H2 retrospective Monster Top1 achieved +20% rate 10.08% but mean -1.71%, median -4.28%, Top1-excluded mean -2.24%; FAIL. Core all policies also failed.
- Interpretation: V3 was too defensive; V4 recovers tail capture but is too permissive. Do not interpolate/tune a risk penalty against H2.
- Decision: reject V4. Next architecture will model q10/q50/q90 of 5BD return directly using causal 4H context.
- Report: `reports/causal_4h_scoring_v4_crosssectional_regime_20260913.md`.
- Reproduction hashes: fold1 ebb47f75daf78b5f5e01baacdcf999a3f71479ffad66747f19ade6d4cdd01adc; fold2 f046c1a883959c21cb3fff789d9a25ce1c7302ce386d2448536b0e8471784df4; H2 6a9a6d9c6e55fb17127eec7a1e04cbbb9606037c3ad5f4339f11b5dab8e734e3.
- 2026 outcomes opened: false. Production modified: false.


## CAUSAL-4H-SCORING-V5-QUANTILE-DISTRIBUTION-20260913 — REJECT STATIC MODEL / NO_PROMOTION

- Preregistered before V5 row-level evaluation. Replaced classification probabilities with fixed q10/q50/q90 HistGradientBoosting regressors on the same causal 4H + cross-sectional context features.
- Core score=q50. Monster score=q90+min(q10,0). No return clipping or tuned risk coefficient.
- H1 fold1 Monster Top1 mean +1.78% but Top1-excluded mean -0.04% and +20% only 3.66%; FAIL.
- H1 fold2 Monster Top1 mean +3.35%, Top1-excluded +2.03%, +20% 9.76%, <=-10% 9.76%; narrowly misses only the right-tail gate. Monster Top5 mean +1.14%, Top1-excluded +0.96%; +20% 6.83%. All formally FAIL.
- H2 retrospective Monster Top1 mean -0.05%, +20% 6.05%, <=-10% 16.94%, Top1-excluded -0.48%; all policies FAIL. Core all policies FAIL.
- Interpretation: quantile modeling is promising in later H1 but the fixed model degrades across H2. Next hypothesis changes only retraining cadence to causal monthly expanding walk-forward; V5 model/feature/hyperparameters stay fixed.
- Report: `reports/causal_4h_scoring_v5_quantile_distribution_20260913.md`.
- Reproduction hashes: fold1 ad16fbc3ea3c7b370cf92fd0cf78af293f7d668795d10863ddf1e347492c9d4d; fold2 36b6e34fa67c35cfae07a34542b45cdcdcb83799b25237156f9144ecc3f47e2b; H2 09a9152fa4a676072a9756af3c0d9dea42e70873f3d7162bfd2de4b7e4b74447.
- 2026 outcomes opened: false. Production modified: false.


## CAUSAL-4H-SCORING-V6-MONTHLY-WALKFORWARD-20260913 — REJECT / NO_PROMOTION

- Preregistered before V6 row-level evaluation. Only change from V5: monthly expanding causal retraining; all features, q10/q50/q90 models, hyperparameters, scores, TopN, cooldown and gates unchanged.
- Causal maturity verified every month: each monthly training max exit date is strictly before the evaluation month start.
- H1 Mar-Jun Monster Top1: n=164, mean +1.28%, +20% 6.71%, <=-10% 10.98%, Top1-excluded +0.38%; FAIL. Core Top1 mean +1.73% but median -0.50%, win 44.5%, Top3-excluded -1.17%; FAIL.
- H2 Jul-Dec Monster Top1: n=248, mean -1.87%, +20% 4.03%, <=-10% 17.34%, Top1-excluded -2.09%; Top5 mean -0.54%, +20% 4.76%; all FAIL. Core all policies fail.
- Interpretation: model staleness alone is not the main cause. Do not tune cadence from H2.
- Next structural hypothesis: Monster viability gate q50>=0 followed by q90 tail ranking, avoiding a fitted risk coefficient.
- Report: `reports/causal_4h_scoring_v6_monthly_walkforward_20260913.md`.
- H1 hash f5c44e192dde2b951e46df29b28501168c79ed9bd4e22e12920472ead493ee15; H2 hash 02fe6a44c8c34901aa6aeedc39abd835211e85e7ddb807a301e9491317849a2c.
- 2026 outcomes opened: false. Production modified: false.


## CAUSAL-4H-MONSTER-V7-MEDIAN-VIABILITY-TAIL-20260913 — REJECT / NO_PROMOTION

- Preregistered before V7 selection metrics. Reused V6 monthly q10/q50/q90 scored rows; no model/feature retraining.
- Frozen structural rule: q50>=0 viability gate, then q90 descending, no backfill, same Top1/2/3/5 and cooldown.
- H1: viable 54.93%. Top1 n=125, mean +1.31%, +20% 7.20%, <=-10% 12.0%, Top1-excluded +0.11%; FAIL. All TopN fail.
- H2 retrospective: viable 42.19%. Top1 n=146, mean -1.66%, +20% 3.42%, <=-10% 19.86%, Top1-excluded -2.00%; all fail.
- Interpretation: hard median viability removes too much right-tail and does not repair H2. Do not tune q50 threshold.
- Decision: reject V7. Next structural direction: weight-free Pareto selection on upside/downside predictions.
- Report: `reports/causal_4h_monster_v7_median_viability_tail_20260913.md`.
- 2026 outcomes opened: false. Production modified: false.


## CAUSAL-4H-MONSTER-V8-PARETO-FRONT-20260913 — H1 PASS / H2 FAIL / REJECT PRODUCTION

- Preregistered before V8 metrics. Reused unchanged V6 monthly q10/q50/q90 predictions.
- Frozen rule: first nondominated Pareto front on maximizing q90 and q10, q90-first rank within front, no backfill, same cooldown.
- H1 Pareto front 3.79% of rows. Top2 n=328 passed all frozen Monster gates: mean +0.88%, +20% 10.06%, <=-10% 18.90%, Top1-excluded +0.56%. Top1/3/5 failed.
- H2 Pareto front 5.20%. Top2 mean -1.28%, +20% 5.44%, <=-10% 22.78%, Top1-excluded -1.56%; all TopN fail.
- Decision: reject V8 as standalone production architecture. Do not choose Top2 as a promoted policy from exposed H1.
- Interpretation: Pareto structure is the first current causal-4H design to pass all Monster gates on a named retrospective period, but regime/time instability remains.
- Next: diagnose causal signal-time regime/context differences between passing and failing periods before freezing any new regime-aware rule.
- Report: `reports/causal_4h_monster_v8_pareto_front_20260913.md`.
- 2026 outcomes opened: false. Production modified: false.


## CAUSAL-4H-SCORING-V9-PRIOR-DAILY-CONTEXT-20260913 — REJECT AFTER H1 / H2 NOT OPENED

- Preregistered before V9 evaluation. Kept 19 causal intraday/cross-sectional features primary and added seven prior-completed-daily context features only.
- Coverage remained 398,751/398,772 = 99.995%.
- H1 Core all TopN fail. Top1 mean +1.30% but median -0.50%, win 45.1%, Top3-excluded -1.16%.
- H1 Monster all TopN fail. Top1 mean -3.41%, +20% 10.98%, <=-10% 35.98%, Top1-excluded -3.95%; Top2 mean -1.62%, +20% 8.84%.
- Decision: reject V9 without opening V9 H2 because H1 already fails every frozen policy.
- Interpretation: generic prior-daily technical context worsens the Monster architecture. Do not expand daily-only context further; return to causal intraday feature research.
- Next: data-quality audit and frozen test of source-internal same-bin relative volume using raw intraday history, with log transform and no same-day finalized daily-volume anchor.
- Report: `reports/causal_4h_scoring_v9_prior_daily_context_20260913.md`.
- 2026 outcomes opened: false. Production modified: false.


## CAUSAL-4H-SCORING-V10-RELATIVE-VOLUME-20260913 — REJECT AFTER H1 / H2 NOT OPENED

- Preregistered before V10 evaluation. Added only causal source-internal log_volume_rel20 and its cohort rank to the 19-feature intraday panel; V9 daily context removed.
- 2025 feature coverage remained 398,772/398,772 = 100%.
- H1 Core all fail despite positive means: Top1 +2.62% but median -0.50% and Top3-excluded -0.46%.
- H1 Monster all fail: Top1 mean -1.44%, +20% 9.76%; Top2 mean -0.49%, +20% 9.15%, Top1-excluded -0.82%.
- Decision: reject V10 without H2. Relative volume remains data-quality-approved but not standalone predictive evidence.
- Next: change candidate generation. Test a frozen causal 4H reversal/ignition event gate before scoring rather than ranking every eligible 4H bin.
- Report: `reports/causal_4h_scoring_v10_relative_volume_20260913.md`.
- 2026 outcomes opened: false. Production modified: false.


## CAUSAL-4H-MONSTER-V11-WEAK-REVERSAL-IGNITION-20260913 — REJECT CANDIDATE GENERATION / H2 NOT OPENED

- Preregistered before outcome evaluation. Frozen causal gate: cohort breadth<=50%, prior4 mean return<=0, current bar positive, range expansion, same-bin relative volume>=1x prior20 median.
- Feature-only population: 13,873 rows (3.48%), 232 dates, 1,210 symbols.
- H1 ranked policies all fail: Top1 n=124 mean -0.83%, +20% 7.26%, <=-10% 22.58%, Top1-excluded -1.71%; Top3 mean -0.49%, +20% 5.11%.
- Gate-population diagnostic confirms the problem exists before ranking. Base H1 population: mean about -0.01%, median -0.37%, win 46.12%, +20% 1.53%, <=-10% 5.09%. Frozen event pool: mean -1.06%, median -1.08%, win 37.28%, +20% 1.92%, <=-10% 7.67%.
- Decision: reject V11 at candidate-generation level. Per preregistration, V11 H2 remains unopened.
- Do not tune event thresholds against exposed H1 outcomes.
- Next: return to a sparse Bollinger/RSI/squeeze/persistence 4H mechanism family inspired by the existing Tentei architecture, without requiring exact TradingView signal matching.
- Report: `reports/causal_4h_monster_v11_weak_reversal_ignition_20260913.md`.
- 2026 outcomes opened: false. Production modified: false.


## TENTEI-INSPIRED-4H-V12-STATE-REVERSAL-20260913 — MONSTER GATE FAIL / CANDIDATE GENERATOR PROMISING / H2 UNOPENED

- Preregistered before outcome access and explicitly not claimed as exact TradingView/Tentei replication.
- 2025 candidate rows after prior-day gates: 23,959. H1 raw signal rows: 8,245.
- H1 ALL after cooldown n=3,583: mean +1.43%, median +0.58%, win 55.04%, +20% 1.98%, <=-10% 4.30%, Top1-excluded +1.31%. Fails only the +20% Monster-tail gate.
- RSI_RECOVERY n=2,662: mean +1.90%, median +1.09%, win 59.17%, +20% 2.14%, Top1-excluded +1.74%.
- TREND_FLIP n=674: mean -0.44%, median -0.77%, win 40.80%.
- EMERGENCY_REVERSAL n=1,874: mean +2.13%, median +1.82%, win 62.06%, +20% 1.71%, <=-10% 3.09%, Top1-excluded +2.09%.
- Decision: V12 Monster gate fail; per preregistration V12 H2 remains unopened.
- Interpretation: V12 is the first current sparse 4H mechanism with clearly positive central and robustness statistics, but it does not concentrate enough +20% outcomes.
- Next: V13 keeps ALL V12 candidates unchanged and applies the already-existing V6 causal q10/q50/q90 predictions for Pareto tail ranking. Do not pick RSI or emergency path post hoc.
- Report: `reports/tentei_inspired_4h_v12_state_reversal_20260913.md`.
- 2026 outcomes opened: false. Production modified: false.


## TENTEI-INSPIRED-4H-V13-V6-QUANTILE-RANK-20260913 — REJECT AFTER H1 / H2 UNOPENED

- Preregistered before V13 metrics. Kept all V12 events unchanged and applied existing V6 q10/q50/q90 Pareto ranking.
- H1 scored V12 rows: 8,207.
- Top1 n=164: mean +0.67%, median -1.87%, win 42.68%, +20% 6.10%, <=-10% 14.02%, Top1-excluded +0.22%; FAIL.
- Top2 mean +0.47%, +20% 5.81%; Top3 +0.38% / 4.33%; Top5 +0.23% / 3.51%; all fail.
- Decision: reject V13 without H2.
- Interpretation: broad-universe V6 predictions are not suitable as the tail ranker for the sparse V12 event population.
- Next: V14 event-specific dual classifiers trained only on resolved pre-2025 V12 events. One predicts >=+20% tail, one predicts <=-10% downside; selection uses a weight-free Pareto front.
- 2026 outcomes opened: false. Production modified: false.


## TENTEI-INSPIRED-4H-V14-PRE2025-DUAL-CLASSIFIER-20260913 — REJECT AFTER H1 / H2 UNOPENED

- Parallel-lane check: the other ChatGPT lane owns `TENTEI-STATE-ENTRY-REPRESENTATION-20260913`; this lane continued V14 and did not duplicate that experiment.
- Fixed canonical daily source recovered from artifact 10264205130; SHA-256 `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0` exactly matched the frozen receipt.
- Fast-parser equivalence before outcomes: pre-2025 V12 candidates after gates 7,099 / 1,065 symbols and H1 candidates after gates 8,245, both exact registered/official counts.
- Input receipt correction recorded before H1 metrics: 7,099 is the pre-feature-finiteness event pool. The fixed 19-feature V14 model actually fits 4,924 finite resolved rows / 966 symbols. No model or threshold changed.
- Pre-2025 model-fit prevalence: +20% target 1.056%; <=-10% target 2.660%. 2025 labels were not used for fit.
- H1 Top1: n=163, mean -0.689%, median -1.717%, win 40.49%, +20% 4.91%, <=-10% 14.11%, Top1-excluded -1.147%; FAIL.
- Top2/3/5 means -0.372/-0.582/-0.481%; +20% 3.42/2.16/1.68%; all FAIL.
- Even at 0% cost, Top2/Top5 means are only +0.128/+0.019% and winner-excluded means remain negative.
- Decision: reject V14; per preregistration V14 H2 remains unopened. Do not tune V14 against H1.
- Next candidate task after parallel-lane recheck: outcome-free pre-2025 vs 2025-H1 V12 feature-distribution drift audit before designing another supervised ranker.
- Report: `reports/tentei_inspired_4h_v14_pre2025_dual_classifier_20260913.md`.
- 2026 outcomes opened: false. Production modified: false.


## TENTEI-V14-FEATURE-DRIFT-20260913-01 — MATERIAL_COVARIATE_SHIFT

- Parallel-lane recheck found no duplicate drift audit; the other lane was working on prospective-shadow/export infrastructure and state-entry evidence.
- Outcome-free comparison: V14 pre-2025 model-fit-like feature cohort 4,924 rows / 966 symbols vs 2025 H1 feature-complete V12 cohort 8,227 rows / 1,173 symbols. No strategy return column was used.
- Frozen decision: MATERIAL_COVARIATE_SHIFT (4 severe continuous features + 1 severe trigger flag).
- Severe continuous: prev4_range_mean KS 0.269 / PSI 0.395 / median shift +0.653 IQR; bb_width_pct 0.332 / 0.651 / +0.927; atr_pct 0.281 / 0.448 / +0.667; prior5_rsi_min PSI 0.270.
- Emergency-reversal trigger share shifted from 47.54% to 60.62% (+13.07pt, severe). RSI-recovery share fell 6.99pt (moderate); trend-flip share was stable.
- Relative volume stayed low-drift: median 0.789 -> 0.797, KS 0.031, PSI 0.014.
- Interpretation: V14's fixed pre-2025 supervised representation is materially regime-sensitive, particularly to volatility level/state. This is diagnostic, not proof of causal performance failure.
- Next after overlap recheck: preregister a regime-normalized V15 representation using causal relative/rank volatility features while keeping V12 candidate generation unchanged. Do not tune from H1 outcomes.
- Report: `reports/tentei_v14_feature_drift_20260913.md`.
- 2026 outcomes opened: false. Production modified: false.


## TENTEI-V15-REGIME-NORMALIZED-DRIFT-20260913-01 — FAIL REPRESENTATION / RETURNS UNOPENED

- Parallel-lane check confirmed no overlap: other lane was on prospective-shadow evidence/reporting and ledger reconciliation.
- Outcome-free V15 drift audit used no strategy return values.
- Cohorts after V12 gates + all 16 V15 features finite: pre-2025 2,672 rows / 793 symbols; H1 8,207 rows / 1,166 symbols.
- Frozen representation gate failed: 3 SEVERE + 4 MODERATE features; gate required zero severe and <=4 moderate.
- Severe: atr_rel20_log KS 0.315 / PSI 0.588 / median shift +0.633 IQR; bb_width_rel20_log 0.284 / 0.496 / +0.578; prev4_range_rel20_log 0.262 / 0.392 / +0.601.
- Moderate: range_rel20_log, dist_prior5_low_atr_rank20, prior5_rsi_min_rank20, prior5_band_min_rank20.
- Low-drift examples include bar_log_return, bb_position, rsi12, rsi_delta, log_volume_rel20 and lower_wick_rank20.
- Decision: reject V15 representation before any strategy-return evaluation. H1/H2 V15 returns remain unopened.
- Next after overlap recheck: replace volatility log-ratio features with bounded prior-history percentile ranks; keep V12 candidate generation and frozen low-drift retained features unchanged.
- Report: `reports/tentei_v15_regime_normalized_drift_20260913.md`.
- 2026 outcomes opened: false. Production modified: false.


## TENTEI-V16-HISTORY-RANK-DRIFT-20260913-01 — FAIL REPRESENTATION / RETURNS UNOPENED

- Parallel-lane check confirmed no overlap; other lane remained on prospective-shadow evidence/reporting and ledger reconciliation.
- Outcome-free cohorts: pre-2025 2,672 rows / 793 symbols; H1 8,207 rows / 1,166 symbols.
- Frozen representation gate failed: 1 SEVERE + 5 MODERATE; required zero severe and <=4 moderate.
- Severe: bb_width_pct_rank20 KS 0.2015 / PSI 0.1738 / median shift +0.417 IQR.
- Moderate: atr_pct_rank20, prev4_range_mean_rank20, dist_prior5_low_atr_rank20, prior5_rsi_min_rank20, prior5_band_min_rank20.
- Low-drift examples: range_pct_rank20, lower_wick_pct_rank20, bar_log_return, bb_position, rsi12, rsi_delta, log_volume_rel20.
- Interpretation: same-symbol prior20 ranks reduce but do not remove broad market volatility-regime shift.
- Decision: reject V16 before any strategy-return evaluation.
- Next after overlap recheck: same-date + same-bin cross-sectional percentile representation to remove common market volatility level directly.
- Report: `reports/tentei_v16_history_rank_drift_20260913.md`.
- 2026 outcomes opened: false. Production modified: false.


## TENTEI-V17-CROSSSECTIONAL-RANK-DRIFT-20260913-01 — PASS REPRESENTATION / RETURNS STILL UNOPENED

- Parallel-lane check confirmed no overlap; the other lane remained on prospective-shadow evidence/reporting and ledger reconciliation.
- Outcome-free cross-sectional rank universe: 283,750 gated complete bins / 181 dates / 1,248 symbols.
- V12 feature-complete cohorts: pre-2025 4,924 rows / 966 symbols; H1 8,227 rows / 1,173 symbols.
- Frozen representation gate passed: 0 SEVERE + 1 MODERATE + 15 LOW.
- Previously severe V16 volatility dimensions became LOW: xrank_bb_width_pct KS 0.061/PSI 0.027; xrank_atr_pct 0.033/0.009; xrank_prev4_range_mean 0.035/0.010.
- Only moderate feature: xrank_prior5_rsi_min, PSI 0.1365.
- Decision: PASS_TO_SUPERVISED_PREREGISTRATION. No V17 return metric was opened during the representation audit.
- Next: separately preregister the unchanged V14 dual-classifier/Pareto architecture using V17 features only, then evaluate H1. H2 only if a frozen H1 TopN passes.
- Report: `reports/tentei_v17_crosssectional_rank_drift_20260913.md`.
- 2026 outcomes opened: false. Production modified: false.


## TENTEI-INSPIRED-4H-V17-CROSSSECTIONAL-DUAL-CLASSIFIER-20260913 — REJECT AFTER H1 / H2 UNOPENED

- V17 representation first passed its frozen outcome-free drift gate (0 severe / 1 moderate), then the supervised architecture was separately preregistered.
- Same V14 model architecture and selection; only the stable V17 representation changed. Pre-2025 fit rows 4,924 / 966 symbols; +20% training prevalence 1.056%; 2025 labels not used for fit.
- H1 Top1: n=163, mean -0.476%, median -1.642%, win 37.42%, +20% 6.13%, <=-10% 14.11%, Top1-excluded -0.894%; FAIL.
- Top2/3 means -0.404/-0.134%; Top5 +0.061% but median -0.500%, +20% 2.75%, Top1-excluded -0.048%; all FAIL.
- Decision: reject V17 supervised; per preregistration H2 remains unopened.
- Interpretation: covariate drift was materially fixed, but direct +20% classification is too sparse/weak for robust ranking. Next hypothesis should use continuous/quantile return modeling on the same stable V17 representation.
- Report: `reports/tentei_v17_crosssectional_dual_classifier_h1_20260913.md`.
- 2026 outcomes opened: false. Production modified: false.


## TENTEI-INSPIRED-4H-V18-CROSSSECTIONAL-QUANTILE-20260913 — REJECT AFTER H1 / H2 UNOPENED

- V18 reused the stable V17 representation and replaced sparse +20 classification with fixed q10/q50/q90 regression; pre-2025 fit rows 4,924 / 966 symbols; 2025 labels not used for fit.
- Quantile crossing raw rate only 0.0365%.
- Core all TopN fail. Top1 mean -0.063%, median -0.500%, win 44.51%, Top3-excluded -0.339%; Top5 mean -0.221%.
- Monster all TopN fail. Top1 mean -0.518%, +20% 3.05%, <=-10% 14.02%, Top1-excluded -0.933%; Top5 mean -0.325%, +20% 1.89%.
- Decision: reject V18; H2 remains unopened.
- Interpretation: V17 fixed covariate drift, but both classifier and quantile ranking degrade the V12 event population. The structural event generator itself is currently stronger than learned ranking.
- Next after overlap recheck: evaluate V12 ALL, with no ML rank, under the already-established Core metrics as a retrospective baseline; any H2 use is refutation-only because V12 H1 is exposed.
- Report: `reports/tentei_v18_crosssectional_quantile_h1_20260913.md`.
- 2026 outcomes opened: false. Production modified: false.
