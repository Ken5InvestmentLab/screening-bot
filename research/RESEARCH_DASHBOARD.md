# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-14 22:22 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。  
> **固定リンク:** https://github.com/Ken5InvestmentLab/screening-bot/blob/research/automation-coordination/research/RESEARCH_DASHBOARD.md

---

## 0. 全体サマリー

| 項目 | 現在 |
|---|---|
| 最終GO候補 | **0件** |
| Active research branches | **4本** |
| 全体マイルストーン進捗 | **約61%** — 成功確率ではなく、事前定義済み研究工程の消化率 |
| Weak+Early Phase-2 | 2022 fresh validation **FAILED ROBUSTNESS**。Round2は閉鎖 |
| 2023-25暫定首位 | **DUAL + G3** mean +7.98% / win 53.85% / Top3-ex +5.14%（ただし2022 fresh fail） |
| Consensus V47 | H1/H2はdiagnostic-only。NOCAP H2 cost0 = n37 / mean +3.03% / median +0.38% / win 51.35% / Top3-ex -0.54%。formal raw acceptance未PASS |
| V20 | cost0診断が全TopN負、**DEPRIORITIZE** |
| Shadow/Data | **endpoint acquisition chronology guard CI GREEN**。取得日時がCSV内の最新データ日より前ならfail-closed。run `34848598262` SUCCESS |
| Core / Cloud | Core既reject維持。Cloud exact replay **HISTORICAL_EXACT_REPRO_UNAVAILABLE** |
| OSS / Validation | **Optuna cost0実装ギャップ解消 / CI 34846417896 SUCCESS**。次はtrial-ledger provenance固定 |
| 最終判定 | **NO-GO / 研究継続** |

### レーン別マイルストーン進捗

| Lane | 進捗率 | 現在地 |
|---|---:|---|
| Canonical/Event + Shadow/Data | 約72% | V20はDEPRIORITIZE。Shadow endpoint provenanceのacquisition chronology guardをCI固定 |
| Core/Cloud | 約90% | Core reject確定、Cloud exact replayは同時代一次証拠欠落までforensic監査済み |
| Consensus V47 | 約73% | daily/PIT契約済み、formal raw取得・acceptanceがblocker |
| OSS/Validation | 約75% | Optuna cost0境界をCI固定。trial-ledger provenanceとEDINET実データsame-ZIPが残る |

進捗率は**成功確率ではない**。performance未開封工程について推測成績は載せない。

---

## 1. Active lanes / HEAD / Actions

| Lane | HEAD | Status | Latest run | Next |
|---|---|---|---|---|
| Canonical/Event + Shadow/Data | `7606b72f...` | V20 DEPRIORITIZE / Shadow temporal guard CI green | `34848598262` **SUCCESS** | 次のstaleness/temporal integrity holeをoutcome-blindで監査 |
| **Core/Cloud** | **`30ddf912...`** | Core reject / Cloud exact replay unavailable | `34799307163` SUCCESS | 新しい同時代一次証拠のみ探索。無ければ再現性・endpoint監査 |
| Consensus V47 | `4c202b16...` | diagnostic完了 / formal raw未PASS | `34810592135` **active/queued matrix** | active runを重複起動せず終了後artifact回収→frozen acceptance |
| OSS/Validation | `098653c2...` | **Optuna cost0 implementation VERIFIED** | `34846417896` **SUCCESS** | completed-trial ledger/provenanceを改変不能化→PSR/DSR入力をreceiptへ拘束 |

### 今回のCanonical/Shadow更新

既存のProspective Shadow daily endpoint guardは `acquired_at` がtimezone-awareであることは検証していたが、CSV内の最新market-data dateより取得日時が前でもmanifestを受理できる余地があった。これをtemporal provenance holeとして修正し、**`acquired_at` のcalendar date < pinned CSVの`last_date`ならmanifest作成時・検証時ともfail-closed**にした。strategy outcome、閾値、TopN、ranker、cooldown、endpointは一切変更していない。新規backtestもない。

既存continuity CIでは候補削除・並べ替え、resolved endpoint改変、resolved→unresolved回帰、daily SHA改変、receipt改変など42 testsがgreenだった。今回のchronology guard用にcreation/validationの2 regression testsを追加し、run `34848598262` は**SUCCESS**。直前の実装commitに対するrun `34848560630` もSUCCESS。

---

## 2. 候補ランキングと正式性

### 現在の暫定ランキング

1. **Weak+Early DUAL + G3** — 2023-2025 cost0では最上位だが、2022 fresh robustness failのためGO不可。
2. **Weak+Early DUAL_TOP1** — 同じく2022 fresh fail。Round2は閉鎖済み。
3. **Consensus V47 NOCAP** — diagnostic上はCAP1000_PITより関心度が高いが、formal raw acceptance未PASSのため**promotion rankingには未参加**。

V20 / fixed Core / Failed-Breakdown Reclaim / Precision系はrejectまたはDEPRIORITIZE。既開封結果を見てthreshold・ranker・gate・cooldown・endpoint・weightを後付け調整して救済しない。

---

## 3. 現在の主要performance（すべて新規比較は cost 0%）

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

**判定:** robustness FAIL。2022を見てthresholdを後付け変更しない。

### Consensus V47 — midterm diagnostic only

