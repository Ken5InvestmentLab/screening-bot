# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 00:08 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。  
> **固定リンク:** https://github.com/Ken5InvestmentLab/screening-bot/blob/research/automation-coordination/research/RESEARCH_DASHBOARD.md

---

## 0. 全体サマリー

| 項目 | 現在 |
|---|---|
| 最終GO候補 | **0件** |
| Active research branches | **5本** |
| Weak+Early Phase-2 | 2022 fresh validation **FAILED ROBUSTNESS**。G3凍結、Round2閉鎖 |
| 2023-25暫定首位 | **DUAL + G3** mean +7.98% / median +1.74% / win 53.85% / Top3-ex +5.14% |
| Parallel Wave-1 | **新規独立レーン登録済み**。A/B/Eをoutcome未開封で選定し、exact manifest凍結済み |
| Consensus V47 | 48-shard retry `34849054884` active。fetch(0)/fetch(1) raw取得中、accepted artifact 0 |
| V20 | **DEPRIORITIZE** |
| Shadow/Data | endpoint acquisition chronology guard CI GREEN |
| Core / Cloud | fixed Core reject維持。Cloud exact replay unavailable。endpoint provenance primitiveは凍結済み、real receipt/wiring待ち |
| OSS / Validation | cost0 + immutable trial ledger primitive GREEN。DSR receipt binding待ち |
| 最終判定 | **NO-GO / 研究継続** |

---

## 1. Active lanes / HEAD / Next

| Lane | HEAD | Status | Next |
|---|---|---|---|
| Canonical/Event + Shadow/Data | `7606b72f...` | V20 deprioritized / temporal guard GREEN | staleness・endpoint completenessをoutcome-blind監査 |
| Core/Cloud | `6e7dfa45...` | reject維持 / endpoint provenance primitive frozen | real XTKS/vendor manifest + immutable source receipt + evaluator wiring/CI |
| Consensus V47 | `fc96b801...` | raw48 retry active | 重複起動せずusable artifact/timeout receipt監査→frozen acceptance |
| OSS/Validation | `7704641d...` | immutable completed-trial receipt primitive verified | `run_study`/DSRをreceipt-bound化 |
| **Parallel Condition Exploration** | **`7e164ae6...`** | **A1/B1/E1 manifest frozen / performance unopened** | preserved-source/schema receiptをbind→1回だけcost0 batch |

processed済みSHAは再処理しない。production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterには触れない。

---

## 2. Weak+Early Phase-2順位 — frozen cost0

| Rank | Candidate | n | Mean | Median | Win | Top3-ex | Status |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | **DUAL + G3** | 117 | **+7.98%** | **+1.74%** | **53.85%** | **+5.14%** | 2023-25 leader / fresh robustness fail |
| 2 | DUAL_TOP1_AGREEMENT | 140 | +7.17% | +1.25% | 52.14% | +4.79% | primary structural challenger / fresh fail |
| 3 | mean-rank(volr20,body_pct) | 172 | +6.89% | +1.45% | 52.33% | +4.95% | frozen baseline leader |
| 4 | body_pct LOW | 172 | +6.54% | +0.99% | 50.58% | +4.60% | frozen baseline |
| 5 | volr20 LOW | 172 | +6.33% | +1.06% | 51.74% | +4.38% | frozen comparator |

### G3状態
`NO_ACUTE_SELLOFF = previous-session med_ret1 >= -1%`。-1% thresholdは**永久にこのopened evidenceに対してretuneしない**。

- 2023-24: n83 / mean +7.38% / median +1.74% / win 55.42% / Top3-ex +3.62%
- unchanged 2025: n34 / mean +9.43% / median +0.37% / win 50.00% / Top3-ex +0.77%
- 2023-25 total: n117 / mean +7.98% / median +1.74% / win 53.85% / Top3-ex +5.14%

---

## 3. 2022 fresh validation

Preserved causal sourceからfresh validationを構築できたため、2022 surrogateは使っていない。

| Candidate | n | Mean | Median | Win | Top3-ex |
|---|---:|---:|---:|---:|---:|
| DUAL_TOP1 | 21 | +2.62% | -6.19% | 28.57% | -7.55% |
| DUAL + G3 | 17 | +6.08% | -6.00% | 29.41% | -6.26% |

**判定: FAILED ROBUSTNESS**。平均はtail winnerで残るが、中央値・勝率・Top3-exが崩れる。2022結果を見てWeak+Early threshold/gate/rankerを変更しない。

現在のWeak+Early作業はpopulation scarcity / forced-choice / model-period差の**outcome-blind root-cause監査のみ**。

---

## 4. Regime Round2

**CLOSED**。

