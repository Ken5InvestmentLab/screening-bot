# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 17:48 JST  
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
| OSS / Validation | 🟢 P1 | **99%** | Class Bをdocument-level correlated ambiguityへnarrow。actual source context inspectionは未完了fail-closed |
| Cloud Monster exact forensic | ⚫ legacy/reference | 100% | exact model unavailable。参考枠として保持 |

## 🎯 P0 — 5候補を脱落させず全期間比較
primary poolは `body_pct LOW` / `volr20 LOW` / `mean-rank(volr20, body_pct)` / `DUAL_TOP1_AGREEMENT` / `DUAL_TOP1_AGREEMENT + G3 NO_ACUTE_SELLOFF` の5本。threshold/ranker/weight/gate/期間/endpointは変更しない。2022は既開封robustness、2026はreport-only。

まずexact trade rowsまたはdeterministic reproducerで既知2022・2023-25 anchorsを再現し、その後のみ同一コードで2026を開く。単年度マイナスだけでは脱落させず、aggregate・中央値・勝率・Top3-ex・downsideを横並び評価する。

## Parallel Wave-1 — STALE継続
実HEAD `5a5a22f138d6ebecdc5f172f00907ff06a1a2f41` はSTATE processed SHAと一致し、新SHAなし。旧failed run/calendar/source forensicは再確認せず、source-grounded OHLC dispositionが可能になるまでP1 STALE。performanceは未開封、silent repair/drop禁止。

## OSS / EDINET — Class Bをsource-receiptで1段narrow
same-ZIP run `34944902155` のartifact `10386890723`（digest `sha256:2affc141851b7701490866be5ddfd35b740ac15e3a0bd48670d2aba3127f96a7`）を再利用し、既processed SHAの分類を繰り返さず、3 Class-B documentsのper-document receiptsを直接比較した。

凍結denominatorは不変: primary 48、source unavailable 4、comparable 44、all-match 17、finding docs 27、one-sided rows 33。

### Class B1 — document-level correlated ambiguity signature
`S100QF0X`, `S100RWZI`, `S100UXL5` は3文書すべてで、custom parserが **assets / equity / operating_income / net_income の4 mapped fieldsを同時に `ambiguous`** と判定している。one-sided findingとして数えるのはassets/equity/operating_incomeの9 rowsで、net_incomeはOSSもnullのため`BOTH_MISSING`だが、ambiguity signature自体は4 fieldに跨る。

一方、同じreceipt内でrevenue / operating_cash_flowはcustom `missing` であり、`ambiguous`とは区別されている。したがって現時点では「個別field alias欠落」よりも、**instant fields（assets/equity）とduration fields（operating_income/net_income）を横断するdocument-level context/member collision** が安全なnarrow classification。OSS値を採用せず、field-specific aliasも追加しない。

Class B1 taxonomy commit: `74d7afa3133b3cd61c495c7f5052346e044fde93`。次は3 frozen source ZIPのactual XBRL contexts/membersを取得し、4 ambiguous mapped conceptsのcandidate contextsを列挙して、1つのdeterministic cross-field ruleで整合的に解けるかを確認する。sourceが取れなければfail-closed継続。

Class Cの24 docs / 24 rows（custom `ProfitLoss` NonConsolidated vs OSS `net_income_owners=null`）は未変更。semantic equivalenceを証明するまでfail-closed。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。新規performanceはcost 0%のみ、win=gross return>0。2026はreport/robustness-only。新規条件探索・retune禁止。

## GO / NO-GO
**研究継続 / production NO-GO。** 最終候補を1本へ絞る前に凍結5候補の同一条件2022-2026比較を完了する。
