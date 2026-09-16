# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-16 15:24 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## 📈 全体進捗
**研究全体の進捗率: 約83%**

> 比較対象をDUAL+G3単独から5候補へ拡張したため、完了済み作業が戻ったのではなくP0スコープ増加により84%→83%へ再計算。

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | 🟢 凍結済み | 100% | 既開封結果をretuneしない |
| **5候補 2022-2026 全期間比較** | 🔴 **P0** | **60%** | exact trade rowsまたはdeterministic reproducerで凍結結果再現 → 年別表 → 2026 report-only |
| Parallel Wave-1 | 🟡 P1 | 78% | OHLC integrity issueは保持。P0比較中にperformanceを開かない |
| Core24 OHLCV completeness | 🟡 **P0 endpoint補助** | 97% | 5候補のentry/exit O/C true-missing影響を照合 |
| Consensus V47 | 🟡 P1 / formal raw BLOCKED | 84% | corrected H2 diagnostic opened。tail-dependent、同family retune禁止 |
| Canonical/Shadow endpoint integrity | 🟢 P1 | 93% | P0比較を直接unblockしない追加拡張は後回し |
| Core endpoint provenance | 🟡 source semantics確定 | 99% | independent raw execution/activity bytesのpin |
| Cloud Monster exact forensic | ⚫ legacy/reference | 100% | exact model unavailable。参考枠として保持 |
| OSS / Validation | 🟢 P1 | 98% | EDINET 27 findings source-grounded taxonomy |
| V20 Session-Impulse | ⚫ CLOSED | 100% | active queue外 |

## 🎯 新P0 — 5候補を脱落させず全期間比較

ユーザー判断により、DUAL+G3だけを先に最終候補扱いする方針を撤回。  
同じpreserved causal Weak+Early baseで凍結済みの以下5条件を、同じendpoint・cost契約で横並び比較する。

1. **body_pct LOW**
2. **volr20 LOW**
3. **mean-rank(volr20, body_pct)**
4. **DUAL_TOP1_AGREEMENT**
5. **DUAL_TOP1_AGREEMENT + G3 NO_ACUTE_SELLOFF**（`med_ret1 >= -1%`固定）

変更禁止:
- threshold
- ranker / weight
- G3 gate
- signal period
- endpoint
- cost / win definition

2022は既開封fresh robustness blockでありtuning禁止。2026はreport/robustness-only。

### 凍結済みhistorical anchors

| Candidate | 2022 computable | 2022 mean | 2023-25 n | 2023-25 mean | median | win | Top3-ex |
|---|---:|---:|---:|---:|---:|---:|---:|
| body_pct LOW | n23 | +1.77% | 172 | +6.54% | +0.99% | 50.58% | +4.60% |
| volr20 LOW | n23 | +1.95% | 172 | +6.33% | +1.06% | 51.74% | +4.38% |
| mean-rank | n23 | +1.73% | 172 | +6.89% | +1.45% | 52.33% | +4.95% |
| DUAL_TOP1 | n21 | +2.62% | 140 | +7.17% | +1.25% | 52.14% | +4.79% |
| DUAL + G3 | n17 | +6.08% | 117 | +7.98% | +1.74% | 53.85% | +5.14% |

### 完了条件

まず過去artifact/branchからexact trade rowsを回収する。回収不能なら1本のdeterministic reproducerで5候補を再生成する。

2026を開く前に、各候補について少なくとも既知の2022 computable blockと2023-25凍結結果が一致すること。historical trade rowsが回収できる場合は `signal_date + symbol + candidate` の完全一致を要求する。

その後に同じコード・同じsourceで以下を生成する。

- 2022 / 2023 / 2024 / 2025 / 2026
- 2022-2026 aggregate
- n / mean / median / win / +10 / +20 / -10 / -20 / max up / max down / Top1-ex / Top3-ex
- exact entry/exit価格が固定できた場合のみ100株ずつの損益も参考値として併記

**単年度マイナスだけでは脱落させない。** 全期間aggregateと年別安定性、中央値、勝率、Top3-ex、下方tailを合わせて比較する。

## 参考枠 — 脱落ではなく正規化待ち

- **Old Cloud Monster Priority A** — legacy n63 / mean +9.86%。exact probability model消失のためprimary表へは未投入。
- **V29 fixed_min98_both** — target/populationが異なり、historical 350-name watchlist。exact replay可能になるまで参考。
- **weak+early × V31 full-JPX** — historical結果は保持。April 2025依存が強いため、同一契約へのrow-level正規化まで参考。
- **Consensus CAP1000_PIT** — corrected H2 run 34976174775はSUCCESSだがcoverage契約が別で、Top1/Top3-exでtail依存。Weak+Early 5候補の直接順位には混ぜない。

## Core24 OHLCV実数監査
endpoint影響監査もDUAL+G3だけでなく、5候補すべての `next XTKS open` / `fifth XTKS close` に必要なO/Cへ拡張する。true missingと正常no-dataを分離し、補間・synthetic barは禁止。

## Coordination
- multi-candidate frozen spec: `research/SUPERVISOR_MULTI_CANDIDATE_FULL_PERIOD_20260916.md`
- Consensus branch new HEAD `28389b7be8f1a8c95720b844ce5ce72aaedae35c` は今回processed済み。
- corrected CAP1000_PIT H2: run `34976174775` SUCCESS、formal raw promotion evidenceではなくdiagnosticのみ。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。新規performanceはcost 0%のみ、win=gross return>0。2026はreport/robustness-only。新規条件探索・retune禁止。

## GO / NO-GO
**研究継続 / production NO-GO。** 最終候補を1本へ絞る前に、凍結済み5候補の同一条件2022-2026比較を完了する。
