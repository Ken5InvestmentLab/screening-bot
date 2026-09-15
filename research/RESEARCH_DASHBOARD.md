# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 02:24 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## ⏱ 自動研究ハートビート
5本すべてenabled・直近90分以内。automation停止疑い0本。

## 📈 全体進捗
**研究全体の進捗率: 約83%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、surrogate/retune禁止 |
| Parallel Wave-1 | 🟢 STALE解除・calendar gate修復 | 76% | repaired causal A1/B1/E1 pick ledger → SHA freeze → completeness receipt |
| Core24 OHLCV補完 | 🟢 transfer source family verified / byte-pin pending | 90% | verified transfer current/2025/2024 exact bytes/SHA → transfer ledger + 375-vs-395 audit → corrected PIT receipt |
| Consensus V47 | 🟢 corrected H2 diagnostic完了 / formal raw BLOCKED | 84% | same-family retune禁止、formal raw acceptanceのみ |
| Canonical/Shadow endpoint integrity | 🟢 crash-consistency監査 | 90% | sidecar-ahead interruption recovery/two-phase protocol + regression tests |
| Core endpoint provenance | 🟢 transfer URL/schema provenance verified | 98% | exact-byte transfer receipt + corrected PIT membership receipt |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟢 policy固定 | 98% | 27 findings source-grounded taxonomy |
| V20 Session-Impulse | ⚫ CLOSED | 100% | active queue外 |

## Core24 今回の前進 — JPX transfer source family確定
JPX公式のsegment-transfer source familyを独立確認。current=`/english/listing/stocks/transfers/`、2025=`00-archives-01.html`、2024=`00-archives-02.html`。公式rendered schemaは Date / Issue Name / Code / Market Segment / Previous Market Segment / Underwriter。`277A Globe-ing Inc.` の2026-04-30 Growth→Primeに加え、target start直後の2024-09-20/25/27にもtransferが存在するため、PIT reverse replayにtransfer ledgerが必須であることを再確認した。

ただしrendered/search textはbyte-pinned evidenceへ格上げしない。PITはFAIL-CLOSED継続。次は既存research-only byte-preserving workflowで上記3 URLのexact bytes・SHA-256・byte size・retrieval timestampを固定し、transfer ledgerを生成する。旧375-event receiptとforensic 395-event listing/delisting差分20件は未解決のまま保持し、row-level audit完了前にPIT PASSしない。

## Phase-2 frozen順位 / G3 / fresh / Round2
順位変更なし。Frozen DUAL+G3 comparatorは **n=117 / mean +7.98% / median +1.74% / win 53.85% / Top3-ex +5.14%**。2022 fresh validationはROBUSTNESS FAIL固定、surrogate/retune禁止。

## STALE / BLOCKED / CLOSED
Consensus formal raw acceptanceはBLOCKED、same-family retune禁止。Weak+Early Phase-2 / Cloud exact forensic / V20はCLOSED。CoreはJPX segment-transfer PIT repairがactive。

## 残タスク
P0: Core transfer exact-byte capture → transfer ledger → 375-vs-395 row audit → corrected reverse replay/PIT receipt。Parallel repaired picks/endpoint receipt、Canonical sidecar-ahead recoveryも継続。P1: OSS EDINET 27 findings taxonomy。Consensusはformal raw provenanceのみ。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。新規performanceはcost 0%のみ、win=gross return>0。2026はreport/robustness-only。

## GO / NO-GO
**NO-GO / 研究継続。GO候補0件。**
