# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 13:04 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## ⏱ 自動研究ハートビート

> **確認時刻:** 2026-09-15 13:04 JST  
> 5本すべて **ENABLED**、90分超の停止疑い **0本**。

| Worker | 直近実行(JST) | 状態 |
|---|---:|---|
| Supervisor :00 | 13:00 | 🟢 現run稼働 |
| Canonical :12 | 12:14 | 🟢 GREEN |
| Core :24 | 12:27 | 🟢 GREEN |
| Consensus :36 | 12:39 | 🟢 GREEN |
| OSS+Parallel :48 | 12:49 | 🟢 GREEN |

GitHub最終commit時刻だけでは停止判定しない。task-level停滞とautomation heartbeatは分離する。

## 📈 全体進捗

**研究全体の進捗率: 約72%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、retune禁止、Round2 CLOSED |
| Parallel Wave-1 | 🔴 STALE / P0 | 72% | causal A1/B1/E1 pick ledger SHA固定 → completeness receipt → one-shot cost0 |
| Core24 OHLCV補完 | 🟢 稼働中 | 75% | official JPX PIT source route特定済み。exact input bytes/SHA pin → independent exact-hour activity evidence |
| Consensus V47 | 🟠 **transport STALE / reuse監査へ再配分** | 67% | formal raw1H run `34849054884` はusable raw=0のまま長時間停滞。単純待機を打切り、V47 frozen inventoryとCore24のSHA-pinned observed raw1Hの互換性をoutcome-blind監査へ。threshold緩和・duplicate retry禁止 |
| Canonical/Shadow endpoint integrity | 🟢 稼働中 | 84% | 新HEAD `fe0e89c5…`監査済み。cross-run shadow receipt chain guardをCIへ接続、run `34902927347` PASS |
| Core endpoint provenance | 🟢 稼働中 | 87% | JPX source route確認済み。byte-pinned PIT receiptとexact-hour activity sourceが残り |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | `HISTORICAL_EXACT_REPRO_UNAVAILABLE`。新しいidentity-critical一次証拠時のみ再開 |
| OSS / Validation | 🟠 EDINET repair | 84% | EDINET retry `34922234308` は第2のnull形でFAIL。exact raw shape→fixture→最小fail-closed修正→再実行をownerへ固定 |
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

Canonical `fe0e89c5…` とConsensus `5a205f4e…` はSTATE上未processedだったため差分監査し、processed SHAへ昇格した。Canonicalは既存chain guardをCI対象へ追加しただけで、run `34902927347` はPASS、performance未開封。Consensusは8 shardまで進んだがusable rawは0で、HTTP429 transport failureの追加確認のみ。戦略成績として扱わない。

EDINETは取得自体ではなくfreeze正規化の第2null形が残る。skip条件を広げるのは禁止し、exact failing raw rowをfixture化してから最小修正する。ParallelはHEAD据置のためSTALE/P0を維持し、次actionをcausal pick-ledger freezeに固定。

## 残タスク

P0: Parallel causal pick ledger、OSS/EDINET第2null形のfixture/minimal repair、Core24 official-JPX exact bytes/SHA pin。  
P1: Canonical次のoutcome-blind shadow integrity、Consensusは新しいreal raw/terminal evidenceのみ処理。  
CLOSED: Weak+Early Phase-2、Cloud exact forensic、V20。

## GO / NO-GO

**NO-GO / 研究継続。GO候補0件。** production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更しない。
