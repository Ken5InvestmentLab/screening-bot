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
- **5BD horizon purge必須**: test月のモデル/ポリシー選択に使える過去行は `exit_date_5bd < test_start` のみ。前月末シグナルの5BD結果がtest月に確定する場合は使用禁止。

## 無効 / 最終採用に使わない成績
### V11 / V11.1 / V13 / V14 の旧350-symbol smoke
理由1: 350銘柄抽出時にAugust actual BOTTOM銘柄を優先していたため、outcome予測に未来ラベルのsample leakageがある。
理由2: final daily top選択が09/13を同一日グループで比較し、09時判断時に13時候補を見ていた intraday lookahead がある。
これらの+6%台成績は構造確認用のみ。Champion比較には使用禁止。

### V17
銘柄サンプリングはMar05-Apr30のみで非リーク化したが、絶対score thresholdが月跨ぎで崩壊し、さらにdaily topの09/13 lookaheadが残っていた。最終採用禁止。

### V18 / V19 / V20 run #2 / V21 / V22 / V24
09/13 intraday lookaheadやsample leakageを修正した世代だが、**前月validationの5BD horizon overlap**を後から発見。
例: 6月用ポリシーを選ぶ際、5月末シグナルの5BD結果（6月に入ってから確定）を使っていた。
したがって以下の数字は構造比較・アイデア選定には使えるが、完全因果OOS/Champion判定には使用禁止。
- V18 V13 consensus: n=23 avg +3.97%, win65.2%, +10%率34.8%。Jun/Jul/Augは+5.58/+2.05/+6.66%。
- V19 V13: n=64 avg +0.85%。
- V20 run #2: n=88 avg -2.83%。
- V21 V14: n=41 avg +1.57%。
- V22: n=25 avg +0.10%。
- V24: n=35 avg +0.80%。
V18のコンセンサス構造はV29以降でpurge付き再検証する。

### V20 run #1
自動boolean列検出が outcome-derived の `win10` / `win_5bd` を特徴量として採用していたため、32件・平均+18.4%・+10%到達100%という結果は完全なtarget leakage。**全数値を無効扱い**する。
V20 run #2以降はsignal-time特徴の明示allow-list方式へ変更し、`win10 / lose10 / win_5bd / confirmed_5bd` 等を禁止。未知列は自動採用しない。

### V25 / V26 / V27 first runs
実装後に5BD horizon overlapを発見したため、初回runは完走してもChampion判定禁止。V29 purgeルールを共通化してから再利用する。

### Old Stage2
実TV BOTTOMで学習したoutcome selectorをYahoo候補へ移すとdistribution shift。Full-universeでも改善弱く、本線から降格。

## 有効な構造上の発見
- V12 Yahoo Pine state: BOTTOM再現は旧V10より大幅改善。August exact Pine Precision約62.9%, Recall約49.7%。
- Pine state start sensitivity: 2024-09〜2026-02で初期化開始を変えてもAugust Recall約49.5〜49.9%。開始位置は主因ではない。
- production保存4H上でPine状態機械を再計算するとYahoo合成4Hより高Recall。小OHLC差によるstate transition連鎖が残る。
- Pine状態は完全再現のためだけでなく、direct outcome modelの特徴量として使う価値がある。
- V18構造比較では、単純weightedより「p_win / p_hit10 / pred_ret が同一session内ですべて上位」のconsensusが最も有望だった。ただしhorizon purge付きで再検証が必要。

## 有効な記述監査
### V23 — Stable★6 regime drift audit
Actual production BOTTOM snapshots, same six Stable conditions。最適化ではなく記述統計なのでhorizon-overlap問題の影響を受けない。
- Mar-May: n=25 avg +16.08%, median +3.8%, win64.0%, +10%率32.0%。
- Jun-Aug: n=30 avg -1.32%, median +0.1%, win50.0%, +10%率6.67%。
- Mar-Aug total: n=55 avg +6.59%, win56.36%, +10%率18.18% — production headlineを再現。
- 月別 avg: Mar +19.56%, Apr +25.66%, May +7.76%, Jun -7.70%, Jul +0.19%, Aug +1.43%。
Conclusion: headline +6.6%は前半、特にMar-Aprの大勝ちに強く依存。Promotionは直近regime robustnessを重視する。

## 現在の正式評価候補
### V29 — first horizon-purged causal benchmark
- 350銘柄はMar05-Apr30 watchlist frequencyのみで固定。
- 09時は09時候補だけ、13時は13時候補だけで判断。
- モデルtrainおよびvalidationは `exit_date_5bd < test_start` をassert。
- V18型V13 consensusをpurge付きで再評価。
- dynamic policyに加え、validation outcomeで設定を選ばない固定 `cons_min>=.97/.98, both sessions` も比較。
- V29結果が今後の新しい基準。V18以前の+3.97%を基準にしない。

### V18 Full Universe run
350→歴史上の監視全銘柄へのスケール監査として実行中。ただし元V18はhorizon purge未実装のため、**結果は構造/スケール確認のみ**。V29が有望ならV29 full-universeを正式実行する。

## 次段階候補（purge移植前提）
- V25: consensus集約方法拡張 + validation half stability + policy bagging。
- V26: `p_loss10` を4番目のveto headとして使うsafe consensus。
- V27: 5BD絶対リターンではなく、同date/session内のfuture cross-sectional rankを直接教師にするrelative target。
これらは初回run結果で選ばず、V29と同じhorizon purgeを入れてから正式比較する。

## Current route priority
1. V29 horizon-purged 350-symbol benchmarkを回収。
2. V29がプラスかつ月別安定ならfull historical monitored universeへ拡張。
3. V25/V26/V27の有望構造をV29 purge基盤へ1つずつ移植。
4. architectureをfreezeした後、新規データでlive forward shadow。これが次の本当のholdout。
5. Pine reconstructionはsecondary feature/gate研究。exact TV parityはprimary objectiveではない。

## Promotion conditions
1. future label/returnを使わないuniverse selection。
2. 09時判断が13時データを使わない完全因果。
3. **label horizon purge: `exit_date_5bd < decision/test start` を満たすこと。**
4. 複数月rolling OOSで一貫。
5. tiny sampleだけの勝利は禁止。
6. Yahoo取得欠損・corporate action・tail lossを監査。
7. 最終的にはlive forward shadowで確認。
8. TradingView teacherは開発時のみ。完成runtimeはTVアクセス0、新規teacher追加0。
9. Production変更はユーザーの明示的Goがあるまで禁止。
