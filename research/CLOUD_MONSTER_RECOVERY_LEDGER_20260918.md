# Cloud Monster / weak+early Recovery Ledger — 2026-09-18

Status: RESEARCH ONLY / RECOVERY PRIORITY OVERRIDE.
Production/main/Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist-builder/updater are untouched.
2026 strategy outcomes remain SEALED and must not be used to choose or retune recovery conditions.

## Absolute recovery objective
1. Recover the exact legacy Cloud Monster lineage behind the historical headline around n=63 / 5BD mean +9.86%.
2. Recover an exact, executable weak+early pipeline from source/input -> candidate rows -> evaluation.
3. Freeze both as REPRO_PACKs so the result cannot be lost again.

Legacy headline numbers are search signatures only. Never tune thresholds to match them.

## Legacy Cloud Monster search signature — NOT YET EXACT
Historical notes/user-visible research previously reported approximately:
- n = 63
- 5BD mean = +9.86%
- median = +3.33%
- win = 57.1%
- +20% = 30.2%
- +30% = 19.0%
- <= -10% = 22.2%
- Top5-ex mean = +4.03%

Current status: the exact generator / input / canonical rows / source SHA chain for this n=63 result has not yet been recovered. Do not call this canonical or reproducible until REPRO_PACK A-H is complete.

## Confirmed weak+early evidence already recovered
Source:
- branch: research/tvfree-canonical-batch02
- file: tvfree_screener/research_20260912_core_monster.md
- fetched blob SHA: 762b38e99d11866925abbdb47b5fd61854897120

The file explicitly states the fixed weak+early gate:
1. market `med_ret5 <= 0`
2. candidate `ret10 <= 0.5735294117647058`
Applied to the preserved causal V7 Tail population. The document states no 2026 outcomes were used for this gate.

Same-day ranking evidence in that file, 2023-2024 development, one candidate per day:
- volr20 LOW: n=128, mean +6.24%, median +1.06%, +20 18.75%, +50 8.59%, -10 25.78%, Top3-ex +3.81%
- body_pct LOW: n=128, mean +6.46%, median +1.25%, +20 17.97%, +50 7.81%, -10 28.12%, Top3-ex +4.03%
- mean rank(volr20, body_pct): n=128, mean +7.16%, median +1.81%, +20 19.53%, +50 8.59%, -10 25.78%, Top3-ex +4.75%

The same file also records 2025 descriptive checks and later canonical reconciliation. Those later sections must not be silently conflated with the earlier legacy headline.

Equivalent earlier file also exists on:
- branch: research/tvfree-monster-v14
- file: tvfree_screener/research_20260912_core_monster.md
- fetched blob SHA: 3ba2090e641c4d08c82687729664251b4ff04d7f

## Additional weak+early reconstruction evidence
Source:
- branch: research/tvfree-canonical-batch02
- file: tvfree_screener/batch02/EXPERIMENT_LEDGER.md

Recovered excerpt records a frozen annual extension for weak+early+volr20-low and states:
- feature scoring uses original V7/V9 source recipe
- monthly causal training with matured labels before month start
- minimum 30,000 rows
- 2022/2026 runtime-sensitive reconstructions were explicitly separated from preserved-cache 2023-2025 replay
This is a strong lead for exact generator/input/command recovery.

## Branches / surfaces to search without duplication
Lane :12 provenance:
- research/tentei-cloud-1h
- research/tentei-cloud-mtf
- research/tvfree-canonical-batch01
- research/tvfree-canonical-batch02
- research/tvfree-monster-v14
- test/tvfree-screener-v1
- commit history / workflow run+artifact metadata / handoff / reports / specs

Lane :24 weak+early exact:
- V7/V9 source recipe
- preserved cache identity
- tail threshold
- monthly causal training contract
- fixed weak+early gate
- same-day ranking and tie-break
- cooldown
- endpoint builder
- 2023-2025 identity-level row replay

Lane :36 result-signature reverse lookup:
- search legacy Cloud Monster n=63/+9.86 signature across reports/JSON/CSV/actions artifacts
- record partial matches with path/ref/SHA/date range/row count
- no threshold fitting

