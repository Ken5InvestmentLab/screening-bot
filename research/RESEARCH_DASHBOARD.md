# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 04:45 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## 📈 全体進捗

**研究全体の進捗率: 約68%**

`██████████████░░░░░░ 68%`

### タスク別進捗・稼働状態

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | 🟡 **整理中** | **90%** | 2023-25 ranking + 2022 fresh完了。robustness FAIL、G3凍結、Round2 CLOSED |
| Parallel Wave-1 新条件探索 | 🟢 **稼働中** | **72%** | source/schema + 独立XTKS calendar固定、outcome-blind endpoint verifier実装。causal pick ledger → actual completeness receipt → one-shot cost0開封が残り |
| Core24 OHLCV補完 | 🟢 **稼働中** | **55%** | missing-inventory builder + SHA-bound実行runner CI GREEN。real expected/raw1H pin → fallback raw → verifier → coverage deltaが残り |
| Consensus V47 raw 1H取得・formal acceptance | 🟠 **外部待機** | **66%** | raw48非terminal。shard 0-3が合計324/324 HTTP429・usable raw 0、4/5以降待機。merge acceptance spec固定済み |
| Canonical/Shadow endpoint integrity | 🟢 **稼働中** | **79%** | full hash-provenance chainをverified resolve boundaryへ実装。CI `34886599423` SUCCESS。link-tamper回帰/次のoutcome-blind controlへ |
| Core endpoint provenance | 🟢 **稼働中** | **70%** | provenance primitive GREEN。real XTKS/vendor manifest + actual receipt + evaluator配線が残り |
| Cloud Monster exact forensic | ⚪ **保留 / 閉鎖候補** | **76%** | exact replay一次証拠なし。新しいidentity-critical証拠が無ければactive workから外す |
| OSS / Validation | 🟢 **稼働中** | **86%** | cost0 + immutable trial ledger + run_study→receipt検証→DSR bindingまで契約再CI含めGREEN。次のoutcome-blind validation controlへ |
| EDINET same-ZIP cross-check | 🟠 **外部入力待ち** | **35%** | real API keyまたはpinned real ZIP待ち |
| Supervisor coordination / dashboard | 🟢 **常時稼働** | **90%** | 新HEAD吸収・task state管理・自動再配分を運用中 |
| V20 Session-Impulse | ⚫ **CLOSED / deprioritized** | **100%** | promotion候補から除外。新証拠が無ければworker cycleを使わない |

**状態:** 🟢 稼働中 / 🟡 整理中 / 🟠 外部待機 / ⚪ 保留・閉鎖候補 / ⚫ CLOSED / 🔴 STALE。2回連続で同じSHA・同じblocker確認だけならSTALE候補とし、workerを別の安全なpending taskへ再配分する。

## 0. 全体サマリー

| 項目 | 現在 |
|---|---|
| 最終GO候補 | **0件** |
| Weak+Early Phase-2 | **DUAL+G3**が2023-25首位。ただし2022 fresh **FAILED ROBUSTNESS**、Round2 CLOSED |
| 2023-25首位 | n117 / mean **+7.98%** / median **+1.74%** / win **53.85%** / Top3-ex **+5.14%** |
| Parallel Wave-1 | source bytes + exact schema + **独立XTKS calendar固定 / endpoint completeness verifier実装**。performance未開封 |
| Consensus V47 | raw48 transport blocker / formal acceptance未PASS。shard 0-3 = **324/324 HTTP429 / 0 raw rows** |
| Canonical/Shadow | full hash-provenance chain **実装済み / CI GREEN** / performance未開封 |
| Core24 OHLCV | SHA-bound real-inventory runner **実装済み / CI GREEN** / real raw1H input pin待ち |
| OSS | immutable completed-trial receipt → DSR consumption binding **verified / CI GREEN** / performance未開封 |
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

HEAD `858998cceb10f263d181233a20c55c5bc4f92aa6`。preserved artifact `10264205130` の `tse_daily.csv` source/schemaに加えて、独立XTKS calendar bytesとendpoint mappingをoutcome-blindに固定済み。

- source origin run `34545440155` / preservation run `34599959356`
- CSV SHA-256 `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`
- 4,061,361 data rows / header `date,open,high,low,close,volume,symbol`
- XTKS calendar: `research/PARALLEL_WAVE1_XTKS_CALENDAR_2022_2026.csv`
- calendar generator: `exchange_calendars 4.13.1 / XTKS`
- calendar coverage: 2022-01-04 .. 2026-12-30 / **1,220 sessions**
- calendar SHA-256 `58e67bd20be08d04c143fa7e8f707bb3b82c21c2de2af9dfd7c2a05a406de71b`
- frozen mapping: signal session → next XTKS open → fifth XTKS close（entry sessionを1日目として数える）
- outcome-blind verifier: `research/parallel_wave1_endpoint_receipt.py`
- verifierはreturnを計算せず、calendar/daily/pick-ledger SHA、schema、session mapping、entry-open/exit-close completenessをfail-closed検証
- A1/B1/E1 preregistered条件・threshold変更なし
- bound sourceに`tail_p`列が無いため、事前登録済みfallbackの**symbol ascending**を使用
- performance **未開封**
- 次: A1/B1/E1 causal pick ledgerをreturnなしで生成→bytes/SHA固定→actual endpoint completeness receipt PASS→one-shot cost0 batch

