# CLOUD_MONSTER_LEGACY_EXACT_V1 recovery pack

Status: **EXACT_NOT_YET_RECOVERED**. This pack is deliberately fail-closed. It preserves the contemporaneous evidence chain and missing-evidence boundary; it does not manufacture a new Cloud Monster.

## Historical identity signature, not a tuning target

- 63 matured Priority-A rows, 2026-03-05 through 2026-08-28.
- Legacy 5BD mean +9.86%, median +3.33%, win 57.1%.
- +20% 30.2%, +30% 19.0%, -10% 22.2%, Top5-ex mean +4.03%.

## A. Exact/probable/missing rule boundary

Exact from contemporaneous records: Priority A is score top 10%; Priority B is the next 20%; the score was trained/developed on March-June 2026 and July-August was the later block. The 63 rows are all Priority A.

Probable lineage: daily `pre_down3`, daily `gap_up`, recent pseudo-4H three-bar return at least +6%, then a score influenced by 4H momentum, daily momentum, volume, and risk. A historical note records a 575-row Watch pool. These fragments are not an executable exact rule.

Missing and identity-critical: final Watch filters/calendar/session/dedup ordering; model versus weighted-rule ambiguity in surviving accounts; exact objective; feature list and transforms; missing values; calibration; weights/parameters; serialized model; seed; score grouping/ties; cooldown; original endpoint/cost implementation. No value may be inferred from the headline outcomes.

## B-D. Source, input, execution

- Frozen exact-recovery spec: commit `9c4aed248cb3dd680a5608cd62b00fe294e254e1`, path `research/tentei_cloud/OLD_CLOUD_MONSTER_EXACT_REPRO_SPEC_20260914.md`.
- Forensic report: commit `7d19533560a186ffd4dceccb72fbaf1bd54117cc`, path `research/tentei_cloud/OLD_CLOUD_MONSTER_FORENSIC_20260914.md`.
- Recovered raw input: Actions artifact `10266329903`, run `34608845800`, `teacher_ohlcv_4h_raw.csv`, SHA-256 `f28bcb4546a4806c67feae4b45f346d08a881dc530f95da870ee50a6be9b7ce2`.
- Verification command: `py research/repro_packs/cloud_monster_legacy_exact_v1/verify_recovery_inputs.py --artifact-dir .cache/recovery/artifact_10266329903`.
- The verifier must remain nonzero until both historical CSVs named in `ARTIFACT_RECEIPT.json` and the missing score generator/model are recovered and independently authenticated.

## E-F. Canonical rows and evaluation

Canonical 63-row trade data is absent. Therefore no canonical CSV hash and no new canonical next-XTKS-open to fifth-close bridge may be claimed. The legacy endpoint headline is preserved without reinterpretation. When the historical rows and generator are recovered, first reproduce the legacy endpoint exactly; then create a separately named cost-0% canonical bridge with win=`gross > 0`, yearly and aggregate n/mean/median/win/+10/+20/-10/-20/max-up/max-down/Top3-ex/100-share P/L.

## G. Identity

Reserved identity: `CLOUD_MONSTER_LEGACY_EXACT_V1`. It remains `EXACT_NOT_YET_RECOVERED`, not `EXACT_REPRODUCED`.

## H. Handoff receipt

1. The target is the historical 63-row Priority-A result, not a similar new selector.
2. Its headline metrics are search signatures only.
3. Priority A top-10% and Priority B next-20% are confirmed.
4. March-June development and July-August later-block split are confirmed.
5. Watch seed fragments are probable, not executable exact rules.
6. The 575 Watch count is evidence, not a target for parameter fitting.
7. The raw teacher 4H corpus is recovered by artifact ID and SHA.
8. `cloud_two_lane_union_jpx.csv` and `cloud_priorityA_monsters_compare_teacher.csv` remain missing.
9. ChatGPT history still contains file-citation references to those two sources, but the connector exposed no downloadable attachment resource.
10. Git refs/history, current non-expired Actions artifact metadata, and bounded local paths were searched.
11. The broad 696-row / 62-of-63 reconstruction is rejected as exact.
12. Current 1H Cloud artifacts belong to a different lineage.
13. No 2026 outcome was used to infer any rule, feature, or threshold in this recovery session.
14. No parameter search or score-family guessing was performed.
15. Exact recovery requires the original two CSVs plus the score generator/model or equivalent identity evidence.
16. Until then the only valid disposition is `EXACT_NOT_YET_RECOVERED`.

