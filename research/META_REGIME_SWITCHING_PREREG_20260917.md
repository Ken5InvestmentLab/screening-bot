# META Regime Switching Preregistration — 2026-09-17

## Purpose

固定1本のranker/gateだけでなく、**signal時点で観測可能な地合いに応じて既存の凍結候補を切り替えるMetaモード**に再現性があるかを検証する。

重要: これはP0の各候補exact/deterministic再現を置き換えない。まず2022-2025 historical rowsを全候補で同一endpointへ揃え、その後にだけMeta検証を開始する。**2026 outcomeはMeta ruleをfreezeするまで開かない。**

## Candidate pool

Metaが選べるのは、P0でexact/deterministic再現済みになった既存候補だけ。

現行primary:
- weak+early + body_pct LOW
- weak+early + volr20 LOW
- weak+early + mean-rank(volr20, body_pct)
- DUAL_TOP1_AGREEMENT
- DUAL_TOP1_AGREEMENT + G3 NO_ACUTE_SELLOFF

追加候補:
- strict_3pt等の別系統は、exact trade rows/source/code SHAが確定した場合のみpoolへ追加
- legacy Cloud Monsterはexact forensic再現できた場合のみ追加

Meta検証のために新しいcandidate-level ranker、連続閾値探索、weight最適化は行わない。

## Data split / sequence

1. P0-A: 2022-2025 historical exact rowsを候補ごとに完成
2. P0-B: 2022-2025だけで地合い×候補のcross-tabを作成
3. P0-C: leave-one-year-outで単純Meta ruleを評価
4. Meta ruleをコード・閾値・mapping・source SHAごとfreeze
5. **その後に初めて2026を開封**
6. 2026はstatic候補とfrozen Metaの両方をreport/robustness-onlyで一回評価。2026を見てMeta ruleを変更しない

2022は現行Tail modelで計算可能なJun-Dec blockを使用し、full-yearのように扱わない。

## Regime inputs

signal T時点までに観測できるoutcome-blind情報だけを使用する。初期検証軸は3つに限定する。

### A. Market breadth
- feature: causal `breadth_ma20` または同等のsignal-time breadth
- 固定数値grid searchは禁止
- 状態化は原則、signal Tより前のrolling historyだけで計算したpercentile band:
  - LOW: <= 33rd percentile
  - MID: 33rd–67th percentile
  - HIGH: >= 67th percentile
- rolling windowは120 XTKS sessionsを第一候補とし、coverage不足ならfail-closed。window lengthをperformanceで選ばない

### B. Candidate scarcity
- frozen weak+early gate通過後、rank前の同日candidate count
- SCARCE = 1 candidate
- MULTI = 2 candidates以上
- 後から2/3/4件などの閾値gridを作らない

### C. Market / candidate-population range
- feature: causal `range_pct` のsignal-day population statistic
- signal Tより前のrolling history percentile:
  - LOW: <= 33rd percentile
  - MID: 33rd–67th percentile
  - HIGH: >= 67th percentile
- breadthと同様にperformanceによるcutoff調整禁止

初期Metaはこの3軸だけ。特徴量追加は、上記で説明力が不足しても2026を開く前に別preregを作った場合だけ許可。

## Allowed Meta complexity

過学習を避けるため、最終Meta ruleは:
- 最大3 branches
- 使用regime軸は最大2つ
- branchごとの選択肢は「既存候補1本」またはNO TRADEのみ
- continuous score blend / learned weight / tree ensemble / ML classifierは禁止
- 同じregime内で日ごとに別rankerを選ぶようなoutcome-based rescueは禁止

## Historical evaluation

各candidate × regimeについて2022-computable / 2023 / 2024 / 2025とaggregateを出す。

必須:
- n
- mean
- median
- win
- +10 / +20
- -10 / -20
- max up / max down
- Top3-ex
- 100-share P/L
- symbol/date concentration

Meta rule候補はleave-one-year-outで評価し、held-out年をrule構築に使わない形のfold結果を必ず併記する。

## Promotion bar before opening 2026

Metaを2026へ持ち込むには、2022-2025で以下を満たすこと。

1. 単純な固定候補よりaggregate meanだけでなくTop3-exも改善、または同等
2. median / winが明確に悪化しない
3. leave-one-year-outで改善が1年だけに依存しない
4. 特定regimeのnが極端に少なく、数件の大勝ちだけでmappingが決まっていない
5. exact deterministic rowsとregime labelsを再生成できる
6. rule/mappingをSHA pinし、2026開封前にfreeze

満たさない場合はMetaを採用せず、最良のfixed候補比較へ戻る。

## 2026 holdout rule

2026は完全にreport/robustness-only:
- static候補とfrozen Metaを同時に評価
- cutoffを明記
- Meta mapping / threshold / branch / candidate poolの変更禁止
- 2026不調を見てNO TRADE条件や別rankerを追加しない

## Guardrails

production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updater変更禁止。
P0 historical exact comparisonが終わるまでMeta performance探索を先行しない。
