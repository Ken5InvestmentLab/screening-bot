# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 16:46 JST  
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
| OSS / Validation | 🟢 P1 | **99%** | frozen 27 finding docsをClass B/Cへ完全partition。semantic resolutionは未完了fail-closed |
| Cloud Monster exact forensic | ⚫ legacy/reference | 100% | exact model unavailable。参考枠として保持 |

## 🎯 P0 — 5候補を脱落させず全期間比較
primary poolは `body_pct LOW` / `volr20 LOW` / `mean-rank(volr20, body_pct)` / `DUAL_TOP1_AGREEMENT` / `DUAL_TOP1_AGREEMENT + G3 NO_ACUTE_SELLOFF` の5本。threshold/ranker/weight/gate/期間/endpointは変更しない。2022は既開封robustness、2026はreport-only。

まずexact trade rowsまたはdeterministic reproducerで既知2022・2023-25 anchorsを再現し、その後のみ同一コードで2026を開く。単年度マイナスだけでは脱落させず、aggregate・中央値・勝率・Top3-ex・downsideを横並び評価する。

## Parallel Wave-1 — STALE継続
実HEAD `5a5a22f138d6ebecdc5f172f00907ff06a1a2f41` はSTATE processed SHAと一致し、新SHAなし。旧failed run/calendar/source forensicは再確認せず、source-grounded OHLC dispositionが可能になるまでP1 STALE。performanceは未開封、silent repair/drop禁止。

## OSS / EDINET — frozen row ledger回収・taxonomy前進
same-ZIP run `34944902155` の未失効artifact `10386890723`（digest `sha256:2affc141851b7701490866be5ddfd35b740ac15e3a0bd48670d2aba3127f96a7`）を回収し、44 comparable document receipts + summaryを直接監査した。

凍結denominatorは維持: primary 48、source unavailable 4、comparable 44、all-match 17、**finding docs 27**。one-sided finding rowsは33件で、構造的に完全partitionできた。

- **Class B: context/member ambiguity — 3 docs / 9 rows**。`S100QF0X`, `S100RWZI`, `S100UXL5` はcustom側が assets/equity/operating_income の3項目すべて `ambiguous`、OSS側は値あり。alias missingではない。source context/member確認までfail-closed。
- **Class C: ProfitLoss vs OSS net_income_owners semantic coverage — 24 docs / 24 rows**。全件が custom=`jppfs_cor:ProfitLoss`, context=`CurrentYearDuration_NonConsolidatedMember`, custom valueあり、OSS `net_income_owners=null` の同一pattern。24件の独立欠損ではなくsemantic/concept coverage disagreement。ProfitLossを自動的にowners profitへ置換しない。source/OSS semantics確認までfail-closed。

taxonomy更新commitは `e9af85cb8c4b4aad33bc5898dbe47b2e19c5d0b3`。これは分類完了であって27 findingsの解消ではない。performanceはparser選択に使用していない。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。新規performanceはcost 0%のみ、win=gross return>0。2026はreport/robustness-only。新規条件探索・retune禁止。

## GO / NO-GO
**研究継続 / production NO-GO。** 最終候補を1本へ絞る前に凍結5候補の同一条件2022-2026比較を完了する。
