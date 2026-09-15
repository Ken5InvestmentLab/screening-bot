# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 10:58 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## ⏱ 自動研究ハートビート

> **確認時刻:** 2026-09-15 10:58 JST  
> 5本の研究automationはすべて **ENABLED**。GitHub Actionsの最終run時刻とChatGPT研究workerの実行時刻は別管理。

| Worker | 定刻 | 直近実行(JST) | 状態 |
|---|---:|---:|---|
| Supervisor + WeakEarly | :00 | **10:03** | 🟢 稼働（この巡回で11時枠処理中） |
| Canonical + Shadow | :12 | **10:14** | 🟢 稼働 |
| Core + Cloud/Core24 | :24 | **10:26** | 🟢 稼働 |
| Consensus V47 | :36 | **10:34** | 🟠 稼働中 / 外部429待ち |
| OSS + Parallel | :48 | **10:45** | 🟢 稼働 |

> 90分超のautomation停止疑いは **0本**。GitHub Actions側の最新runが増えなくても、workerがSTATE/HEAD/artifact監査だけを行う回があるため停止とは限らない。逆に同じSHA/同じblockerだけが2回続くlaneはtask-level STALE候補として次の安全actionへ再配分する。

## 📈 全体進捗

**研究全体の進捗率: 約71%**

`██████████████░░░░░░ 71%`

### タスク別進捗・稼働状態

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ **CLOSED** | **100%** | 2023-25 ranking + 2022 fresh完了。robustness FAIL、G3凍結、Round2 CLOSED。比較記録としてのみ保持 |
| Parallel Wave-1 新条件探索 | 🔴 **TASK STALE候補 / 次action明示済み** | **72%** | HEAD `858998c…` が連続据置。source/schema + 独立XTKS calendar + endpoint verifierまでは固定済み。次の安全actionは **returnsを読まず causal A1/B1/E1 pick ledgerを生成・SHA固定** → completeness receipt → one-shot cost0 |
| Core24 OHLCV補完 | 🟢 **稼働中 / ローカル作業優先** | **73%** | real raw1H 8-shard byte pin PASS。XTKS 1,220-session CSV/receiptをCoreへ正式pin済み。次はofficial-JPX PIT source/input receipt固定、その後にindependent exact-hour activity evidence探索 |
| Consensus V47 raw 1H取得・formal acceptance | 🟠 **外部待機 / run稼働中** | **66%** | raw48 transport blocker。新artifact/terminal変化が無い限り同じ待機確認だけで1runを消費しない |
| Canonical/Shadow endpoint integrity | 🟢 **稼働中** | **82%** | full hash-provenance chain + schema-v2 link-tamper regressionをCI GREEN化。次はresolution-receipt replay/rollback・cross-run continuityのoutcome-blind監査 |
| Core endpoint provenance | 🟢 **稼働中 / ローカル作業優先** | **85%** | observed raw1H byte identity + Core XTKS byte identity固定済み。JPX PIT receipt → independent exact-hour activity sourceが残り。Cartesian expected-key生成は禁止 |
| Cloud Monster exact forensic | ⚫ **CLOSED** | **100%** | exact replay一次証拠なし。新しい同時代identity-critical証拠が出た場合だけ再開 |
| OSS / Validation | 🔴 **P0 STALE候補 / 修正action明示済み** | **84%** | HEAD `65e10483…` 据置。`feature_cutoff_column`省略時のPIT fail-open gapは記録済み。次actionは run_study境界で明示cutoff/同等immutable PIT receiptを必須化し、省略・null/不正・future cutoffを拒否する回帰test → isolated CI |
| EDINET same-ZIP cross-check | 🟠 **外部入力待ち** | **35%** | real API keyまたはpinned real ZIP待ち。同じ確認にworker cycleを使わない |
| Supervisor coordination / dashboard | 🟢 **常時稼働** | **96%** | heartbeatを実worker実行とGitHub Actionsに分離し、task-level STALE候補を明示 |
| V20 Session-Impulse | ⚫ **CLOSED / deprioritized** | **100%** | promotion候補から除外。worker cycleを使わない |

