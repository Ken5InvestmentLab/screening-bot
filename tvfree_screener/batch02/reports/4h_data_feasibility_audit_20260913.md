# 4時間足データ取得可能性と日足補完案の再監査

評価日: 2026-09-13
実験ID: DATA-QUALITY-4H-FEASIBILITY-20260913-01
判定: **4H_INFEASIBLE**（無料・契約なし・東証全銘柄・2022年以降の複数年研究について、今回確認した公式ソースの範囲）

この判定は「4時間足がどこにも存在しない」という意味ではない。現行GASにはYahoo Financeの1時間足をAM/PMへ集約する経路があり、直近の4時間足相当データは通常のGASで作られている。一方、研究worktreeにあるのは日足CSVで、raw 1時間足またはlegacy 4時間足CSVはない。既存手順の保存期間は365日で、現行経路から東証全銘柄×複数年の研究データが揃うとは確認できない。既存データは読み取り専用とし、上書きや本番変更は行っていない。

## 無料データ源の確認

| データ源 | 確認できたこと | 判定 |
|---|---|---|
| JPX J-Quants Free | 公式の個人向けプラン表では無料枠の株価は日足で12週間遅延。2026年1月追加の分足・ティックはLight以上の有料オプション | 無料intraday要件を満たさない |
| Twelve Data Basic | 公式API仕様には4h intervalがある。無料Basicは8 credits/分・800/日で、海外市場はglobal trial symbolsの範囲。全東証銘柄、上場廃止銘柄、複数年の無料4h履歴は確認できない | 全市場研究ソースとして未証明 |
| Alpha Vantage | intraday APIは長い履歴を案内する一方、TIME_SERIES_INTRADAYはPremium endpointと明記 | 無料の長期intraday要件を満たさない |
| Yahoo Finance | 現行GASはYahoo 1hからAM/PM値を作り、365日保持している。ただし公式利用規約は明示的な事前許可なしの自動データ収集を禁じる。研究worktreeにraw intraday履歴はない | 現行経路の存在は確認したが、許諾・全銘柄・複数年履歴の適格性は未確認 |

公式資料:

