# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-14 21:43 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。  
> **固定リンク:** https://github.com/Ken5InvestmentLab/screening-bot/blob/research/automation-coordination/research/RESEARCH_DASHBOARD.md

---

## 0. 全体サマリー

| 項目 | 現在 |
|---|---|
| 最終GO候補 | **0件** |
| Active research branches | **4本** |
| Weak+Early Phase-2 | 2022 fresh validation **FAILED ROBUSTNESS**。Round2は閉鎖 |
| 2023-25暫定首位 | **DUAL + G3** mean +7.98% / win 53.85% / Top3-ex +5.14%（ただし2022 fresh fail） |
| Consensus V47 | H1/H2はdiagnostic-only。NOCAP H2 cost0 = n37 / mean +3.03% / median +0.38% / win 51.35% / Top3-ex -0.54%。formal raw acceptance未PASS |
| V20 | cost0診断が全TopN負、**DEPRIORITIZE** |
| Core / Cloud | Core既reject維持。Cloud exact replay **HISTORICAL_EXACT_REPRO_UNAVAILABLE** |
| OSS / Validation | Optuna cost0実装ギャップで新規performance **fail-closed** |
| 最終判定 | **NO-GO / 研究継続** |

---

## 1. Active lanes

| Lane | HEAD | Status | Next |
|---|---|---|---|
| Canonical/Event | `480bc9b5...` | V20 DEPRIORITIZE | V47 accepted rawが自然に得られた場合のみgap reconciliation |
| **Core/Cloud** | **`30ddf912...`** | Core reject / Cloud exact replay unavailable / primary-evidence provenance監査前進 | 新しい同時代一次証拠のみ探索。無ければ再現性・endpoint監査 |
| Consensus V47 | `263b91af...` | diagnostic完了 / formal raw未PASS | formal retry終了後、exact merge + frozen acceptance |
| OSS/Validation | `6e9045e9...` | Optuna cost0 implementation gap BLOCKED | API/CLI/tests cost0-only化→isolated CI green |

---

## 2. Core / Cloud forensic

### 進捗

- **Core/Cloud進捗率:** forensic exact-replay可否の判定は **約90%**。残る10%は「失われた同時代一次証拠がGit履歴/保存artifactから新たに見つかるか」のみで、model-family guessingでは埋めない。
- **Cloud Monster完全一致復元段階:** `spec凍結 → 元期間再現` の入口で停止。**HISTORICAL_EXACT_REPRO_UNAVAILABLE**。別期間横展開には進んでいない。
- **最新HEAD:** `30ddf9120188fd62cc5d29d2ab235df58b4e94e0`
- **最新Core Action:** run `34799307163` / **SUCCESS**（Precision Discovery Batch）。今回のforensic docs-only更新では新規Actionなし。

### 歴史値と再現結果を分離

| 種別 | n | 5BD平均 | 扱い |
|---|---:|---:|---|
| **旧Cloud Monster 歴史値** | **63** | **+9.86%** | legacy evidence。新規再現値ではない |
| 現代surrogate（既棄却例） | 69 | -1.36% | exact replayではない。再利用しない |
| exact replay | — | — | **未成立** |

歴史値については、当時のexact 575 Watch pool、元model/serialized state、完全feature list/transforms/objective/calibration、training manifestが未回収。したがって `n=63 / +9.86%` を新規結果として扱わない。

### 今回の新しいforensic finding

1. Core/Cloud branchの現在treeをserialized/model/notebook候補拡張子で全件監査したが、`.pkl/.pickle/.joblib/.onnx/.pt/.pth/.sav/.ipynb` は**0件**。
2. `research/tentei_cloud/mtf_monster_model.py` の履歴は **2026-09-11** の commit `0de654b4aac1e1d57c346ae2063378d9364f723c`（`research: predeclare causal 4H vs MTF Monster model`）から始まる。
3. よって同ファイルは旧Cloud Monster `n=63 / +9.86%` の同時代一次証拠ではなく、**exact replay代用品として使用禁止**。
4. 新しいperformance計算・portability replay・model-family guessingは実施していない。

詳細: `research/tentei_cloud/CORE_CLOUD_FORENSIC_LOG_20260914_2143.md`

### 既reject Core

- current fixed Core: **REJECT**
- Failed-Breakdown Reclaim: **REJECT**
- Prior-Close Reclaim: **REJECT**
- Precision 3-family batch: **REJECT**
- 既reject familyはthreshold/liquidity/cooldown/ranker等で救済retuneしない。

### Blocker

Cloud exact replayのblockerは性能不足ではなく、**identity-critical historical evidenceの欠落**。新証拠が無い限りこの結論を維持する。

### 次アクション

- older Git objects / preserved Actions artifacts に genuinely contemporaneous な一次証拠が現れた場合だけ exact replayを再開。
- 無ければCloudを閉じたまま、Coreのcross-lane reproducibility / endpoint監査へ戻る。
- rejected familyの再実行によるmetric再生成はしない。

### 候補ランキングへの影響

**なし。** 旧Cloud Monsterをpromotion候補へ戻していない。

---

## 3. 現在の主要performance（cost 0%）

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

### Consensus diagnostic only

| Arm/Period | n | Mean | Median | Win | +10 | +20 | +50 | -10 | -20 | Top3-ex |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| NOCAP H1 | 50 | +0.11% | -2.73% | 36.00% | 16.00% | 8.00% | 0.00% | 12.00% | 2.00% | -2.01% |
| CAP1000_PIT H1 | 60 | -1.16% | -0.40% | 46.67% | 13.33% | 0.00% | 0.00% | 11.67% | 3.33% | -2.06% |
| **NOCAP H2** | **37** | **+3.03%** | **+0.38%** | **51.35%** | **27.03%** | **16.22%** | **2.70%** | **13.51%** | **2.70%** | **-0.54%** |

formal raw acceptance前のためpromotion/ranking evidenceではない。

---

## 4. Current decision

**NO-GO / 研究継続**

主因:
- Weak+Earlyは2023-25で高性能だが2022 fresh robustness fail。
- Consensusはformal raw acceptance未PASS。
- Core/V20はreject/deprioritize。
- Cloud exact replayは一次証拠欠落でclosed。
- OSS Optunaはcost0実装ギャップ修正待ち。

新規評価はすべて **cost 0%**、勝率は **gross return > 0**。過去の0.5%/1% costed結果はlegacy evidenceのみで、新しい順位・GO/NO-GOに使わない。
