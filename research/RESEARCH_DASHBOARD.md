# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 02:18 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。  
> **正式promotion evidenceと中締め診断は分離する。**

## 0. 全体サマリー

| 項目 | 現在 |
|---|---|
| 最終GO候補 | **0件** |
| Canonical/Event + Shadow/Data | V20 **DEPRIORITIZE** / Shadow prewrite completeness receipt boundary **CI GREEN** |
| Weak+Early Phase-2 | 2022 fresh validation **FAILED ROBUSTNESS**。G3凍結、Round2閉鎖 |
| 2023-25暫定首位 | **DUAL + G3** mean +7.98% / median +1.74% / win 53.85% / Top3-ex +5.14% |
| Parallel Wave-1 | source bytes/provenance bound / performance未開封 |
| Consensus V47 | formal raw acceptance未PASS / raw48はsystemic Yahoo HTTP429 blocker / diagnostic NOCAP H2のみ開封 |
| Core / Cloud | fixed Core reject維持 / endpoint source-receipt primitive **CI GREEN** / Cloud exact replay unavailable |
| Core24 OHLCV補完 | **data-plane acceptance boundary preregistered** / formal dataset adoption未許可 / performance再計算禁止 |
| OSS / Validation | cost0 + immutable trial-ledger primitive GREEN / DSR receipt binding待ち |
| 最終判定 | **NO-GO / 研究継続** |

### マイルストーン消化率

以下は成功確率ではなく、各レーンで事前定義した検証・実装マイルストーンの消化率の目安。

| 範囲 | 進捗 |
|---|---:|
| 全体 | **約62%** |
| Canonical/Event + Shadow/Data | 約72% |
| Weak+Early Phase-2 | 約90%（fresh robustnessまで開封済み、候補はFAIL） |
| Consensus V47 | 約65% |
| Parallel Wave-1 | 約55% |
| Core / Cloud forensic | 約70% |
| OSS / Validation | **約80%** |

## 1. Canonical/Event + Shadow/Data

### V20 Session-Impulse — `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE`

734 symbol/date gapを残したcoverage-bypassed診断。frozen 1810 symbols / 82 sessions、Top1/2/3/5、endpointは変更なし。正式promotionには従来どおりexact raw acceptance PASSが必要。

| Policy | Period | n | Mean | Median | Win | +10 | +20 | +50 | -10 | -20 | Top1-ex | Top3-ex | Endpoint | Coverage caveat |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| V20 Top1 | H1 diagnostic | — | **-1.346%** | — | — | — | — | — | — | — | — | — | next XTKS open -> 5th close | 734 gaps / not promotion evidence |
| V20 Top2 | H1 diagnostic | — | **-1.573%** | — | — | — | — | — | — | — | — | — | next XTKS open -> 5th close | same |
| V20 Top3 | H1 diagnostic | — | **-1.118%** | — | — | — | — | — | — | — | — | — | next XTKS open -> 5th close | same |
| V20 Top5 | H1 diagnostic | — | **-0.538%** | — | — | — | — | — | — | — | — | — | next XTKS open -> 5th close | same |

**Decision: DEPRIORITIZE.** opened resultを見たthreshold/TopN/ranker/cooldown変更は禁止。

### Shadow/Data integrity

Canonical HEAD `0d93b87bfa8abf1009efa94bf81d68277825dc98`。既存のfrozen prospective symbol-set + exact endpoint-session completeness guardを、verified resolution/write boundaryへ直接配線した。成熟済み候補のnext XTKS open / fifth XTKS closeが欠ける、非finite、非positive、またはdaily symbol/dateが重複する場合は、**resolved outputを書き換える前に fail-closed** する。

各resolution attemptは outcome-blind な `PROSPECTIVE_SHADOW_ENDPOINT_COMPLETENESS_RECEIPT` をresolved write前にimmutable生成する。receiptはshadow input SHA、daily rows SHA、session calendar SHA、completeness result SHA、mature/pending/required/missing/invalid counts、canonical endpoint contractを固定し、strategy outcome / gross returnを含めない。同一入力の再実行は同一receiptをidempotent再利用し、入力が変わればreceipt SHA由来の別ファイルをappend-onlyで作る。FAIL時はreceiptだけを残し既存resolved historyは不変。PASS後のみ従来のstaged resolve + continuity guard + resolved replaceへ進む。

Prospective Shadow CI **`34873808933` SUCCESS**。今回performanceは開いていない。次はdaily endpoint manifest + pinned XTKS calendar → prewrite completeness receipt → resolved output / legacy resolution receiptの**provenance-chain exact hash binding**をoutcome-blindで監査する。

