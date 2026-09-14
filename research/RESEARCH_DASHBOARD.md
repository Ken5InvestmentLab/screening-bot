# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 00:58 JST  
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
| Parallel Wave-1 | **A/B/E manifest凍結済み、source bytes/provenance receiptまでbind。performance未開封** |
| Consensus V47 | 48-shard retry `34849054884` active。fetch(0)/fetch(1) raw取得中、visible artifact 0 |
| V20 | **DEPRIORITIZE** |
| Shadow/Data | endpoint `expected_through_date` completeness guard **CI GREEN** |
| Core / Cloud | fixed Core reject維持。Cloud exact replay unavailable。real receipt/wiring待ち |
| OSS / Validation | cost0 + immutable trial-ledger primitive GREEN。DSR receipt binding待ち |
| 最終判定 | **NO-GO / 研究継続** |

---

## 1. Active lanes / HEAD / Next

| Lane | HEAD | Status | Next |
|---|---|---|---|
| Canonical/Event + Shadow/Data | `208e1358...` | V20 deprioritized / endpoint completeness guard GREEN | frozen prospective ledgerのsymbol-set・endpoint-session completeness監査 |
| Core/Cloud | `6e7dfa45...` | reject維持 / endpoint provenance primitive frozen | real XTKS/vendor manifest + immutable source receipt + evaluator wiring/CI |
| Consensus V47 | `fc96b801...` | raw48 retry active | 重複起動せずusable artifact/timeout receipt監査→frozen acceptance |
| OSS/Validation | `7704641d...` | immutable completed-trial receipt primitive verified | `run_study`/DSRをreceipt-bound化 |
| **Parallel Condition Exploration** | **`8cfcee63...`** | **source bytes/provenance receipt bound / performance unopened** | exact schema + pinned XTKS endpoint receipt→A1/B1/E1 fail-closed→one-shot cost0 batch |

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
`NO_ACUTE_SELLOFF = previous-session med_ret1 >= -1%`。-1% thresholdはopened evidenceに対してretuneしない。

- 2023-24: n83 / mean +7.38% / median +1.74% / win 55.42% / Top3-ex +3.62%
- unchanged 2025: n34 / mean +9.43% / median +0.37% / win 50.00% / Top3-ex +0.77%
- 2023-25 total: n117 / mean +7.98% / median +1.74% / win 53.85% / Top3-ex +5.14%

---

## 3. 2022 fresh validation

Preserved causal sourceからfresh validationを構築済み。2022 surrogateは不使用。

| Candidate | n | Mean | Median | Win | Top3-ex |
|---|---:|---:|---:|---:|---:|
| DUAL_TOP1 | 21 | +2.62% | -6.19% | 28.57% | -7.55% |
| DUAL + G3 | 17 | +6.08% | -6.00% | 29.41% | -6.26% |

**判定: FAILED ROBUSTNESS**。平均はtail winnerで残るが中央値・勝率・Top3-exが崩れる。2022結果を見てWeak+Early threshold/gate/rankerは変更しない。現在はpopulation scarcity / forced-choice / model-period差の**outcome-blind root-cause監査のみ**。

---

## 4. Regime Round2

**CLOSED**。事前ルールが「2022 fresh validationが不可能な場合のみRound2」で、実際には2022 freshを構築できたため。Round1の `breadth_ma20` / `breadth_ret1_pos` / `med_ret1` thresholdも変更しない。

---

## 5. Parallel Condition Exploration — Wave 1

Weak+Earlyとは完全分離。2022 Weak+Early fresh outcomeをtuning inputにしない。

### Frozen families — performance未開封
- **A1:** prior 5-session range compression / prior20 median <= 0.75 AND signal-session range / prior20 median >= 1.25
- **B1:** candidate 5-session relative return vs same-date market median <= -5pp AND signal-day relative return >= 0
- **E1:** signal close is 0%〜5% above strictly-prior 20-session low

C Gap/overnightはsame-open timing ambiguityでDEFER。D Liquidity/turnoverはopened `volr20 LOW`とのsemantic redundancy riskでDEFER。Dense threshold grid、weight tuning、opened result後のA2/B2/E2追加は禁止。