Lane :48 reproducer:
- turn recovered spec into executable deterministic entrypoint
- produce canonical rows SHA and metrics SHA
- compare against preserved rows/metrics at identity level
- never approximate missing semantics and call them exact

## REPRO_PACK hard gate
Recovery is COMPLETE only when all are pinned:
A. exact expression / thresholds / tie-break / causal timing
B. source path + commit SHA
C. input artifact id/path + content SHA
D. exact command / entrypoint + args
E. canonical trade rows + rows SHA
F. evaluation contract + metrics SHA
G. identity name + version
H. 10-20 line handoff linking A-G

## Immediate interpretation
- weak+early is not lost; its core gate and ranking evidence are already documented and appears recoverable.
- the exact old Cloud Monster n=63 lineage is still unresolved and is now the highest-priority provenance target.
- normal primary-historical / Meta work is temporarily secondary until this recovery is finished or definitively bounded by evidence, without using 2026 to rescue or tune anything.

## 2026-09-18 manual recovery session

### Workspace and branch isolation
- Working branch: `research/cloud-monster-recovery`.
- Branch created from `origin/research/automation-coordination` at `cc08da7523e5037ff5575427fbf4b57bb590f4fd`.
- Merge base with then-current `origin/main`: `c2d52f5e41aee3f529cfdc98e00e139b6090079c`.
- Result: research-only branch; no production/main checkout or mutation.

### Weak+early preserved inputs — EXACT
- Actions artifact `10264205130`, run `34599959356`, original source run `34545440155`, file `tse_daily.csv`.
- Daily corpus SHA-256: `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`.
- Actions artifact `10264251140`, run `34600083474`, file `v7_causal_tail_cache_2023_2025.csv`.
- Tail cache SHA-256: `0398969e13cc4b79f64cf8ad3b300ab34c0270ac70d20367994979478b60849d`.
- Source commit: `ef8754d835ccb39faf783092f969417a3ea74ce9`.
- V7 source blob: `f7f49ab2e09496494adfb365c94e969973c4070c`; V9 source blob: `45a1272fe49c526bbf69956419e34e96d696f7d6`.
- Search result: 1,306 preserved Tail rows; years 2023=267, 2024=557, 2025=482. No 2026 row was read.

### Weak+early selector reconstruction — EXACT
- Fixed gate applied verbatim: `med_ret5 <= 0 AND ret10 <= 0.5735294117647058`.
- Gate result: 204 eligible 2023-2024 rows on 128 unique signal dates.
- Selector: one candidate per signal date; `volr20` LOW, `body_pct` LOW, or mean of within-day ascending percentile ranks.
- Tie-break: `tail_cdf` descending. All three selectors have zero unresolved winning ties after this tie-break.
- Cooldown: none for the legacy n=128/n=44 rank comparison. A one-prior-session same-symbol cooldown changes n and is rejected as a different later variant.
- Endpoint replay against the fixed daily corpus had zero entry-date, entry-open, fifth-session-date, exit-close-derived-return, or cached-target mismatches.
- Reproducer: `research/repro_packs/weak_early_exact_v1/reproduce.py`.
- Canonical output hashes are pinned in `research/repro_packs/weak_early_exact_v1/output/manifest.json`.
- Status: `WEAK_EARLY_EXACT_V1` is `EXACT_REPRODUCED` for the preserved 2023-2025 legacy comparison.

