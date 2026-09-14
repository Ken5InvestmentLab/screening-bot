# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 01:12 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。  
> **正式promotion evidenceと中締め診断は分離する。**

## 0. 全体サマリー

| 項目 | 現在 |
|---|---|
| 最終GO候補 | **0件** |
| Canonical/Event + Shadow/Data | V20 **DEPRIORITIZE** / Shadow endpoint completeness guard **CI GREEN** |
| Weak+Early Phase-2 | 2022 fresh validation **FAILED ROBUSTNESS**。G3凍結、Round2閉鎖 |
| 2023-25暫定首位 | **DUAL + G3** mean +7.98% / median +1.74% / win 53.85% / Top3-ex +5.14% |
| Parallel Wave-1 | source bytes/provenance bound / performance未開封 |
| Consensus V47 | formal raw acceptance未PASS / diagnostic NOCAP H2のみ開封 |
| Core / Cloud | fixed Core reject維持 / Cloud exact replay unavailable |
| OSS / Validation | cost0 + immutable trial-ledger primitive GREEN |
| 最終判定 | **NO-GO / 研究継続** |

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

### Shadow/Data integrity — 今回前進

Canonical HEAD `962a062bc8a46eb32df65cfa737676463ec3ea1a`。

新規 `prospective_shadow_endpoint_completeness_guard.py` を追加し、frozen prospective selection ledgerに対して、成熟済み候補の必要endpointをperformance非開封で事前監査する境界を実装した。

- exact **next XTKS session open** の symbol/date/open が必要
- exact **fifth XTKS session close** の symbol/date/close が必要
- required pair欠損、required symbol全欠損、非finite/非positive価格、calendar重複、signal_dateがpinned calendar外なら **fail-closed**
- まだ5営業日成熟していない候補は `pending` として扱いfailureにしない
- gross returnは計算しない
- threshold/ranker/cooldown/strategy logicは変更しない
- production変更なし

Prospective Shadow CI **`34867054366` SUCCESS**。次はこのguardをverified resolution/write boundaryへ配線し、受理前のimmutable completeness receiptを作る。

## 2. Weak+Early Phase-2 — frozen cost0

| Rank | Candidate | n | Mean | Median | Win | Top3-ex | Status |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | **DUAL + G3** | 117 | **+7.98%** | **+1.74%** | **53.85%** | **+5.14%** | 2023-25 leader / fresh robustness fail |
| 2 | DUAL_TOP1_AGREEMENT | 140 | +7.17% | +1.25% | 52.14% | +4.79% | fresh fail |
| 3 | mean-rank(volr20,body_pct) | 172 | +6.89% | +1.45% | 52.33% | +4.95% | frozen baseline |
| 4 | body_pct LOW | 172 | +6.54% | +0.99% | 50.58% | +4.60% | frozen baseline |
| 5 | volr20 LOW | 172 | +6.33% | +1.06% | 51.74% | +4.38% | frozen comparator |

2022 fresh: DUAL_TOP1 n21 mean +2.62% / median -6.19% / win 28.57% / Top3-ex -7.55%。DUAL+G3 n17 mean +6.08% / median -6.00% / win 29.41% / Top3-ex -6.26%。**FAILED ROBUSTNESS**。retune禁止。

## 3. Consensus V47

Formal raw acceptanceは未PASS。正式promotion evidenceではない。

中締め diagnostic-only NOCAP H2（2025-07-01〜2025-12-30、cost 0%、next XTKS open -> D+5 close）:

| n | Mean | Median | Win | Top3-ex | Caveat |
|---:|---:|---:|---:|---:|---|
| 37 | **+3.0295%** | **+0.3817%** | **51.35%** | **-0.5393%** | MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE |

formal raw retryはsingle-active扱いを維持し、重複triggerしない。

## 4. Parallel Wave-1

A1/B1/E1 manifestとsource bytes/provenanceは固定済み。performance未開封。exact schema + pinned XTKS endpoint-session completeness receipt後に one-shot cost0 batchのみ実行。2026はreport-only。

## 5. Core / Cloud / OSS

Core fixed candidateはREJECT維持。Cloud historical exact replayは `HISTORICAL_EXACT_REPRO_UNAVAILABLE`。OSSはcost0 Optuna contractとimmutable completed-trial ledger primitiveがGREENで、DSR receipt binding待ち。

## 6. 残タスク

1. **Canonical/Shadow:** endpoint completeness guardをverified resolution/write boundaryへ配線し、immutable completeness receiptを追加。
2. **Parallel Wave-1:** exact schema + pinned XTKS endpoint-session receipt → one-shot A1/B1/E1 cost0。
3. **Consensus:** formal raw retryを重複起動せず、usable artifact後にfrozen acceptance。
4. **Core:** real XTKS/vendor manifest + immutable source receipt + evaluator wiring/CI。
5. **OSS:** `run_study`/DSR completed-trial receipt binding。

production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更しない。
