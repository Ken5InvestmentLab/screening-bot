# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 22:24 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## ⏱ 自動研究ハートビート

> **確認時刻:** 2026-09-15 22:24 JST  
> 5本すべて **ENABLED**、90分超の停止疑い **0本**。

| Worker | 直近実行(JST) | 状態 |
|---|---:|---|
| Supervisor :00 | 21:00 | 🟢 GREEN |
| Canonical :12 | 21:12 | 🟢 GREEN |
| Core :24 | 22:24 | 🟢 GREEN / current run |
| Consensus :36 | 21:35 | 🟢 GREEN |
| OSS+Parallel :48 | 21:49 | 🟢 GREEN |

GitHub最終commit時刻だけでは停止判定しない。task-level停滞とautomation heartbeatは分離する。

## 📈 全体進捗

**研究全体の進捗率: 約80%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、surrogate/retune禁止、Round2 CLOSED |
| Parallel Wave-1 | 🔴 STALE / P0再指示 | 72% | causal A1/B1/E1 pick ledger → completeness receipt → one-shot cost0 |
| Core24 OHLCV補完 | 🟢 稼働中 | 85% | JPX 375-event ledger導出済み。official listed-issues page byte-pin PASS、workbook byte capture実行中 → PIT membership receipt → independent exact-hour activity evidence |
| Consensus V47 | 🟢 corrected H1 diagnostic完了 / formal raw BLOCKED | 78% | corrected H1はCAP1000_PITがdiagnostic leader。次はCAP1000_PITのみのcorrected H2 prereg/repair。formal raw acceptanceは未PASS |
| Canonical/Shadow endpoint integrity | 🟢 稼働中 | 89% | outcome-blind integrity継続 |
| Core endpoint provenance | 🟢 稼働中 | 96% | JPX listed-issues publication pageをexact bytes/SHA固定。公式workbook hrefをpinned bytesから一意に発見し、workbook capture run 34974693057実行中 |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟢 disposition policy固定 | 98% | unresolved findingsはfail-closed、performanceでparser/value選択禁止 |
| V20 Session-Impulse | ⚫ CLOSED | 100% | active queue外 |

## Weak+Early Phase-2 frozen ranking

| Rank | Candidate | n | Mean | Median | Win | Top3-ex | Status |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | **DUAL + G3** | 117 | **+7.98%** | **+1.74%** | **53.85%** | **+5.14%** | frozen comparator / 2022 fresh robustness FAIL |
| 2 | DUAL_TOP1_AGREEMENT | 140 | +7.17% | +1.25% | 52.14% | +4.79% | frozen |
| 3 | mean-rank(volr20,body_pct) | 172 | +6.89% | +1.45% | 52.33% | +4.95% | frozen baseline |
| 4 | body_pct LOW | 172 | +6.54% | +0.99% | 50.58% | +4.60% | frozen baseline |
| 5 | volr20 LOW | 172 | +6.33% | +1.06% | 51.74% | +4.38% | frozen baseline |

G3 = `med_ret1 >= -1%` は**凍結維持**。2022 fresh validationは**ROBUSTNESS FAIL**固定、2022 surrogate/retune禁止。Regime Round2は**CLOSEDのまま再開しない**。

## Consensus V47

corrected H1 run `34943802848` は **SUCCESS**。cost 0%、2025-01-06..2025-06-30、next XTKS open → D+5 closeのdiagnostic leaderはCAP1000_PIT。ただし `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE` でありformal raw acceptanceは未PASS。次はCAP1000_PITだけを同一normalization/cost0/cooldown stateでcorrected H2へ渡す。

## Core24現在地

開始時Core HEAD `80bcd6c1…` はSTATE v92でprocessed済みだったため重複処理なし。JPX公式 `List of TSE-listed Issues` publication pageをActions run `34974570085` でexact-byte captureしSUCCESS。artifact `10399005661` digest `sha256:900252325c56d7d7a966dfba7b789217ca32973e7c1a947972733efd21cf39fa`。pageは30,060 bytes、SHA-256 `19dd761cdf1ef75ce02e84a398c97dc2be4ee44021824756b6450a906cfe9389`。そのpinned bytesから公式workbook href `/english/markets/statistics-equities/misc/tvdivq0000001vg2-att/jyoujyou(updated)_e.xlsx` を一意に発見した。commit `0f274c13…` でworkbook自体のbyte-preserving captureを追加し、run `34974693057` を開始。次はworkbook SHA/effective month-end固定 → frozen 375-event ledgerのreverse replay → PIT membership receipt。

## STALE / blocked / closed

- 🔴 Parallel Wave-1: causal pick ledgerが次P0。XTKS forensic再実行禁止。
- 🟠 Consensus formal raw: systemic Yahoo HTTP429 / incomplete raw coverageでBLOCKED。diagnostic laneはcorrected H2へ前進可能。
- ⚫ Weak+Early Phase-2: CLOSED。2022 fresh FAIL固定。
- ⚫ Regime Round2: CLOSED / DO NOT REOPEN。
- ⚫ Cloud exact forensic: CLOSED。
- ⚫ V20: CLOSED / active queue外。

## 残タスク

P0: Consensus corrected H2 prereg/repair、Core24 official-JPX listed-issues workbook bytes/SHA + PIT reverse replay、Parallel causal A1/B1/E1 pick ledger。  
P1: OSS/EDINET source-grounded taxonomy、Canonical outcome-blind integrity。  
Formal V47 rawは外部transport blocker継続だが、duplicate Yahoo bulk retryはしない。

## Guardrails

production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。新規performanceはcost 0%のみ、win=gross return>0。2026はreport/robustness-only。

## GO / NO-GO

**NO-GO / 研究継続。GO候補0件。**
