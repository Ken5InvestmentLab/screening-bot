# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 14:00 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## ⏱ 自動研究ハートビート

> **確認時刻:** 2026-09-15 14:00 JST  
> 5本すべて **ENABLED**、90分超の停止疑い **0本**。

| Worker | 直近実行(JST) | 状態 |
|---|---:|---|
| Supervisor :00 | 14:00 | 🟢 現run稼働 |
| Canonical :12 | 13:14 | 🟢 GREEN |
| Core :24 | 13:23 | 🟢 GREEN |
| Consensus :36 | 13:38 | 🟢 GREEN |
| OSS+Parallel :48 | 13:47 | 🟢 GREEN |

GitHub最終commit時刻だけでは停止判定しない。task-level停滞とautomation heartbeatは分離する。

## 👤 ユーザー作業待ち

**現在0件。** EDINET_API_KEYは設定・疎通確認済み。Parallel/Consensus/EDINET repair/Core24/Canonicalはいずれもworker側または外部transport/data取得側の課題で、ユーザー操作は不要。新しいSecret・API key・手動ファイル提供などが必須になった場合だけここを「要対応」に変更する。

## 📈 全体進捗

**研究全体の進捗率: 約72%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、retune禁止、Round2 CLOSED |
| Parallel Wave-1 | 🔴 STALE / P0 | 72% | causal A1/B1/E1 pick ledger SHA固定 → completeness receipt → one-shot cost0 |
| Core24 OHLCV補完 | 🟢 稼働中 | 75% | official JPX PIT source route特定済み。exact input bytes/SHA pin → independent exact-hour activity evidence |
| Consensus V47 | 🟠 transport STALE / reuse監査へ再配分 | 67% | formal raw1H run `34849054884` はusable raw=0。単純待機は打切り、V47 frozen inventoryとCore24 SHA-pinned raw1H互換性をoutcome-blind監査。duplicate retry・threshold緩和禁止 |
| Canonical/Shadow endpoint integrity | 🟢 稼働中 | 84% | `fe0e89c5…` processed済み。cross-run shadow receipt chain guard CI `34902927347` PASS |
| Core endpoint provenance | 🟢 稼働中 | 87% | JPX source route確認済み。byte-pinned PIT receiptとexact-hour activity sourceが残り |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | `HISTORICAL_EXACT_REPRO_UNAVAILABLE`。新しいidentity-critical一次証拠時のみ再開 |
| OSS / Validation | 🟠 EDINET repair | 84% | EDINET retry `34922234308` は第2null形でFAIL。exact raw shape→fixture→最小fail-closed修正→再実行 |
| V20 Session-Impulse | ⚫ CLOSED / deprioritized | 100% | active queueから除外 |

## Weak+Early Phase-2 frozen ranking

| Rank | Candidate | n | Mean | Median | Win | Top3-ex | Status |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | **DUAL + G3** | 117 | **+7.98%** | **+1.74%** | **53.85%** | **+5.14%** | frozen comparator / 2022 fresh robustness FAIL |
| 2 | DUAL_TOP1_AGREEMENT | 140 | +7.17% | +1.25% | 52.14% | +4.79% | frozen |
| 3 | mean-rank(volr20,body_pct) | 172 | +6.89% | +1.45% | 52.33% | +4.95% | frozen baseline |
| 4 | body_pct LOW | 172 | +6.54% | +0.99% | 50.58% | +4.60% | frozen baseline |
| 5 | volr20 LOW | 172 | +6.33% | +1.06% | 51.74% | +4.38% | frozen baseline |

G3 = `med_ret1 >= -1%` は**凍結維持**。2022 fresh validationは**FAILED ROBUSTNESS**として固定し、surrogate/retune禁止。Regime Round2は**CLOSEDのまま再開しない**。

## 今回のSupervisor前進

全active research laneの実HEADをSTATEの`last_processed_sha`と照合し、**新規未processed HEADは0件**。したがって既処理SHAを再監査せず、停滞監視とheartbeatを前進させた。5 automationはいずれも13時台に実行済みで停止疑いなし。

タスク単位ではConsensusのYahoo待ちは引き続きSTALE扱いで、Core24 raw1H互換性監査へ再配分済み。ParallelもSTALE/P0のためcausal pick-ledger freezeを次actionとして維持。EDINETは第2null形のexact fixture/minimal fail-closed repairをownerへ維持する。Phase-2順位・G3・fresh 2022 FAIL・Round2 CLOSEDは変更なし。

## 残タスク

P0: Parallel causal pick ledger、OSS/EDINET第2null形のfixture/minimal repair、Core24 official-JPX exact bytes/SHA pin。  
P1: Canonical次のoutcome-blind shadow integrity、Consensus Core24 raw1H互換性監査。  
CLOSED: Weak+Early Phase-2、Cloud exact forensic、V20。

## GO / NO-GO

**NO-GO / 研究継続。GO候補0件。** production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更しない。
