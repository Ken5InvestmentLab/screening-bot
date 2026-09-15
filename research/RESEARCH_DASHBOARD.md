# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 01:24 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## ⏱ 自動研究ハートビート
5本すべてenabled・直近90分以内。automation停止疑い0本。

## 📈 全体進捗
**研究全体の進捗率: 約82%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、surrogate/retune禁止 |
| Parallel Wave-1 | 🔴 STALE ESCALATED / P0再配分 | 72% | causal A1/B1/E1 pick ledger → SHA freeze → completeness receipt |
| Core24 OHLCV補完 | 🟢 PIT event repair | 89% | transfer bytes/SHA + 375-vs-395 audit → corrected PIT receipt |
| Consensus V47 | 🟢 corrected H2 diagnostic完了 / formal raw BLOCKED | 84% | same-family retune禁止、formal raw acceptanceのみ |
| Canonical/Shadow endpoint integrity | 🟢 crash-consistency監査 | 90% | sidecar-ahead interruptionの明示的・provenance-preserving recovery/two-phase protocol + regression tests |
| Core endpoint provenance | 🟢 parser contract + transfer contract frozen | 98% | corrected PIT membership receipt |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟢 policy固定 | 98% | 27 findings source-grounded taxonomy |
| V20 Session-Impulse | ⚫ CLOSED | 100% | active queue外 |

## Core24 今回の前進
開始Core HEAD `5ea40f52e6bd967406446ebc2574d6c06628a71b` はSTATE v98で既処理だったため重複処理せず、JPX PIT reverse replayの欠落event familyを公式ソースで確認。`List of Segment Transferred Companies` は Date / Code / Market Segment / Previous Market Segment を持ち、277A Globe-ing Inc. が2026-04-30に Growth→Primeへ移行しているため、listing/delistingだけでは2026-08-31 anchorから過去segment stateを復元できないことを確定した。2024 archiveにもtarget date 2024-09-17後のtransferが存在する。

Core branchに `CORE_JPX_PIT_SEGMENT_TRANSFER_SPEC_20260916.md`、forensic log、handoffを追加。旧375-event listing/delisting receiptは、後続forensic recountの395 replay-eligible eventsとの差分が未説明のためcanonical入力から一旦降格。次P0は current/2025/2024 transfer page exact-byte/SHA固定 → normalized transfer ledger → 375-vs-395 row-set監査 → conflict-checked reverse replay → membership count/SHA/quarantine receipt。

## 中締め診断 / 正式成績の分離
今回Coreでは新規performance診断なし。既存Consensus corrected CAP1000_PIT H2は `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE` のまま（2025-07-01..2025-12-30、cost0、n=26、mean +3.82%、median 0.00%、win 30.77%、+10 19.23%、+20 7.69%、+50 3.85%、-10 15.38%、-20 3.85%、Top1-ex -0.62%、Top3-ex -3.06%、endpoint next XTKS open -> D+5 close、formal raw acceptance FAIL）。promotion evidenceではなくsame-family retune禁止。

Frozen DUAL+G3 comparatorは n=117 / mean +7.98% / median +1.74% / win 53.85% / Top3-ex +5.14%。2022 fresh validationはROBUSTNESS FAIL固定・surrogate/retune禁止。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。V12/V17/V18/compression-breakout/canonical Monster-v2等reject familyはretuneしない。新規performanceはcost 0%のみ、win=gross return>0。2026はreport/robustness-only。

## GO / NO-GO
**NO-GO / 研究継続。GO候補0件。**
