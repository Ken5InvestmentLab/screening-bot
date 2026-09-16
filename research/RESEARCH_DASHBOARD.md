# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 19:49 JST  
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
| OSS / Validation | 🟢 P1 | **99%** | **Class C 24件の原因解決。Class B2のみsemantic mapping未確立でfail-closed** |
| Cloud Monster exact forensic | ⚫ legacy/reference | 100% | exact model unavailable、参考枠保持 |

## 🎯 P0 — 5候補を脱落させず全期間比較
primary poolは `body_pct LOW` / `volr20 LOW` / `mean-rank(volr20, body_pct)` / `DUAL_TOP1_AGREEMENT` / `DUAL_TOP1_AGREEMENT + G3 NO_ACUTE_SELLOFF`。threshold/ranker/weight/gate/期間/endpointは変更しない。2022は既開封robustness、2026はreport-only。

## Parallel Wave-1 — STALE継続
実HEAD `5a5a22f138d6ebecdc5f172f00907ff06a1a2f41` はprocessed SHAと一致、新SHAなし。旧failed run/calendar/source forensicは再確認せず、source-grounded OHLC dispositionまでP1 STALE。performance未開封、silent repair/drop禁止。

## OSS / EDINET — Class C semantic cause resolved
最新の成功same-ZIP run `35081622646` / artifact `10440293333`（digest `sha256:147181ed5fd58df53d223f107d3539520a578c11055092705dc84db5f889cb55`）を回収し、Class C 24 docs / 24 rowsを再確認した。全24件が custom `jppfs_cor:ProfitLoss` / `CurrentYearDuration_NonConsolidatedMember` を OSS `net_income_owners` と比較した `OSS_MISSING_CUSTOM_VALUE` だった。

固定OSS dependencyは `edinet-tools==0.8.4`。upstream 0.8.0+仕様ではnet incomeはownership basisで明示分離され、`jppfs_cor:ProfitLoss` は **total basis → `net_income_total`**、owners-attributable elementsだけが **`net_income_owners`** を埋める。cross-basis coalescingは明示的に禁止されている。

したがってClass Cは「OSS parserが同じfactを24件取りこぼした」のではなく、**こちらのresearch crosscheck adapterがtotal-basis custom factをowners-basis OSS fieldへ誤対応させたsemantic mapping mismatch** とsource-groundedに確定した。

固定disposition:
- `jppfs_cor:ProfitLoss` → `report.net_income_total`
- owners-attributable net-income element → `report.net_income_owners`
- basis不明 → fail-closed、推測/coalesce禁止

taxonomy: `research/EDINET_CLASS_C_OWNERSHIP_BASIS_DISPOSITION_20260916.md`、OSS HEAD `072ca5a0b94322e4225841ba87435ae48d3ab558`。次はresearch-only adapterへbasis-aware mappingを実装し、同じfrozen ZIPを再実行する。残差があればfail-closed。

### Class B2 — 未解決継続
`S100QF0X / S100RWZI / S100UXL5` は複数embedded `G...` reportによるmulti-source context collision。filing identityからexactly one reportへ対応する独立semantic mappingが証明できるまで3 docs / 9 rowsはfail-closed。first/last/max/min/OSS値による選択は禁止。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updater変更なし。新規performance cost0%、win=gross return>0、2026 report-only。retune禁止。

## GO / NO-GO
**研究継続 / production NO-GO。** 最終候補を1本へ絞る前に凍結5候補の同一条件2022-2026比較を完了する。
