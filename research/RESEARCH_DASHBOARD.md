# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-14 23:05 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。  
> **固定リンク:** https://github.com/Ken5InvestmentLab/screening-bot/blob/research/automation-coordination/research/RESEARCH_DASHBOARD.md

---

## 0. 全体サマリー

| 項目 | 現在 |
|---|---|
| 最終GO候補 | **0件** |
| Active research branches | **4本** |
| 全体マイルストーン進捗 | **約61%** — 成功確率ではなく研究工程の消化率 |
| Weak+Early Phase-2 | 2022 fresh validation **FAILED ROBUSTNESS**。Round2は閉鎖 |
| 2023-25暫定首位 | **DUAL + G3** mean +7.98% / win 53.85% / Top3-ex +5.14%（ただし2022 fresh fail） |
| Consensus V47 | 旧12-shard run `34810592135` は180分timeout反復でcancel。48-shard retry `34849054884` はactive。23:05時点でfetch(0)/fetch(1)がraw取得中、artifactはまだ0件 |
| V20 | cost0診断が全TopN負、**DEPRIORITIZE** |
| Shadow/Data | endpoint acquisition chronology guard CI GREEN。run `34848598262` SUCCESS |
| Core / Cloud | Core既reject維持。Cloud exact replay **HISTORICAL_EXACT_REPRO_UNAVAILABLE**。XTKS calendar / endpoint-row completeness未固定を監査で確認 |
| OSS / Validation | Optuna cost0実装ギャップ解消 / CI `34846417896` SUCCESS。次はtrial-ledger provenance |
| 最終判定 | **NO-GO / 研究継続** |

---

## 1. Active lanes / HEAD / Actions

| Lane | HEAD | Status | Latest run | Next |
|---|---|---|---|---|
| Canonical/Event + Shadow/Data | `7606b72f...` | V20 DEPRIORITIZE / Shadow temporal guard CI green | `34848598262` SUCCESS | staleness / temporal integrityをoutcome-blind監査 |
| Core/Cloud | `c41cb897...` | Core reject / Cloud exact replay unavailable / endpoint provenance audit | `34799307163` legacy | pinned XTKS calendar + endpoint completeness receiptを凍結 |
| Consensus V47 | **`0d4aabac...`** | **48-shard raw retry active / formal raw未PASS** | `34849054884` active | 重複起動せずfirst artifact待ち→payload監査→終了後frozen acceptance |
| OSS/Validation | `098653c2...` | Optuna cost0 implementation VERIFIED | `34846417896` SUCCESS | completed-trial ledger/provenanceを改変不能化 |

### 23:05 Supervisor更新

Consensus branchに未処理HEAD `0d4aabac...` を検出してdiff確認済み。これは48-shard retryの状態同期のみで、strategy / model / threshold / price-arm / cooldownは変更していない。run `34849054884` はfetch(0) / fetch(1)が `Fetch raw 1H shard` 実行中で、visible remaining jobsはqueued。artifactはまだ0件。重複triggerはしていない。

Canonical / Core / OSSはSTATE記録済みSHAと一致し、重複処理なし。

---

## 2. 候補ランキングと正式性

1. **Weak+Early DUAL + G3** — 2023-2025 cost0では最上位だが、2022 fresh robustness failのためGO不可。
2. **Weak+Early DUAL_TOP1** — 同じく2022 fresh fail。Round2は閉鎖済み。
3. **Consensus V47 NOCAP** — diagnostic上は関心候補だが、formal raw acceptance未PASSのためpromotion ranking未参加。

V20 / fixed Core / Failed-Breakdown Reclaim / Precision系はrejectまたはDEPRIORITIZE。既開封結果を見てthreshold・ranker・gate・cooldown・endpoint・weightを後付け調整して救済しない。

---

## 3. 現在の主要performance（新規比較はすべて cost 0%）

### Weak+Early 2023-2025 frozen

| Candidate | n | Mean | Median | Win | Top3-ex |
|---|---:|---:|---:|---:|---:|
| DUAL_TOP1 | 140 | +7.17% | +1.25% | 52.14% | +4.79% |
| **DUAL + G3** | **117** | **+7.98%** | **+1.74%** | **53.85%** | **+5.14%** |

### 2022 fresh validation

