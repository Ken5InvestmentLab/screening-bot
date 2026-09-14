# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 03:57 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## 📈 全体進捗

**研究全体の進捗率: 約65%**

`█████████████░░░░░░░ 65%`

### タスク別進捗・稼働状態

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | 🟡 **整理中** | **90%** | 2023-25 ranking + 2022 fresh完了。robustness FAIL、G3凍結、Round2 CLOSED |
| Parallel Wave-1 新条件探索 | 🟢 **稼働中** | **62%** | exact source schema freeze完了。独立XTKS calendar固定 → endpoint completeness receipt → one-shot cost0開封 |
| Core24 OHLCV補完 | 🟢 **稼働中** | **50%** | exact missing-inventory builder CI GREEN。real dataset inventory → fallback raw → verifier → coverage deltaが残り |
| Consensus V47 raw 1H取得・formal acceptance | 🟠 **外部待機** | **66%** | raw48非terminal。shard 0/1全429、2/3 fetch中。merge acceptance spec固定済み |
| Canonical/Shadow endpoint integrity | 🟢 **稼働中** | **74%** | completeness guard GREENに加え、exact hash-provenance-chain contractを凍結。実装・CIが残り |
| Core endpoint provenance | 🟢 **稼働中** | **70%** | provenance primitive GREEN。real XTKS/vendor manifest + actual receipt + evaluator配線が残り |
| Cloud Monster exact forensic | ⚪ **保留 / 閉鎖候補** | **76%** | exact replay一次証拠なし。新しいidentity-critical証拠が無ければactive workから外す |
| OSS / Validation | 🟢 **稼働中** | **86%** | cost0 + immutable trial ledger + **run_study→receipt検証→DSR bindingまでCI GREEN**。次のoutcome-blind validation controlへ |
| EDINET same-ZIP cross-check | 🟠 **外部入力待ち** | **35%** | real API keyまたはpinned real ZIP待ち |
| Supervisor coordination / dashboard | 🟢 **常時稼働** | **88%** | 新HEAD吸収・task state管理・自動再配分を運用中 |
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
| Canonical/Shadow | hash-provenance-chain契約凍結 / performance未開封 |
| OSS | immutable completed-trial receipt → DSR consumption binding verified / performance未開封 |
| Cloud exact | HOLD / close candidate |
| V20 | **CLOSED / DEPRIORITIZED** |
| 最終判定 | **NO-GO / 研究継続** |

## 1. 候補ランキング — frozen cost0 evidence

| Rank | Candidate | n | Mean | Median | Win | Top3-ex | Status |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | **DUAL + G3** | 117 | **+7.98%** | **+1.74%** | **53.85%** | **+5.14%** | 2023-25 leader / 2022 fresh robustness fail |
| 2 | DUAL_TOP1_AGREEMENT | 140 | +7.17% | +1.25% | 52.14% | +4.79% | fresh fail |
| 3 | mean-rank(volr20,body_pct) | 172 | +6.89% | +1.45% | 52.33% | +4.95% | frozen baseline |
| 4 | body_pct LOW | 172 | +6.54% | +0.99% | 50.58% | +4.60% | frozen baseline |
| 5 | volr20 LOW | 172 | +6.33% | +1.06% | 51.74% | +4.38% | frozen comparator |

G3 `med_ret1 >= -1%` は凍結。2022 fresh: DUAL n21 mean +2.62% / median -6.19% / win 28.57% / Top3-ex -7.55%、DUAL+G3 n17 mean +6.08% / median -6.00% / win 29.41% / Top3-ex -6.26%。**FAILED ROBUSTNESS**。Phase-2 Round2はCLOSED。

旧Cloud Monsterの **n=63 / mean +9.86%** は歴史的legacy evidenceであり、現在の候補ランキング・GO/NO-GOには使用しない。exact reproduction forensicは `HISTORICAL_EXACT_REPRO_UNAVAILABLE / HOLD_CLOSE_CANDIDATE` と明確に分離する。

## 2. Parallel Wave-1