- [JPX J-Quants APIの2025年プラン表](https://www.jpx.co.jp/corporate/news/news-releases/6020/20250822-01.html)
- [JPXの2026年1月 分足・ティック追加案内](https://www.jpx.co.jp/english/corporate/news/news-releases/6020/20260119.html)
- [Twelve DataのAPI仕様](https://twelvedata.com/docs) / [料金と無料Basicの制限](https://twelvedata.com/pricing) / [無料Trialの説明](https://support.twelvedata.com/en/articles/5335783-trial)
- [Alpha Vantage intraday仕様](https://www.alphavantage.co/documentation/)
- [Yahoo Finance利用規約](https://legal.yahoo.com/ca/en/yahoo/terms/otos/index.html)

価格API呼び出し、アカウント作成、課金プランの試用はしていない。判定は公式公開仕様の監査で、無料APIキーを使った銘柄別実測ではない。

## 日足で1時間足の誤差を調べ、補える範囲

ご提案どおり、同一銘柄・同一営業日の日足を使って、1時間足から再集約した終日OHLCVとの一致度を調べる。始値・高値・安値・終値・出来高ごとの差、日中の時間帯、欠損・重複・不正値を記録し、年・銘柄・時間帯ごとの偏りを見る。ただし、Yahoo日足とYahoo 1時間足の一致は同一提供元内の整合性であり、それだけで日足が真値だとは証明できない。調整後/未調整価格、分割、時刻の足区間定義が同じかを先に確認する。

日足が使える補助と使えない補助を分ける。

- 終日集約値の検証には使える。売買日が終わった後のシグナルには、その日の確定日足終値や日足コンテキストを別特徴として使える可能性がある。
- 日足終値は引け後のPM終値として検証・補助できる。前場始値は日足始値と照合できる。
- 日足の高値・安値・終日出来高だけから、その極値や出来高が前場/後場のどちらで発生したかは復元できない。欠けた前場/後場OHLCを作る用途には使えない。
- 取引時間中に同日の最終日足高値・安値・終値・出来高を使うと、まだ発生していない将来情報が混ざる。信号時刻時点の特徴量へ入れない。
- 日足出来高から既知の前場出来高を差し引く後場残差は、ソース基準一致・前場完全性・非負を確認した別フィールドとしてのみ検討できる。観測された後場1時間出来高と混同しない。

## 時間足の区切りを再検討

TradingViewの区切りを最終目的にしない。JPXの公式現行時間は前場09:00–11:30、後場12:30–15:30。2024-11-05より前の後場は15:00終了で、その日以降は15:25–15:30のクロージング・オークションもある。従ってセッション区切りは実際の市場に沿う有力候補だが、同じ長さの4時間足ではない。

同じ候補集合と5BD評価定義で次を比べる仕様を登録した。

1. raw intradayから作る東証セッションバー（制度変更日を反映）
2. raw intradayから作るTradingView互換の09:00–12:59／13:00–公式終値区切り
3. 日足のみの独立特徴量
4. 日足で終日集約を照合し、信号時刻までに利用可能な日足情報だけを加える方法

11:30/12:30境界をまたぐ1時間足を分割してはいけない。raw timestampと足区間が境界に揃うと確認できない場合、より細かいデータが必要になる。新しいスコア候補にlegacyの特殊生成済みohlcv_4hは使わない。raw intradayから独自仕様で再生成し、入力ハッシュ・変換コード・市場カレンダー・調整基準を固定して、既存データとは別の研究用出力へ保存する。

## 5BD評価と検証

日足エンドポイントは承認済み定義「シグナル翌営業日の始値で入り、エントリー日を1日目として5営業日目の日足終値で評価」を使用する。端点リターンはstrict path/actionability成績と別に集計する。特徴量利用可能時刻は各シグナル時刻へ揃え、日足の確定前は同日の最終値を利用しない。

2025/2026は特徴や境界の選択に使わず、凍結後の報告だけにする。日足＋直近intradayのhybrid案も残すが、カバレッジ・欠損偏り・価格調整・Codexなし再現性が確認できるまで採用しない。日足だけにも4時間足だけにも今は固定しない。

## 実際の検証に必要なデータ

研究worktreeには日足CSV（4,061,361行）はあるが、raw 1時間足とlegacy 4時間足のCSVがない。そのため、Yahoo 1時間足と日足の実際の一致度、欠損4時間足の実件数、同日OHLCVの照合結果はまだ出せない。Codex/APIなしの標準Pythonで動く照合スクリプトとギャップ監査ツールを用意し、合成データの13テストで検証した。

全件照合には、既存値の読み取り専用exportが必要。1時間足の品質確認と新しいセッションバー構築には、raw 1時間足（境界が正確でなければ30分足以下）、足の長さ、timestampが足の開始/終了どちらを示すか、価格調整基準が必要。11:00–12:00や12:00–13:00のように昼休みをまたぐ足は日足比較へ丸ごと含めて境界またぎとして記録し、前場・後場の足へ分割しない。いずれも元シートや元ファイルは編集しない。

詳しい定義は4H_DATA_FEASIBILITY_AUDIT_SPEC.json、HOURLY_DAILY_CONSISTENCY_AUDIT_SPEC.json、INTRADAY_BAR_DEFINITION_STUDY_SPEC.jsonに保存した。


## 2026-09-13 read-only coverage addendum

The connected `ohlcv_4h` tab was reconciled against same-day daily OHLCV for 2025-12-23 through 2026-09-11. There were 645,187 daily symbol/session pairs; 439,557 did not have a complete valid 09:00 and 13:00 pair, and 439,207 of those had numerically valid daily OHLCV. This is availability/basic-validity evidence only; absent bars cannot be distinguished as intentionally untracked versus failed retrieval. It does not establish hourly price accuracy or permit daily-to-4H synthesis. See `reports/intraday_daily_coverage_audit_20260913.md`.

## 2026-09-13 read-only GAS source and provenance review

The ordinary GAS path in weekly_report_gas/gas.txt confirms that the stored legacy 09:00/13:00 rows are not a clean, source-tagged raw-hourly dataset:

- parseIntraResponse_ treats Yahoo timestamps as interval starts and bins 09:00/10:00/11:00/12:00 into AM, and 13:00/14:00/15:00/15:30 or 16:00 into PM. A 12:00 one-hour interval crosses the actual 11:30–12:30 TSE lunch break and cannot be split into valid session bars from this input.
- A flat zero-volume 15:30/16:00 close snapshot can update the PM close without contributing volume. The legacy buckets therefore have special close-snapshot semantics.
- The 1d gap fallback copies the same daily O/H/L/C into both AM and PM placeholder rows and divides daily volume 50/50. That supplies rows but does not reconstruct either session's true OHLCV.
- The alert_id marker is not a reliable source label. The sheet has 8,610 GAP_REPAIR rows, but the GAS code also assigns GAP_REPAIR to rows refetched from Yahoo 1h and to the 1d-derived duplicated placeholders. Thus the two sources cannot be separated from this marker. Other values such as new_session and MIDDAY_<date> identify fetch/update batches, not the underlying feed.

Consequently the existing connected sheet cannot support a defensible hourly-versus-daily accuracy comparison: its source provenance is mixed, raw hourly timestamps are absent, and the research repository has no raw 1h export. Do not infer the source from duplicate-looking OHLC values; legitimate illiquid sessions can also be flat. Record value-level accuracy as INCONCLUSIVE_SOURCE_PROVENANCE_MIXED. Do not score from this legacy sheet or mutate it. The agreed daily endpoint remains valid for outcome measurement, while any feature series must preserve its own timeframe and source.

Source receipt for DATA-QUALITY-4H-PROVENANCE-20260913-01: read-only weekly_report_gas HEAD f2fb9df22565e29890a91c16c5063acb2f5d4cb1; gas.txt SHA-256 0ab6326c0eeca1090fc9cbbc116794481982db0e5fdf45afccd6a138a1ee9b46; connected legacy 4H projection SHA-256 32c5e53f77487d17545abdbe80205289a53af532f37ae8f517c29c5f8b86402a; daily panel SHA-256 6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0.

Source receipt for DATA-QUALITY-4H-PROVENANCE-20260913-01: read-only weekly_report_gas HEAD f2fb9df22565e29890a91c16c5063acb2f5d4cb1; gas.txt SHA-256 0ab6326c0eeca1090fc9cbbc116794481982db0e5fdf45afccd6a138a1ee9b46; connected legacy 4H projection SHA-256 32c5e53f77487d17545abdbe80205289a53af532f37ae8f517c29c5f8b86402a; daily panel SHA-256 6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0.
