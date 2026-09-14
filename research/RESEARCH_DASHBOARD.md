# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-14 23:30 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。  
> **固定リンク:** https://github.com/Ken5InvestmentLab/screening-bot/blob/research/automation-coordination/research/RESEARCH_DASHBOARD.md

---

## 0. 全体サマリー

| 項目 | 現在 |
|---|---|
| 最終GO候補 | **0件** |
| Active research branches | **4本** |
| 全体マイルストーン進捗 | **約63%** — 成功確率ではなく研究工程の消化率 |
| Weak+Early Phase-2 | 2022 fresh validation **FAILED ROBUSTNESS**。Round2は閉鎖 |
| 2023-25暫定首位 | **DUAL + G3** mean +7.98% / win 53.85% / Top3-ex +5.14%（ただし2022 fresh fail） |
| Consensus V47 | 48-shard retry `34849054884` はactive/queued。accepted raw artifactはまだ0件 |
| V20 | cost0診断が全TopN負、**DEPRIORITIZE** |
| Shadow/Data | endpoint acquisition chronology guard CI GREEN。run `34848598262` SUCCESS |
| Core / Cloud | Core既reject維持。Cloud exact replay **HISTORICAL_EXACT_REPRO_UNAVAILABLE**。pinned XTKS/vendor endpoint primitiveを凍結、real manifest/source receiptとevaluator wiringは未完 |
| OSS / Validation | cost0実装GREEN。immutable completed-trial ledger primitive CI `34855659820` SUCCESS、`run_study`/DSR bindingは未完 |
| 最終判定 | **NO-GO / 研究継続** |

### レーン別マイルストーン消化率

| Lane | 進捗 | 意味 |
|---|---:|---|
| Canonical/Event + Shadow/Data | 約64% | V20診断済み、Shadow temporal guard GREEN。staleness / endpoint completeness監査が残る |
| Core/Cloud | **約56%** | reject/forensic整理済み。fail-closed endpoint provenance primitive凍結済み。real manifest/source receipt + evaluator wiring/CIが残る |
| Consensus V47 | 約58% | daily PIT pass済み。formal raw acceptanceが未達でH2 promotion判定不可 |
| OSS/Validation | **約80%** | cost0・EDINET freeze・trial-ledger primitiveまで固定。DSR receipt bindingとreal EDINET same-ZIPが残る |

進捗率は成功確率ではなく、各laneで事前に必要とした研究・監査工程の消化率。

---

## 1. Active lanes / HEAD / Actions

| Lane | HEAD | Status | Latest run | Next |
|---|---|---|---|---|
| Canonical/Event + Shadow/Data | `7606b72f...` | V20 DEPRIORITIZE / Shadow temporal guard CI green | `34848598262` SUCCESS | staleness / temporal integrityをoutcome-blind監査 |
| Core/Cloud | **`6e7dfa45...`** | Core reject / Cloud exact replay unavailable / pinned endpoint provenance primitive frozen | `34799307163` legacy SUCCESS | real XTKS+vendor manifest/source receiptを凍結→evaluator wiring→dedicated CI |
| Consensus V47 | `0d4aabac...` | 48-shard raw retry active/queued / formal raw未PASS | `34849054884` active/queued | 重複起動せずusable artifact待ち→payload監査→終了後frozen acceptance |
| OSS/Validation | **`7704641d...`** | immutable trial-ledger primitive VERIFIED / DSR binding pending | `34855659820` SUCCESS | `run_study`をreceipt-bound DSRへ接続しintegration test |

### 23:30 Core / Cloud更新

開始時Core HEAD `c41cb897...` はSTATEのlast_seen/last_processedと一致し、processed済みSHAの重複処理なし。最新Core Actionは引き続き `34799307163` SUCCESSで、今回の文書/研究primitive pushから新Action/artifactは発生していない。

Core endpoint再現性監査を1段階進め、`endpoint_provenance.py` とsynthetic unit testを追加。XTKS/vendor endpoint manifestをcalendar name/version + exact open/close raw-bar timestampで固定し、canonical JSONのSHA-256でidentityを縛る。signal+1 / signal+5はmanifest順序だけで決め、missing/duplicate/non-positive endpointはFAIL_CLOSED。observed-dateやfirst/last available rowへのfallbackは禁止。戦略performanceは再計算していない。

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

同時代のexact watch pool / serialized model / feature transforms / training manifestが欠落。現代surrogateで旧Cloudを再現したことにはしない。今回も新しい同時代一次証拠はなく、model-family guessingやportability replayは実施していない。

