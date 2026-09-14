# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 02:29 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。  
> **正式promotion evidenceと中締め診断は分離する。**

## 📈 全体進捗

**研究全体の進捗率: 約63%**

`█████████████░░░░░░░ 63%`

> この進捗率は「GOできる確率」ではなく、Supervisorが管理する研究マイルストーンの消化率。各laneの検証・データ整備・provenance・fresh robustness・formal acceptanceまでを含む。

## 0. 全体サマリー

| 項目 | 現在 |
|---|---|
| 最終GO候補 | **0件** |
| Canonical/Event + Shadow/Data | V20 **DEPRIORITIZE** / Shadow prewrite completeness receipt boundary **CI GREEN** |
| Weak+Early Phase-2 | 2022 fresh validation **FAILED ROBUSTNESS**。G3凍結、Round2閉鎖 |
| 2023-25暫定首位 | **DUAL + G3** mean +7.98% / median +1.74% / win 53.85% / Top3-ex +5.14% |
| Parallel Wave-1 | source bytes/provenance bound / performance未開封 |
| Consensus V47 | formal raw acceptance未PASS / raw48はsystemic Yahoo HTTP429 blocker / diagnostic NOCAP H2のみ開封 |
| Core / Cloud | fixed Core reject維持 / endpoint provenance + OHLCV supplement contract **CI GREEN** / Cloud exact replay unavailable |
| Core24 OHLCV補完 | **fail-closed verifier実装済み** / source policy凍結 / real missing-pair handoff待ち / performance再計算禁止 |
| OSS / Validation | cost0 + immutable trial-ledger primitive GREEN / DSR receipt binding待ち |
| 最終判定 | **NO-GO / 研究継続** |

### マイルストーン消化率

| 範囲 | 進捗 |
|---|---:|
| 全体 | **約63%** |
| Canonical/Event + Shadow/Data | 約72% |
| Weak+Early Phase-2 | 約90%（fresh robustnessまで開封済み、候補はFAIL） |
| Consensus V47 | 約65% |
| Parallel Wave-1 | 約55% |
| Core / Cloud forensic | **約73%** |
| OSS / Validation | 約80% |

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

Canonical HEAD `0d93b87bfa8abf1009efa94bf81d68277825dc98`。frozen prospective symbol-set + exact endpoint-session completeness guardをverified resolution/write boundaryへ配線済み。成熟済み候補のnext XTKS open / fifth XTKS closeが欠ける、非finite、非positive、またはdaily symbol/dateが重複する場合はresolved outputを書き換える前にfail-closed。

Prospective Shadow CI **`34873808933` SUCCESS**。performance未開封。次はdaily endpoint manifest + pinned XTKS calendar → prewrite completeness receipt → resolved output / legacy resolution receiptのprovenance-chain exact hash bindingをoutcome-blindで監査する。

## 2. Weak+Early Phase-2 — frozen cost0

| Rank | Candidate | n | Mean | Median | Win | Top3-ex | Status |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | **DUAL + G3** | 117 | **+7.98%** | **+1.74%** | **53.85%** | **+5.14%** | 2023-25 leader / fresh robustness fail |
| 2 | DUAL_TOP1_AGREEMENT | 140 | +7.17% | +1.25% | 52.14% | +4.79% | fresh fail |
| 3 | mean-rank(volr20,body_pct) | 172 | +6.89% | +1.45% | 52.33% | +4.95% | frozen baseline |
| 4 | body_pct LOW | 172 | +6.54% | +0.99% | 50.58% | +4.60% | frozen baseline |
| 5 | volr20 LOW | 172 | +6.33% | +1.06% | 51.74% | +4.38% | frozen comparator |

2022 fresh: DUAL_TOP1 n21 mean +2.62% / median -6.19% / win 28.57% / Top3-ex -7.55%。DUAL+G3 n17 mean +6.08% / median -6.00% / win 29.41% / Top3-ex -6.26%。**FAILED ROBUSTNESS**。retune禁止。G3 `med_ret1 >= -1%` は凍結継続、Round2はCLOSED。

## 3. Consensus V47

Formal raw acceptanceは未PASS。正式promotion evidenceではない。

- authoritative retry: **`34849054884`**（48 shards / max-parallel 2）
- shard 0: artifact `10357093848` / 81/81 HTTP429 / ok_symbols=0 / total_rows=0
- shard 1: artifact `10357611796` / 81/81 HTTP429 / ok_symbols=0 / total_rows=0
- state v47時点でshard 2/3 fetch中、later shards queued
- blockerはsystemic Yahoo HTTP429。戦略性能FAILではない。
- current runは重複triggerしない。future missing-only retryはall-429 fail-fast guard付き。

Formal frozen acceptance: pair coverage >=99.5%、monthly >=99%、completely missing required symbols=0、>=20 dates対象symbol coverage >=95%、restored-pair >=99%。閾値緩和・interpolation・synthetic barは禁止。

中締め diagnostic-only NOCAP H2（2025-07-01〜2025-12-30、cost 0%、next XTKS open -> D+5 close）:

| n | Mean | Median | Win | Top3-ex | Caveat |
|---:|---:|---:|---:|---:|---|
| 37 | **+3.0295%** | **+0.3817%** | **51.35%** | **-0.5393%** | MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE |

Formal clean V47 H1/H2は未開封。2026はreport/robustness-only。

## 4. Parallel Wave-1

