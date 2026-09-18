# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-18 15:02 JST  
> **比較契約:** cost 0%、win = gross return > 0、signal T → next XTKS open → fifth XTKS close。  
> **重要:** 2026はMeta mapping SHA freeze + STATE明示許可までSEALED。production/mainは変更禁止。

## 現在地

**研究全体: 約85%** / **P0 historical比較: 70%** / **Meta地合い切替: 10%**。15:00 hard exitを実行したが、新規trade rows/comparison cellそのものではないため進捗率は据え置き。

## 直近1時間の実成果

- :48 → **担当強制切替**。旧89→29→23 exact artifact回収は15:00で終了。以後の探索・旧29/23へのretuneを禁止し、deterministic primary-5 2022 canonical rows実生成へ移行。
- :36 → V16 backwardは `2bafa6a74ead8e3aa833ddefc8b468ba60150106` で別系統exact候補admit、`48743b9c94abf33646866e09412c4e4d08bf3d2d` でcross-year inputs固定済み。現在は2023 rows生成フェーズ。
- :24 → 14:22 run済み。coordination branchでは新規COMPARISON_CELLをまだ確認できず。既存2023-25 exact rowsの未充足metric埋めを継続。
- :12 → 14:11 run済み。2022 fallback支援→Meta causal labelsへのリレー担当を継続。

## last substantive commit

`696a11bbf211e62e1f7b775c3babd97b3561b93e` — Supervisor STATE v132。2022 old-artifact recoveryを正式終了し、deterministic reconstructionを唯一のcanonical pathに変更。

## 現在の最大blocker

**primary 2022 canonical rowsがまだ存在しない。** ただし探索blockerではなくなった。次に必要なのは:48/:12からの**最初のdeterministic primary-5 2022 TRADE_ROWS SHA**。

独立経路では、V16側の次の必要証拠は**2023 canonical rows SHA**。同じblockerへ全workerは集中させない。

## 次の担当割当

| Lane | 担当 | 成果条件 |
|---|---|---|
| :12 | 2022 fallback → Meta準備 | deterministic manifest/rows補完後、2022-25 causal META_LABELへリレー |
| :24 | primary historical比較 | 既存2023-25 exact rowsから新規COMPARISON_CELL、2022 rows出現後即統合 |
| :36 | **V16 2023-25 rows生成** | まず2023 canonical rows artifact+SHA、その後2024→2025。候補探索禁止 |
| :48 | **2022 deterministic再構築** | primary 5を候補単位でもTRADE_ROWS commit。旧artifact探索・29/23 retune禁止 |
| :00 | Supervisor | NONE×2・停止・重複を即再配分、STATE/Dashboard writeback |

## P0残タスク

- deterministic primary-5 2022 canonical rowsを完成し、旧summary不一致ならOLD_SUMMARY_NOT_EXACTLY_REPRODUCED receiptを固定。
- V16別系統の2023/2024/2025 canonical rows + 年別/aggregate metrics完成。
- primary 5の2022-2025 + aggregate全metric完成。
- Meta causal label coverageを2022-2025で完成しmapping SHAをfreeze。
- freeze SHA + STATE許可後だけ2026 one-shot開封。2026結果によるretune禁止。

## GO / NO-GO

**研究継続 / production NO-GO / 2026 SEALED。**