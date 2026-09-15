# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 01:12 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## ⏱ 自動研究ハートビート
5本すべてenabled・直近90分以内。automation停止疑い0本。

## 📈 全体進捗
**研究全体の進捗率: 約82%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、surrogate/retune禁止 |
| Parallel Wave-1 | 🔴 STALE ESCALATED / P0再配分 | 72% | causal A1/B1/E1 pick ledger → SHA freeze → completeness receipt |
| Core24 OHLCV補完 | 🟢 稼働中 | 88% | 375-event reverse replay → PIT receipt |
| Consensus V47 | 🟢 corrected H2 diagnostic完了 / formal raw BLOCKED | 84% | same-family retune禁止、formal raw acceptanceのみ |
| Canonical/Shadow endpoint integrity | 🟢 crash-consistency監査 | 90% | sidecar-ahead interruptionの明示的・provenance-preserving recovery/two-phase protocol + regression tests |
| Core endpoint provenance | 🟢 parser contract PASS | 98% | PIT membership receipt |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟢 policy固定 | 98% | 27 findings source-grounded taxonomy |
| V20 Session-Impulse | ⚫ CLOSED | 100% | active queue外 |

## Canonical / Shadow 今回の前進
Canonical HEAD `90f56dcd426e8d1a85cfd8f38eee5a8afda9d471` はSTATE上で既処理だったため重複処理せず、その次のoutcome-blind integrity監査を実施。prewrite guardは receipt + chain link を `staged.replace(resolved)` より先にdurable化しているため、sidecar永続化後〜resolved replace完了前にprocess/filesystem failureが起きると、次回起動時にchain tail SHAと現resolved SHAが不一致となりfail-closedでstrandedになるcrash-consistency windowを確認した。監査commit `d7ffa6df8f688cea19515beca365a6d1fe79526f`。分類は `OUTCOME_BLIND_INTEGRITY_GAP_FAIL_CLOSED_RECOVERY_REQUIRED`。performance/H1/H2/2026 outcomeは未開封。

次のsafe work unitは、immutable historyを黙って削除・書換えせず、committed / sidecar-ahead(interrupted) / invalid-tamperedを区別できる明示的recoveryまたはtwo-phase pending/commit protocolとregression tests。strategy threshold/TopN/ranker/cooldownには触れない。

## 中締め診断 / 正式成績の分離
今回Canonicalでは新規performance診断なし。既存Consensus corrected CAP1000_PIT H2は `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE` のまま（2025-07-01..2025-12-30、cost0、n=26、mean +3.82%、median 0.00%、win 30.77%、+10 19.23%、+20 7.69%、+50 3.85%、-10 15.38%、-20 3.85%、Top1-ex -0.62%、Top3-ex -3.06%、endpoint next XTKS open -> D+5 close、formal raw acceptance FAIL）。promotion evidenceではなくsame-family retune禁止。

Frozen DUAL+G3 comparatorは n=117 / mean +7.98% / median +1.74% / win 53.85% / Top3-ex +5.14%。2022 fresh validationはROBUSTNESS FAIL固定・surrogate/retune禁止。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。V12/V17/V18/compression-breakout/canonical Monster-v2等reject familyはretuneしない。新規performanceはcost 0%のみ、win=gross return>0。2026はreport/robustness-only。

## GO / NO-GO
**NO-GO / 研究継続。GO候補0件。**
