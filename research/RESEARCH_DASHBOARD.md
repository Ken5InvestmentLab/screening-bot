# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-18 09:00 JST  
> **比較契約:** cost 0%、win = gross return > 0、signal T → next XTKS open → fifth XTKS close。  
> **重要:** 2026はMeta mapping SHA freeze + STATE明示許可までSEALED。production/mainは変更禁止。

## 現在地

**研究全体: 約84%** / **P0 historical比較: 68%** / **Meta地合い切替: 10%**。08時台は新規research SHA / trade rows / comparison cell / Meta labelがまだ増えていないため、heartbeatで進捗率を上げない。

## 直近1時間の監督判定

- :12 Meta exact-chain: ACTIVE。新規evidence SHAはまだ無し → **NONE**。
- :24 alternate-family lane: 08:26 run後に自動停止、新規rows SHA無し → **NONE**。同じalternate-familyを:36と重複させないため、09:00に**primary 5の2023-2025未充足comparison metric専任**へ再起動・再配分。
- :36: 08:35 run、V16 backwardを別系統候補として2023-2025へ正規化中。新規確定SHA待ち → 現時点 **NONE**。
- :48: 08:47 run、2022 Phase-2 artifact chain回収を継続。新規artifact SHA待ち → 現時点 **NONE**。
- :00: worker停止/重複を検知して再配分、STATE v127へwriteback → **NEW_SHA / supervisory reallocation**。

## last substantive commit

`d4404984b25d2b24fdb246edbba998dc4bb21a13` — V16 backward 2022の31 rowsを固定daily corpusで31/31 endpoint一致まで監査し、current primary Phase-2 volr20 n=23とは別契約であることを確定。primaryへの誤昇格を禁止。

09:00の監督STATE更新: `a885a7c5d17e441a6adb45b00f0fb75e18a36d6b`。

## 現在の最大blocker

**primary 2022の89 extreme Tail → 29 frozen gate rows → 23 signal datesを作ったexact generator / intermediate artifact chainが未回収。** 同時に、Meta exact input chainと別系統2023-2025 rowsもまだ新規SHA待ち。

## 次の担当割当

| Lane | 担当 | 成果条件 |
|---|---|---|
| :12 | Meta exact-chain | 1軸META_INPUT_CHAIN_COMPLETE、または最小欠損artifactを1個へ限定 |
| :24 | **primary比較metrics** | 既存2023-2025 exact rowsから +20/-10/-20/max/100株P/L 等のCOMPARISON_CELLを最低1つ追加 |
| :36 | **V16別系統rows正規化** | 2022 spec/source固定 + 同spec 2023-2025 rows SHAを最低1年追加、またはadmissibility NO固定 |
| :48 | **2022 primary artifact鎖** | 89/29 rows artifact ID、run/job ID、保存pathのいずれかを確定 |
| :00 | Supervisor | NONE×2・重複・停止を即再配分、STATE/Dashboard writeback |

## P0残タスク

- 2022 primary exact generator/artifact chain回収 → primary 5 rows正規化。
- exact再現可能な別系統候補の2022-2025 canonical rows。
- primary 5のrow必須comparison metric完成。
- Meta causal input chain成立 → pre-2026 exact dataだけでmapping freeze。
- freeze SHA + STATE許可後だけ2026 one-shot開封。

## GO / NO-GO

**研究継続 / production NO-GO / 2026 SEALED。**