## 2. Weak+Early Phase-2 — frozen cost0

| Rank | Candidate | n | Mean | Median | Win | Top3-ex | Status |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | **DUAL + G3** | 117 | **+7.98%** | **+1.74%** | **53.85%** | **+5.14%** | 2023-25 leader / fresh robustness fail |
| 2 | DUAL_TOP1_AGREEMENT | 140 | +7.17% | +1.25% | 52.14% | +4.79% | fresh fail |
| 3 | mean-rank(volr20,body_pct) | 172 | +6.89% | +1.45% | 52.33% | +4.95% | frozen baseline |
| 4 | body_pct LOW | 172 | +6.54% | +0.99% | 50.58% | +4.60% | frozen baseline |
| 5 | volr20 LOW | 172 | +6.33% | +1.06% | 51.74% | +4.38% | frozen comparator |

2022 fresh: DUAL_TOP1 n21 mean +2.62% / median -6.19% / win 28.57% / Top3-ex -7.55%。DUAL+G3 n17 mean +6.08% / median -6.00% / win 29.41% / Top3-ex -6.26%。**FAILED ROBUSTNESS**。retune禁止。

G3 `med_ret1 >= -1%` は凍結継続。結果を見たthreshold変更は禁止。2022 fresh validationが実行可能だったため、ユーザー指定どおりRegime Round2は **CLOSED** のまま。candidate-level新ranker探索も停止継続。

## 3. Consensus V47

Formal raw acceptanceは未PASS。正式promotion evidenceではない。

### Formal raw48 transport status

- authoritative retry: **`34849054884`**（48 shards / max-parallel 2）
- shard 0: workflow SUCCESS / artifact **`10357093848`** / **81/81 symbols HTTP429 / ok_symbols=0 / total_rows=0**
- shard 1: workflow SUCCESS / artifact **`10357611796`** / **81/81 symbols HTTP429 / ok_symbols=0 / total_rows=0**
- shard 2/3: `Fetch raw 1H shard` 実行中（02:02 JST確認時点）
- later shards: queued
- artifactが存在しても0-rowなのでformal raw data successとは数えない。
- blockerは **systemic Yahoo HTTP429**。戦略性能の失敗ではない。
- future missing-only retryには2 symbols × 2 Yahoo hostsのall-429 fail-fast circuit breakerを追加済み。ただし現在runは旧trigger SHAに固定されているため途中差し替え・重複triggerしない。

Formal frozen acceptanceは従来どおり pair coverage >=99.5%、monthly >=99%、completely missing required symbols=0、>=20 dates対象symbol coverage >=95%、restored-pair >=99%。閾値緩和・interpolation・synthetic barは禁止。

中締め diagnostic-only NOCAP H2（2025-07-01〜2025-12-30、cost 0%、next XTKS open -> D+5 close）:

| n | Mean | Median | Win | Top3-ex | Caveat |
|---:|---:|---:|---:|---:|---|
| 37 | **+3.0295%** | **+0.3817%** | **51.35%** | **-0.5393%** | MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE |

### H1/H2開封状態

| 区分 | H1 | H2 |
|---|---|---|
| Formal clean V47 | **未開封** | **未開封** |
| Midterm NOCAP diagnostic | 開封済み | 開封済み |
| Midterm CAP1000_PIT diagnostic | H1開封済み | **閉鎖維持（rescue開封禁止）** |
| 2026 | selection用途は閉鎖 | report/robustness-only |

## 4. Parallel Wave-1

Branch `research/parallel-condition-exploration` HEAD `8cfcee630164ae022c98100cd9339eaa20bbe84d`。A1/B1/E1 manifestとsource bytes/provenanceは固定済み。performance未開封。exact schema + pinned XTKS endpoint-session completeness receipt後に one-shot cost0 batchのみ実行。2026はreport-only。

## 5. Core / Cloud / OHLCV Supplement / OSS

### Core endpoint provenance

Core/Cloud latest HEAD: `adca8963302644857e4bb05f668e660c84bffb82`。

- Fixed Core / Failed-Breakdown Reclaim / Prior-Close Reclaim / Precision 3-family等の既reject familyは閉鎖維持、retuneなし。
- `endpoint_provenance.py` にimmutable raw-source receiptを追加。raw fileのexact SHA-256/size、source Actions run ID、artifact名、vendor identity、pinned calendar SHA-256を束縛し、receipt自体もSHA-256固定。
- raw bytes、file set、size、metadata、calendar SHAにdriftがあればfail-closed。
- outcome/returnを使わず検証可能。
- dedicated CI **`34868543771` SUCCESS**。
- 今回performance再計算なし。したがって新しいn/平均/中央値/勝率/tail値はなく、ランキング・GO/NO-GOへの影響なし。

