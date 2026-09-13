# Monster / Core候補の年別検出・評価

- 監査ID: TVFREE-ANNUAL-CANDIDATE-AUDIT-20260913-01
- 凍結仕様SHA-256: 67f4724bf5dd1b2c497fc934eb44dfd1549aac112069e2e23717dc959b9a2670
- Git SHA: 1adae835040bbccdb65dc8c3dfa35ca018e7ad13
- 全結果は回顧再計算です。以前に候補・結果を閲覧済みのため、OOS成績ではありません。
- MonsterのV7キャッシュはTail上位候補行のみで、東証全銘柄・全日のスコア履歴ではありません。
- 日次上限なしで全候補を検出。前の東証営業日に検出した同一銘柄だけを1営業日cooldownで除外します。
- 5BDは次の東証営業日の始値から5営業日目の終値まで。年末をまたぐ結果はpurgeし未解決扱いです。
- 主指標は0.5%の往復コスト仮定を差し引いた値。0%/1%感度はJSONと銘柄別CSVに記載。

## Monster 年次サマリー

| 年 | 状態 | 生pool | 検出 | 銘柄数 | 稼働日 | 解決/未解決 | 平均 | 中央値 | 勝率 | +10% | +20% | +50% | -10% | -20% | 最大1件除外 | 最大3件除外 | 日次等ウェイト平均 | 月プラス/対象 | 週プラス/対象 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2022 | NOT_AVAILABLE_NO_PRESERVED_V7_SCORE_ROWS | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2023 | 回顧再計算 | 69 | 55 | 41 | 45 | 54/1 | 1.48% | -1.51% | 40.74% | 25.93% | 18.52% | 5.56% | 37.04% | 16.67% | -0.49% | -3.27% | 1.50% (44/45日完了) | 5/12 | 9/26 |
| 2024 | 回顧再計算 | 138 | 109 | 43 | 69 | 105/4 | 1.68% | -3.59% | 42.86% | 21.90% | 15.24% | 5.71% | 31.43% | 13.33% | 0.57% | -1.34% | 2.82% (65/69日完了) | 6/12 | 13/30 |
| 2025 | 回顧再計算 | 67 | 54 | 38 | 37 | 54/0 | 2.19% | -7.53% | 37.04% | 25.93% | 12.96% | 5.56% | 35.19% | 5.56% | -0.21% | -2.90% | 3.57% (37/37日完了) | 5/11 | 10/26 |
| 2026 | NOT_AVAILABLE_NO_PRESERVED_V7_SCORE_ROWS | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |

日付・銘柄・順位・特徴量・個別5BD評価はローカルCSVに全件あります: tvfree_screener/batch02/.cache/annual_candidate_detections.csv
cooldown除外も含む適格候補pool: tvfree_screener/batch02/.cache/annual_candidate_all_pool.csv

- 平均/中央値/到達率は個別シグナル単位。Top1/Top3除外は最良リターンの1件/3件を外す診断。
- 日次等ウェイトはその日の全検出銘柄を等ウェイト化し、全銘柄のラベルが解決した日だけを集計。
- 月/週欄はコスト控除後にプラスだった期間数/対象期間数。JSONには期間別成績と銘柄集中度を収録。

## Core V29 fixed_min98_both

年別の個別銘柄再現は NOT_REPLAYABLE_FROM_PRESERVED_INPUTS です。V29の生教師行、日付付き350銘柄watchlist、当時のYahoo取得行がありません。日足から当時の時間足を合成して代替することもしません。
過去に保存された非年次の参考集計: n=35, mean 4.86%, median 2.90%, win 55.88%, +10% 31.43%。
これは350銘柄のwatchlist頻度サンプル、signal close→5営業日目closeの別ターゲットです。Monsterとの直接比較や年別への割り振りはできず、個別銘柄一覧も復元できません。

## 年別の利用可能性

| 系統 | 年 | 状態 |
|---|---:|---|
| Monster | 2022 | NOT_AVAILABLE_NO_PRESERVED_V7_SCORE_ROWS |
| Monster | 2023 | REPLAYED_RETROSPECTIVE |
| Monster | 2024 | REPLAYED_RETROSPECTIVE |
| Monster | 2025 | REPLAYED_RETROSPECTIVE |
| Monster | 2026 | NOT_AVAILABLE_NO_PRESERVED_V7_SCORE_ROWS |
| Core V29 | 2022 | NOT_REPLAYABLE_FROM_PRESERVED_INPUTS |
| Core V29 | 2026 | NOT_REPLAYABLE_FROM_PRESERVED_INPUTS |

V7の2022/2026スコアは保存されていないため日足から再現していません。全入力ハッシュと凍結仕様を実行前に検証し、V7の結果列を読み込まず日足OHLCVからラベルを再計算しています。
この結果は説明的な過去評価で、全市場スコア再現、Walk-Forward/OOS昇格、Codexなしの本番実行性は証明しません。
