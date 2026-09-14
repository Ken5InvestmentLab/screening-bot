# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 03:29 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## 📈 全体進捗

**研究全体の進捗率: 約64%**

`█████████████░░░░░░░ 64%`

### タスク別進捗・稼働状態

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | 🟡 **整理中** | **90%** | 2023-25 ranking + 2022 fresh完了。robustness FAIL、G3凍結、Round2 CLOSED |
| Parallel Wave-1 新条件探索 | 🟢 **稼働中** | **62%** | exact source schema freeze完了。独立XTKS calendar固定 → endpoint completeness receipt → one-shot cost0開封 |
| Core24 OHLCV補完 | 🟢 **稼働中** | **50%** | fail-closed verifier/source policy/CIに加え、expected−observedからexact missing inventoryを作るoutcome-blind builderを追加。run 34881004528 SUCCESS。次はreal datasetでinventory生成 → fallback raw → verifier → coverage delta |
| Consensus V47 raw 1H取得・formal acceptance | 🟠 **外部待機** | **66%** | raw48非terminal。shard 0/1全429、2/3 fetch中。merge acceptance spec固定済み |
| Canonical/Shadow endpoint integrity | 🟢 **稼働中** | **72%** | completeness guard GREEN。manifest/calendar/receipt/output exact hash bindingが残り |
| Core endpoint provenance | 🟢 **稼働中** | **70%** | provenance primitive GREEN。real XTKS/vendor manifest + actual receipt + evaluator配線が残り |
| Cloud Monster exact forensic | ⚪ **保留 / 閉鎖候補** | **76%** | exact replay一次証拠なし。新しいidentity-critical証拠が無ければactive workから外す |
| OSS / Validation | 🟢 **稼働中** | **80%** | cost0 + immutable trial-ledger GREEN。run_study→DSR receipt bindingが残り |
| EDINET same-ZIP cross-check | 🟠 **外部入力待ち** | **35%** | real API keyまたはpinned real ZIP待ち |
| Supervisor coordination / dashboard | 🟢 **常時稼働** | **87%** | 新HEAD吸収・task state管理・自動再配分を運用中 |
| V20 Session-Impulse | ⚫ **CLOSED / deprioritized** | **100%** | promotion候補から除外。新証拠が無ければworker cycleを使わない |

**状態:** 🟢 稼働中 / 🟡 整理中 / 🟠 外部待機 / ⚪ 保留・閉鎖候補 / ⚫ CLOSED / 🔴 STALE。2回連続で同じSHA・同じblocker確認だけならSTALE候補とし、workerを別の安全なpending taskへ再配分する。

## 0. 全体サマリー

| 項目 | 現在 |
|---|---|
| 最終GO候補 | **0件** |
| Weak+Early Phase-2 | **DUAL+G3**が2023-25首位。ただし2022 fresh **FAILED ROBUSTNESS**、Round2 CLOSED |
| 2023-25首位 | n117 / mean **+7.98%** / median **+1.74%** / win **53.85%** / Top3-ex **+5.14%** |
| Parallel Wave-1 | source bytes + exact schema frozen / performance未開封 |
| Consensus V47 | raw48 transport blocker / formal acceptance未PASS |
| Core24 OHLCV | HEAD `4e038e4e...` / exact missing-inventory builder + contract tests GREEN / real gap handoff待ち / performance再計算禁止 |
| Cloud exact | HOLD / close candidate |
| V20 | **CLOSED / DEPRIORITIZED** |
| 最終判定 | **NO-GO / 研究継続** |

## 1. Weak+Early Phase-2 — frozen cost0

| Rank | Candidate | n | Mean | Median | Win | Top3-ex | Status |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | **DUAL + G3** | 117 | **+7.98%** | **+1.74%** | **53.85%** | **+5.14%** | 2023-25 leader / fresh robustness fail |
| 2 | DUAL_TOP1_AGREEMENT | 140 | +7.17% | +1.25% | 52.14% | +4.79% | fresh fail |
| 3 | mean-rank(volr20,body_pct) | 172 | +6.89% | +1.45% | 52.33% | +4.95% | frozen baseline |
| 4 | body_pct LOW | 172 | +6.54% | +0.99% | 50.58% | +4.60% | frozen baseline |
| 5 | volr20 LOW | 172 | +6.33% | +1.06% | 51.74% | +4.38% | frozen comparator |