### Cloud Monster reverse lookup — bounded surfaces completed so far
- Git refs/history searched: requested Cloud/Monster branches plus research handoffs/specs/reports; no tracked copy of `cloud_two_lane_union_jpx.csv` or `cloud_priorityA_monsters_compare_teacher.csv` found.
- Historical exact-recovery specs found on `origin/research/tentei-cloud-mtf`: `research/tentei_cloud/OLD_CLOUD_MONSTER_EXACT_REPRO_SPEC_20260914.md` at commit `9c4aed248cb3dd680a5608cd62b00fe294e254e1`, and forensic report at commit `7d19533560a186ffd4dceccb72fbaf1bd54117cc`.
- Those frozen documents record 63 historical Priority-A rows and exact scores for 19 high-return A rows, but explicitly record the missing model class/objective/features/transforms/calibration/serialized model/seed and final Watch-detail formula.
- Current non-expired GitHub Actions artifact metadata was searched by Cloud/Monster/teacher names. No artifact containing either legacy 63-row CSV was identified.
- Expired 1H Cloud artifacts `10193961732` and `10193889055` are a later/different 1H lane and are not evidence for the legacy 63-row identity.
- Local filename/content search covered the repository, Product, Downloads, and Documents. No copy of the two legacy CSVs was found.
- Recovered input-side evidence: Actions artifact `10266329903`, run `34608845800`, `teacher_ohlcv_4h_raw.csv`, SHA-256 `f28bcb4546a4806c67feae4b45f346d08a881dc530f95da870ee50a6be9b7ce2`.
- Classification: raw 4H corpus is exact input evidence; Watch/priority rule fragments are probable lineage; the legacy n=63 selection/model/canonical rows remain missing.
- Current Cloud status: `EXACT_NOT_YET_RECOVERED`. No parameter search or signature fitting was performed.
- ChatGPT conversation `6aa764a5-8648-83e8-818a-3fa0c5352f1f` was read as a distinct evidence surface. It retains historical file-citation references to the 63-row source and 19-score comparison, plus sample scores, but `read_thread` exposed no attachment resource or downloadable file. This confirms the provenance claim but does not recover row data.
- A fail-closed evidence pack now exists at `research/repro_packs/cloud_monster_legacy_exact_v1/`; its verifier authenticates the recovered teacher input and exits nonzero while the two identity CSVs and score generator/model remain missing.

### Do not repeat
- Do not repeat default-branch-only code search; all listed research refs/history were queried.
- Do not repeat non-expired artifact-name enumeration for the same run set unless new runs/artifacts appear.
- Do not rerun local filename search in repo/Product/Downloads/Documents without a new path or cache lead.
- Do not treat current 1H artifacts or the broad 696-row reconstruction as the legacy n=63 result.

### Fixed-spec 2022 replay — exact historical identity NOT recovered
- The pinned V7/V9 source blobs on the working branch exactly match the validation receipt.
- Windows Python 3.12 with the pinned 2026 Actions dependency versions produced 94 raw Tail rows, 30 gated rows, 22 gated dates.
- WSL2 Linux Python 3.12 with `numpy 2.5.3`, `pandas 2.3.3`, `scikit-learn 1.9.1`, `xgboost 3.4.1`, `requests 2.34.2`, and `yfinance 0.2.66` produced 95 raw Tail rows, 25 gated rows, 20 gated dates.
- Neither matches the historical comparison 89/29/23. No threshold, feature, seed, or input was changed to improve the match.
- Both raw/gated ledgers and their hashes are saved under `research/repro_packs/weak_early_exact_v1/2022_runtime_sensitivity/`.
- Classification: fixed-spec execution is exact; historical 2022 row identity remains `EXACT_NOT_YET_RECOVERED` because XGBoost/platform lineage is insufficiently pinned.

### Weak+Early Phase-2 structural selectors — EXACT
- Historical source for `DUAL_TOP1_AGREEMENT`: commit `4b37f18d7601f8fd6ff42155879faff5b7d1e9e3`, `research/WEAK_EARLY_PHASE2_20260914.md`.
- Historical G3 preregistration: commit `bb7e9dcddcf1ff9e931f0e2f92925d6f761cf7e5`, exact expression `previous-session med_ret1 >= -0.01`.
- Frozen G3 selection before 2025 open: commit `aed2690c5972edff99b0b06a26f8cb37b86165c1`.
- DUAL is the identity intersection of independently selected volr20 LOW Top1 and body_pct LOW Top1 on the same date; disagreement is NO TRADE.
- Reproducer now emits exact DUAL canonical rows: n=140, mean +7.17%, median +1.25%, win 52.14%, Top3-ex +4.79%, SHA `b4f9fff630577492198732c91275f2fafb0114e78a519074393d13e03ab88031`.
- It also emits exact DUAL+G3 rows: n=117, mean +7.98%, median +1.74%, win 53.85%, Top3-ex +5.14%, SHA `e98d4d82e81d05ac3b3ffae7f6dc91fa1bcd567d58c24403ae5568406ec8de27`.
- Commit `38edc77234e5bc283a55e14028a2b88e136c1ec4` pins code, rows, metrics, rule source commits, and output hashes.

