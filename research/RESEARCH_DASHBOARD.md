# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 15:50 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## 📈 全体進捗
**研究全体の進捗率: 約83%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | 🟢 凍結済み | 100% | 既開封結果をretuneしない |
| **5候補 2022-2026 全期間比較** | 🔴 **P0** | **60%** | exact trade rowsまたはdeterministic reproducerで凍結結果再現 → 年別表 → 2026 report-only |
| Parallel Wave-1 | 🔴 **STALE / P1** | 78% | step8はOHLC ordering integrityでfail-closed。calendar/source再監査禁止。source-grounded dispositionまで停止 |
| Core24 OHLCV completeness | 🟡 **P0 endpoint補助** | 97% | 5候補のentry/exit O/C true-missing影響を照合 |
| Consensus V47 | 🟡 P1 / formal raw BLOCKED | 84% | corrected H2 diagnostic opened。tail-dependent、同family retune禁止 |
| Canonical/Shadow endpoint integrity | 🟢 P1 | 93% | P0比較を直接unblockしない追加拡張は後回し |
| OSS / Validation | 🟢 P1 | **99%** | EDINET 27 findings taxonomy開始。OperatingRevenue1をsource-grounded Class Aとして固定 |
| Cloud Monster exact forensic | ⚫ legacy/reference | 100% | exact model unavailable。参考枠として保持 |

## 🎯 P0 — 5候補を脱落させず全期間比較

primary poolは `body_pct LOW` / `volr20 LOW` / `mean-rank(volr20, body_pct)` / `DUAL_TOP1_AGREEMENT` / `DUAL_TOP1_AGREEMENT + G3 NO_ACUTE_SELLOFF` の5本。threshold/ranker/weight/gate/期間/endpointは変更しない。2022は既開封robustness、2026はreport-only。

まずexact trade rowsまたはdeterministic reproducerで既知2022・2023-25 anchorsを再現し、その後のみ同一コードで2026を開く。単年度マイナスだけでは脱落させず、aggregate・中央値・勝率・Top3-ex・downsideを横並び評価する。

## Parallel Wave-1 — STALE再配分

実HEADは `5a5a22f138d6ebecdc5f172f00907ff06a1a2f41` でSTATEと一致し、新SHAなし。failed run `34998500020` はsource receiptとpinned XTKS calendarまでPASS、step8 causal ledgerでFAIL、endpoint/artifactはskip。既追加のoutcome-blind auditはfrozen daily SHA `6adfb626...` と4,061,361行を固定し、OHLC ordering違反があればperformanceを開かずfail-closedする。

同blockerを複数cycle確認済みのため **STALE** とし、このrunではcalendar/source forensicを繰り返さずOSSへ再配分。Parallelの次境界はsource-generation原因とdispositionの事前固定であり、silent repair/dropは禁止。

## OSS / EDINET — source-grounded taxonomy前進

新規 `research/EDINET_FINDINGS_TAXONOMY_20260916.md` をcommit `771ffc0cd84bcbdd20f4a23d045ff6e03d446572` で追加。

最初の分類 **Class A = custom parserの明示的revenue concept alias欠落** をsource-groundedに固定した。frozen real fixture `S100TYEA` では `jppfs_cor:OperatingRevenue1` / `CurrentYearDuration` / 49,687,000,000 が同一ZIP内に存在し、OSS側 `net_sales` と同値。修正は `OperatingRevenue1` だけをrevenue aliasへ追加する狭い変更 `dcbb7c8726cb02edd3e59c260354a8e7f1f63044`。same-ZIP rerun `34944902155` はSUCCESS、artifact `10386890723` / digest `sha256:2affc141851b7701490866be5ddfd35b740ac15e3a0bd48670d2aba3127f96a7` を確認。performanceによるparser選択ではない。

残りはrow ledgerを回収し、concept alias / context selection / dimensional ambiguity / issued-share priority / normalization / genuine semantic disagreement等へ分類する。未解決はfail-closed、27-finding denominatorは変更しない。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。新規performanceはcost 0%のみ、win=gross return>0。2026はreport/robustness-only。新規条件探索・retune禁止。

## GO / NO-GO
**研究継続 / production NO-GO。** 最終候補を1本へ絞る前に凍結5候補の同一条件2022-2026比較を完了する。
