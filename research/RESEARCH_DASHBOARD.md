# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 23:57 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## ⏱ 自動研究ハートビート

> **確認時刻:** 2026-09-15 23:57 JST  
> 5本すべてenabled・90分以内。再armしたOSS+Parallel :48は23:52 actual runを確認し復旧確定。

| Worker | 直近実行(JST) | 状態 |
|---|---:|---|
| Supervisor :00 | 23:00 | 🟢 GREEN / current scan |
| Canonical :12 | 23:15 | 🟢 GREEN |
| Core :24 | 23:26 | 🟢 GREEN |
| Consensus :36 | 23:39 | 🟢 GREEN |
| OSS+Parallel :48 | 23:52 | 🟢 GREEN / re-arm recovery confirmed |

## 📈 全体進捗

**研究全体の進捗率: 約82%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、surrogate/retune禁止、Round2 CLOSED |
| Parallel Wave-1 | 🔴 STALE / worker復旧 | 72% | causal A1/B1/E1 pick ledger → completeness receipt → one-shot cost0 |
| Core24 OHLCV補完 | 🟢 稼働中 | 88% | JPX anchor/parser固定済み → 375-event reverse replay → PIT receipt |
| Consensus V47 | 🟢 corrected H2 diagnostic完了 / formal raw BLOCKED | 84% | H2 receipt固定。same-family retune/NOCAP H2開封禁止、formal raw acceptanceのみ継続可 |
| Canonical/Shadow endpoint integrity | 🟢 稼働中 | 89% | outcome-blind integrity継続 |
| Core endpoint provenance | 🟢 parser contract PASS | 98% | anchor 2026-08-31、eligible domestic individual equities 3,707。次はPIT membership receipt |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟢 worker復旧 / policy固定 | 98% | 27 findings source-grounded taxonomy。unresolvedはfail-closed |
| V20 Session-Impulse | ⚫ CLOSED | 100% | active queue外 |

## Consensus V47 今回の前進
STATEが未回収だったConsensus実HEAD `7059322a1c85f9db87a035003490ecd1545aa565` と corrected H2 run `34976174775` を回収。runはSUCCESS、artifact `10402109524` / digest `sha256:ad2bd2388425aaad55ed8485f5f20dfefbf62014c1f746e464851d9c093d7688`。

H1で事前固定したleader **CAP1000_PITのみ**を、同じprice-basis normalization・cooldown carry・cost 0%契約のまま2025H2へ開封。結果は `n=26 / mean +3.82% / median 0.00% / win 30.77% / +10 19.23% / +20 7.69% / +50 3.85% / -10 15.38% / -20 3.85% / Top1-ex -0.62% / Top3-ex -3.06%`。

これは `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE`。formal raw acceptanceはFAILのまま、NOCAP H2はcorrected basisで未開封。2025H2を見た後のsame-family threshold/TopN/ranker/cooldown/price-cap retuneは禁止。H2の弱いwin/Top3-exはrobustness warningとして固定する。

## Core24 現在地
Actions run `34974864648` / artifact `10398473275` のimmutable `data_e.xlsx` は227,579 bytes / SHA-256 `4d10497c2aa03bcca0b92f0673d3ab19ecc6aca6a9c9a70a3e19cd490f1d8754`。Effective Date `20260831`、国内Prime/Standard/Growth exact-label eligibilityは3,707。次は凍結375-event ledgerを2024-09-17までreverse replayしPIT membership receiptを固定。

## Frozen comparator / Phase-2順位
1. **DUAL_TOP1_AGREEMENT** — frozen primary challenger
2. mean-rank(volr20, body_pct)
3. body_pct LOW
4. volr20 LOW

DUAL+G3 (`med_ret1 >= -1%`) は n=117 / mean +7.98% / median +1.74% / win 53.85% / Top3-ex +5.14%。G3 thresholdは固定。2022 fresh validationはROBUSTNESS FAIL固定・surrogate/retune禁止。Regime Round2はCLOSEDのまま再開しない。

## STALE / BLOCKED / CLOSED
- 🔴 Parallel Wave-1: STALE。次actionはcausal A1/B1/E1 pick ledger freeze → completeness receipt。
- 🟠 Consensus formal raw acceptance: BLOCKED。corrected H2 diagnosticは完了したがpromotion evidenceではない。
- ⚫ Weak+Early Phase-2 frozen validation: CLOSED。
- ⚫ Regime Round2: CLOSED_DO_NOT_REOPEN。
- ⚫ Cloud exact forensic: CLOSED / exact reproduction unavailable。
- ⚫ V20: CLOSED / deprioritized active queue外。

## 残タスク
P0: Core24 PIT membership receipt、Parallel causal pick ledger、OSS EDINET 27 findings taxonomy。P1: Consensus formal raw acceptance/provenance（条件緩和なし）、Canonical outcome-blind integrity。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。新規performanceはcost 0%のみ、win=gross return>0。2026はreport/robustness-only。

## GO / NO-GO
**NO-GO / 研究継続。GO候補0件。**
