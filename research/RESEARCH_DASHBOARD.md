# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 17:02 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## ⏱ 自動研究ハートビート

> **確認時刻:** 2026-09-15 17:02 JST  
> 5本すべて **ENABLED**。再arm対象だったCore/Consensusとも実run復帰。90分超の停止疑いは現在0本。

| Worker | 直近実行(JST) | 状態 |
|---|---:|---|
| Supervisor :00 | 17:00 | 🟢 現run |
| Canonical :12 | 15:14 | 🟢 90分以内・次17:12 |
| Core :24 | 16:47 | 🟢 再arm後復帰 |
| Consensus :36 | 16:11 | 🟢 再arm後復帰 |
| OSS+Parallel :48 | 16:48 | 🟢 GREEN |

GitHub最終commit時刻だけでは停止判定しない。task-level停滞とautomation heartbeatは分離する。

## 👤 ユーザー作業待ち

**現在0件。** worker側で継続可能。

## 📈 全体進捗

**研究全体の進捗率: 約75%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、retune禁止、Round2 CLOSED |
| Parallel Wave-1 | 🔴 STALE / P0 | 72% | causal A1/B1/E1 pick ledger SHA固定 → completeness receipt → one-shot cost0 |
| Core24 OHLCV補完 | 🟢 稼働中 | 75% | official JPX PIT exact input bytes/SHA pin → independent exact-hour activity evidence |
| Consensus V47 | 🟠 transport STALE / reuse監査へ再配分 | 67% | raw=0。Core24 SHA-pinned raw1H互換性をoutcome-blind監査 |
| Canonical/Shadow endpoint integrity | 🟢 稼働中 | 88% | durable prewrite resolution chain CI GREEN。次はcrash/orphan recovery semantics |
| Core endpoint provenance | 🟢 稼働中 | 87% | byte-pinned PIT receiptとexact-hour activity sourceが残り |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟢 再実行中 | 92% | full freeze `34940882530` は全年度取得後、同一timestampのtimezone文字列表現差でfalse conflict。UTC instant比較へ修正。fresh OSS `34944518975` / freeze `34944519021` 実行中 |
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

EDINET full freeze `34940882530` は2023/2024/2025の取得自体は成功し、snapshotで docID `S1006Y3L` の重複判定に失敗していた。原因は同じhistorical local timestampが `+09:00` / `+09:18` と異なる文字列でrenderされ、文字列比較がfalse conflictを作ったこと。outcome/returnは開かず、既にparse済みtimestampを**UTC instantで比較**するよう最小修正した。120/130のdocType conflictは引き続きfail-closed。implementation `77116de3…`、audit `4514891a…`。fresh OSS validation `34944518975` とfull freeze `34944519021` が実行中。

heartbeatではCoreが16:47に復帰、Consensusも16:11に復帰し、現時点で90分超停止疑いは0本。

## 残タスク

P0: Parallel causal pick ledger、OSS/EDINET fresh runs terminal監査→sample receipt/selected ZIP SHA固定、Core24 official-JPX exact bytes/SHA pin。  
P1: Canonical crash/orphan recovery semantics、Consensus Core24 raw1H互換性監査。  
CLOSED: Weak+Early Phase-2、Cloud exact forensic、V20。

## GO / NO-GO

**NO-GO / 研究継続。GO候補0件。** production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更しない。
