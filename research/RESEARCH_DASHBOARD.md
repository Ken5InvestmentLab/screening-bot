# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 05:00 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## 📈 全体進捗

**研究全体の進捗率: 約69%**

`██████████████░░░░░░ 69%`

### タスク別進捗・稼働状態

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ **CLOSED** | **100%** | 2023-25 ranking + 2022 fresh完了。robustness FAIL、G3凍結、Round2 CLOSED。比較記録としてのみ保持 |
| Parallel Wave-1 新条件探索 | 🟢 **稼働中** | **72%** | source/schema + 独立XTKS calendar固定、endpoint verifier実装。causal pick ledger → receipt → one-shot cost0が残り |
| Core24 OHLCV補完 | 🟢 **稼働中** | **55%** | missing-inventory runner CI GREEN。real expected/raw1H pin → fallback raw → verifier → coverage deltaが残り |
| Consensus V47 raw 1H取得・formal acceptance | 🟠 **外部待機** | **66%** | raw48非terminal。shard 0-3は324/324 HTTP429・usable raw 0。重複trigger禁止 |
| Canonical/Shadow endpoint integrity | 🟢 **稼働中** | **79%** | full hash-provenance chain実装/CI GREEN。link-tamper回帰または次のoutcome-blind controlへ |
| Core endpoint provenance | 🟢 **稼働中** | **70%** | provenance primitive GREEN。real XTKS/vendor manifest + actual receipt + evaluator配線が残り |
| Cloud Monster exact forensic | ⚫ **CLOSED** | **100%** | exact replay一次証拠なし。新しい同時代identity-critical証拠が出た場合だけ再開 |
| OSS / Validation | 🟢 **稼働中** | **86%** | receipt-bound DSRまでGREEN。次のoutcome-blind validation controlへ |
| EDINET same-ZIP cross-check | 🟠 **外部入力待ち** | **35%** | real API keyまたはpinned real ZIP待ち。同じ確認にworker cycleを使わない |
| Supervisor coordination / dashboard | 🟢 **常時稼働** | **92%** | 新HEAD吸収・task state管理・停滞検出・不要task閉鎖を運用中 |
| V20 Session-Impulse | ⚫ **CLOSED / deprioritized** | **100%** | promotion候補から除外。worker cycleを使わない |

**状態:** 🟢 稼働中 / 🟡 整理中 / 🟠 外部待機 / ⚪ 保留 / ⚫ CLOSED / 🔴 STALE。2回連続で同じSHA・同じblocker確認だけならSTALE候補とし、workerを別の安全なpending taskへ再配分する。

## 0. 全体サマリー

| 項目 | 現在 |
|---|---|
| 最終GO候補 | **0件** |
| Weak+Early Phase-2 | **CLOSED**。DUAL+G3が2023-25首位だが2022 fresh FAILED ROBUSTNESS。retune/Round2再開なし |
| 2023-25首位（比較記録） | n117 / mean **+7.98%** / median **+1.74%** / win **53.85%** / Top3-ex **+5.14%** |
| Parallel Wave-1 | source/schema/独立XTKS calendar/endpoint verifier固定。performance未開封 |
| Consensus V47 | raw48 transport blocker / formal acceptance未PASS |
| Canonical/Shadow | full hash-provenance chain実装済み / CI GREEN |
| Core24 OHLCV | SHA-bound real-inventory runner CI GREEN / real raw1H input pin待ち |
| OSS | immutable completed-trial receipt → DSR binding verified / CI GREEN |
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

## 2. 現在のactive queue

**P0:** Parallel causal A1/B1/E1 pick ledger固定→actual endpoint completeness receipt→one-shot cost0。Core24 exact expected/raw1H input pin→one-shot missing inventory→fallback verification。Consensusはraw48 terminal後だけformal merge/acceptance。

**P1:** Canonical link-tamper regression/次のoutcome-blind integrity control。Core endpoint evaluator binding。OSSは次のoutcome-blind validation controlへ。

**外部待機:** EDINET real input。待機確認だけにworker cycleを使わない。

**CLOSED:** Weak+Early Phase-2、Cloud exact forensic、V20。新証拠/明示reopen条件が無い限りactive queueへ戻さない。

## 3. GO / NO-GO

**NO-GO / 研究継続。GO候補0件。** Parallelはperformance未開封、Consensusはformal raw acceptance未PASS、既存Phase-2 leaderはfresh robustness FAIL。検証インフラ改善をperformance改善と混同しない。

production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更しない。
