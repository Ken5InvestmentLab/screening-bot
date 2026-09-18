# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-18 17:00 JST  
> **比較契約:** cost 0%、win = gross return > 0、signal T → next XTKS open → fifth XTKS close。  
> **重要:** 2026はMeta mapping SHA freeze + STATE明示許可までSEALED。production/mainは変更禁止。

## 現在地

**研究全体: 約88%** / **P0 historical比較: 75%** / **Meta地合い切替: 10%**。今回はheartbeatではなく、primary C1-C4 selector exact pinとV16 canonical rowsの2025までの前進が出たため正式に進捗加算。

## 直近1時間の実成果

- :12 → **NEW_SHA + RECEIPT** `fb02a7e124836668999fc6ee4f484a2c1a94fbc6`。C1 body_pct LOW / C2 volr20 LOW / C3 mean-rank / C4 DUAL_TOP1_AGREEMENT のdeterministic selector、tie-break、required columnsを性能非依存でpin。C5だけG3 semantics待ちでfail-closed。
- :36 → **TRADE_ROWS + NEW_SHA**。V16別系統は2025 canonical rowsまで進み、full artifact fix `710b948c...`、receipt `b9e245e01d03bf1e3287599757167eed4354f94a`。2024 receipt `4c80304d...` も固定済み。
- :48 → C1-C4 selector blockerが解除されたため、C5を待たず2022 C1-C4 canonical rows実生成へ即切替。
- :24 → 新規COMPARISON_CELLは未確認。既存2023-25 exact rowsの空欄埋めを継続。

## last substantive commit

`b9e245e01d03bf1e3287599757167eed4354f94a` — V16 alternate-family 2025 canonical rows receipt。primary selector側は `fb02a7e124836668999fc6ee4f484a2c1a94fbc6`。

Supervisor STATE v134 commit: `a4d7a20add5557258c47aa177648365f0f94afd5`。

## 現在の最大blocker

**primary 2022 C1-C4の実TRADE_ROWS SHA。** selector定義はもうblockerではない。:48は追加探索やG3待ちをせずrows生成へ直結。

C5は **G3 NO_ACUTE_SELLOFF value semantics** の1点だけを:12が限定回収し、見つからなければREFERENCE_ONLY/PARKEDへ確定してPENDINGを終わらせる。

別系統V16はrows生成blockerをほぼ抜けたため、次は**2022-2025年別+aggregate全metricsとALT_HISTORICAL_COMPLETE receipt**。

## 次の担当割当

| Lane | 担当 | 成果条件 |
|---|---|---|
| :12 | **G3 semantics pin** | C5をPINNEDまたはREFERENCE_ONLYへ確定。PENDING継続禁止。その後Meta準備へ復帰 |
| :24 | primary historical比較 | 既存2023-25 exact rowsから新規COMPARISON_CELL。2022 rows出現後即統合 |
| :36 | **V16 metrics完成** | 不足年だけ補完し、年別+aggregate全metrics + ALT_HISTORICAL_COMPLETE |
| :48 | **2022 C1-C4 rows実生成** | C1→C4を候補単位でもcanonical rows artifact+SHAとしてcommit |
| :00 | Supervisor | NONE×2・停止・重複を即再配分、STATE/Dashboard writeback |

## P0残タスク

- deterministic primary C1-C4 2022 canonical rowsを実生成。
- G3 semanticsを既存値からpin、存在しなければC5をREFERENCE_ONLY/PARKED確定。
- V16別系統の2022/2023/2024/2025 + aggregate全metricを完成しALT_HISTORICAL_COMPLETE。
- primary computable candidatesの2022-2025 + aggregate全metric完成。
- Meta causal label coverageを2022-2025で完成しmapping SHAをfreeze。
- freeze SHA + STATE許可後だけ2026 one-shot開封。2026結果によるretune禁止。

## GO / NO-GO

**研究継続 / production NO-GO / 2026 SEALED。**