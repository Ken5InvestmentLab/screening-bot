# 天底極致 No-TV 代替 — Research Ledger

この台帳は実験結果の有効性を取り違えないための記録。Production main / Discord / Sheets は変更しない。

## 正式目標
TradingViewなしで天底極致 BOTTOM 検出＋現行スコアリングを代替し、最終的に Production Stable★6 を超える。
M式は目標ではない。アイデア源として参照する場合のみ可。

## Production benchmark
- Stable★6: ema25 + macdpos + stoch75 + bb80 + pre_down3 + gap_up
- n=55
- 5BD平均 +6.6%
- 勝率 56.4%
- +10%到達 10/55 = 18.18%

## 確定したデータ設計
- 当時の監視母集団: tv-watchlist-builder の historical commits から復元。
- 完成済み日足: Yahoo公式1Dを正本にする。
- 当日途中: Yahoo 1Hから09/13セッションを構成。
- 1H→4H境界: 13:00未満を09側、13:00以降を13側。production ohlcv_4h照合で最良。
- Stable条件再現: 公式1D＋途中1Hで Stable★6 Recall 90.9%, Precision 100%（監査サンプル）。
- teacher BOTTOM件数はライブで増えるので4041固定禁止。2026-09-10途中で4058まで増加。

## 無効 / 最終採用に使わない成績
### V11 / V11.1 / V13 / V14 の旧350-symbol smoke
理由1: 350銘柄抽出時にAugust actual BOTTOM銘柄を優先していたため、outcome予測に未来ラベルのsample leakageがある。
理由2: final daily top選択が09/13を同一日グループで比較し、09時判断時に13時候補を見ていた intraday lookahead がある。
これらの+6%台成績は構造確認用のみ。Champion比較には使用禁止。

### V17
銘柄サンプリングはMar05-Apr30のみで非リーク化したが、絶対score thresholdが月跨ぎで崩壊し、さらにdaily topの09/13 lookaheadが残っていた。最終採用禁止。

### V20 run #1
自動boolean列検出が outcome-derived の `win10` / `win_5bd` を特徴量として採用していたため、32件・平均+18.4%・+10%到達100%という結果は完全なtarget leakage。**全数値を無効扱い**する。
V20 run #2以降はsignal-time特徴の明示allow-list方式へ変更し、`win10 / lose10 / win_5bd / confirmed_5bd` 等を禁止。未知列は自動採用しない。

### Old Stage2
実TV BOTTOMで学習したoutcome selectorをYahoo候補へ移すとdistribution shift。Full-universeでも改善弱く、本線から降格。

## 有効な構造上の発見
- V12 Yahoo Pine state: BOTTOM再現は旧V10より大幅改善。August exact Pine Precision約62.9%, Recall約49.7%。
- Pine state start sensitivity: 2024-09〜2026-02で初期化開始を変えてもAugust Recall約49.5〜49.9%。開始位置は主因ではない。
- production保存4H上でPine状態機械を再計算するとYahoo合成4Hより高Recall。小OHLC差によるstate transition連鎖が残る。
- Pine状態は完全再現のためだけでなく、direct outcome modelの特徴量として使う価値がある。

## 2026-09-10 completed research results
### V18 — current development leader
Leakage-free universe + intraday-causal 09/13 + session-relative multi-head consensus。
- V13 consensus Jun-Aug combined: n=23, avg +3.97%, median +1.18%, robust avg +3.37%, win 65.2%, +10% rate 34.8%, min -11.5%.
- Monthly OOS: Jun n=6 avg +5.58%, Jul n=12 avg +2.05%, Aug n=5 avg +6.66%. All three months positive.
- V13 weighted: n=64 avg +1.18%, win 57.1%.
- V14 consensus: n=26 avg +1.51%; V14 weighted: n=84 avg +0.44%.
- V18 Jun-Aug is now a reused development OOS because later designs were informed by these results. It is no longer a pristine final holdout.

### V19 — session-separated tail model
- V13: n=64 avg +0.85%, median +1.20%, win 62.3%, +10% rate 6.25%.
- V14: n=64 avg +0.55%, win 52.5%.
- Lower-tail head as a simple utility penalty did not beat V18 consensus. Keep only the idea of a tail veto.

### V20 run #2 — leakage-fixed boolean AND miner
- Candidate: n=88 avg -2.83%, win 31.8%, +10% rate 1.14%.
- Current Stable★6 on same Jun-Aug window: n=30 avg -1.32%, win 50.0%.
- Pure boolean AND re-mining is not the path forward.

### V21 — Yahoo Pine-gated outcome model
- V13: n=23 avg +0.29%, win 45.5%.
- V14: n=41 avg +1.57%, win 63.2%.
- Better than Pine fixed rules but below V18 direct consensus. Pine should remain a feature/secondary gate, not the sole candidate gate.

### V22 — adaptive Pine/Stable candidate gate
- Combined: n=25 avg +0.10%, win 58.3%, +10% rate 0%.
- Adaptive gate did not improve the direct route.

### V23 — Stable★6 regime drift audit
Actual production BOTTOM snapshots, same six Stable conditions:
- Mar-May: n=25 avg +16.08%, median +3.8%, win 64.0%, +10% rate 32.0%.
- Jun-Aug: n=30 avg -1.32%, median +0.1%, win 50.0%, +10% rate 6.67%.
- Mar-Aug total: n=55 avg +6.59%, win 56.36%, +10% rate 18.18% — reproduces production headline.
- Monthly Stable★6 avg: Mar +19.56%, Apr +25.66%, May +7.76%, Jun -7.70%, Jul +0.19%, Aug +1.43%.
Conclusion: headline +6.6% is heavily front-loaded. Recent-regime robustness must be a primary promotion criterion.

### V24 — actual-BOTTOM continuous snapshot ML
- Candidate Jun-Aug: n=35 avg +0.80%, robust avg +0.19%, win 48.5%, +10% rate 5.71%.
- Same-window current Stable★6: n=30 avg -1.32%.
- Continuous production snapshot features improve recent average vs current, but remain far below V18 consensus.

## Current development candidates
### V25
- Based on V18 V13 consensus.
- 4 consensus aggregators: min / geometric / harmonic / spread-adjusted.
- top1/top2 per session, no 09→13 lookahead.
- Prior validation is split into first/second halves; unstable one-half-only policies are rejected.
- Also tests a validation-ranked policy bag/vote ensemble.
- Jun-Aug is development OOS, not final untouched holdout.

### V26
- V18-style consensus plus a fourth `p_loss10` head.
- The lower-tail model is trained on prior data only; low predicted -10% risk must also rank well within the current session.
- Tail model is used as a veto/consensus head instead of V19-style simple subtraction.

## Current route priority
1. V25/V26 direct Yahoo-only causal consensus.
2. If one is clearly best, run full historical monitored universe rather than 350-symbol smoke.
3. Freeze architecture and begin live forward shadow. New post-freeze data is the next true holdout.
4. Pine reconstruction remains secondary feature/gate research; exact TV parity is no longer the primary objective.

## Promotion conditions
1. future label/returnを使わないuniverse selection。
2. 09時判断が13時データを使わない完全因果。
3. 複数月rolling OOSで一貫。
4. tiny sampleだけの勝利は禁止。
5. Yahoo取得欠損・corporate action・tail lossを監査。
6. 最終的にはlive forward shadowで確認。
7. TradingView teacherは開発時のみ。完成runtimeはTVアクセス0、新規teacher追加0。
8. Production変更はユーザーの明示的Goがあるまで禁止。