**残blocker:** real XTKS + raw-vendor endpoint manifestを生成/freezeし、actual fetch artifactからsource receiptをemit/verifyし、`audit_core_canonical_endpoint.py` をobserved-date + first/last-row方式からfail-closed `resolve_canonical_endpoints` へ配線する。そのCIが通るまでformal Core returnを再計算しない。

### Core24 OHLCV supplementation — Supervisor acceptance boundary

Core24側で進行中の「足りないOHLCVを別経路で補完する」作業は、研究条件変更ではなく**data-plane repair**として扱う。Supervisor側で `research/SUPERVISOR_OHLCV_SUPPLEMENT_ACCEPTANCE_20260915_0202.md` を結果を見る前に固定した。

Formal research datasetへ補完rowを採用する前に、少なくとも以下を必須とする：

- missing pair inventory（補完前）
- vendor/source hierarchyとacquisition method
- per-pair native/supplement provenance + acquisition timestamp
- immutable source payload/file receipt（可能な場合SHA-256）
- OHLC整合性・XTKS calendar/session整合性
- future-information非使用
- accepted/rejected/conflicted件数とcoverage delta
- deterministic verifier PASS

**禁止:** interpolation、OHLCのforward/back fill、daily barからintradayを合成、performanceを見たsource選択、nativeと補完値のsilent merge。conflictは平均せずfail-closed。

このdata-plane receiptがPASSするまでは補完datasetによるstrategy performance再計算をformal evidenceにしない。V47のsystemic HTTP429は引き続きtransport blockerであり、戦略FAILではない。

### Cloud Monster forensic

完全一致段階は **`HISTORICAL_EXACT_REPRO_UNAVAILABLE`** を維持。新しい同時代一次証拠なし。model-family guessing / portability replayは再開していない。

- **歴史値（legacy evidence）:** `n=63 / 5BD平均 +9.86%`
- **新しい完全一致再現結果:** なし

歴史値と新規再現値を混同しない。exact model / exact 575 Watch pool等の新証拠が出ない限り、Cloudをpromotion候補へ戻さない。

### OSS / Validation

OSS HEAD `7704641db12a7ed593b794cf87002c4a7bae1b7f`。cost0 Optuna contractとimmutable completed-trial ledger primitiveがGREEN。`run_study()`はまだcompleted trial user_attrsからSharpe配列を直接生成してDSRへ渡しており、immutable receipt-bound consumptionへのintegration bindingが残る。新規performanceは開いていない。

## 6. 優先残タスク

### P0
1. **Core24 OHLCV supplement:** 補完処理はpreregistered data-plane contract下で継続可。Supervisor採用にはmissing inventory/source hierarchy/per-pair provenance/receipt/verifier/coverage deltaのhandoffが必要。PASS前はperformance再計算禁止。
2. **Consensus transport/formal acceptance:** run `34849054884`を重複起動しない。terminal後にgenuinely observed raw rowsのみをpreserved seedとprovenance付きmergeし、unchanged frozen verifierを再実行。Yahoo回復後も不足ならmissing pairsのみをnew 429 circuit breaker付きで再取得。

### P1
1. **Canonical/Shadow:** daily endpoint manifest + pinned XTKS calendar → immutable prewrite completeness receipt → resolved output / legacy resolution receiptのprovenance-chain exact hash bindingを監査し、driftをfail-closedにする。
2. **Parallel Wave-1:** exact schema + pinned XTKS endpoint-session receipt → one-shot A1/B1/E1 cost0。
3. **Core:** real XTKS/vendor manifest freeze → actual source receipt emit/verify → canonical evaluatorをfail-closed primitiveへ配線 → CI → その後のみcost0再計算。
4. **OSS:** `run_study`/DSRをimmutable completed-trial receiptへbindingし、summaryへreceiptを永続化、integration testを追加。

### P2
1. **EDINET same-ZIP real cross-check:** preregister済み2023-2025 metadata snapshot/selected doc IDs/ZIP SHA固定後のみ実比較。外部EDINET API key/data取得境界が満たされるまでsynthetic/contract validationのみ。parser不一致はoutcome-blind audit findingとして扱う。

production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更しない。