**状態:** 🟢 稼働中 / 🟡 整理中 / 🟠 外部待機 / ⚪ 保留 / ⚫ CLOSED / 🔴 STALE。automation停止とtask停滞を分離して扱う。

## 0. 全体サマリー

| 項目 | 現在 |
|---|---|
| 最終GO候補 | **0件** |
| Weak+Early Phase-2 | **CLOSED**。DUAL+G3が2023-25首位だが2022 fresh FAILED ROBUSTNESS。retune/Round2再開なし |
| 2023-25首位（比較記録） | n117 / mean **+7.98%** / median **+1.74%** / win **53.85%** / Top3-ex **+5.14%** |
| Parallel Wave-1 | performance未開封。task-level停滞を検出し、causal pick ledger固定を次actionとして再明示 |
| Consensus V47 | transport blocker継続 / formal acceptance未PASS / performance evidenceなし |
| Canonical/Shadow | full hash-provenance chain + schema-v2 full link-tamper regression / performance未開封 |
| Core24 OHLCV | real observed raw1H byte pin + XTKS provenance pin PASS。JPX PIT receiptsとexact-hour activity evidenceが残り |
| OSS | receipt-bound DSR GREEN。PIT feature cutoff fail-open gapの実装修正がP0 |
| Cloud exact | **CLOSED** |
| V20 | **CLOSED / DEPRIORITIZED** |
| 最終判定 | **NO-GO / 研究継続** |

## 1. 候補ランキング — frozen cost0 evidence

| Rank | Candidate | n | Mean | Median | Win | Top3-ex | Status |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | **DUAL + G3** | 117 | **+7.98%** | **+1.74%** | **53.85%** | **+5.14%** | frozen comparator / 2022 fresh robustness fail |
| 2 | DUAL_TOP1_AGREEMENT | 140 | +7.17% | +1.25% | 52.14% | +4.79% | fresh fail |
| 3 | mean-rank(volr20,body_pct) | 172 | +6.89% | +1.45% | 52.33% | +4.95% | frozen baseline |
| 4 | body_pct LOW | 172 | +6.54% | +0.99% | 50.58% | +4.60% | frozen baseline |
| 5 | volr20 LOW | 172 | +6.33% | +1.06% | 51.74% | +4.38% | frozen comparator |

G3 `med_ret1 >= -1%` は凍結。2022 fresh: DUAL n21 mean +2.62% / median -6.19% / win 28.57% / Top3-ex -7.55%、DUAL+G3 n17 mean +6.08% / median -6.00% / win 29.41% / Top3-ex -6.26%。**FAILED ROBUSTNESS**。Phase-2 taskは完了・CLOSED。

## 2. 現在のactive queue

**P0:** Parallelは causal A1/B1/E1 pick ledger固定を最優先（returns未開封）→ actual endpoint completeness receipt → one-shot cost0。OSSは `run_study()` 境界で明示的feature availability/cutoff証拠または同等immutable PIT receiptを必須化し、省略・未来cutoffをfail-closedにする回帰testを追加。Core24は official-JPX PIT source/input receipt固定 → independent exact-hour activity evidence探索。Consensusはraw48 terminalまたは新しいnon-zero artifactが出た時だけformal merge/acceptanceへ進む。

**P1:** Canonicalはresolution-receipt replay/rollback・cross-run chain continuityをoutcome-blindで監査。Core endpoint evaluator binding。

**外部待機:** EDINET real input、Consensus transport recovery。外部待機だけでworker cycleを消費しない。

**CLOSED:** Weak+Early Phase-2、Cloud exact forensic、V20。

## 3. GO / NO-GO

**NO-GO / 研究継続。GO候補0件。** Parallelはperformance未開封、Consensusはformal raw acceptance未PASS、既存Phase-2 leaderはfresh robustness FAIL。OSSのPIT gapはvalidation infrastructureのfail-closed問題であり、新規performanceは開いていない。検証インフラ改善をperformance改善と混同しない。

production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更しない。