理由: 事前ルールは「2022 fresh validationが不可能な場合のみRound2」。実際には2022 freshを構築できたため、新しいmarket gateを2022結果を見て作らない。Round1の `breadth_ma20` / `breadth_ret1_pos` / `med_ret1` thresholdも変更しない。

---

## 5. Parallel Condition Exploration — Wave 1

Weak+Earlyとは**完全分離した新規探索**として登録。2022 Weak+Early fresh outcomeをtuning inputにしない。

### Readiness audit
| Family | 判定 | Wave 1 |
|---|---|---|
| A Compression -> expansion | DERIVABLE-CAUSALLY | **SELECT** |
| B Relative reversal vs causal market | DERIVABLE-CAUSALLY | **SELECT** |
| C Gap / overnight | same-open timing ambiguity | DEFER |
| D Liquidity / turnover shock | volr20 redundancy risk | DEFER |
| E Distance to prior structure | DERIVABLE-CAUSALLY | **SELECT** |

### Frozen manifest — performance未開封
- **A1:** prior 5-session range compression / prior20 median <= 0.75 AND signal-session range / prior20 median >= 1.25
- **B1:** candidate 5-session relative return vs same-date market median <= -5pp AND signal-day relative return >= 0
- **E1:** signal close is 0%〜5% above strictly-prior 20-session low

Dense threshold grid、weight tuning、opened resultを見たA2/B2/E2追加は禁止。次にexact preserved-source artifact/run、SHA-256、schema、row/date range、XTKS endpoint receiptをbindし、fail-closed implementation後に**一括1回だけ**cost0 performanceを開く。

Stable advancement screen: win>=55%, mean>=+4%, median>0, Top3-ex>=+3%, sufficient n。  
Monster advancement screen: mean>=+6%, Top3-ex>=+4%, sufficient n + win/median/tail concentration明示。

これらはresearch advancementでありproduction GO基準ではない。

---

## 6. Consensus V47

Formal raw acceptanceは未PASS。48-shard retry run `34849054884` はsingle-activeのまま。

現在:
- `fetch(0)` / `fetch(1)` が raw 1H shard取得中
- visible accepted artifacts = 0
- 残りshardはqueue待ち
- strategy/model/threshold/price-arm/cooldownは変更なし
- duplicate trigger禁止

既存diagnostic-only NOCAP H2: n37 / mean +3.03% / median +0.38% / win 51.35% / Top3-ex -0.54%。**promotion evidenceではない**。

実raw artifactが得られた場合だけpayload/provenance監査後、frozen acceptanceを再実行し、0% diagnosticを比較表へ追加する。

---

## 7. Other lanes

### Canonical / Shadow
Endpoint manifestは`acquired_at`がcontained market-data最新日より前ならfail-closed。CI `34848598262` SUCCESS。V20はdeprioritizedのまま。

### Core / Cloud
Fixed Coreはreplacement candidateとしてreject維持。旧Cloud Monster n63 / historical mean +9.86%はlegacy evidenceのみで、exact replayは **HISTORICAL_EXACT_REPRO_UNAVAILABLE**。pinned XTKS/vendor exact endpoint primitiveは凍結済みだが、real manifest/source receipt + evaluator wiring/CI前にperformance再計算しない。

### OSS / Validation
Optuna cost0-onlyはGREEN。immutable completed-trial ledger/receipt primitiveもCI `34855659820` SUCCESS。次はDSR入力をreceipt-boundにしてmissing/extra/reordered/modified trialをintegration levelでもfail-closed。EDINET real same-ZIPはexternal `EDINET_API_KEY`待ち。

---

## 8. 残タスク

1. **Parallel Wave-1:** preserved-source/schema receipt bind → A1/B1/E1 fail-closed implementation → untouched confirmationを残してsingle cost0 batch。
2. **Weak+Early:** Round2閉鎖維持。population scarcity / forced-choiceをoutcome-blind監査。
3. **Consensus:** run `34849054884` を重複起動せずfirst usable artifactまたはtimeout receiptを回収し、終了後frozen acceptance。
4. **Canonical/Shadow:** staleness / temporal integrity / endpoint completeness監査。
5. **Core:** real XTKS/vendor manifest + source receipt + evaluator wiring/CI。
6. **OSS:** `run_study`/DSR completed-trial receipt binding。
7. Formal/comparable evidenceが揃ったlaneだけでcross-lane arbitration。

---

## 9. Current decision

**NO-GO / 研究継続**

Weak+Earlyは2023-25で強いが2022 fresh robustness fail。Round2は規約どおり閉鎖。並列新探索はperformanceをまだ開けずにA/B/Eのcausal readinessとexact manifest凍結まで進行した。V47はformal raw待ち。Core/Cloud/OSSもprovenance工程が残る。

新規performance比較はすべて **cost 0%**、winは **gross return > 0**。
