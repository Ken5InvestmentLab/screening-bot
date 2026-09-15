# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 17:57 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## ⏱ 自動研究ハートビート

> **確認時刻:** 2026-09-15 17:57 JST  
> 5本すべて **ENABLED**、90分超の停止疑いは0本。

| Worker | 直近実行(JST) | 状態 |
|---|---:|---|
| Supervisor :00 | 17:00 | 🟢 GREEN / current run |
| Canonical :12 | 17:15 | 🟢 GREEN |
| Core :24 | 17:27 | 🟢 GREEN |
| Consensus :36 | 17:36 | 🟢 GREEN |
| OSS+Parallel :48 | 17:46 | 🟢 GREEN |

GitHub最終commit時刻だけでは停止判定しない。task-level停滞とautomation heartbeatは分離する。

## 👤 ユーザー作業待ち

**現在0件。** worker側で継続可能。

## 📈 全体進捗

**研究全体の進捗率: 約76%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、retune禁止、Round2 CLOSED |
| Parallel Wave-1 | 🔴 STALE / P0 | 72% | causal A1/B1/E1 pick ledger SHA固定 → completeness receipt → one-shot cost0 |
| Core24 OHLCV補完 | 🟢 稼働中 | 77% | official JPX exact bytes/SHA + deterministic membership receipt → independent exact-hour activity evidence |
| Consensus V47 | 🟠 transport STALE / reuse監査へ再配分 | 67% | raw=0。Core24 SHA-pinned raw1H互換性をoutcome-blind監査 |
| Canonical/Shadow endpoint integrity | 🟢 稼働中 | 88% | outcome-blind integrity継続 |
| Core endpoint provenance | 🟢 稼働中 | 89% | PIT byte-pin contract固定。実bytes/receiptとexact-hour activity sourceが残り |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟢 metadata freeze PASS | 95% | EDINET full freeze `34944519021` SUCCESS。frozen sample artifact `10387200654` digest `91f9c369…`。次はselected ZIP byte SHA固定 → same-ZIP parser cross-check |
| V20 Session-Impulse | ⚫ CLOSED / deprioritized | 100% | active queue外 |

## Weak+Early Phase-2 frozen ranking

| Rank | Candidate | n | Mean | Median | Win | Top3-ex | Status |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | **DUAL + G3** | 117 | **+7.98%** | **+1.74%** | **53.85%** | **+5.14%** | frozen comparator / 2022 fresh robustness FAIL |
| 2 | DUAL_TOP1_AGREEMENT | 140 | +7.17% | +1.25% | 52.14% | +4.79% | frozen |
| 3 | mean-rank(volr20,body_pct) | 172 | +6.89% | +1.45% | 52.33% | +4.95% | frozen baseline |
| 4 | body_pct LOW | 172 | +6.54% | +0.99% | 50.58% | +4.60% | frozen baseline |
| 5 | volr20 LOW | 172 | +6.33% | +1.06% | 51.74% | +4.38% | frozen baseline |

G3 = `med_ret1 >= -1%` は**凍結維持**。2022 fresh validationは**FAILED ROBUSTNESS**固定、surrogate/retune禁止。Regime Round2は**CLOSEDのまま再開しない**。

## 今回のSupervisor前進

EDINET timezone invariant修正後のfull-freeze run `34944519021` をterminal監査し、**SUCCESS**を確認。2023/2024/2025の全year artifact取得とfrozen metadata/sample artifact生成まで完了した。frozen sample artifact IDは `10387200654`、artifact digestは `sha256:91f9c36947a6e215848708c34ebe4bc6841777aad302826fd06fa4de464586f6`。year artifact digestもSTATEへ固定した。performanceは未開封。

これでEDINET laneは「metadata/sample freeze失敗の原因探索」から抜け、次の事前登録済み段階である **selected filing ZIPのexact bytes/SHA固定 → 同一ZIPを自作parserとedinet-toolsでcross-check** へ進める状態になった。

## 残タスク

P0: Parallel causal pick ledger、OSS/EDINET selected ZIP SHA freeze→same-ZIP parser cross-check、Core24 official-JPX exact bytes/SHA pin + deterministic PIT membership receipt。  
P1: Canonical次のoutcome-blind integrity、Consensus Core24 raw1H互換性監査、Core independent exact-hour activity evidence。  
CLOSED: Weak+Early Phase-2、Cloud exact forensic、V20。

## GO / NO-GO

**NO-GO / 研究継続。GO候補0件。** production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更しない。
