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

### Do not repeat
- Do not repeat default-branch-only code search; all listed research refs/history were queried.
- Do not repeat non-expired artifact-name enumeration for the same run set unless new runs/artifacts appear.
- Do not rerun local filename search in repo/Product/Downloads/Documents without a new path or cache lead.
- Do not treat current 1H artifacts or the broad 696-row reconstruction as the legacy n=63 result.