### Source provenance receipt — 今回前進
`research/PARALLEL_WAVE1_SOURCE_RECEIPT_20260915.md` を追加し、dataset bytesのlineageを明示的にbindした。

- **original source-data run:** `34545440155`
- source artifact ID: `10179500303`
- source artifact ZIP SHA-256: `85cf79fea74f9a122bf0b6b5c1e94d1fda80d468e68ac0d8c774e1a69010bfc4`
- **preservation/hosting run:** `34599959356`
- preserved artifact ID: `10264205130`
- preserved artifact ZIP SHA-256: `095e58986d45bda0092be1767e1b44a4791bf3c617179791d0c99c6d7d01bcb0`
- `tse_daily.csv` SHA-256: `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`
- rows: `4,061,361`
- symbols: `3,700`
- date range: `2022-01-04` → `2026-09-11`

重要: `34599959356`は**preservation host run**、実データ起点は`34545440155`。今後はこの2つを混同しない。2026はdataset内に存在してもselection/tuningには使わずreport/robustness-only。

現在状態は **SOURCE_BYTES_BOUND / SCHEMA+XTKS ENDPOINT RECEIPT PENDING / PERFORMANCE UNOPENED**。次にexact required-column schemaとpinned XTKS session/endpoint completenessをfail-closedでbindしてから、A1/B1/E1を一括1回だけcost0評価する。

Stable advancement screen: win>=55%, mean>=+4%, median>0, Top3-ex>=+3%, sufficient n。  
Monster advancement screen: mean>=+6%, Top3-ex>=+4%, sufficient n + win/median/tail concentration明示。

---

## 6. Consensus V47

Formal raw acceptanceは未PASS。48-shard retry run `34849054884` はsingle-active。

- `fetch(0)` / `fetch(1)` が raw 1H shard取得中
- visible artifacts = 0
- duplicate trigger禁止
- strategy/model/threshold/price-arm/cooldown変更なし

既存diagnostic-only NOCAP H2: n37 / mean +3.03% / median +0.38% / win 51.35% / Top3-ex -0.54%。promotion evidenceではない。実raw artifact取得後のみpayload/provenance監査→frozen acceptance→0% diagnostic追加。

---

## 7. Other lanes

### Canonical / Shadow
`expected_through_date`をmanifest必須化し、acquired_atが期待日より前またはCSV last_dateが期待日を覆わない場合fail-closed。Prospective Shadow CI `34861810023` SUCCESS。performance未開封、V20はdeprioritized。

### Core / Cloud
Fixed Core reject維持。旧Cloud Monster n63 / historical mean +9.86%はlegacy evidenceのみ。exact replayは **HISTORICAL_EXACT_REPRO_UNAVAILABLE**。real XTKS/vendor manifest/source receipt + evaluator wiring/CI前に再計算しない。

### OSS / Validation
Optuna cost0-only GREEN。immutable completed-trial ledger/receipt primitive CI `34855659820` SUCCESS。次はDSR入力をreceipt-bound化。EDINET real same-ZIPはexternal `EDINET_API_KEY`待ち。

---

## 8. 残タスク

1. **Parallel Wave-1:** exact schema + pinned XTKS endpoint-session completeness receipt → A1/B1/E1 fail-closed → one-shot cost0 batch。2026はreport-only。
2. **Weak+Early:** Round2閉鎖維持。population scarcity / forced-choiceをoutcome-blind監査。
3. **Consensus:** run `34849054884` を重複起動せずfirst usable artifactまたはtimeout receipt回収→frozen acceptance。
4. **Canonical/Shadow:** frozen prospective selection ledgerに対するsymbol-set / endpoint-session completeness監査。
5. **Core:** real XTKS/vendor manifest + source receipt + evaluator wiring/CI。
6. **OSS:** `run_study`/DSR completed-trial receipt binding。
7. Formal/comparable evidenceが揃ったlaneだけでcross-lane arbitration。

---

## 9. Current decision

**NO-GO / 研究継続**

Weak+Earlyは2023-25で強いが2022 fresh robustness fail。G3は凍結、Round2は規約どおり閉鎖。並列Wave-1はperformanceを開けずにA/B/E manifestに加え、今回dataset source bytes/provenanceまで固定した。V47はformal raw待ち。新規performance比較はすべて **cost 0%**、winは **gross return > 0**。
