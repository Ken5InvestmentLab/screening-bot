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

## 現在の正式評価候補
### V18
- 350銘柄はMar05-Apr30のwatchlist frequencyだけで固定。
- Jun/Jul/Aug expanding rolling OOS。
- 09/13を別々に意思決定し、09時は13時を見ない。
- absolute probability thresholdを使わず、session内relative rankを使用。
- weighted rank と multi-head consensusを比較。
- fixed Pine/Stable baselinesも同じOOS窓で比較。

### V19
- V18と同じ非リーク・intraday causal。
- 09用 / 13用モデルを分離。
- p_win / p_hit10 / predicted return に加え p_loss10 を明示的に学習。

### V20 run #2+
- actual Tenchi BOTTOMだけに限定した scoring-only rule miner。
- **signal-time特徴のexplicit allow-listのみ**でAND探索。outcome-derived列は禁止。
- Mar-Apr→May validation→Jun test、Mar-May→Jun→Jul、Mar-Jun→Jul→Aug。
- current Stable★6を同一テスト窓で比較。

### V21
- Yahoo Pine BOTTOMだけをtrain/valid/test母集団にする。
- TV actual BOTTOMで学習してYahooへ移すdistribution shiftを解消。
- runtimeはTradingView不要。

### V22
- gate候補: Pine / Stable>=4 / Stable>=5 / Pine OR Stable>=4 / Pine OR Stable>=5 / Pine AND Stable>=4。
- gate/model/policyを前月validationだけで選び、次月testへ固定。

## 今後のPromotion条件
1. future label/returnを使わないuniverse selection。
2. 09時判断が13時データを使わない完全因果。
3. 複数月rolling OOSで一貫。
4. tiny sampleだけの勝利は禁止。
5. Yahoo取得欠損・corporate action・tail lossを監査。
6. 最終的にはlive forward shadowで確認。
7. TradingView teacherは開発時のみ。完成runtimeはTVアクセス0、新規teacher追加0。
8. Production変更はユーザーの明示的Goがあるまで禁止。