## 3. Consensus V47 / H1・H2

HEAD `fd7f7c5d26f154a760dd9a025bb242620bce0dc9`。Run `34849054884` は非terminal/queued。shard 0-3は各81銘柄すべてHTTP429で、合計 **324 requested / 0 ok / 0 raw rows / 324 HTTP429**。artifact `10357093848` / `10357611796` / `10363982190` / `10364352429` の4件のみ確認済み。shard 4/5以降はまだmatrix待機/実行中。**重複triggerなし**。これはtransport failureでありstrategy performance FAILではない。

- formal raw acceptance: **未PASS**
- formal promotion H1/H2: **未開封 / promotion evidenceなし**
- diagnostic-only NOCAP H2: n37 / mean +3.0295% / median +0.3817% / win 51.35% / Top3-ex -0.5393%
- diagnostic H2はpromotion evidenceではない
- completed shard 0-3だけでは `NOT_COMPUTABLE_NO_INPUT_DATA`
- terminal後のみ、genuinely observed rowsをpinned merge specで統合しfrozen acceptance再実行

## 4. Data / Provenance / Validation

**Canonical/Shadow:** HEAD `2fe2981f43a8c80a510ca446241ad44ed6e2c6eb`。freeze済み `daily endpoint manifest → pinned XTKS calendar → frozen selection ledger → completeness receipt → resolved output → resolution receipt` chainをverified resolve boundaryへ実装。CLIはverified daily manifestとpinned calendar artifactを必須化し、completeness receiptは3 upstream SHAを明示的にbind、resolution receiptはcompleteness receipt自己SHAとresolved output SHAをbindする。欠損artifactはresolved write前にfail-closed。最終CI `34886599423` **SUCCESS**。strategy logic / performanceは未変更・未開封。

**Core24 OHLCV補完:** HEAD `fcc86fbd15b821cc3b17f3f71845afde8bdf5cbc`。`build_missing_inventory(expected, observed)` に加え、exact expected/observed CSV bytesを事前SHA-bindし、`missing_inventory.csv` とreceiptもSHA-bindする real-inventory runnerを追加。CI `34886738844` **SUCCESS**。artifact `10264205130` はdaily-only、artifact `10330772110` はlineage receipt-onlyであり、formal raw1H observed inputの代替には使わない。real expected endpoint-key universe + exact raw1H bytesのpin、fallback raw receipt、accepted/rejected/conflicted counts、coverage deltaが揃うまでformal dataset採用・performance再計算禁止。

**Core endpoint provenance:** immutable source receipt primitive GREEN。real XTKS/raw-vendor manifest、actual fetch receipt、canonical evaluator fail-closed配線が残る。

**OSS / Validation:** `run_study()` はcompleted Optuna trialsからcanonical ledger + SHA-256 receiptを構築し、`trial_sharpes_from_receipt()` の検証を通ったSharpe vectorだけを `selection_bias_summary()` / DSRへ渡す。summaryにcanonical rows + receipt + `dsr_input_source` を永続化。CI `34883481600` **SUCCESS**、契約再CI `34883717045` **SUCCESS**。cost0、Discovery 2022-07-01..2023-12-31、later-period selection禁止は維持。戦略performanceは新規開封していない。

**EDINET:** real API keyまたはpinned real ZIP待ち。same-ZIP不一致はoutcome-blind audit findingとして扱い、成績でparserを選ばない。外部待機中は同じ確認を繰り返さない。

## 5. P0 / P1 / P2

**P0:** Parallel causal A1/B1/E1 pick ledger固定→actual endpoint completeness receipt→one-shot cost0、Core24 exact expected/raw1H input pin→one-shot missing inventory→fallback verification、Consensus raw48 terminal後formal merge/acceptance。

**P1:** Canonical hash chainは実装・CI GREEN。次はexplicit link-tamper regressionまたは別のoutcome-blind Shadow/Data integrity control。Core endpoint evaluator binding、OSSはreceipt-bound DSR control完了のため次のoutcome-blind validation controlへ移行。

**P2 / 外部待機:** EDINET real input。Cloud exactは新しい同時代identity-critical evidenceが出るまでHOLD。V20はclosed/deprioritized。

## 6. GO / NO-GO

**NO-GO / 研究継続。GO候補0件。** Parallelはperformance未開封、Consensusはformal raw acceptance未PASS、既存Phase-2 leaderはfresh robustness FAIL。検証インフラの改善をperformanceの改善と混同しない。

production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更しない。
