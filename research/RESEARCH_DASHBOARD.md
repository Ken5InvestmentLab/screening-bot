# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 22:26 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## ⏱ 自動研究ハートビート

> **確認時刻:** 2026-09-15 22:26 JST  
> 5本すべて **ENABLED**、90分超の停止疑い **0本**。

| Worker | 直近実行(JST) | 状態 |
|---|---:|---|
| Supervisor :00 | 21:00 | 🟢 GREEN |
| Canonical :12 | 21:12 | 🟢 GREEN |
| Core :24 | 22:24 | 🟢 GREEN / current run |
| Consensus :36 | 21:35 | 🟢 GREEN |
| OSS+Parallel :48 | 21:49 | 🟢 GREEN |

## 📈 全体進捗

**研究全体の進捗率: 約80%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、surrogate/retune禁止、Round2 CLOSED |
| Parallel Wave-1 | 🔴 STALE / P0再指示 | 72% | causal A1/B1/E1 pick ledger → completeness receipt → one-shot cost0 |
| Core24 OHLCV補完 | 🟢 稼働中 | 85% | JPX 375-event ledger導出済み。listed-issues page byte-pin PASS、誤ったcorrection workbookをrejectし `data_e.xlsx` captureへ修正 → PIT receipt → exact-hour evidence |
| Consensus V47 | 🟢 corrected H1 diagnostic完了 / formal raw BLOCKED | 78% | corrected H1はCAP1000_PITがdiagnostic leader。次はCAP1000_PITのみのcorrected H2 prereg/repair |
| Canonical/Shadow endpoint integrity | 🟢 稼働中 | 89% | outcome-blind integrity継続 |
| Core endpoint provenance | 🟢 稼働中 | 96% | JPX publication page SHA固定。`jyoujyou(updated)_e.xlsx` は2022 correction fileと実物確認してreject。current `data_e.xlsx` capture run 34974864648実行中 |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟢 disposition policy固定 | 98% | unresolved findingsはfail-closed |
| V20 Session-Impulse | ⚫ CLOSED | 100% | active queue外 |

## Frozen comparator
DUAL+G3 (`med_ret1 >= -1%`) は n=117 / mean +7.98% / median +1.74% / win 53.85% / Top3-ex +5.14%。2022 fresh robustness FAIL固定、surrogate/retune禁止、Regime Round2 CLOSED。

## Consensus V47
corrected H1 run `34943802848` はSUCCESS、cost 0%、2025-01-06..2025-06-30、next XTKS open → D+5 close。diagnostic leaderはCAP1000_PITだがpromotion evidenceではなくformal raw acceptance未PASS。次は同一contractでCAP1000_PITのみcorrected H2。

## Core24現在地
開始時Core HEAD `80bcd6c1…` はSTATE v92でprocessed済みのため重複処理なし。JPX公式 List of TSE-listed Issues pageをrun `34974570085` でexact-byte captureしSUCCESS。page 30,060 bytes / SHA-256 `19dd761cdf1ef75ce02e84a398c97dc2be4ee44021824756b6450a906cfe9389`。pinned HTMLにはExcel hrefが2本あり、初回selectorが選んだ `jyoujyou(updated)_e.xlsx` をartifactで開くと337 rows、Effective Date=20220428のhistorical correction workbookだったためanchorとしてrejectした。current universeは同pageの `data_e.xlsx`。commit `bf1de1d2…` でselectorをfail-closedに修正し、run `34974864648` でcorrect workbookをcapture中。次はSHA/effective month-end固定 → frozen 375-event ledger reverse replay → PIT membership receipt。

## STALE / blocked / closed
Parallel Wave-1はcausal pick ledgerがP0。Consensus formal rawはYahoo HTTP429/incomplete raw coverageでBLOCKED。Weak+Early、Regime Round2、Cloud exact forensic、V20はCLOSED。

## 残タスク
P0: Consensus corrected H2 prereg/repair、Core24 `data_e.xlsx` bytes/SHA + PIT reverse replay、Parallel causal A1/B1/E1 pick ledger。P1: OSS/EDINET taxonomy、Canonical outcome-blind integrity。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。新規performanceはcost 0%のみ、win=gross return>0。2026はreport/robustness-only。

## GO / NO-GO
**NO-GO / 研究継続。GO候補0件。**
