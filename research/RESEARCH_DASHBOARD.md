# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 20:50 JST  
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
| OSS / Validation | 🟢 P1 | **99%** | **Class C basis-aware adapter実装済み・same-ZIP rerun中。Class B2はfail-closed** |
| Cloud Monster exact forensic | ⚫ legacy/reference | 100% | exact model unavailable、参考枠保持 |

## 🎯 P0 — 5候補を脱落させず全期間比較
primary poolは `body_pct LOW` / `volr20 LOW` / `mean-rank(volr20, body_pct)` / `DUAL_TOP1_AGREEMENT` / `DUAL_TOP1_AGREEMENT + G3 NO_ACUTE_SELLOFF`。threshold/ranker/weight/gate/期間/endpointは変更しない。2022は既開封robustness、2026はreport-only。

## Parallel Wave-1 — STALE継続
実HEAD `5a5a22f138d6ebecdc5f172f00907ff06a1a2f41` はprocessed SHAと一致、新SHAなし。旧failed run/calendar/source forensicは再確認せず、source-grounded OHLC dispositionまでP1 STALE。performance未開封、silent repair/drop禁止。

## OSS / EDINET — Class C basis-aware mappingを実装
Class C 24 docs / 24 rowsのsource-grounded原因は、custom `jppfs_cor:ProfitLoss`（total basis）をOSS `net_income_owners`へ比較していたresearch adapterのownership-basis mismatch。

research-only `tvfree_screener/edinet_oss_crosscheck.py` をcommit `700de43b199ace40920df441764af03ca9b59a64` で修正した。固定rule:
- `jppfs_cor:ProfitLoss` → `net_income_total`
- owners-attributable element → `net_income_owners`
- basis不明かつcustom値あり → `UNCLASSIFIED_NET_INCOME_BASIS` としてfail-closed
- 値やperformanceを見てbasisを選ばない

このcommitでsame-ZIP workflow run `35092381577` が起動済み。20:50 JST時点ではin-progressで、exact frozen pre-parser ZIPを再利用する。完了後にClass C残差を確認し、cleanならcorrected receiptをfreeze、残差があればそのままfail-closed。

### Class B2 — 未解決継続
`S100QF0X / S100RWZI / S100UXL5` は複数embedded `G...` reportによるmulti-source context collision。filing identityからexactly one reportへ対応する独立semantic mappingが証明できるまで3 docs / 9 rowsはfail-closed。first/last/max/min/OSS値による選択は禁止。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updater変更なし。新規performance cost0%、win=gross return>0、2026 report-only。retune禁止。

## GO / NO-GO
**研究継続 / production NO-GO。** 最終候補を1本へ絞る前に凍結5候補の同一条件2022-2026比較を完了する。
