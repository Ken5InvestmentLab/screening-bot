# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-18 18:00 JST  
> **比較契約:** cost 0%、win = gross return > 0、signal T → next XTKS open → fifth XTKS close。  
> **重要:** 2026はMeta mapping SHA freeze + STATE明示許可までSEALED。production/mainは変更禁止。

## 現在地

**研究全体: 約90%** / **P0 historical比較: 80%** / **Meta地合い切替: 12%**。V16別系統historicalが正式完了したため実成果として進捗加算。

## 直近1時間の実成果

- :36 → **ALT_HISTORICAL_COMPLETE + NEW_SHA** `42a3ed0c641d7cd8c27604f7722c5d0575ecebe2`。V16別系統の2022/2023/2024/2025 + aggregate全metrics完成。aggregate n=273、mean +1.6188%、median -5.4286%、win 40.6593%、100株P/L -87,422.78円。V16 laneは終了しMeta causal labelsへリレー。
- :48 → 17:49 run後に停止状態だったが、C1-C4は既に実行可能なので停止理由に関係なくP0継続が妥当。再有効化し2022 C1-C4 rows実生成へ戻した。
- :12 → 17:10 run済み。G3 dispositionの新SHAはまだ確認できず。PENDINGを長引かせずPINNED/REFERENCE_ONLYの二択で確定する指示を維持。
- :24 → 17:26 run済み。新規COMPARISON_CELLはまだ確認できず。primary 2022 rows待ちでも既存空欄を埋める方針を維持。

## last substantive commit

`42a3ed0c641d7cd8c27604f7722c5d0575ecebe2` — V16 alternate-family 2022-2025 historical complete receipt。

Supervisor STATE v135 commit: `288fe178880107a31c55ae1dd74609cb114c5e75`。

## 現在の最大blocker

**deterministic primary 2022 C1-C4の実TRADE_ROWS SHA。** selectorとentrypointは既に固定済みなので、これ以上の定義探索は不要。

C5はG3 semanticsの最終dispositionだけ。Metaはprimary完了を待たず、2023-2025 causal label coverageを独立に進められる。

## 次の担当割当

| Lane | 担当 | 成果条件 |
|---|---|---|
| :12 | G3 semantics最終確定 | C5をPINNEDまたはREFERENCE_ONLYへ確定。その後Meta補助へ |
| :24 | primary historical比較 | COMPARISON_CELL追加。2022 rows出現後即統合 |
| :36 | **Meta causal labels** | prereg済みinputsで2023-2025 META_LABEL coverage + SHA |
| :48 | **2022 C1-C4 rows実生成** | 候補単位でもTRADE_ROWS + SHAをcommit |
| :00 | Supervisor | 停止・NONE×2・重複を即再配分、STATE/Dashboard更新 |

## P0残タスク

- deterministic primary C1-C4 2022 canonical rowsを実生成。
- G3 semanticsをpin、存在しなければC5をREFERENCE_ONLY/PARKED確定。
- primary computable candidatesの2022-2025 + aggregate全metric完成。
- Meta causal label coverageを2022-2025で完成しmapping SHAをfreeze。
- freeze SHA + STATE許可後だけ2026 one-shot開封。2026結果によるretune禁止。

## 完了済みP0

- **V16 alternate family historical complete**: 2022-2025 + aggregate全metrics、receipt `42a3ed0c...`。
- primary 2023-2025 exact rows固定済み。
- primary C1-C4 deterministic selector固定済み。

## GO / NO-GO

**研究継続 / production NO-GO / 2026 SEALED。**