G3 `med_ret1 >= -1%` は凍結。2022 fresh: DUAL n21 mean +2.62% / median -6.19% / win 28.57% / Top3-ex -7.55%、DUAL+G3 n17 mean +6.08% / median -6.00% / win 29.41% / Top3-ex -6.26%。**FAILED ROBUSTNESS**。Phase-2 regime Round2はCLOSED。

## 2. Parallel Wave-1

HEAD `c7d5e0b023b5331cfba62186aeae2949e765e3cf`。preserved artifact `10264205130` の `tse_daily.csv` をoutcome-blindに確認し、exact schema receiptを固定した。

- source origin run `34545440155` / preservation run `34599959356`
- CSV SHA-256 `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`
- 4,061,361 data rows / exact header `date,open,high,low,close,volume,symbol`
- A1/B1/E1 thresholds変更なし、performance未開封
- 次: observed price rowsから休日を推測せず、独立XTKS calendar artifact/version/SHAを固定 → next open/fifth close mapping → endpoint completeness receipt → one-shot cost0 batch

## 3. Consensus V47

Run `34849054884` は非terminal。shard 0/1は各81/81 HTTP429、usable raw=0。現時点でshard 2/3が`Fetch raw 1H shard`中、残りmatrix queued。transport failureでありstrategy performance FAILではない。

新HEAD `848cb233c6780c92c0513ebd5e3122885d7964ae` とmerge acceptance specをSupervisor吸収済み。重複trigger禁止。terminal後に全shard receiptを列挙し、genuinely observed rowsだけをprovenance付きmergeしてfrozen acceptanceを再実行する。

Diagnostic-only NOCAP H2: n37 / mean +3.0295% / median +0.3817% / win 51.35% / Top3-ex -0.5393%。promotion evidenceではない。

## 4. Data / Provenance / Validation

**Core24 OHLCV補完:** source policy / fail-closed verifierに加え、`build_missing_inventory(expected, observed)` を実装。expected endpoint keyからobserved keyをexact subtractionし、symbol `.T` / timeframe case / UTC timestampをcanonicalize、observed重複はfail-closed、unexpected observed rowsはinventoryへ混入させずreceiptで別計上する。CI run `34881004528` SUCCESS。Yahoo native優先、Alpha Vantage freeはdaily-only低優先度、Stooqはformal未承認、Google Finance snapshotはcorroboration-only。real missing-pair inventory、fallback raw receipt、accepted/rejected/conflicted counts、coverage deltaが揃うまでformal datasetへ採用せずperformance再計算もしない。

**Canonical/Shadow:** prewrite endpoint completeness guard GREEN。次はdaily manifest + independently pinned XTKS calendar → immutable receipt → resolved output/resolution receiptのexact hash binding。

**Core endpoint provenance:** immutable source receipt primitive GREEN。real XTKS/raw-vendor manifest、actual fetch receipt、canonical evaluator fail-closed配線が残る。

**OSS:** cost0 Optuna contract + immutable completed-trial ledger primitive GREEN。次はrun_study/DSRをreceiptへbinding。

**EDINET:** real API keyまたはpinned real ZIP待ち。待機中はworker cycleを優先消費しない。

**Cloud exact forensic:** `HISTORICAL_EXACT_REPRO_UNAVAILABLE`。新しい同時代identity-critical evidenceが出るまでHOLD。歴史値n63 / mean +9.86%はlegacy evidence。

## 5. 自動継続キュー

P0: Parallel XTKS calendar/endpoint receipt、Core24 real missing inventory生成/fallback verification、Consensus raw48 terminal後のformal merge/acceptance。

P1: Canonical provenance-chain binding、Core endpoint evaluator binding、OSS DSR receipt binding。

P2/待機: EDINET external input。Cloud exactは新証拠が出るまで保留。V20はclosed/deprioritized。

production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更しない。