### Outcome-blind TV-free shadow boundary
- Added `research/repro_packs/weak_early_exact_v1/select_shadow_candidates.py`.
- It reads only signal-time Tail fields and never loads labels, entry/exit prices, or realized returns.
- Historical assertion reproduces selector counts 172 / 172 / 172 / 140 / 117 and all date+symbol identities match the canonical trade-row files.
- This makes the selection layer forward-shadow-ready once a causally generated monthly Tail pool is supplied; it does not make the upstream model runtime deterministic and does not authorize production use.

### 2022 reverse-lookup clarification
- The apparent 2022 CSV rows found in the latest filename/content scan resolve to the already-saved Linux runtime replay under `2022_runtime_sensitivity/`, not to the missing historical 89-row ledger.
- No new historical 89/29/23 identity artifact was recovered. Do not repeat this same row-signature search unless a new path/ref/artifact appears.

### ChatGPT UI evidence-surface incident
- While attempting to locate legacy Cloud file citations in the old ChatGPT conversation, browser find did not activate and the search text `Bitcoin Japan` was accidentally submitted as a new message.
- The response was immediately stopped. No attachment, automation, repository file, production setting, or external message channel was changed. Browser/UI exploration was stopped and all subsequent work used repository/history only.

### Fixed five-candidate 2026 reporting-only open
- Explicit user request authorized calculation through 2026. It did not authorize rule/threshold/feature/gate retuning or production changes.
- Ranking contract `WEAK_EARLY_FIVE_CANDIDATE_RANKING_V1` was frozen and pushed at commit `26653f45` before 2026 performance was generated.
- Runtime: Python 3.12.13 / numpy 2.5.3 / pandas 2.3.3 / scikit-learn 1.9.1 / XGBoost 3.4.1 on Windows 11.
- Input: artifact `10264205130`, daily SHA `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`, cutoff 2026-09-11.
- Causal 2026 Tail: 220 rows, signal dates 2026-01-05 through 2026-09-03, SHA `8363340cc8ea48f6b6b41307da7cdb6f59860200b96f6849503145516ab021dd`.
- All selected rows passed next-open, fifth-XTKS-close, cached next-open, target-end-date, and gross-return consistency checks.
- 2026 rows: each base selector n=42; DUAL n=36; DUAL+G3 n=32.
- 2026 mean: volr20 +3.20%, body +4.90%, mean-rank +5.08%, DUAL +3.26%, DUAL+G3 +2.58%.
- Exact 2023-2026 total means: volr20 +5.71%, body +6.22%, mean-rank +6.53%, DUAL +6.37%, DUAL+G3 +6.82%.
- Pre-frozen equal-weight ordinal ranking for exact 2023-2026 rows: 1 mean-rank, 2 DUAL+G3, 3 body, 4 DUAL, 5 volr20.
- Pre-2026 2023-2025 ranking is retained separately: 1 DUAL+G3, 2 mean-rank, 3 DUAL, 4 volr20, 5 body.
- 2022 stays summary-only and excluded from exact total/ranking; missing historical row identity was not substituted with either runtime replay.
- Full report: `research/repro_packs/weak_early_exact_v1/output/full_period_2026/FULL_PERIOD_COMPARISON_20260918.md`.

## 2026-09-19 ChatGPT Library exact recovery breakthrough

