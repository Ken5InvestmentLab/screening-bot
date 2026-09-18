# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-18 14:00 JST  
> **比較契約:** cost 0%、win = gross return > 0、signal T → next XTKS open → fifth XTKS close。  
> **重要:** 2026はMeta mapping SHA freeze + STATE明示許可までSEALED。production/mainは変更禁止。

## 現在地

**研究全体: 約85%** / **P0 historical比較: 70%** / **Meta地合い切替: 10%**。今回はheartbeatではなく、別系統候補のadmissibility確定とcross-year input固定が増えたため正式に前進。

## 直近1時間の実成果

- :36 → **CANDIDATE_ADMISSIBILITY + NEW_SHA**。`2bafa6a74ead8e3aa833ddefc8b468ba60150106` でV16 backwardをexact再現可能な別系統候補としてadmitし、`48743b9c94abf33646866e09412c4e4d08bf3d2d` でcross-year canonical inputsを固定。
- :48 → 2022 primary exact recoveryは最終期限内。既に `aaf53ab8d9678dcade730b3f4554a1e8ba72b7f4` でfresh-validation generator input contractをpin済み。15:00 JSTでartifact探索を強制終了し、未解決ならdeterministic 2022-computable再構築へ移る。
- :24 → 新規comparison cellはまだ未確認。既存2023-25 exact rowsの未充足metric埋めを継続。
- :12 → 2022 fallback manifest準備後、そのままMeta causal labelsへリレーする設計に変更済み。

## last substantive commit

`48743b9c94abf33646866e09412c4e4d08bf3d2d` — V16 cross-year canonical inputs lock。これにより別系統は候補探索フェーズを終了し、2023-2025 rows生成へ進める。

14:00 supervisor STATE commit: `342c39b3cd59eae348dddcd32393aa981ca34288`。

## 現在の最大blocker

**primary 2022 canonical rowsがまだ存在しない。** ただしこのblockerには15:00 JSTのhard exitを設定済み。旧29 rows/23 datesのexact identityを回収できなくても、15:00以降は旧summaryへretuneせずdeterministic 2022-computable rowsを作るため、無限探索には戻らない。

別系統側はV16 admissibilityとcross-year inputsが固定されたため、次のblockerは単純に**2023 canonical rows SHAの生成**。

## 次の担当割当

| Lane | 担当 | 成果条件 |
|---|---|---|
| :12 | 2022 fallback → Meta準備 | deterministic manifest/補完後、2022-25 causal META_LABELへリレー |
| :24 | primary historical比較 | 既存2023-25 exact rowsから新規COMPARISON_CELL、2022 rows出現後即統合 |
| :36 | **V16 2023-25 rows生成** | 候補探索禁止。まず2023 canonical rows artifact+SHA、その後2024→2025 |
| :48 | **2022最終回収→再構築** | 15:00まで最終exact回収。以後はdeterministic primary-5 2022 rows生成へ強制移行 |
| :00 | Supervisor | NONE×2・停止・重複を即再配分、STATE/Dashboard writeback |

## P0残タスク

- 15:00まで2022 exact最終回収、未解決ならdeterministic primary-5 2022 canonical rowsを完成。
- V16別系統の2023/2024/2025 canonical rows + 年別/aggregate metrics完成。
- primary 5の2022-2025 + aggregate全metric完成。
- Meta causal label coverageを2022-2025で完成しmapping SHAをfreeze。
- freeze SHA + STATE許可後だけ2026 one-shot開封。2026結果によるretune禁止。

## GO / NO-GO

**研究継続 / production NO-GO / 2026 SEALED。**
