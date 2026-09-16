# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 22:22 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## 📈 全体進捗
**研究全体の進捗率: 約83%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | 🟢 凍結済み | 100% | 既開封結果をretuneしない |
| **5候補 2022-2026 全期間比較** | 🔴 **P0** | **60%** | exact trade rowsまたはdeterministic reproducerで凍結結果再現 → 年別表 → 2026 report-only |
| Parallel Wave-1 | 🔴 **STALE / P1** | 78% | step8 OHLC integrity fail-closed。calendar/source再監査禁止 |
| Core24 OHLCV completeness | 🟡 **P0 endpoint補助** | **98%** | daily raw固定済み。Phase2 freeze commitにはtrade rows無しと確認。exact rows/generator回収後ただちにintersection |
| Consensus V47 | 🟡 P1 / formal raw BLOCKED | 84% | corrected H2 diagnostic opened、retune禁止 |
| Canonical/Shadow endpoint integrity | 🟢 P1 | 93% | P0を直接unblockしない追加拡張は後回し |
| OSS / Validation | 🟢 P1 | 99% | Class C same-ZIP再検証成功・解決。残りClass B2 3 docs / 9 rowsのみfail-closed |
| Cloud Monster exact forensic | ⚫ legacy/reference | 100% | exact model unavailable、参考枠保持 |

## 🎯 P0 — 5候補を脱落させず全期間比較
primary poolは `body_pct LOW` / `volr20 LOW` / `mean-rank(volr20, body_pct)` / `DUAL_TOP1_AGREEMENT` / `DUAL_TOP1_AGREEMENT + G3 NO_ACUTE_SELLOFF`。threshold/ranker/weight/gate/期間/endpointは変更しない。2022は既開封robustness、2026はreport-only。

## Core24 — endpoint recovery forensic
`research/WEAK_EARLY_PHASE2_20260914.md` のfreeze commit `4b37f18d...` をparentと比較し、追加ファイルはsummary markdown 1本のみ。**exact per-trade rowsはfreeze commitへ保存されていなかった**。coordination treeに存在する `annual_candidate_detections_2022_2026.csv` は別annual-candidate laneなので5候補の代替には使わない。surrogate substitution禁止。

既存immutable Actions artifact `10264205130` の `tse_daily.csv` は固定済み（4,061,361 rows、SHA-256 `6adfb626...107ba0`）。観測済みrow内field nullは O/H/L/C/V = 0/0/0/0/0、nonpositive O/C = 0/0。OHLC ordering violationは **797 rows**。exact candidate rowsを回収できた候補から required O/C absent row と797-row着地を即時照合する。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updater変更なし。新規performance cost0%、win=gross return>0、2026 report-only。retune禁止。exact-hour/activityはSEALED separate。

## GO / NO-GO
**研究継続 / production NO-GO。** 最終候補を1本へ絞る前に凍結5候補の同一条件2022-2026比較を完了する。
