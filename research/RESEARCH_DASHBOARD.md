# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 19:59 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## ⏱ 自動研究ハートビート

> **確認時刻:** 2026-09-15 19:59 JST  
> Heartbeat監査で **Canonical :12 がDISABLEDになっている実不整合を検出**。20:12開始・1時間周期で再arm済み。他4本はENABLED。90分超の停止疑いは0本だが、Canonicalは次回実run確認まで🟠。

| Worker | 直近実行(JST) | 状態 |
|---|---:|---|
| Supervisor :00 | 18:58 | 🟢 GREEN / current run |
| Canonical :12 | 19:11 | 🟠 DISABLED検出→再arm、次回20:12 |
| Core :24 | 19:26 | 🟢 GREEN |
| Consensus :36 | 19:36 | 🟢 GREEN |
| OSS+Parallel :48 | 19:48 | 🟢 GREEN |

GitHub最終commit時刻だけでは停止判定しない。task-level停滞とautomation heartbeatは分離する。

## 👤 ユーザー作業待ち

**現在0件。** worker側で継続可能。

## 📈 全体進捗

**研究全体の進捗率: 約78%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、retune禁止、Round2 CLOSED |
| Parallel Wave-1 | 🔴 STALE / P0 | 72% | causal A1/B1/E1 pick ledger SHA固定 → completeness receipt → one-shot cost0 |
| Core24 OHLCV補完 | 🟢 稼働中 | 79% | official JPX archive URL map解決済み → exact source bytes/SHA capture → deterministic membership receipt → independent exact-hour activity evidence |
| Consensus V47 | 🟠 transport STALE / reuse監査へ再配分 | 67% | raw=0。Core24 SHA-pinned raw1H互換性をoutcome-blind監査 |
| Canonical/Shadow endpoint integrity | 🟠 worker再arm | 88% | research state自体はactive。automationがdisabled化していたため20:12へ再arm。実run復帰確認後outcome-blind integrity継続 |
| Core endpoint provenance | 🟢 稼働中 | 91% | 2024/2025/2026 official JPX listing+delisting archive URL map解決。exact byte captureが残り |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟢 disposition policy固定 | 98% | same-ZIP 44 comparable / 17 all-match / 27 findings / 4 unavailable。全mismatch/one-sided missingはaudit findingとしてfail-closed。semantic correctionはsource-grounded evidence+regression test必須、同じfrozen sampleで再実行。performanceでparser/value選択禁止 |
| V20 Session-Impulse | ⚫ CLOSED / deprioritized | 100% | active queue外 |

## Weak+Early Phase-2 frozen ranking

| Rank | Candidate | n | Mean | Median | Win | Top3-ex | Status |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | **DUAL + G3** | 117 | **+7.98%** | **+1.74%** | **53.85%** | **+5.14%** | frozen comparator / 2022 fresh robustness FAIL |
| 2 | DUAL_TOP1_AGREEMENT | 140 | +7.17% | +1.25% | 52.14% | +4.79% | frozen |
| 3 | mean-rank(volr20,body_pct) | 172 | +6.89% | +1.45% | 52.33% | +4.95% | frozen baseline |
| 4 | body_pct LOW | 172 | +6.54% | +0.99% | 50.58% | +4.60% | frozen baseline |
| 5 | volr20 LOW | 172 | +6.33% | +1.06% | 51.74% | +4.38% | frozen baseline |

G3 = `med_ret1 >= -1%` は凍結維持。2022 fresh validationはFAILED ROBUSTNESS固定、surrogate/retune禁止。Regime Round2はCLOSEDのまま再開しない。

## 今回のSupervisor前進

Heartbeatをautomation実体で再監査したところ、前回dashboardが5本ENABLEDとしていた一方、**Canonical :12だけ実際にはdisabled**になっていた。研究commit時刻だけでは見つからない種類の停止なので、CanonicalをAsia/Tokyo 20:12開始・hourly exact cadenceで再armした。20:12の実runが復帰確認ポイント。

研究側ではEDINET same-ZIP findingsのdispositionをpreregistered contractに沿って固定した。契約上、mismatchまたはone-sided missingはすべてaudit findingで、research admissionはfail-closed。48-doc primary sampleは変更せず、source-available 44-docだけparser diagnostic対象、source-unavailable 4-docは親文書・後続文書等で置換しない。27 findingsについて、performanceでcustom/OSSの値を選ぶことは禁止し、semantic/source-groundedな根拠とreal-file regression testが揃った修正だけ同じfrozen sampleへ適用可能とした。strategy outcomes/performanceは開いていない。

## 停滞監視

- Parallel Wave-1: 🔴 STALE。P0 causal pick ledger未着手。:48 ownerへ継続指示。
- Consensus V47: 🟠 external transport STALE。Yahoo duplicate retry禁止、Core24 raw1H互換性監査へ再配分。
- Canonical: 🟠 automation disabledを検出し再arm。20:12実run確認待ち。
- Core24: active。exact byte capture待ち。
- OSS: active。27 findingsのsource-grounded taxonomyへ。
- Weak+Early Phase-2 / Cloud exact forensic / V20: CLOSED。

## 残タスク

P0: Canonical 20:12 heartbeat復帰確認、Parallel causal pick ledger、Core24 official-JPX exact bytes/SHA pin → deterministic PIT membership receipt。  
P1: OSS/EDINET 27 findingsのsource-grounded taxonomy、Consensus Core24 raw1H互換性監査、Core independent exact-hour activity evidence、Canonical次のoutcome-blind integrity。  
CLOSED: Weak+Early Phase-2、Cloud exact forensic、V20。

## GO / NO-GO

**NO-GO / 研究継続。GO候補0件。** production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更しない。