| Candidate | n | Mean | Median | Win | Top3-ex |
|---|---:|---:|---:|---:|---:|
| DUAL_TOP1 | 21 | +2.62% | -6.19% | 28.57% | -7.55% |
| DUAL + G3 | 17 | +6.08% | -6.00% | 29.41% | -6.26% |

**判定:** robustness FAIL。2022結果を見てthresholdを後付け変更しない。

### Consensus V47 — diagnostic only

| Arm/Period | n | Mean | Median | Win | Top3-ex |
|---|---:|---:|---:|---:|---:|
| NOCAP H1 | 50 | +0.11% | -2.73% | 36.00% | -2.01% |
| CAP1000_PIT H1 | 60 | -1.16% | -0.40% | 46.67% | -2.06% |
| NOCAP H2 | 37 | +3.03% | +0.38% | 51.35% | -0.54% |

formal raw acceptance前のためpromotion evidenceではない。CAP1000_PIT H2は未開封。

---

## 4. Weak+Early Phase-2 status

Frozen basis:
- previous-session `med_ret5 <= 0`
- candidate `ret10 <= 0.5735294117647058`
- one candidate/day
- endpoint = next XTKS open -> fifth XTKS close
- DUAL_TOP1_AGREEMENT = body_pct Top1とvolr20 Top1が一致した日のみ採用
- G3 = `med_ret1 >= -1%`。**-1%をretuneしない**

2023H2 / 2025H2の弱さと2022 fresh failureを確認済み。2022 freshが構築できたため、事前ルールどおり**Regime Round2は開かない**。現在はpopulation scarcity / forced-choice / model-period差のoutcome-blind root-cause監査のみ継続する。opened outcomeから新gateを発明しない。

---

## 5. Core / Cloud forensic

| 種別 | n | 5BD平均 | 扱い |
|---|---:|---:|---|
| 旧Cloud Monster 歴史値 | 63 | +9.86% | legacy historical evidence |
| exact replay | — | — | **HISTORICAL_EXACT_REPRO_UNAVAILABLE** |

同時代のexact watch pool / serialized model / feature transforms / training manifestが欠落。現代surrogateで旧Cloudを再現したことにはしない。

Core endpoint監査では、rawで観測されたdate集合やfirst/last available rowだけで5BD endpointを作ると、市場全体欠損日やpartial sessionでcanonical mappingが崩れるリスクを確認。新しいcanonical relabeling前にpinned XTKS calendar/version/hashとrequired endpoint-row completenessをfail-closedで固定する。

---

## 6. OSS / Validation

Optunaはcost0-onlyへ修正済み。非zero `round_trip_cost` はfail-closed、CI `34846417896` SUCCESS。

次工程はcompleted trial全件を決定的順序でledger化・hash化し、missing / extra / reorder / modifyをrejectして、PSR/DSRをad-hoc vectorではなくreceiptだけから消費させる。

EDINET real same-ZIPは外部 `EDINET_API_KEY` がblocker。

---

## 7. 残タスク / blocker

### P0
- **Consensus V47:** run `34849054884` を重複起動しない。first artifact出現時にreal payload / provenanceを監査し、完了後usable rawだけmergeしてfrozen acceptanceを再実行。
- **Shadow/Data:** chronology guard後のstaleness / endpoint completeness境界をoutcome-blind監査。

### P1
- **Weak+Early:** Round2閉鎖維持。2022 / 2023H2 / 2025H2のpopulation scarcity / forced-choice構造をoutcome-blindで監査。
- **Core:** pinned XTKS calendar + endpoint completeness receiptを凍結。
- **OSS:** immutable completed-trial ledger / provenance。
- **Cloud:** 新しい同時代一次証拠が出た場合だけexact replay再開。

### P2
- Formal/comparable evidenceが揃ったlaneだけでcross-lane arbitration。
- NO TRADEを許容する最終統合条件の明文化。

---

## 8. Current decision

**NO-GO / 研究継続**

主因:
- Weak+Earlyは2023-25で高性能だが2022 fresh robustness fail。
- Consensusはformal raw acceptance未PASSで、48-shard raw retry実行中。
- Core / V20はreject / deprioritize。
- Cloud exact replayは一次証拠欠落でclosed。
- OSSはcost0契約解消済みだがmultiple-testing provenance未完了。

新規評価はすべて **cost 0%**、勝率は **gross return > 0**。過去のcosted結果はlegacy evidenceのみで、新しい順位・GO/NO-GOに使わない。
