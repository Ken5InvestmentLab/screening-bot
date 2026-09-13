# 年別候補再評価: Monster / Core

登録時刻: 2026-09-12T23:29:06.358Z UTC. ID: `TVFREE-ANNUAL-CANDIDATE-AUDIT-20260913-01`. 仕様hashは `ANNUAL_CANDIDATE_AUDIT_SPEC.sha256`。

## 対象と境界

ユーザー指定により、過去にもっとも見込みがあると評価したMonster `weak+early+volr20 low` を、保存V7 Tail特徴がある全暦年で年別に再評価する。仕様hashはbatch01の凍結Monster仕様に固定する。volr20の低い順に並べ、日ごとの全適格銘柄を出力し、1日最大銘柄数は設けない。前の東証営業日に実際に検出した同一コードだけを除外する1BD cooldownを適用する。cooldown前poolと後detectionの両方を保存する。

V7キャッシュには既存の `target5_no` / `target_end_date` / `y_hit20` / `y_loss10` 等の結果列が含まれる。これらは使用禁止。読み込むのはsignal-time特徴列だけとし、評価ラベルは保存済み日足OHLCVからcanonical next-openから5営業日目closeで再構成する。日足を1h/4hへ変換しない。

V7 tail scores are preserved only for 2023–2025. 2022 and 2026 receive explicit `NOT_AVAILABLE` rows; no model or scores are reconstructed from daily OHLCV. 2023–2025 results are retrospective reports. 2025 is opened once for the user-requested frozen report only; no selection, tuning or policy changes follow.

CoreはV29 `fixed_min98_both` をCore referenceとして監査する。保全artifactには年間signal行・当時の4時間足取得値・日付付き350銘柄watchlistが存在せず、完全再現不可。日足からの近似スコアは別物なので作らない。年ごとの結果は `NOT_REPLAYABLE_FROM_PRESERVED_INPUTS` とする。保存済みaggregate値は年次値に分解しない。

## 年別評価

- シグナル単位と日別等ウェイトcohortを分ける。
- annual rowには検出数、解決/未解決数、ユニーク銘柄、active dates、日次候補数、mean/median/win、+10/+20/+50/-10/-20、Top1/Top3除外、月/週/銘柄集中を含める。
- 0.5% round-trip costを主表示、0%/1%を感度分析とする。コストは仮定で実測ではない。
- partial/unresolved outcomeを除外した信号集計は件数を明記し、partial daily cohortを完全cohort平均に混ぜない。ラベルを落としたり銘柄を差替えたりしない。
- CoreとMonsterはターゲット/母集団が異なるため直接順位付けしない。