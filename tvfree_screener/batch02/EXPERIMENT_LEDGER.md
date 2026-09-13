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
