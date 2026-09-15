# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 22:00 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## ⏱ 自動研究ハートビート

> **確認時刻:** 2026-09-15 22:00 JST  
> 5本すべて **ENABLED**、90分超の停止疑い **0本**。

| Worker | 直近実行(JST) | 状態 |
|---|---:|---|
| Supervisor :00 | 21:00 | 🟢 GREEN / current run |
| Canonical :12 | 21:12 | 🟢 GREEN |
| Core :24 | 21:24 | 🟢 GREEN |
| Consensus :36 | 21:35 | 🟢 GREEN |
| OSS+Parallel :48 | 21:49 | 🟢 GREEN |

GitHub最終commit時刻だけでは停止判定しない。task-level停滞とautomation heartbeatは分離する。

## 📈 全体進捗

**研究全体の進捗率: 約80%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、surrogate/retune禁止、Round2 CLOSED |
| Parallel Wave-1 | 🔴 STALE / P0再指示 | 72% | causal A1/B1/E1 pick ledger → completeness receipt → one-shot cost0 |
| Core24 OHLCV補完 | 🟢 稼働中 | 84% | JPX exact-byte capture PASS。375-event ledger導出PASS、anchor universe bytes → PIT membership receipt → independent exact-hour activity evidence |
| Consensus V47 | 🟢 corrected H1 diagnostic完了 / formal raw BLOCKED | 78% | corrected H1はCAP1000_PITがdiagnostic leader。次はCAP1000_PITのみのcorrected H2 prereg/repair。formal raw acceptanceは未PASS |
| Canonical/Shadow endpoint integrity | 🟢 稼働中 | 89% | outcome-blind integrity継続 |
| Core endpoint provenance | 🟢 稼働中 | 95% | JPX 6-source exact bytes/SHA固定、375 events（listing 134 / delisting 241 / conflict 0）導出。window-start anchor universeが残り |
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

## Consensus V47 今回の横断回収

STATE pointerが古く、実HEADは `27e9e1e1…` まで進んでいたため横断回収した。corrected H1 run `34943802848` は **SUCCESS**。Core24 nominal OHLCをfrozen normalizationした同一contract、cost 0%、2025-01-06..2025-06-30、next XTKS open → D+5 closeのdiagnosticで、結果は以下。

| Arm | Pair coverage | n | Mean | Median | Win | Top3-ex |
|---|---:|---:|---:|---:|---:|---:|
| NOCAP | 35.3898% | 43 | +1.3817% | -0.7375% | 39.53% | -1.0890% |
| **CAP1000_PIT** | **83.1124%** | **41** | **+1.7117%** | -2.0305% | **43.90%** | -1.3069% |

frozen chooser上の**corrected H1 diagnostic leaderはCAP1000_PIT**。ただしこれは `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE` であり、formal raw acceptanceは依然未PASS。Yahoo authoritative raw run `34849054884` のduplicate triggerは禁止継続。次はH1結果を見て条件変更せず、**CAP1000_PITだけ**を同一normalization/cost0/cooldown stateでcorrected H2へ渡すprereg/repair。旧invalid H1から選ばれたNOCAP H2はranking evidenceに戻さない。

## Core24現在地

Actions artifact `10393968557` の6本のSHA-pinned JPX公式HTML bytesから `2024-09-17..2026-09-10` の **375 events = LISTING 134 + DELISTING 241** をdeterministic導出済み。identity conflict 0、ledger SHA-256 `5babf8d153f243e4be3bab6c8ef2c0f45ff773ca744917329cd97f551788ff28`。event archiveだけではwindow開始時点の既存上場銘柄を確定できないため、official-JPX anchor universe exact bytes/SHA固定がP0。

## STALE / blocked / closed

- 🔴 Parallel Wave-1: 実HEAD `57d28537…` から実質進展なし。XTKS forensicは再実行禁止。causal pick ledgerを次P0として再指示済み。
- 🟠 Consensus formal raw: systemic Yahoo HTTP429 / incomplete raw coverageでBLOCKED。ただしdiagnostic laneはcorrected H2へ前進可能。
- ⚫ Weak+Early Phase-2: CLOSED。2022 fresh FAIL固定。
- ⚫ Regime Round2: CLOSED / DO NOT REOPEN。
- ⚫ Cloud exact forensic: CLOSED。
- ⚫ V20: CLOSED / active queue外。

## 残タスク

P0: Consensus corrected H2 prereg/repair、Core24 official-JPX anchor universe bytes/SHA、Parallel causal A1/B1/E1 pick ledger。  
P1: OSS/EDINET source-grounded taxonomy、Canonical outcome-blind integrity。  
Formal V47 rawは外部transport blocker継続だが、duplicate Yahoo bulk retryはしない。

## Guardrails

production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。新規performanceはcost 0%のみ、win=gross return>0。2026はreport/robustness-only。

## GO / NO-GO

**NO-GO / 研究継続。GO候補0件。**
