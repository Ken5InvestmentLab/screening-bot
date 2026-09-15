# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 02:00 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## ⏱ 自動研究ハートビート
5本すべてenabled・直近90分以内。automation停止疑い0本。直近実run: Supervisor 02:00 / Canonical 01:15 / Core 01:24 / Consensus 01:36 / OSS+Parallel 01:49 JST。

## 📈 全体進捗
**研究全体の進捗率: 約83%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、surrogate/retune禁止 |
| Parallel Wave-1 | 🟢 STALE解除・calendar gate修復 | 76% | repaired causal A1/B1/E1 pick ledger → SHA freeze → completeness receipt |
| Core24 OHLCV補完 | 🟢 PIT event repair | 89% | transfer bytes/SHA + 375-vs-395 audit → corrected PIT receipt |
| Consensus V47 | 🟢 corrected H2 diagnostic完了 / formal raw BLOCKED | 84% | same-family retune禁止、formal raw acceptanceのみ |
| Canonical/Shadow endpoint integrity | 🟢 crash-consistency監査 | 90% | sidecar-ahead interruptionの明示的・provenance-preserving recovery/two-phase protocol + regression tests |
| Core endpoint provenance | 🟢 parser contract + transfer contract frozen | 98% | corrected PIT membership receipt |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟢 policy固定 | 98% | 27 findings source-grounded taxonomy |
| V20 Session-Impulse | ⚫ CLOSED | 100% | active queue外 |

## Supervisor 今回の前進 — Parallel STALE解除
ParallelのP0を実際に阻害していた原因を回収。causal picks run `34944605476` はsource artifact検証まではPASSしたが、picks生成直前にXTKS calendar SHA mismatchでfail-closedしていた。独立forensic run `34944974099` は、committed calendar SHA `7342d778...` に対しpreregistered/independently regenerated SHAが `58e67bd2...` で、差分は1 sessionだけと確定: committed側は `2026-08-11` を含み `2026-08-10` を欠落。performance/returnsは未開封。

同じcalendar確認を繰り返さず、research-only workflowをcommit `500093a9` で修正。`exchange-calendars==4.13.1` から2022-2026 XTKS calendarをrun内再生成し、**事前固定済みSHA `58e67bd2...` と完全一致した場合だけ** A1/B1/E1 causal pick ledger生成へ進む。閾値・ranker・endpoint・performance条件は変更していない。次はこのrepaired runのterminal/artifact回収 → endpoint completeness PASSならledger/source/endpoint SHA固定 → その後だけone-shot cost0評価。

## Phase-2 frozen順位 / G3 / fresh / Round2
順位は変更なし。1位 DUAL_TOP1_AGREEMENT、baseline leaderはmean-rank。G3 `med_ret1>=-1%` はretune禁止で固定。Frozen DUAL+G3 comparatorは **n=117 / mean +7.98% / median +1.74% / win 53.85% / Top3-ex +5.14%**。2022 fresh validationは **ROBUSTNESS FAIL固定**、2022 surrogate禁止。Regime Round2は **CLOSED** のまま再開しない。

## STALE / BLOCKED / CLOSED
Parallelは今回の実修正によりSTALE ESCALATEDからACTIVEへ戻した。Consensus V47 formal raw acceptanceはBLOCKED、same-family retune禁止。Weak+Early Phase-2 / Cloud exact forensic / V20はCLOSED。OSSは27 findings taxonomy、Canonicalはcrash-consistency、CoreはJPX segment-transfer PIT repairがactive。

## 中締め診断 / 正式成績の分離
既存Consensus corrected CAP1000_PIT H2は `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE` のまま（2025-07-01..2025-12-30、cost0、n=26、mean +3.82%、median 0.00%、win 30.77%、Top3-ex -3.06%、formal raw acceptance FAIL）。promotion evidenceではなくsame-family retune禁止。

## 残タスク
P0: Parallel repaired picks/endpoint receipt回収、Canonical sidecar-ahead recovery、Core JPX transfer bytes/SHA + 375-vs-395 audit。P1: OSS EDINET 27 findings taxonomy。Consensusはformal raw provenanceのみ。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。新規performanceはcost 0%のみ、win=gross return>0。2026はreport/robustness-only。

## GO / NO-GO
**NO-GO / 研究継続。GO候補0件。**