- Evidence surface: ChatGPT conversation `研修継続報告`, URL `https://chatgpt.com/c/6aa38426-70f4-83ee-a623-29577859a638`, message id `3141d527-c580-4ae7-a045-764138f04611`.
- Recovered Library file `libfile_a5ca557456f0819195d1d03342885513` as `cloud_two_lane_union_jpx.csv`; repository-normalized SHA `91f1f956a48a308e21e49aa2a80c7075677ac5aa6d5dfae5d26c1b1ad7db4a62`.
- Recovered `cloud_priorityA_monsters_compare_teacher.csv`; repository-normalized SHA `1920e2e69b89feee473cd2e6f6542fe1766f754c3ff60397b65d026614037d54`.
- The union has 210 rows: Monster 63 and Stable 147. The Monster subset independently reproduces every search signature exactly, including Top5-ex.
- Recovered original final generator `/mnt/data/v3r/revalidate_lanes_jpx.py`. Exact Watch gate is `d_pre3 & d_gap & ret3>=.06 & ret3<5 & ret5.notna()`, first symbol-date row.
- Recovered model: 52 ordered features, median imputer, StandardScaler, balanced LogisticRegression C=.15/max_iter=500/random_state=1.
- Recovered walk-forward: April/May/June, prior-only training, fixed fractions .10/.20/.30, historical objective preserved in `recovered_selector.py`; selected .10.
- Recovered final fit before 2026-07-01 and fixed training-score quantile threshold `0.7480177317229793`. No cooldown and no per-day quota.
- Recovered source texts also exist in the conversation for `/mnt/data/v3r/build_mtf_fast.py` and `/mnt/data/v3r/relabel_jpx_5bd.py`; the latter uses official JPX session index +5.
- Exact row/selector evidence pack commit: `bb597947` on `research/cloud-monster-recovery`.
- Classification: exact rows and final selector recovered; full from-raw reproduction remains blocked by the missing builder of `cloud4h_frame_dedup_sep.pkl` and exact 1,314-symbol universe construction.
- Canonical bridge warning: recovered legacy endpoint is signal snapshot close→fifth XTKS close. The requested next-open→fifth-close bridge must be emitted separately after entry/exit prices are joined; never replace the legacy headline.
- Do not repeat: ChatGPT Library download of the two CSVs, message-38 final generator extraction, or signature verification. Resume only at earlier tool logs that built `cloud4h_frame_dedup_sep.pkl`.
- Usage stop: Codex weekly usage showed 98% used. New heavy exploration stopped; commit/push and handoff took priority.

## 2026-09-19 full raw reproduction

- Recovered the earlier original source `/mnt/data/v3r/build_cloud4h_dedup_sep.py` plus complete `build_mtf_fast.py`, `relabel_jpx_5bd.py`, and `revalidate_lanes_jpx.py` from conversation `6aa38426-70f4-83ee-a623-29577859a638`.
- Preserved all four under `research/repro_packs/cloud_monster_legacy_exact_v1/source/`; no production file or workflow was changed.
- Exact input: Actions artifact `10266329903`; raw OHLCV SHA-256 `f28bcb4546a4806c67feae4b45f346d08a881dc530f95da870ee50a6be9b7ce2`.
- Exact command is pinned in the pack README and uses Python 3.12, numpy 2.5.3, pandas 2.3.3, scikit-learn 1.9.1, and exchange-calendars 4.13.2.
- Base builder independently reproduced 245,334 rows, 74 columns, zero duplicate symbol/timestamps; MTF added 27 columns for the same 245,334 rows and 1,314 symbols with zero missing `d_rsi`.
- JPX official-session relabel completed, then the recovered fixed Watch/model/walk-forward/final-fit selector ran unchanged.
- Result: expected 63 / actual 63; symbol+timestamp+date identities equal; close bitwise equal; maximum absolute `ret5` difference `0.0`.
- Exact legacy headline reproduced: mean 9.8569267443%, median 3.3333333333%, win 57.1428571429%, +20 30.1587301587%, +30 19.0476190476%, -10 22.2222222222%, Top5-ex 4.0268601425%.
- Machine receipt: `research/repro_packs/cloud_monster_legacy_exact_v1/output/raw_reproduction_receipt.json`.
- Classification upgraded to `CLOUD_MONSTER_LEGACY_EXACT_V1 / EXACT_REPRODUCED_FROM_RAW`.
- No parameter search, threshold fitting to n=63, or 2026-based rule choice was performed.
- Do not repeat: base-builder/source search, raw-to-63 reproduction, or legacy signature verification. Remaining work is only the separately named next-open canonical endpoint bridge and final handoff refresh.

## 2026-09-19 canonical endpoint bridge and comparison

