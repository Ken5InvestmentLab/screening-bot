# 5BD評価窓の日足欠損 — 検証結果と対策案

更新日: 2026-09-13  
範囲: TV-Free research only。production、Discord、Sheets、workflow、intraday生成は変更していない。

## 結論

公式取引日の5BD評価窓に銘柄バーが1日でも無いと、現行の保守的評価ではそのシグナルのリターンを確定しない。翌日へずらしたり、前値を埋めたりしない。特にエントリー日の始値または5営業日目の終値が欠ければ、5BDリターンを正確に計算できない。中間日の欠損は単純な端点比だけなら出せる場合があるが、その間の売買可能性・価格経路・コーポレートアクションを検証できないため、現行評価定義では未解決のままにする。

## 現行コードと保存データの証拠

- batch01/evaluation.py の build_five_session_labels は、全選出に1行を残し、シグナル翌営業日から5営業日目までの全バーを検査する。欠損は MISSING_ENTRY_BAR / MISSING_HOLDING_SESSION_BAR / MISSING_EXIT_BAR として未解決にする。出来高ゼロ・不正OHLCVもリターン計算対象外にし、要求件数から削除しない。
- 既存テスト test_evaluation.py / test_core_moderate_ridge.py は、entry・holding・exit欠損を別状態にするケースを含む。
- 保存済みYahoo由来データはXTKSの市場営業日1,148日をすべて含むが、日ごとの銘柄行数は646〜3,696（中央値3,555）。市場カレンダーが完全でも、個別銘柄の日足が完全とは言えない。point-in-time上場期間・売買停止・無約定を識別する情報はこのCSVにない。
- research downloaderのrun.pyは取得例外・空バッチを再試行する一方、応答全体が非空でも個別tickerの欠損日を期待カレンダーと照合して単独再取得する処理を持たない。欠損が通信失敗と確定したわけではない。
- 今回の凍結CMF選出では1,800件中32件（1.8%）が未解決で、2022H2は8/595、2023は24/1,205。内訳はゼロ出来高の保有日16、entryのゼロ/不明出来高3、canonical label行なし13。後者は取引データ自体の欠損を証明しない。CMF成績は解決ラベルの成績としてのみ報告した。

## 最有力なデータ補完ルート

JPXのJ-Quants日足を、欠損した銘柄×日付の照合元として検討する。JPXの公式説明では、個人向けJ-Quants APIは過去時点の上場会社一覧と調整前/調整後の株価を提供する。J-Quants Proの日次株価仕様は銘柄コードまたは日付・期間で取得でき、OHLC、売買高、調整係数、調整価格を返す。売買の無かった日のOHLC/出来高はNullとして扱われるため、Yahoo行が欠けても公式側に値があれば取得漏れ候補、公式側もNullなら無約定等の未解決候補として区別できる。

ただしJ-Quants APIは個人向けで、JPXは法人利用と再配信を不可としている。J-Quants Proは法人利用可能だが料金は問い合わせ、DataCubeはデータ商品ごとの購入で法人利用可能。Botの用途・出力・運営主体に合う契約を確認するまでは、productionで使えると見なさない。日次OHLCでも調整対象外のコーポレートアクションがあるため、現在のYahoo系列との価格基準・銘柄コード変更・権利処理を一致させる監査が必要。

## 実装前の検証手順

1. 公式XTKSカレンダーと過去時点の上場銘柄一覧から、対象日付に期待される銘柄×営業日を作る。上場前・上場廃止後の日は欠損として数えない。
2. Yahooに内側の欠損がある場合、まず同じYahooソースをticker単位・短い重複期間で限定再取得する。取得日時・リクエスト範囲・ソース・原本ハッシュを保存する。
3. まだ欠ける行は、利用契約が許可したJPX公式APIまたは同等ライセンスソースで照合する。完全なOHLCV、日付、銘柄コード、調整係数を検査し、日足基準を一致できた行だけを provenance付き修復sidecarへ置く。
4. 公式ソースが無約定を示す、上場/停止状態を確定できない、価格調整をそろえられない、API取得が失敗する場合は未解決を維持する。前値補間・次観測日への置換・推測売買価格は禁止する。
5. 元データのみの結果、検証済み修復後の結果、未解決率/理由とシグナル時期・銘柄別偏りを並べる。採用判断はカバレッジが偏っていないことを確認してから行う。

この処理は通常のPythonジョブと保管済み認証情報でCodexなしに実行できる形に限定する。実装前にAPI利用契約、認証、rate limit、再試行、保管場所、定期実行の独立テストが必要。APIキー・実データ・productionへの接続はまだ行っていない。日足で1h/4hを合成する案はこの調査の対象外であり、実装しない。

## 公式資料

- JPX, [J-Quants API](https://www.jpx.co.jp/english/markets/other-data-services/j-quants-api/)
- JPX, [Historical Data and delivery/licensing channels](https://www.jpx.co.jp/english/markets/paid-info-equities/historical/)
- J-Quants Pro, [Daily stock prices API specification](https://jpx.gitbook.io/j-quants-pro/api-reference/daily_quotes)
