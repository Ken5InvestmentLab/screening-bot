# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-18 16:00 JST  
> **比較契約:** cost 0%、win = gross return > 0、signal T → next XTKS open → fifth XTKS close。  
> **重要:** 2026はMeta mapping SHA freeze + STATE明示許可までSEALED。production/mainは変更禁止。

## 現在地

**研究全体: 約86%** / **P0 historical比較: 71%** / **Meta地合い切替: 10%**。今回はheartbeatではなく、deterministic 2022 fallbackの実行entrypointが新規commitされたため正式に前進。

## 直近1時間の実成果

- :48系統 → **NEW_SHA** `42e5cd8fd7e9e34e90ddae790b1d4cbd3ede1887`。固定corpus SHAを検証し、2022 raw Tail + frozen weak/early base ledgersを決定論的に生成するresearch-only entrypointを追加。2026参照・旧29/23へのretune・return再計算を明示禁止。
- このentrypoint自身が、primary candidate rowsをまだ出せない理由を **primary 5 selector / G3 semantics未pin** と明示。blockerが「artifact探索」から具体的なselector spec 1点へ縮小した。
- :12 → Meta準備を一時停止し、既確定2023-25 primary定義からselector expression / ranking / tie-break / required columns / G3 semanticsを性能非依存でpinする担当へ即再配分。
- :36 → V16は候補探索禁止のまま2023 canonical rows生成を継続。現時点で新規TRADE_ROWS SHAは未確認。
- :24 → 既存2023-25 exact rowsの比較表埋めを継続。現時点で新規COMPARISON_CELLは未確認。

## last substantive commit

`42e5cd8fd7e9e34e90ddae790b1d4cbd3ede1887` — deterministic 2022 fallback entrypoint追加。Supervisor STATE v133 commitは `7b26d5add685ac6066451a3256687a01efa8b8f9`。

## 現在の最大blocker

**primary 5 selector / G3 semanticsのexact pin。** base Tail + weak/early ledger生成経路は既に固定されたため、ここがpinされれば:48は2022 primary candidate rows生成へ直結できる。旧89→29→23 artifact探索へは戻らない。

独立経路のblockerは **V16 2023 canonical rows SHA**。同じblockerへ全workerを集中させない。

## 次の担当割当

| Lane | 担当 | 成果条件 |
|---|---|---|
| :12 | **primary selector固定** | 2023-25既確定定義からprimary 5 selector/G3 semanticsをspec+SHAでpin。Metaは一時停止 |
| :24 | primary historical比較 | 既存2023-25 exact rowsから新規COMPARISON_CELL。2022 rows出現後即統合 |
| :36 | V16 2023-25 rows生成 | まず2023 canonical rows artifact+SHA、その後2024→2025。候補探索禁止 |
| :48 | 2022 deterministic再構築 | selector spec受領後、primary 5 candidate rowsを候補単位でもTRADE_ROWS commit |
| :00 | Supervisor | NONE×2・停止・重複を即再配分、STATE/Dashboard writeback |

## P0残タスク

- primary 5 selector/G3 semanticsを既確定2023-25定義からpin。
- deterministic primary-5 2022 canonical rowsを完成し、旧summary不一致ならOLD_SUMMARY_NOT_EXACTLY_REPRODUCED receiptを固定。
- V16別系統の2023/2024/2025 canonical rows + 年別/aggregate metrics完成。
- primary 5の2022-2025 + aggregate全metric完成。
- Meta causal label coverageを2022-2025で完成しmapping SHAをfreeze。
- freeze SHA + STATE許可後だけ2026 one-shot開封。2026結果によるretune禁止。

## GO / NO-GO

**研究継続 / production NO-GO / 2026 SEALED。**