# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 21:48 JST  
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
| OSS / Validation | 🟢 P1 | 99% | **Class C same-ZIP再検証成功・解決**。残りClass B2 3 docs / 9 rowsのみfail-closed |
| Cloud Monster exact forensic | ⚫ legacy/reference | 100% | exact model unavailable、参考枠保持 |

## 🎯 P0 — 5候補を脱落させず全期間比較
primary poolは `body_pct LOW` / `volr20 LOW` / `mean-rank(volr20, body_pct)` / `DUAL_TOP1_AGREEMENT` / `DUAL_TOP1_AGREEMENT + G3 NO_ACUTE_SELLOFF`。threshold/ranker/weight/gate/期間/endpointは変更しない。2022は既開封robustness、2026はreport-only。

## OSS — Class C corrected same-ZIP validation
basis-aware adapter commit `700de43b...` のsame-ZIP run `35092381577` は **SUCCESS**。artifact `10444563724`、digest `sha256:c207bce85ef2bf1dc8185a6ddf086cb0c4261e1655d060da478064af1613950c` を固定。

44 comparable documents中、**41 docsがall compared fields agree、findingsは3 docsだけ**。旧Class C 24件の `ProfitLoss` vs `net_income_owners` findingは全消滅し、net incomeは `MATCH=41 / BOTH_MISSING=3`。したがってClass Cは `CROSSCHECK_ADAPTER_OWNERSHIP_BASIS_MISMATCH` としてsame-ZIP実証まで完了。

残るfindingはClass B2の `S100QF0X / S100RWZI / S100UXL5` のみで、assets/equity/operating_incomeの **3 docs / 9 one-sided rows**。filing/documentから正しいembedded `G...` reportを独立に一意化できるまでfail-closed。performance/returnsは未開封。

## Core24 — daily raw corpusを回収・固定
既存immutable Actions artifact `tvfree-frozen-dataset-run80-preserved` に `tse_daily.csv` が存在。観測済みrow内field nullは O/H/L/C/V = 0/0/0/0/0、nonpositive O/C = 0/0。ただし required symbol-date row自体の欠落は候補ledgerとのintersection前なので missing zero claimは禁止。

OHLC ordering violationは **797 rows**。silent repair/drop禁止。5候補のentry/exitがこの797 rowsへ着地するかを別計上する。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updater変更なし。新規performance cost0%、win=gross return>0、2026 report-only。retune禁止。

## GO / NO-GO
**研究継続 / production NO-GO。** 最終候補を1本へ絞る前に凍結5候補の同一条件2022-2026比較を完了する。