HEAD `c7d5e0b023b5331cfba62186aeae2949e765e3cf`。preserved artifact `10264205130` の `tse_daily.csv` exact schema receiptをoutcome-blindに固定済み。

- source origin run `34545440155` / preservation run `34599959356`
- CSV SHA-256 `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`
- 4,061,361 data rows / header `date,open,high,low,close,volume,symbol`
- A1/B1/E1 preregistered条件・threshold変更なし
- performance **未開封**
- 次: 独立XTKS calendar artifact/version/SHA固定 → signal session→next XTKS open→fifth XTKS close mapping → endpoint completeness receipt → source/endpoint hash binding → one-shot cost0 batch

## 3. Consensus V47 / H1・H2

HEAD `b9579857c598730bc7e3dbad35517fd5c6dc98a4`。Run `34849054884` は非terminal。shard 0/1は各81/81 HTTP429、usable raw=0。shard 2/3 fetch中、残りqueued。**重複triggerなし**。これはtransport failureでありstrategy performance FAILではない。

- formal raw acceptance: **未PASS**
- formal promotion H1/H2: **未開封 / promotion evidenceなし**
- diagnostic-only NOCAP H2: n37 / mean +3.0295% / median +0.3817% / win 51.35% / Top3-ex -0.5393%
- diagnostic H2はpromotion evidenceではない
- terminal後のみ、genuinely observed rowsをpinned merge specで統合しfrozen acceptance再実行

## 4. Data / Provenance / Validation

**Canonical/Shadow:** HEAD `030287cb02337fe24e497b3fccf659a7cb57a5d6`。既存prewrite completeness guardはCI `34873808933` SUCCESS。新たにdaily endpoint manifest / pinned XTKS calendar / selection ledger / completeness receipt / resolved output / resolution receiptのexact hash chainをoutcome-blind契約として凍結。performance未開封。次は契約どおりの実装・CI。

**Core24 OHLCV補完:** `build_missing_inventory(expected, observed)` はCI `34881004528` SUCCESS。real missing inventory、fallback raw receipt、accepted/rejected/conflicted counts、coverage deltaが揃うまでformal dataset採用・performance再計算禁止。

**Core endpoint provenance:** immutable source receipt primitive GREEN。real XTKS/raw-vendor manifest、actual fetch receipt、canonical evaluator fail-closed配線が残る。

**OSS / Validation:** `run_study()` はcompleted Optuna trialsからcanonical ledger + SHA-256 receiptを構築し、`trial_sharpes_from_receipt()` の検証を通ったSharpe vectorだけを `selection_bias_summary()` / DSRへ渡す。summaryにcanonical rows + receipt + `dsr_input_source` を永続化。実装commit `6011e740...`、integration test commit `811467f5...`、CI **`34883481600` SUCCESS**。契約HEAD `82706784...` のcontract-only再CI `34883717045` はこの更新時点でin progress。cost0、Discovery 2022-07-01..2023-12-31、later-period selection禁止は維持。戦略performanceは新規開封していない。

**EDINET:** real API keyまたはpinned real ZIP待ち。same-ZIP不一致はoutcome-blind audit findingとして扱い、成績でparserを選ばない。外部待機中は同じ確認を繰り返さない。

## 5. P0 / P1 / P2

**P0:** Parallel XTKS calendar/endpoint receipt、Core24 real missing inventory/fallback verification、Consensus raw48 terminal後formal merge/acceptance。

**P1:** Canonical frozen provenance-chain実装、Core endpoint evaluator binding、OSS contract-only CI `34883717045`回収後に次のoutcome-blind validation controlへ移行。

**P2 / 外部待機:** EDINET real input。Cloud exactは新しい同時代identity-critical evidenceが出るまでHOLD。V20はclosed/deprioritized。

## 6. GO / NO-GO

**NO-GO / 研究継続。GO候補0件。** Parallelはperformance未開封、Consensusはformal raw acceptance未PASS、既存Phase-2 leaderはfresh robustness FAIL。検証インフラの改善をperformanceの改善と混同しない。

production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更しない。
