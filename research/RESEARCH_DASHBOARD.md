# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 18:48 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## 📈 全体進捗
**研究全体の進捗率: 約83%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | 🟢 凍結済み | 100% | 既開封結果をretuneしない |
| **5候補 2022-2026 全期間比較** | 🔴 **P0** | **60%** | exact trade rowsまたはdeterministic reproducerで凍結結果再現 → 年別表 → 2026 report-only |
| Parallel Wave-1 | 🔴 **STALE / P1** | 78% | step8 OHLC integrity fail-closed。calendar/source再監査禁止 |
| Core24 OHLCV completeness | 🟡 **P0 endpoint補助** | 97% | 5候補のentry/exit O/C true-missing影響を照合 |
| Consensus V47 | 🟡 P1 / formal raw BLOCKED | 84% | corrected H2 diagnostic opened、retune禁止 |
| Canonical/Shadow endpoint integrity | 🟢 P1 | 93% | P0を直接unblockしない追加拡張は後回し |
| OSS / Validation | 🟢 P1 | **99%** | **Class B2 multi-source context collisionをfrozen bytesで確認**。semantic mapping未確立につきfail-closed |
| Cloud Monster exact forensic | ⚫ legacy/reference | 100% | exact model unavailable、参考枠保持 |

## 🎯 P0 — 5候補を脱落させず全期間比較
primary poolは `body_pct LOW` / `volr20 LOW` / `mean-rank(volr20, body_pct)` / `DUAL_TOP1_AGREEMENT` / `DUAL_TOP1_AGREEMENT + G3 NO_ACUTE_SELLOFF`。threshold/ranker/weight/gate/期間/endpointは変更しない。2022は既開封robustness、2026はreport-only。

## Parallel Wave-1 — STALE継続
実HEAD `5a5a22f138d6ebecdc5f172f00907ff06a1a2f41` はprocessed SHAと一致、新SHAなし。旧failed run/calendar/source forensicは再確認せず、source-grounded OHLC dispositionまでP1 STALE。performance未開封、silent repair/drop禁止。

## OSS / EDINET — Class B2までsource-groundedに前進
pre-parser frozen artifact（run `34943585921`, artifact `10385897929`, digest `sha256:3b63996b8cd1d49aadaabbd1b5456e80b24fd68727dd3141f8d724b7d277fe81`）を直接取得し、Class B 3文書のtype=5 XBRL-to-CSV bytesをoutcome-blind監査した。

`S100QF0X / S100RWZI / S100UXL5` は、assets/equity/operating_income/net_incomeすべてで同じCurrentYear context familyを再利用しながら、**3 / 4 / 3個の別embedded `G...` report CSVにそれぞれ異なるcurrent値が存在**する。instantだけでなくdurationにも同じ構造があるため、field alias不足ではない。context-id-onlyでも一意化不能。

- S100QF0X: 3 mapped report CSVs、各mapped field current候補3、distinct current values 3
- S100RWZI: 4 / 4 / 4
- S100UXL5: 3 / 3 / 3

値そのものはreceiptへ出していない。strategy returns/performanceも未開封。**first/last CSV、最大/最小値、OSS値を選ぶ処置は禁止**。filing/document identityからexactly one embedded `G...` reportへ対応する独立semantic mappingを証明できるまで3 docs / 9 Class-B finding rowsはfail-closed維持。

再現script `tvfree_screener/edinet_context_member_audit.py`、taxonomy `research/EDINET_CLASS_B2_FROZEN_CONTEXT_AUDIT_20260916.md`。OSS HEAD `8a5679e70a65efee8240dc3ebbc7ad9929272a15`。connector-originated commitでは今回新Actionが自動起動しなかったため、workflow実行receiptは次のnormal/dispatch run待ち。ただし分類自体はfrozen artifact bytesから直接再現済み。

Class C 24 docs / 24 rows（custom `ProfitLoss` NonConsolidated vs OSS `net_income_owners=null`）は未変更。semantic equivalence証明までfail-closed。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updater変更なし。新規performance cost0%、win=gross return>0、2026 report-only。retune禁止。

## GO / NO-GO
**研究継続 / production NO-GO。** 最終候補を1本へ絞る前に凍結5候補の同一条件2022-2026比較を完了する。