Branch `research/parallel-condition-exploration` HEAD `8cfcee630164ae022c98100cd9339eaa20bbe84d`。A1/B1/E1 manifestとsource bytes/provenanceは固定済み。performance未開封。exact schema + pinned XTKS endpoint-session completeness receipt後にone-shot cost0 batchのみ実行。2026はreport-only。

## 5. Core / Cloud / OHLCV Supplement / OSS

### Core endpoint provenance

Core/Cloud latest HEAD: `4fd4b58dfce6d57c829a4cb79ca91f320cb76053`。supplement verifier implementation headは `d2f24b99d66c2cbfa6dbc3f1aa6e1d623973c3be`。

- Fixed Core / Failed-Breakdown Reclaim / Prior-Close Reclaim / Precision 3-family等の既reject familyは閉鎖維持、retuneなし。
- `endpoint_provenance.py` のimmutable raw-source receiptはraw file exact SHA-256/size、source run/artifact/vendor、pinned calendar SHAを束縛。driftはfail-closed。
- endpoint provenance CI `34868543771` SUCCESS。
- real XTKS + raw-vendor endpoint manifest生成/freeze、actual fetch artifact source receipt、`audit_core_canonical_endpoint.py` のfail-closed `resolve_canonical_endpoints` 配線は残blocker。
- formal Core returnはまだ再計算しない。

### Core24 OHLCV supplementation — implementation CI GREEN

Supervisor prereg `research/SUPERVISOR_OHLCV_SUPPLEMENT_ACCEPTANCE_20260915_0202.md` に沿って、研究用fail-closed verifier `ohlcv_supplement.py`、source policy `OHLCV_SUPPLEMENT_SOURCE_POLICY_20260915.json`、unit tests、専用workflowを追加した。

**CI:**
- `34874773548` SUCCESS — 初回contract implementation
- `34874848913` SUCCESS — source priority guard含むfollow-up

Verifierはpre-supplement missing inventoryに無いrowを拒否し、symbol/timestamp/timeframe、raw SHA-256、acquired_at、latest_market_ts、OHLCV整合性、source/timeframe eligibility、causalityを確認する。eligible source同士が同一pairで異なるOHLCVを返した場合は**CONFLICT_FAIL_CLOSED**。平均・補間・後知恵source選択はしない。

Frozen source policy:
- `yahoo_chart_api_native`: native exact observed path。Yahoo Japan HTML scrapingは追加しない。
- `stooq_intraday_candidate`: **formal_eligible=false**。overlap agreement / timestamp-session / adjustment / raw receipt確認後にのみ昇格検討。
- `alpha_vantage_free`: **低優先度・1dのみformal fallback**。1H/4H補完へのdaily-to-intraday synthesisは禁止。
- `alpha_vantage_intraday_premium`: entitlement/provenance未確認のためdisabled。
- `googlefinance_snapshot`: corroboration/future snapshotのみ。formal historical intradayには使わない。
- Kabutan automated scrapingは禁止。

**まだformal adoption不可。** 次はreal missing-pair inventoryを生成し、実際のfallback raw bytes/receiptsを取得、accepted/rejected/conflicted件数とcoverage deltaを出し、deterministic verifier PASSをSupervisorへ渡す。そこまでstrategy performanceは再計算しない。

### Cloud Monster forensic

完全一致段階は **`HISTORICAL_EXACT_REPRO_UNAVAILABLE`** を維持。新しい同時代一次証拠なし。model-family guessing / portability replayは再開していない。

- **歴史値（legacy evidence）:** `n=63 / 5BD平均 +9.86%`
- **新しい完全一致再現結果:** なし

歴史値と新規再現値を混同しない。exact model / exact 575 Watch pool等の新証拠が出ない限りCloudをpromotion候補へ戻さない。

### OSS / Validation

OSS HEAD `7704641db12a7ed593b794cf87002c4a7bae1b7f`。cost0 Optuna contractとimmutable completed-trial ledger primitiveがGREEN。`run_study()`→DSRのimmutable receipt bindingが残る。新規performance未開封。

## 6. 優先残タスク

### P0
1. **Core24 OHLCV supplement:** real missing-pair inventory → frozen source policyでfallback取得 → per-source raw receipt → verifier → accepted/rejected/conflicted counts + coverage delta。PASS前はperformance再計算禁止。
2. **Consensus transport/formal acceptance:** run `34849054884`を重複起動しない。terminal後にgenuinely observed rowsのみをpreserved seedとprovenance付きmergeし、unchanged frozen verifierを再実行。

### P1
1. **Canonical/Shadow:** daily endpoint manifest + pinned XTKS calendar → immutable prewrite completeness receipt → resolved output / legacy resolution receiptのexact hash binding。
2. **Parallel Wave-1:** exact schema + pinned XTKS endpoint-session receipt → one-shot A1/B1/E1 cost0。
3. **Core:** real XTKS/vendor manifest freeze → actual source receipt emit/verify → canonical evaluatorをfail-closed primitiveへ配線 → CI → その後のみcost0再計算。
4. **OSS:** `run_study`/DSRをimmutable completed-trial receiptへbinding。

### P2
1. **EDINET same-ZIP real cross-check:** prereg済み2023-2025 metadata snapshot/selected doc IDs/ZIP SHA固定後のみ実比較。parser不一致はoutcome-blind audit finding扱い。

production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更しない。
