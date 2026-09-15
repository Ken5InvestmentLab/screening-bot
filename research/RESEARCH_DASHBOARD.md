# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 18:57 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## ⏱ 自動研究ハートビート

> **確認時刻:** 2026-09-15 18:57 JST  
> 5本すべてENABLED。90分超の停止疑いは **0本**。

| Worker | 直近実行(JST) | 状態 |
|---|---:|---|
| Supervisor :00 | 18:58 | 🟢 GREEN / current run |
| Canonical :12 | 18:10 | 🟢 GREEN |
| Core :24 | 18:23 | 🟢 GREEN |
| Consensus :36 | 18:38 | 🟢 GREEN |
| OSS+Parallel :48 | 18:46 | 🟢 GREEN |

GitHub最終commit時刻だけでは停止判定しない。task-level停滞とautomation heartbeatは分離する。

## 👤 ユーザー作業待ち

**現在0件。** worker側で継続可能。

## 📈 全体進捗

**研究全体の進捗率: 約77%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、retune禁止、Round2 CLOSED |
| Parallel Wave-1 | 🔴 STALE / P0 | 72% | causal A1/B1/E1 pick ledger SHA固定 → completeness receipt → one-shot cost0 |
| Core24 OHLCV補完 | 🟢 稼働中 | 78% | official JPX archive/raw byte transport解決 → exact bytes/SHA + deterministic membership receipt → independent exact-hour activity evidence |
| Consensus V47 | 🟠 transport STALE / reuse監査へ再配分 | 67% | raw=0。Core24 SHA-pinned raw1H互換性をoutcome-blind監査 |
| Canonical/Shadow endpoint integrity | 🟢 稼働中 | 88% | outcome-blind integrity継続 |
| Core endpoint provenance | 🟢 稼働中 | 90% | PIT byte-pin contract固定。exact archive/raw byte transportが残り |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟢 same-ZIP audit完了・findings分類へ | 97% | metadata freeze PASS。same-ZIP crosscheck 44 comparable / 17 all-match / 27 parser findings / 4 source unavailable / exceptions 0。次はfindingsをoutcome-blind分類しavailability-safe disposition固定 |
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

未処理だったEDINET same-ZIP crosscheckを回収した。run `34944902155` はSUCCESS、artifact `10386890723` / digest `sha256:2affc141851b7701490866be5ddfd35b740ac15e3a0bd48670d2aba3127f96a7`。

凍結primary sample 48文書のうち、**44文書をcustom parserとedinet-toolsで同一ZIP比較**でき、4文書はsource unavailableとして置換しなかった。44文書中 **17文書は全比較field一致、27文書にparser finding、parser exceptionは0**。主なfield別結果は assets/equity/operating_income が各41 MATCH、net_incomeは17 MATCH + 24 OSS側missing/custom側value + 3 both missing、operating_cfは23 MATCH + 21 both missing、revenueとshares_outstandingは各22 MATCH + 22 both missing。custom側missing/OSS側valueはassets/equity/operating_incomeで各3件。

重要なのは、これは**performanceでparserを選ぶための比較ではない**こと。strategy outcomeは未開封、parser出力後のsample selection変更も0。次は27 findingsをtaxonomy化し、availability policyを変えずに安全に採用可能なalias/context差と、単なる一方missingを分離してreceipt化する。OSS CI `34944942675` もSUCCESS。

## 停滞監視

- Parallel Wave-1: 🔴 STALE。processed HEADのままP0 pick-ledger未着手状態が継続。:48 ownerへ causal ledger freeze を明示済み。
- Consensus V47: 🟠 external transport STALE。Yahoo duplicate retryは禁止。Core24 raw1H互換性監査へ再配分済み。
- Core24: active。JPX raw-byte transport blockerは残るが18:23にworker実行あり。
- Canonical: active。processed SHA重複処理なし。
- Weak+Early Phase-2 / Cloud exact forensic / V20: CLOSEDのまま。

## 残タスク

P0: Parallel causal pick ledger、OSS/EDINET 27 parser findingsのoutcome-blind分類・availability-safe disposition、Core24 official-JPX archive/raw byte transport→exact bytes/SHA pin + deterministic PIT membership receipt。  
P1: Canonical次のoutcome-blind integrity、Consensus Core24 raw1H互換性監査、Core independent exact-hour activity evidence。  
CLOSED: Weak+Early Phase-2、Cloud exact forensic、V20。

## GO / NO-GO

**NO-GO / 研究継続。GO候補0件。** production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更しない。
