# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 23:24 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## 📈 全体進捗
**研究全体の進捗率: 約84%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | 🟢 凍結済み | 100% | 既開封結果をretuneしない |
| **5候補 2022-2026 全期間比較** | 🔴 **P0** | **68%** | 2023-25 exact deterministic recovery完了。次は2022 frozen block回収→同監査→2026 report-only |
| Parallel Wave-1 | 🔴 **STALE / P1** | 78% | step8 OHLC integrity fail-closed。calendar/source再監査禁止 |
| Core24 OHLCV completeness | 🟢 **P0 endpoint補助** | **99%** | 5候補2023-25 endpoint true missing=0、797 invalid rowsとのintersection=0。2022 endpoint待ち |
| Consensus V47 | 🟡 P1 / formal raw BLOCKED | 84% | corrected H2 diagnostic opened、retune禁止 |
| Canonical/Shadow endpoint integrity | 🟢 P1 | 93% | P0を直接unblockしない追加拡張は後回し |
| OSS / Validation | 🟢 P1 | 99% | Class C解決済み。Class B2原因もmulti-fund out-of-domainまで確定、domain gate実装rerun待ち |
| Cloud Monster exact forensic | ⚫ legacy/reference | 100% | exact model unavailable、参考枠保持 |

## 🎯 P0 — 5候補を脱落させず全期間比較
primary poolは `body_pct LOW` / `volr20 LOW` / `mean-rank(volr20, body_pct)` / `DUAL_TOP1_AGREEMENT` / `DUAL_TOP1_AGREEMENT + G3 NO_ACUTE_SELLOFF`。threshold/ranker/weight/gate/期間/endpointは変更しない。2022は既開封robustness、2026はreport-only。

## Core24 — five-candidate endpoint coverage PASS for frozen 2023-2025
Actions run `34600083474` / artifact `10264251140` の preserved `v7_causal_tail_cache_2023_2025.csv`（1306 rows、CSV SHA-256 `0398969e...849d`）を回収。凍結Phase2の共通gate `med_ret5<=0 AND ret10<=0.5735294117647058` と各ranker/DUAL/G3をそのままdeterministic再生し、5候補すべてで既存2023-25 n/mean/median/winにexact一致した。

固定daily corpus artifact `10264205130`（4,061,361 rows、SHA-256 `6adfb626...107ba0`）へ canonical entry O / exit C を照合した結果：
- body_pct LOW: 172 trades / 344 required O/C / **true missing 0** / affected trade 0 / invalid endpoint 0
- volr20 LOW: 172 / 344 / **0** / 0 / 0
- mean-rank: 172 / 344 / **0** / 0 / 0
- DUAL_TOP1: 140 / 280 / **0** / 0 / 0
- DUAL+G3: 117 / 234 / **0** / 0 / 0

したがって**凍結2023-2025 performance endpointへのOHLC直接欠損影響は5候補すべて0**。既知のOHLC ordering violation 797 rowsも5候補のentry/exit endpointへ1件も着地しない。receiptは `research/tentei_cloud/CORE_FIVE_CANDIDATE_ENDPOINT_COVERAGE_RECEIPT_20260916_2324.json`。これは2022/2026を開いた主張ではない。

次P0: 2022 fresh-validationの凍結/recoverable causal rowsを回収し同じendpoint監査を実施。2026はSupervisorのdeterministic historical recovery条件を満たすまで開かない。

## Parallel
実HEAD `5a5a22f138d6ebecdc5f172f00907ff06a1a2f41` はprocessed済みと一致。旧failed run 34998500020のcalendar/source receiptは再監査しない。source-grounded OHLC dispositionが得られるまでSTALE/P1、returns/performance未開封。

## OSS EDINET — Class B2 semantic cause resolved
basis-aware same-ZIP run 35092381577はSUCCESS、44 comparable inputs中41 all-match、残り3 docs / 9 rows。残りは `jpsps070000` の投資信託multi-fund filingであり、corporate-fundamental crosscheckではfail-closed除外。次はresearch-only domain gate実装rerun。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updater変更なし。新規performance cost0%、win=gross return>0、2026 report-only。retune禁止。exact-hour/activityはSEALED separate。

## GO / NO-GO
**研究継続 / production NO-GO。** 最終候補を1本へ絞る前に凍結5候補の同一条件2022-2026比較を完了する。
