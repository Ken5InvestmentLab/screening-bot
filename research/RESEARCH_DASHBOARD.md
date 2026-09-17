# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-17 09:38 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## 📈 全体進捗
**研究全体の進捗率: 約84%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | 🟢 凍結済み | 100% | 既開封結果をretuneしない |
| **全候補 historical比較 + 2026 holdout** | 🔴 **P0** | **68%** | 2023-25 exact recovery完了。2022/別系統を確定→Meta freeze→最後に2026を一回だけ開封 |
| **Meta地合い切替** | 🟡 **preregistered / P0後段** | **10%** | breadth・candidate scarcity・rangeの最大3軸。2026はMeta rule freezeまでSEALED |
| Parallel Wave-1 | 🔴 **STALE / P1** | 78% | step8 OHLC integrity fail-closed。calendar/source再監査禁止、OSSへ再配分 |
| Core24 OHLCV completeness | 🟢 **P0 endpoint補助** | **99%** | 5候補2023-25 endpoint true missing=0、797 invalid rowsとのintersection=0。2022 endpoint待ち |
| Consensus V47 | 🟡 P1 / formal raw BLOCKED | 84% | corrected H2 diagnostic opened、retune禁止 |
| Canonical/Shadow endpoint integrity | 🟢 P1 | 93% | P0を直接unblockしない追加拡張は後回し |
| OSS / Validation | 🟢 P1 | 99% | same-ZIP実測でcorporate 23件all-match / jpsps investment-fund 21件domain exclusion。summary semantics修正rerun待ち |
| Cloud Monster exact forensic | ⚫ legacy/reference | 100% | exact model unavailable、参考枠保持 |

## 🎯 P0 — 全候補historical比較 → Meta freeze → 2026 holdout
primary poolは `body_pct LOW` / `volr20 LOW` / `mean-rank(volr20, body_pct)` / `DUAL_TOP1_AGREEMENT` / `DUAL_TOP1_AGREEMENT + G3 NO_ACUTE_SELLOFF`。`strict_3pt`等の別系統はexact/deterministic再現できたものだけ追加。threshold/ranker/weight/gate/endpointは変更しない。

**順序を更新:** 2022-2025 historical exact比較を先に完成 → `research/META_REGIME_SWITCHING_PREREG_20260917.md` に従い地合い別cross-tab/LOYOを実施 → Meta mappingをSHA freeze → **その後に初めて2026を開封**。2026はstatic候補とfrozen Metaの両方に対するreport/robustness-only holdoutで、結果を見たretuneは禁止。

## Core24 — five-candidate endpoint coverage PASS for frozen 2023-2025
Actions run `34600083474` / artifact `10264251140` の preserved `v7_causal_tail_cache_2023_2025.csv`（1306 rows、CSV SHA-256 `0398969e...849d`）を回収。凍結Phase2の共通gate `med_ret5<=0 AND ret10<=0.5735294117647058` と各ranker/DUAL/G3をそのままdeterministic再生し、5候補すべてで既存2023-25 n/mean/median/winにexact一致した。

固定daily corpus artifact `10264205130`（4,061,361 rows、SHA-256 `6adfb626...107ba0`）へ canonical entry O / exit C を照合した結果：
- body_pct LOW: 172 trades / 344 required O/C / **true missing 0** / affected trade 0 / invalid endpoint 0
- volr20 LOW: 172 / 344 / **0** / 0 / 0
- mean-rank: 172 / 344 / **0** / 0 / 0
- DUAL_TOP1: 140 / 280 / **0** / 0 / 0
- DUAL+G3: 117 / 234 / **0** / 0 / 0

したがって凍結2023-2025 performance endpointへのOHLC直接欠損影響は5候補すべて0。既知のOHLC ordering violation 797 rowsも5候補のentry/exit endpointへ1件も着地しない。次P0は2022 fresh-validation rows回収と同endpoint監査。**2026はhistorical comparisonとMeta rule freezeの両方が終わるまで開かない。**

## Parallel
実HEAD `5a5a22f138d6ebecdc5f172f00907ff06a1a2f41` はprocessed済みと一致。旧failed run 34998500020のcalendar/source receiptは再監査しない。source-grounded OHLC dispositionが得られるまでSTALE/P1、returns/performance未開封。今回も新SHAなしのためOSSへ再配分。

## OSS EDINET — same-ZIP domain partition corrected
run `35111074253` はSUCCESS、artifact `10452048515` / SHA-256 `79ed32fc372222e951af46ec0a94fbd818d53b12958945f143829c6a8cc06747` を回収した。ここで従来の期待値「41 corporate + 3 multi-fund」が誤りと判明した。

凍結44 ZIPの実測は **23 corporate-domain docs all-match + 21 `jpsps070000` investment-fund-domain exclusions + corporate parser findings 0**。旧summaryはdomain exclusionを`AUDIT_FINDING`へ数えていたため、21件をparser findingのように表示していたが、これはsummary semanticsの問題。accounting値・parser一致・performanceではなくsource taxonomy identityだけでdomainを分ける。

research-only修正:
- `32af600c...`: domain statusを単一/複数fund共通の `OUT_OF_DOMAIN_INVESTMENT_FUND_FILING` に修正。multi-component有無はevidenceとして別記。
- `1041fbc6...`: workflow summaryを `DOMAIN_EXCLUDED` とcorporate parser findingへ明示分離。corporate-domainだけfield statusを集計。

この修正commitでsame-ZIP rerunを待つ。期待は **corporate 23 / all-match 23 / parser finding 0 / domain exclusion 21**。異なれば残差のみfail-closed。returns/performance未開封。

## Meta regime-switching preregistered
`research/META_REGIME_SWITCHING_PREREG_20260917.md` をcommit `a586e98d0d7c6dbed471cf9fde419d9760e1f050` で事前登録。初期軸は **market breadth / candidate scarcity / range** の3つだけ。Meta ruleは最大3 branches・最大2軸、既存凍結候補またはNO TRADEのみを選択可能。continuous weight/ML/tree/grid-searchは禁止。2022-2025でcross-tab + leave-one-year-outを行い、rule/mappingをSHA freezeした後に2026を一回だけ評価する。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updater変更なし。新規performance cost0%、win=gross return>0、2026 report-only。**2026はMeta freeze前に開かない。** retune禁止。exact-hour/activityはSEALED separate。

## GO / NO-GO
**研究継続 / production NO-GO。** まず全候補の2022-2025 historical exact比較を完成し、Meta切替ruleをfreeze。その後に2026をstatic/Meta共通holdoutとして一回だけ開く。
