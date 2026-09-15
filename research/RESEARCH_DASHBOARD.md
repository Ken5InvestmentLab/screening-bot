# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 10:42 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## ⏱ 自動研究ハートビート

> **確認時刻:** 2026-09-15 10:42 JST  
> 5本の研究automationはすべて **ENABLED**。7:12以降も実行継続中。

| Worker | 定刻 | 直近実行(JST) | 状態 |
|---|---:|---:|---|
| Supervisor + WeakEarly | :00 | **10:03** | 🟢 稼働 |
| Canonical + Shadow | :12 | **10:14** | 🟢 稼働 |
| Core + Cloud/Core24 | :24 | **10:26** | 🟢 稼働 |
| Consensus V47 | :36 | **10:34** | 🟠 稼働中 / 外部429待ち |
| OSS + Parallel | :48 | **09:45** | 🟢 稼働 |

> Dashboard/STATEは「実質的な研究変化」があるrunで主に更新されるため、GitHub上の最終更新時刻だけではworker停止を判定しない。今後Supervisorは各巡回でこのheartbeatも更新する。

## 📈 全体進捗

**研究全体の進捗率: 約71%**

`██████████████░░░░░░ 71%`

### タスク別進捗・稼働状態

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ **CLOSED** | **100%** | 2023-25 ranking + 2022 fresh完了。robustness FAIL、G3凍結、Round2 CLOSED。比較記録としてのみ保持 |
| Parallel Wave-1 新条件探索 | 🟢 **稼働中** | **72%** | source/schema + 独立XTKS calendar固定、endpoint verifier実装。`58e67bd2…` が正式pinned artifact SHA。別保存`xtks_sessions.csv`の`74ab…`は別artifact表現でありdriftではない。causal pick ledger → receipt → one-shot cost0が残り |
| Core24 OHLCV補完 | 🟢 **稼働中 / ローカル作業優先** | **73%** | real raw1H 8-shard byte pin PASS。**XTKS 1,220-session CSV/receiptをCoreへ正式pin済み**。次はofficial-JPX PIT source/input receipt固定、その後にindependent exact-hour activity evidence探索 |
| Consensus V47 raw 1H取得・formal acceptance | 🟠 **外部待機 / run稼働中** | **66%** | raw48非terminal、shard 0-3は324/324 HTTP429・usable raw 0、shard 4/5はFetch raw 1H継続中。同じ待機確認だけでは1run使わない |
| Canonical/Shadow endpoint integrity | 🟢 **稼働中** | **82%** | full hash-provenance chain + schema-v2 link-tamper regressionをCI GREEN化。次はresolution-receipt replay/rollback・cross-run continuityのoutcome-blind監査 |
| Core endpoint provenance | 🟢 **稼働中 / ローカル作業優先** | **85%** | observed raw1H byte identity固定 + **Core XTKS byte identity固定済み**。JPX PIT receipt → independent exact-hour activity sourceが残り。Cartesian expected-key生成は禁止 |
| Cloud Monster exact forensic | ⚫ **CLOSED** | **100%** | exact replay一次証拠なし。新しい同時代identity-critical証拠が出た場合だけ再開 |
| OSS / Validation | 🟡 **PIT gap修正待ち** | **84%** | receipt-bound DSRはGREENのまま。次controlでOptunaの`feature_cutoff_column`省略時にPIT証拠を要求しないfail-open境界を検出。明示cutoff/同等PIT receiptを必須化＋future cutoff拒否testが次P0 |
| EDINET same-ZIP cross-check | 🟠 **外部入力待ち** | **35%** | real API keyまたはpinned real ZIP待ち。同じ確認にworker cycleを使わない |
| Supervisor coordination / dashboard | 🟢 **常時稼働** | **95%** | STATE v67。OSS PIT gapとParallel calendar artifact identity照合を反映 |
| V20 Session-Impulse | ⚫ **CLOSED / deprioritized** | **100%** | promotion候補から除外。worker cycleを使わない |

**状態:** 🟢 稼働中 / 🟡 整理中 / 🟠 外部待機 / ⚪ 保留 / ⚫ CLOSED / 🔴 STALE。2回連続で同じSHA・同じblocker確認だけならSTALE候補とし、workerを別の安全なpending taskへ再配分する。外部待機laneは新artifact/terminal変化が無い限り監視だけで1runを消費しない。

