# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 22:48 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## 📈 全体進捗
**研究全体の進捗率: 約83%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | 🟢 凍結済み | 100% | 既開封結果をretuneしない |
| **5候補 2022-2026 全期間比較** | 🔴 **P0** | **60%** | exact trade rowsまたはdeterministic reproducerで凍結結果再現 → 年別表 → 2026 report-only |
| Parallel Wave-1 | 🔴 **STALE / P1** | 78% | step8 OHLC integrity fail-closed。calendar/source再監査禁止 |
| Core24 OHLCV completeness | 🟡 **P0 endpoint補助** | **98%** | daily raw固定済み。exact rows/generator回収後ただちにintersection |
| Consensus V47 | 🟡 P1 / formal raw BLOCKED | 84% | corrected H2 diagnostic opened、retune禁止 |
| Canonical/Shadow endpoint integrity | 🟢 P1 | 93% | P0を直接unblockしない追加拡張は後回し |
| OSS / Validation | 🟢 P1 | 99% | Class C解決済み。Class B2原因もmulti-fund out-of-domainまで確定、domain gate実装rerun待ち |
| Cloud Monster exact forensic | ⚫ legacy/reference | 100% | exact model unavailable、参考枠保持 |

## 🎯 P0 — 5候補を脱落させず全期間比較
primary poolは `body_pct LOW` / `volr20 LOW` / `mean-rank(volr20, body_pct)` / `DUAL_TOP1_AGREEMENT` / `DUAL_TOP1_AGREEMENT + G3 NO_ACUTE_SELLOFF`。threshold/ranker/weight/gate/期間/endpointは変更しない。2022は既開封robustness、2026はreport-only。

## Parallel
実HEAD `5a5a22f138d6ebecdc5f172f00907ff06a1a2f41` はprocessed済みと一致。旧failed run 34998500020のcalendar/source receiptは再監査しない。source-grounded OHLC dispositionが得られるまでSTALE/P1、returns/performance未開封。

## OSS EDINET — Class B2 semantic cause resolved
basis-aware same-ZIP run 35092381577はSUCCESS、44 comparable inputs中41 all-match、残り3 docs / 9 rowsだった。

22:48 JSTにimmutable pre-parser artifact `10385897929` の凍結ZIP bytesだけを再確認。残る `S100QF0X / S100RWZI / S100UXL5` は普通の単一企業fundamental filingではなく、`jpsps070000` の**投資信託multi-fund filing**だった。

- S100QF0X / FundCode G04764: `-000` cover/DEI + `-001/-002/-003` component statements
- S100RWZI / FundCode G14585: `-000` + `-001/-002/-003/-004`
- S100UXL5 / FundCode G14307: `-000` + `-001/-003/-004`
- numbered componentsは同じCurrentYear/PriorYear non-consolidated contextを持つが値が異なる
- S100QF0Xの`-000`にはFundNameCoverPageで3ファンドが列挙され、FundCodeDEI=G04764、issuer/filerはDaiwa Asset Management

したがってClass B2は **OUT_OF_DOMAIN_MULTI_FUND_FILING** と分類。first component / max/min / OSS一致値などで1 corporate rowへ潰すことは禁止。corporate-fundamental crosscheckではfail-closed除外し、fund-level identityを別途明示モデル化する場合のみ再投入する。

Disposition: `research/EDINET_CLASS_B2_DOMAIN_DISPOSITION_20260916.md` on OSS commit `ea8e5c4a...`。次はresearch-only domain gateを実装してsame-ZIP rerunし、3件が「match」ではなく明示的domain exclusionになることをreceipt化する。performanceは開かない。

## Core24 — endpoint recovery forensic
Phase2 freeze commitにはexact per-trade rowsが保存されていなかった。既存immutable Actions artifact `10264205130` の `tse_daily.csv` は固定済み（4,061,361 rows、SHA-256 `6adfb626...107ba0`）。観測済みrow内field nullは O/H/L/C/V = 0/0/0/0/0、nonpositive O/C = 0/0。OHLC ordering violationは **797 rows**。exact candidate rowsを回収できた候補から required O/C absent row と797-row着地を即時照合する。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updater変更なし。新規performance cost0%、win=gross return>0、2026 report-only。retune禁止。exact-hour/activityはSEALED separate。

## GO / NO-GO
**研究継続 / production NO-GO。** 最終候補を1本へ絞る前に凍結5候補の同一条件2022-2026比較を完了する。