| Arm/Period | n | Mean | Median | Win | +10 | +20 | +50 | -10 | -20 | Top3-ex |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| NOCAP H1 | 50 | +0.11% | -2.73% | 36.00% | 16.00% | 8.00% | 0.00% | 12.00% | 2.00% | -2.01% |
| CAP1000_PIT H1 | 60 | -1.16% | -0.40% | 46.67% | 13.33% | 0.00% | 0.00% | 11.67% | 3.33% | -2.06% |
| **NOCAP H2** | **37** | **+3.03%** | **+0.38%** | **51.35%** | **27.03%** | **16.22%** | **2.70%** | **13.51%** | **2.70%** | **-0.54%** |

formal raw acceptance前のため**promotion evidenceではない**。NOCAP H2は既開封diagnostic、CAP1000_PIT H2は未開封。formal promotion H1/H2はraw acceptanceとclean PIT feature materialization完了まで未開封扱い。

### V20

coverage-bypassed中締め診断はcost0でも全TopNが負で**DEPRIORITIZE**。formal promotion evidenceではない。734 active symbol/date欠損が残る。既開封診断から救済retuneしない。

---

## 4. Core / Cloud forensic — 歴史値と再現性を分離

| 種別 | n | 5BD平均 | 扱い |
|---|---:|---:|---|
| **旧Cloud Monster 歴史値** | **63** | **+9.86%** | legacy historical evidence。新規再現値ではない |
| 現代surrogate（既棄却例） | 69 | -1.36% | exact replayではない。再利用しない |
| exact replay | — | — | **HISTORICAL_EXACT_REPRO_UNAVAILABLE** |

当時のexact 575 Watch pool、元model/serialized state、完全feature list/transforms/objective/calibration、training manifestが未回収。現在treeにも `.pkl/.pickle/.joblib/.onnx/.pt/.pth/.sav/.ipynb` はなく、現行MTF model codeは2026-09-11以降の研究コードなので旧Cloudの完全一致再現ソースとして扱わない。

---

## 5. OSS / Validation

### 今回解消済みのP0

Frozen contractではOptuna discovery/performanceはcost0必須だったが、実装API/CLIが0.5% defaultかつ非zero costを許容していた。これを以下で解消した。

- `run_study()` defaultを0.0へ固定し、非zero `round_trip_cost` は即 `ValueError`。
- CLI defaultも0.0、非zero指定はfail-closed。
- synthetic testをcost0へ変更し、0.1%指定が拒否される明示テストを追加。
- summaryにも `COST0_ONLY` policyを記録。
- isolated CI `34846417896` **SUCCESS**。

この修正ではstrategy outcomeを新規開封していない。Discovery期間 2022-07-01..2023-12-31、2024/2025/2026 selection禁止、Optunaが調整できるparameterはLogisticRegression `C`のみ、completed trialsのPSR/DSR sensitivity保持という既存境界も維持。

### 次のOSS工程

現在のPSR/DSR helperはtrial Sharpe vectorを受け取れるが、それが**frozen studyで完了した全trialの完全な集合**であることを改変不能に証明していない。次はcompleted-trial ledgerを決定的順序で保存・hash化し、missing/extra/reordered/modified trialでfail-closedし、DSRをad-hoc vectorではなくreceiptからだけ消費させる。

EDINET実歴史same-ZIP cross-checkは、metadata no-replacement selector / daily raw SHA256 / hash-chain / selected ZIP SHA256 / same-ZIP boundaryまで凍結済み。実metadata取得は外部 `EDINET_API_KEY` がblocker。

---

## 6. H1 / H2 開封状態

| Family | H1 | H2 | Promotion evidence |
|---|---|---|---|
| Weak+Early | 既開封 | fresh 2022まで開封 | robustness fail / NO-GO |
| V20 | 中締めdiagnostic開封 | promotion H2へ進めない | NO |
| Core fixed | 既評価 | 2025H2でreject | NO |
| Consensus V47 | diagnostic H1開封 | NOCAP diagnostic H2開封 / CAP1000 H2未開封 | **NO — formal raw acceptance未PASS** |
| OSS Optuna infra | synthetic only | N/A | strategy promotionを許可しない |

---

## 7. 残タスク / blocker

### P0
- **Consensus V47 raw acquisition / frozen acceptance:** run `34810592135` active中。重複起動禁止。終了後artifactを回収し、usable real rawのみprovenance付きでmergeしてfrozen acceptanceを再実行。
- **Shadow temporal integrity:** acquisition chronology guardはCI green。次はsource取得時刻とendpoint completeness/staleness境界をoutcome-blindで監査する。

### P1
- **OSS trial-ledger provenance:** completed Optuna trial集合をimmutable receiptへ固定しPSR/DSR入力を拘束。
- **EDINET real same-ZIP:** 外部 `EDINET_API_KEY` が得られたら2023-2025全calendar-day metadata→hash-chain→frozen selector一回→doc ID/ZIP SHA固定→same-ZIP parser cross-check。
- Core/Cloudは新しい同時代一次証拠が現れた場合のみexact replay再開。

### P2
- Formal/comparable evidenceが揃ったlaneだけでcross-lane arbitration。
- NO TRADEを許容する最終統合条件の明文化。

---

## 8. Current decision

**NO-GO / 研究継続**

主因:
- Weak+Earlyは2023-25で高性能だが2022 fresh robustness fail。
- Consensusはformal raw acceptance未PASS。
- Core/V20はreject/deprioritize。
- Cloud exact replayは一次証拠欠落でclosed。
- Shadow/Dataはprovenance guardを強化済みで、performance rankingには影響なし。
- OSSのcost0実装ギャップは解消したが、multiple-testing provenanceとEDINET実same-ZIP監査が未完了。

新規評価はすべて **cost 0%**、勝率は **gross return > 0**。過去の0.5%/1% costed結果はlegacy evidenceのみで、新しい順位・GO/NO-GOに使わない。
