# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 11:58 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## ⏱ 自動研究ハートビート

> **確認時刻:** 2026-09-15 11:58 JST  
> 5本の研究automationはすべて **ENABLED**。90分超の停止疑い **0本**。

| Worker | 定刻 | 直近実行(JST) | 状態 |
|---|---:|---:|---|
| Supervisor + WeakEarly | :00 | **10:59** | 🟢 稼働（11時枠処理中） |
| Canonical + Shadow | :12 | **11:10** | 🟢 稼働 / 新HEADあり |
| Core + Cloud/Core24 | :24 | **11:24** | 🟢 稼働 |
| Consensus V47 | :36 | **11:35** | 🟢 稼働 / 新HEADあり |
| OSS + Parallel | :48 | **11:50** | 🟢 稼働 / EDINET修復 |

## 📈 全体進捗

**研究全体の進捗率: 約72%**

`██████████████░░░░░░ 72%`

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ **CLOSED** | **100%** | 2023-25 ranking + 2022 fresh完了。robustness FAIL、G3凍結、Round2 CLOSED |
| Parallel Wave-1 新条件探索 | 🔴 **STALE / P0 action明示** | **72%** | HEAD `858998c…` 据置。returns未開封で causal A1/B1/E1 pick ledger SHA固定が次action |
| Core24 OHLCV補完 | 🟢 **稼働中** | **73%** | JPX PIT receipt → independent exact-hour activity evidence |
| Consensus V47 | 🟢 **新HEAD未監査** | **67%** | HEAD `5a205f4e…` に進展。ownerが差分監査。実rawがあれば0% diagnosticのみ |
| Canonical/Shadow endpoint integrity | 🟢 **新HEAD未監査** | **83%** | HEAD `fe0e89c5…` に進展。ownerが差分監査しreplay/rollback・continuityへ |
| Core endpoint provenance | 🟢 **稼働中** | **85%** | JPX PIT receiptとexact-hour activity sourceが残り |
| Cloud Monster exact forensic | ⚫ **CLOSED** | **100%** | 新しいidentity-critical一次証拠が出た場合だけ再開 |
| OSS / Validation | 🟢 **EDINET修復 + PIT P0** | **84%** | EDINET修復後、feature cutoff fail-closed patch/testsへ戻る |
| EDINET same-ZIP cross-check | 🟠 **2回目freeze FAIL / 修復継続** | **45%** | API取得は2023/24/25すべて成功。retry `34922234308` は `2023-01-10 row 292` の別null形でfreeze停止。**生rowを確認する前にskip条件を広げない**。exact-shape fixture→最小修正→再実行 |
| Supervisor coordination | 🟢 **常時稼働** | **96%** | heartbeat・新HEAD・STALE・blockerを再配分 |
| V20 Session-Impulse | ⚫ **CLOSED / deprioritized** | **100%** | active queue外 |

## 0. 全体サマリー

**最終GO候補: 0件 / NO-GO・研究継続。** Phase-2の順位・G3・fresh判定は変更なし。新しいperformanceは開いていない。

## 1. 候補ランキング — frozen cost0 evidence

| Rank | Candidate | n | Mean | Median | Win | Top3-ex | Status |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | **DUAL + G3** | 117 | **+7.98%** | **+1.74%** | **53.85%** | **+5.14%** | frozen comparator / 2022 fresh robustness fail |
| 2 | DUAL_TOP1_AGREEMENT | 140 | +7.17% | +1.25% | 52.14% | +4.79% | fresh fail |
| 3 | mean-rank(volr20,body_pct) | 172 | +6.89% | +1.45% | 52.33% | +4.95% | frozen baseline |
| 4 | body_pct LOW | 172 | +6.54% | +0.99% | 50.58% | +4.60% | frozen baseline |
| 5 | volr20 LOW | 172 | +6.33% | +1.06% | 51.74% | +4.38% | frozen comparator |

G3 `med_ret1 >= -1%` は**凍結**。2022 fresh: DUAL n21 mean +2.62% / median -6.19% / win 28.57% / Top3-ex -7.55%、DUAL+G3 n17 mean +6.08% / median -6.00% / win 29.41% / Top3-ex -6.26%。**FAILED ROBUSTNESS**。retune禁止。Regime Round2は**CLOSED**のまま。

## 2. Active queue

**P0:** EDINETは `2023-01-10 row 292` のraw shapeを先に確認し、exact fixture→最小例外→retry。Parallelはcausal pick ledger固定。OSSはその後PIT feature-cutoff fail-closed patch。  
**P1:** Canonical新HEAD `fe0e89c5…` とConsensus新HEAD `5a205f4e…` を各ownerがprocessed SHAと照合して差分監査。Core24はJPX PIT provenance継続。  
**ユーザー作業待ち:** **0件**。EDINET API keyは正常。  
**CLOSED:** Weak+Early Phase-2、Cloud exact forensic、V20。

## 3. GO / NO-GO

**NO-GO / 研究継続。** 既存Phase-2 leaderはfresh robustness FAIL。Parallelはperformance未開封。EDINETはvalidation補助監査でGOを直接blockしない。production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更しない。
