# 天底極致 No-TV 代替 — 研究方針更新 2026-09-10

この文書は `TENCHI_RESEARCH_LEDGER.md` の旧「Stable★6 +6.6%超え必須」目標を上書きする最新方針。

## 最新の目的
TradingViewなしで、天底極致のBOTTOM検出と現行スコアリングが担っている役割を代替できる、自立した東証普通株スクリーニングシステムを作る。

Production Stable★6の5BD平均+6.6%は比較対象として残すが、**超えることを絶対条件にはしない**。V23で同成績がMar-Aprの大勝ちに強く依存し、Jun-Augは弱かったことが確認されたため、単一の全期間平均を最適化目標にしない。

## 優先順位
1. 完成runtimeでTradingViewアクセス0、新規TV教師追加0。
2. future label/returnによるuniverse leakageなし。
3. 09時判断は13時データを見ない。
4. 5BDラベルは `exit_date_5bd < decision_time/date` を満たす確定済み結果だけを学習に使う。
5. 複数期間で大崩れしないこと。平均だけでなく中央値・勝率・tail loss・月別安定性を見る。
6. 無理に毎回シグナルを出さない。相場環境が悪ければ見送りを正式な出力とする。
7. モデルを複雑化してバックテスト平均だけを上げるより、固定・再現可能・無料運用可能な構造を優先する。
8. Yahoo/JPX等の無料データ取得失敗率も性能の一部として扱う。
9. Production main / Discord / Sheetsはユーザーの明示的Goまで変更しない。

## 現時点の設計仮説
- Universe: JPX公式上場銘柄一覧からPrime/Standard/Growthの内国普通株を取得し、ETF/ETN/REIT/優先系を除外。
- Data: 完成済み日足はYahoo公式1D、当日途中はYahoo 1H。
- Stock selector: 3-head（5BDプラス / +10% / 期待リターン）のsession内relative consensusを少数精鋭で使用。
- Opportunity gate: 市場breadth・return dispersion・ATR・出来高等から「このsessionでそもそも勝負する価値があるか」を判定し、悪い局面はNO TRADE。
- Pine/天底極致状態: exact copyを目的にせず、必要なら特徴量・secondary gateとして使用。
- Learning: 初期研究ではTV履歴を評価・校正に使ってよいが、完成runtimeはYahoo/JPXと自己蓄積した確定結果だけで更新可能にする。

## 次の正式判定
V33以降では「Stable★6超え」ではなく、完全因果・purged・prequentialな評価で、固定selector単体よりopportunity gateが月別安定性とtail riskを改善するかを主判定にする。
