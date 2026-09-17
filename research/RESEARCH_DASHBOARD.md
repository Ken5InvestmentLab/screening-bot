# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-18 04:09 JST  
> **比較契約:** cost 0%、win = gross return > 0、signal T → next XTKS open → fifth XTKS close。  
> **重要:** 2026はMeta mapping SHA freeze + STATE明示許可までSEALED。production/mainは変更禁止。

## 📈 現在地

**研究全体: 約84%**  
**P0 historical比較: 68%**  
**Meta地合い切替: 10%（事前登録済み、mapping未freeze）**

共有STATEの書戻し経路を修復した。`research/AUTOMATION_COORDINATION_STATE.json` は2026-09-17 09:38 JSTのv123で停止していた一方、このDashboardだけは02:02 JSTまでSupervisor更新されていた。原因は、各workerのsubstantive receiptが `test/tvfree-screener-v1` 等へcommitされても、`research/automation-coordination` のSTATEへ同期するwritebackが実行されていなかったこと。GitHub Contents APIによるresearch-only branchへの直接updateが利用可能であることを確認し、STATE v124へ更新した。

## 🧭 Supervisor再配分の反映

| Lane | 現在状態 | 固定証拠 |
|---|---|---|
| :12 2022 primary | **exact探索停止 / SUMMARY_ONLY decision COMPLETE** | `d72fe3bd345823c1b02abffc6f5588d6f69c82db` |
| :24 alternate family | **admissibility receipt committed** | `d9db14ab5621bc12a60e810ceca72326b772edfa` |
| :36 G3 | **existing-value receipt専任**。新規performance計算なし | Supervisor再配分をSTATEへ反映。receipt SHAは次回scanで解決 |
| :48 Meta | **input provenance manifest committed** | `b3d17a0b33070d03bbf7c4c16cc2d9b067160c9d` |
| :00 Supervisor | **reassignment / disabled lane recovery** | `5edf1d0174d7f0eb50fb69c35f7fa9eedb6f7df5` |

## 重要判断

- `strict_3pt` は **REFERENCE_ONLY / PARKED**。再探索でP0を塞がない。
- 2022 primary 5のexact rows探索は停止。既開封frozen summaryは `SOURCE=SUMMARY_ONLY` 境界で利用し、row必須metricやMeta labelへ昇格させない。
- **2022 SUMMARY_ONLYをMeta discoveryへ混ぜない。** Metaはexact row + causal input chainが成立する期間だけをSupervisor判断対象にする。
- 2023-2025 primary 5 exact rowsは既確定。再計算しない。
- Meta input provenance manifestはcommit済みだが、mapping freezeとは別物。2026 open条件を満たしていない。

## 🔒 2026 gate

現在: **SEALED**。

開封条件は `research/META_REGIME_SWITCHING_PREREG_20260917.md` に沿ったMeta mappingのSHA freeze後、`AUTOMATION_COORDINATION_STATE.json` に `2026_OPEN_ALLOWED_AFTER_META_FREEZE` 相当の明示状態が入ること。現時点ではその状態ではない。

## 次の最短経路

1. :36 G3 existing-value receiptの実SHA/pathをcoordination STATEへpin。
2. :48 Meta input manifestでexact chainが成立した軸/期間だけを明示し、summary-only 2022を除外。
3. SupervisorがMeta discovery対象期間を決定。
4. preregどおりのmappingをSHA freeze。
5. STATEに明示open許可を書いた後だけ2026を一回開封。

## Guardrails

production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updater変更なし。2023-25再計算なし。2026 outcome未開封。新規条件探索なし。

## GO / NO-GO

**研究継続 / production NO-GO / 2026 SEALED。**
