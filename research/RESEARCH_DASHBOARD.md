# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-18 07:58 JST  
> **比較契約:** cost 0%、win = gross return > 0、signal T → next XTKS open → fifth XTKS close。  
> **重要:** 2026はMeta mapping SHA freeze + STATE明示許可までSEALED。production/mainは変更禁止。

## 現在地

**研究全体: 約84%** / **P0 historical比較: 68%** / **Meta地合い切替: 10%**。今回は実成果は出たが、primary比較表の確定セル自体はまだ増えていないため進捗率は据え置き。

## 07:58の実成果

V16 backward-2022 artifact `10266990667` と pinned daily corpus `10264205130` を実ファイル回収して機械監査した。

- V16 backward rows: 31件
- `entry_date > signal_date`: 31/31 PASS
- next XTKS open一致: 31/31 PASS
- fifth XTKS close日一致: 31/31 PASS
- pinned corpusから再計算したreturn一致: 31/31 PASS
- entry/exit endpoint true missing: 0
- picks SHA-256: `68ecf2f0344471c486577c80e67302ba1c17334ed6f2a2dfd0dc414cafab78d6`
- daily corpus SHA-256: `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`

ただし、これは**current primary Phase-2 `volr20 LOW` の2022 exact rowsではない**ことも確定した。V16 backwardは `med_ret5<=0` のみで、current frozen Phase-2は `med_ret5<=0 AND ret10<=0.5735294117647058`。V16はn=31、primary frozenはn=23なので別ledger。誤ってprimaryへ昇格させず、commit `d4404984b25d2b24fdb246edbba998dc4bb21a13` で `EXCLUDED_AS_PRIMARY_PHASE2_VOLR20_2022_SOURCE` と固定。

## 正しい2022 primary復元経路

`research/WEAK_EARLY_PHASE2_2022_FRESH_VALIDATION_20260914.md` がauthoritative source。

- pinned daily corpus artifact `10264205130`
- V7/V9 full 45-feature monthly causal Tail
- `tail_cdf >= 0.999`
- frozen Phase-2 gate `med_ret5 <= 0 AND ret10 <= 0.5735294117647058`
- 2022 reconstructed Tail: **89 extreme Tail candidates**
- gate後: **29 candidate rows / 23 signal dates**
- frozen results: body 23 / volr20 23 / mean-rank 23 / DUAL 21 / DUAL+G3 17

## 現在の最大blocker

**89 → 29 → 23 を作ったexact generator code / command / intermediate artifact chainの回収。**

## 監督による再配分

| Lane | 担当 | 成果条件 |
|---|---|---|
| :12 | Meta exact-chain | Meta 1軸chain completeまたは最小欠損1個固定 |
| :24 | 別系統canonical rows | rows SHA / generator+source SHA / 不足artifact1個解消 |
| :36 | **2022 Phase-2 code鎖** | exact generator path+SHA / command / 89→29→23 select logic |
| :48 | **2022 Phase-2 artifact鎖** | Tail/cache/29-row artifact ID / workflow run/job /保存path |
| :00 | Supervisor | NONE×2・誤系譜・重複を即再配分、STATE/Dashboard writeback |

:36と:48は07:58に再起動済み。07:48時点で停止していた状態を放置しない。

## P0残タスク

- 2022 primary exact generator/artifact chainを回収し、5候補rowsを正規化。
- exact再現可能な別系統候補のcanonical rows。
- primary 5比較のrow必須metric（+20/-20/max up/max down/100株P/L等）。
- Meta causal input chain成立 → pre-2026 exact dataのみでmapping freeze。
- freeze SHA + STATE許可後だけ2026 one-shot開封。

## GO / NO-GO

**研究継続 / production NO-GO / 2026 SEALED。**
