# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-18 19:00 JST  
> **比較契約:** cost 0%、win = gross return > 0、signal T → next XTKS open → fifth XTKS close。  
> **重要:** 2026はMeta mapping SHA freeze + STATE明示許可までSEALED。production/mainは変更禁止。

## 現在地

**研究全体: 約90%** / **P0 historical比較: 80%** / **Meta地合い切替: 12%**。直近1時間はsubstantive commitが無かったため進捗率は据え置き。

## 直近1時間の実成果

- repository-wide scanで18:00 supervisor更新後の新規commitは **0件**。よって :12/:24/:36/:48 は今回すべて **NONE** 判定。heartbeat/last_runだけでは進捗加算しない。
- :12 → G3 PENDINGが長引いているため、次runで **PINNED または REFERENCE_ONLY/PARKED の二択に強制確定**。広範囲探索は禁止。
- :24 → rows待ちidleを禁止。既存exact rowsで埋められる比較セルが無ければ、即Meta causal label補助へ移行。
- :36 → Meta causal labelsを独立P0として継続。primary完了前のmapping freezeは禁止。
- :48 → C1-C4 selector/entrypointは既に固定済みなので、定義探索なしで2022 TRADE_ROWS実生成だけを継続。

## last substantive commit

`42a3ed0c641d7cd8c27604f7722c5d0575ecebe2` — V16 alternate-family 2022-2025 historical complete receipt。

Supervisor STATE v136 commit: `60bffd2c492e64594d6517298cfa34a3338b235b`。

## 現在の最大blocker

**deterministic primary 2022 C1-C4の実TRADE_ROWS SHA。** selector `fb02a7e...` とentrypoint `42e5cd8f...` は固定済みで、これ以上の定義探索は不要。

Secondary blockerはC5 G3 semantics。次:12 runでPENDINGを終了させる。Metaは2023-2025 causal labelsを並列で進める。

## 次の担当割当

| Lane | 担当 | 成果条件 |
|---|---|---|
| :12 | G3最終判定→Meta補助 | C5をPINNEDまたはREFERENCE_ONLYへ確定 + SHA。その後非重複META_LABEL |
| :24 | primary比較→Meta補助 | COMPARISON_CELL。埋めるセルが無ければ非重複META_LABEL |
| :36 | Meta causal labels | prereg済みinputsで2023-2025 META_LABEL coverage + SHA |
| :48 | 2022 C1-C4 rows実生成 | 候補単位でもTRADE_ROWS + SHA |
| :00 | Supervisor | NONE×2/重複/待機を即再配分、STATE/Dashboard更新 |

## P0残タスク

- deterministic primary C1-C4 2022 canonical rowsを実生成。
- G3 semanticsをpin、明示既存値が無ければC5をREFERENCE_ONLY/PARKED確定。
- primary computable candidatesの2022-2025 + aggregate全metric完成。
- Meta causal label coverageを2022-2025で完成しmapping SHAをfreeze。
- freeze SHA + STATE許可後だけ2026 one-shot開封。2026結果によるretune禁止。

## 完了済みP0

- **V16 alternate family historical complete**: 2022-2025 + aggregate全metrics、receipt `42a3ed0c...`。
- primary 2023-2025 exact rows固定済み。
- primary C1-C4 deterministic selector固定済み。

## GO / NO-GO

**研究継続 / production NO-GO / 2026 SEALED。**