Core endpoint監査は**primitive凍結段階へ進行**。新しい `endpoint_provenance.py` は次をfail-closedで固定する。

- `calendar_name=XTKS`、一定のcalendar version、strict sorted unique session dates;
- 各sessionのvendor-specific `open_bar_ts` / `close_bar_ts`;
- manifest canonical JSONのSHA-256;
- signal+1をentry、signal+5をexitとしてmanifest位置でmapping;
- exact symbol/timestamp endpointのみ採用し、missing/duplicate/non-positive endpointはFAIL_CLOSED;
- observed-date shifting / first-last available row fallbackは禁止。

Synthetic fixtureでは非取引日gap、missing exact close、hash tamper、duplicate endpoint、unsorted calendarを検証済み。**ただしreal pinned XTKS/vendor manifest、immutable source run/artifact receipt、既存evaluatorへのwiring、dedicated CIは未完**。したがって新しいCore performanceはまだformal comparable evidenceとして計算しない。

---

## 6. OSS / Validation

Optunaはcost0-onlyへ修正済み。非zero `round_trip_cost` はfail-closed。

今回、completed trial provenanceの第一段を完了:
- deterministic ascending trial-number ledger;
- frozen study metadata + completed rowsのcanonical JSON / SHA-256 receipt;
- missing / extra / reordered / duplicate / modified / non-COMPLETE / non-finiteをreject;
- receipt検証後のみtrial-Sharpe vectorを返す `trial_sharpes_from_receipt()`;
- isolated CI `34855659820` **SUCCESS**。

ただし `optuna_discovery.run_study()` はまだDSRへ直接trial-Sharpe listを渡しているため、provenance controlは**PRIMITIVE_VERIFIED_BINDING_PENDING**。次工程でreceipt-bound consumptionへ接続する。

EDINET real same-ZIPは外部 `EDINET_API_KEY` がblocker。synthetic/same-ZIP/hash-chain guardは維持。

---

## 7. H1/H2開封状態

| Lane/Candidate | H1 | H2 | Promotion evidence |
|---|---|---|---|
| Weak+Early | opened | fresh robustness opened | **NO** — robustness fail |
| V20 | 中締め診断 opened | unopened/不適格 | **NO** |
| Consensus V47 NOCAP | diagnostic opened | diagnostic opened | **NO** — formal raw acceptance未PASS |
| Consensus CAP1000_PIT | diagnostic H1 opened | **unopened** | **NO** |
| OSS infrastructure | performance対象外 | performance対象外 | infrastructure only |

---

## 8. 残タスク / blocker

### P0
- **Consensus V47:** run `34849054884` を重複起動しない。usable artifact出現時にreal payload / provenanceを監査し、完了後frozen acceptanceを再実行。
- **Shadow/Data:** chronology guard後のstaleness / endpoint completeness境界をoutcome-blind監査。

### P1
- **Weak+Early:** Round2閉鎖維持。2022 / 2023H2 / 2025H2のpopulation scarcity / forced-choice構造をoutcome-blindで監査。
- **Core:** real pinned XTKS + raw-vendor endpoint manifestとimmutable source receiptを凍結し、`audit_core_canonical_endpoint.py` を新fail-closed primitiveへwiring、dedicated CI PASS後にのみcost0再計算を許可。
- **OSS:** `run_study` selection_bias/DSR inputをimmutable completed-trial receiptへbindingし、receiptをsummaryへ永続化。
- **EDINET:** real same-ZIP cross-checkは外部 `EDINET_API_KEY` 待ち。
- **Cloud:** 新しい同時代一次証拠が出た場合だけexact replay再開。

### P2
- Formal/comparable evidenceが揃ったlaneだけでcross-lane arbitration。
- NO TRADEを許容する最終統合条件の明文化。

---

## 9. Current decision

**NO-GO / 研究継続**

主因:
- Weak+Earlyは2023-25で高性能だが2022 fresh robustness fail。
- Consensusはformal raw acceptance未PASSで、48-shard raw retry実行待ち/進行中。
- Core / V20はreject / deprioritize。
- Cloud exact replayは一次証拠欠落でclosed。
- Core endpoint provenanceはprimitive凍結まで進んだが、real manifest/source receipt + evaluator wiring/CI未完。
- OSSはtrial-ledger primitiveまでGREENだが、DSR consumption bindingが未完了。

新規評価はすべて **cost 0%**、勝率は **gross return > 0**。過去のcosted結果はlegacy evidenceのみで、新しい順位・GO/NO-GOに使わない。
