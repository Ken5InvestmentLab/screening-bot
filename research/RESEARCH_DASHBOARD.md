# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 21:24 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## 📈 全体進捗
**研究全体の進捗率: 約83%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | 🟢 凍結済み | 100% | 既開封結果をretuneしない |
| **5候補 2022-2026 全期間比較** | 🔴 **P0** | **60%** | exact trade rowsまたはdeterministic reproducerで凍結結果再現 → 年別表 → 2026 report-only |
| Parallel Wave-1 | 🔴 **STALE / P1** | 78% | step8 OHLC integrity fail-closed。calendar/source再監査禁止 |
| Core24 OHLCV completeness | 🟡 **P0 endpoint補助** | **98%** | daily raw corpus回収済み。5候補entry/exit O/C intersectionを実行 |
| Consensus V47 | 🟡 P1 / formal raw BLOCKED | 84% | corrected H2 diagnostic opened、retune禁止 |
| Canonical/Shadow endpoint integrity | 🟢 P1 | 93% | P0を直接unblockしない追加拡張は後回し |
| OSS / Validation | 🟢 P1 | 99% | Class C basis-aware adapter実装済み。Class B2はfail-closed |
| Cloud Monster exact forensic | ⚫ legacy/reference | 100% | exact model unavailable、参考枠保持 |

## 🎯 P0 — 5候補を脱落させず全期間比較
primary poolは `body_pct LOW` / `volr20 LOW` / `mean-rank(volr20, body_pct)` / `DUAL_TOP1_AGREEMENT` / `DUAL_TOP1_AGREEMENT + G3 NO_ACUTE_SELLOFF`。threshold/ranker/weight/gate/期間/endpointは変更しない。2022は既開封robustness、2026はreport-only。

## Core24 — daily raw corpusを回収・固定
旧 `daily raw not established` blockerは解消。既存immutable Actions artifact `tvfree-frozen-dataset-run80-preserved`（run 34599959356 / artifact 10264205130 / artifact digest `095e5898...1bcb0`）に `tse_daily.csv` が存在し、file SHA-256=`6adfb626...107ba0`、4,061,361 data rows、2022-01-04〜2026-09-11、3,701 symbol stringsを確認。

観測済みrow内のfield nullは O/H/L/C/V = 0/0/0/0/0、nonpositive O/C = 0/0。ただし required symbol-date row自体の欠落は候補ledgerとのintersection前なので **missing zero claimは禁止**。

OHLC ordering violationは **797 rows**：2022-05-17=272、2024-04-04=1、2024-06-05=16、2024-11-15=10、2025-05-23=9、2026-09-11=489。silent repair/drop禁止。5候補のentry/exitがこの797 rowsへ着地するかを必ず別計上する。exact-hour/activityは別項目SEALEDでdaily endpoint比較を止めない。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updater変更なし。新規performance cost0%、win=gross return>0、2026 report-only。retune禁止。

## GO / NO-GO
**研究継続 / production NO-GO。** 最終候補を1本へ絞る前に凍結5候補の同一条件2022-2026比較を完了する。