- Frozen selection input: the exact 63 `CLOUD_MONSTER_LEGACY_EXACT_V1` identities; no row, threshold, feature, gate, model, or ranking choice changed.
- Canonical endpoint: signal T → next official XTKS session open → fifth official XTKS session close; cost 0%; win=`gross_return > 0`.
- Canonical rows: `output/canonical_next_open_fifth_close/canonical_trade_rows_next_open_fifth_close.csv`, 63 rows, SHA `e8022da46af85fa249e0815768682fe0ccc7730485f9494268bebd8e961a6a17`.
- All 63 fifth-session closes independently reproduce the legacy close→fifth-close returns within absolute tolerance `1e-15`.
- Canonical 2026/TOTAL metrics: mean +4.5821%, median -0.1406%, win 49.2063%, +10 30.1587%, +20 15.8730%, -10 20.6349%, -20 7.9365%, max +87.20%, min -41.0448%, Top3-ex +1.3913%, 100-share aggregate P/L ¥153,500.
- Identity: `CLOUD_MONSTER_CANONICAL_NEXT_OPEN_FIFTH_CLOSE_V1`; legacy headline and canonical endpoint are intentionally separate.
- Built a coverage-aware comparison under `research/comparisons/cloud_weak_early_20260919/` using the previously frozen seven-metric ordinal contract.
- Descriptive 2026 ranking across six fixed candidates: 1 mean-rank, 2 body_pct LOW, 3 Cloud Monster canonical, 4 DUAL+G3, 5 DUAL, 6 volr20 LOW.
- Cloud covers only 2026-03-01 through 2026-08-31, whereas Weak+Early 2026 begins in January; this is descriptive reporting, not a retune or an apples-to-apples production adoption claim.
- Weak+Early 2023-2026 total ranking remains 1 mean-rank, 2 DUAL+G3, 3 body_pct LOW, 4 DUAL, 5 volr20 LOW. Cloud is not mixed into this four-year rank.

## 2026-09-19 outcome-blind Cloud model freeze

- Frozen the exact fitted imputer, scaler, LogisticRegression, feature order, and threshold as `CLOUD_MONSTER_FROZEN_SHADOW_MODEL_V1`; no refit choice or threshold change was introduced.
- JSON artifact SHA `0e46ab60683b20c2ab3a3eeaf79380f0cf39be38903b5686954f0dc69f2bcb26`; sklearn pipeline SHA `f8f1e9402a755bbd4a142adfe06d04f83178474b459f795965c92f5e81057716`.
- `select_cloud_shadow_candidates.py` references only signal-time fields and the 52 frozen features, then applies the frozen sklearn pipeline and threshold.
- Historical causal selection is 64 rows. The 63 legacy evaluated rows are an exact subset with zero missing identities and zero score drift.
- Additional causal identity: `6217|2026-04-13 13:00:00`. Legacy evaluation omitted it solely because `ret5.notna()` was false; endpoint availability is non-causal and is intentionally absent from the forward scorer.
- This 64-vs-63 distinction is not a mismatch and must not be hidden: 64 is candidate selection, 63 is the evaluable legacy performance set.

## 2026-09-19 high-win multi-lane research pause

- User authorized a bounded search for stronger win-rate conditions and allowed 2-3 distinct final scoring lanes.
- Preregistered `HIGH_WIN_MULTI_LANE_RESEARCH_V1` at commit `2a9d644393ac54d1502e29f4412080109bfb5071` before discovery: 12 fixed two-feature rankers, 2023 discovery, 2024 validation, 2025 holdout, 2026 forbidden for selection.
- Discovery selected one family winner, then froze three diversity-bounded finalists at commit `a61cd763a2b5e7a2f3875c74cc57f8774b0fa505` before opening 2025.
- Finalists: `EARLY_PRESSURE_V3 = body_pct LOW + ret1 LOW`; `REVERSAL_WICK_V1 = lower_wick HIGH + body_pct LOW`; `DEFENSIVE_PULLBACK_V3 = bbpct LOW + rsi14 LOW`.
- 2023-2024 aggregate win: 50.78%, 52.34%, 52.34%. These are not yet strong enough to claim success; no extra gate was added after seeing them.
- Frozen 2025 pass gate remains win>=55%, mean>=3%, median>0, Top3-ex>0, +20>=15%, -10<=25%, n>=35.
- 2025 holdout remains unopened in this lane at the 5-hour usage pause. Next action is a single fixed-spec holdout run; `NO_VIABLE_NEW_LANE` is valid.