## 0. 全体サマリー

| 項目 | 現在 |
|---|---|
| 最終GO候補 | **0件** |
| Weak+Early Phase-2 | **CLOSED**。DUAL+G3が2023-25首位だが2022 fresh FAILED ROBUSTNESS。retune/Round2再開なし |
| 2023-25首位（比較記録） | n117 / mean **+7.98%** / median **+1.74%** / win **53.85%** / Top3-ex **+5.14%** |
| Parallel Wave-1 | source/schema/独立XTKS calendar/endpoint verifier固定。正式calendar SHAは`58e67bd2…`。performance未開封 |
| Consensus V47 | raw48 transport blocker継続 / formal acceptance未PASS / performance evidenceなし |
| Canonical/Shadow | full hash-provenance chain + schema-v2 full link-tamper regression / CI **34893503640 SUCCESS** / performance未開封 |
| Core24 OHLCV | **real observed raw1H 8-shard byte pin PASS**。run `34592896202`、4,019,524 rows、bundle SHA `de7710ad…`。さらにXTKS CSVをCore receiptへ正式pin: SHA `58e67bd2…`、1,220 sessions。JPX PIT receiptsとexact-hour activity evidenceが残り。performance未開封 |
| OSS | immutable completed-trial receipt → DSR binding verified / CI GREEN。**PIT feature cutoff省略可能のgapを新規検出、修正前は新Optuna discoveryをfail-closed扱い** |
| Cloud exact | **CLOSED**。新しいidentity-critical evidenceのみ再開条件 |
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

## 1.5 中締め診断 — promotion evidenceとは分離

- **Consensus V47 NOCAP H2:** `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE`。cost 0%、n=37、mean +3.0295%、median +0.3817%、win 51.35%、Top3-ex -0.5393%。formal raw acceptance未PASSのためpromotion evidenceではない。
- **V20 Session-Impulse:** coverage-bypassed cost0診断は既存結果を維持し、734 symbol/date gap caveatあり。Top1 mean -1.346%、Top2 -1.573%、Top3 -1.118%、Top5 -0.538%。全TopN負のためDEPRIORITIZED/CLOSED。既開封結果からのretuneなし。
- この更新では新規H1/H2/outcome/backtestを開いていない。+10/+20/+50、-10/-20、Top1/Top3除外など未記載項目は**再計算せず**既存artifactが確認できる時だけ追記する。

## 2. 現在のactive queue

**P0:** Parallel causal A1/B1/E1 pick ledger固定→actual endpoint completeness receipt→one-shot cost0。OSSは **Optuna `run_study()` 境界で明示的feature availability/cutoff証拠または同等immutable PIT receiptを必須化し、省略・未来cutoffをfail-closedにする回帰testを追加**。Core24は **official-JPX PIT source/input receipt固定 → independent exact-hour activity evidence探索**。XTKS bytesはCore pin完了。**PIT member × XTKS session × required hour のCartesian生成は禁止**。activity evidenceがPASSした場合だけexpected CSVをSHA固定→one-shot missing inventory→宣言gapだけfallback検証。Consensusはraw48 terminalまたは新しいnon-zero artifactが出た時だけformal merge/acceptanceへ進む。

**P1:** Canonicalはresolution-receipt replay/rollback・cross-run chain continuityをoutcome-blindで監査。Core endpoint evaluator binding。OSS receipt-bound DSRは再確認せず、PIT gap修正完了後に次のidentity/data-integrity controlへ進む。

**外部待機:** EDINET real input。Consensus V47はauthoritative raw48 run自体は継続中だがtransport recovery待ち。Core24のexact-hour activity sourceは、JPX PIT receipt pinning完了後に外部blockerとして扱う。

**CLOSED:** Weak+Early Phase-2、Cloud exact forensic、V20。新証拠/明示reopen条件が無い限りactive queueへ戻さない。

## 3. GO / NO-GO

**NO-GO / 研究継続。GO候補0件。** Parallelはperformance未開封、Consensusはformal raw acceptance未PASS、既存Phase-2 leaderはfresh robustness FAIL。OSSのPIT gapはvalidation infrastructureのfail-closed問題であり、新規performanceは開いていない。Core24のraw byte pinとXTKS provenance pinはdata-integrity進捗でありperformance改善ではない。検証インフラ改善をperformance改善と混同しない。

production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更しない。