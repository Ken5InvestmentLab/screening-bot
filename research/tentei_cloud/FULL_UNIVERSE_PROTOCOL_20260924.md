# Cloud JPX全対象化の固定比較契約（研究専用）

## 対象と凍結事項

- 通常の1H取得はJPX公式「東証上場銘柄一覧」ページから当月掲載のExcelリンクを動的発見する。Prime・Standard・Growthの「内国株式」だけを取り、優先株式・種類株式を除く。取得前の株価・出来高フィルタはない。
- 比較用OLDは `symbols_4h_universe.txt` の1,332銘柄。NEWは実行時のJPXスナップショット。旧リストは通常取得経路で使わない。
- Core、Monster Watch、Monster Primeのゲート、特徴量、5BD cooldown、Random Forest構造、7 seed、Watch q65、Prime q90、5BD +7.5%ラベルは変更しない。
- MonsterはOLD由来の学習データだけで各既存walk-forward foldを学習し、その**同一モデル・同一閾値**をOLDとNEW候補に適用する。追加銘柄の事後成績で再学習・閾値調整しない。
- Coreは固定再構築ゲートとcanonical「シグナル翌営業日始値→シグナル日+5営業日終値」。Monsterは既存の「候補session終値→シグナル日+5営業日終値」。各レーン内でOLD/NEWのentry/exitを一致させる。10/20/40BDは同じentryからの補助結果。
- 比較対象のシグナル日は既存 `walkforward_4h_ensemble.py` の2025-07-01～2026-08-31固定fold。1H入力は2024-10-01～2026-09-10とし、2024年10月を特徴量ウォームアップに使う。これより前のYahoo 1Hは再取得時にHTTP 422を確認した。OLD保存済み1Hは2024-09-17から存在するが、NEWにない先行期間をOLDだけに使わない。
- 2023年からの別研究の検証は保存済み**日足**によるものであり、この実1H比較へ流用しない。日足から1H/4Hを生成しない。

## 取得・coverage・比較の証跡

1. `tentei-cloud-1h-research.yml` がJPX元ファイルSHA、一覧CSV、銘柄TXT、12 shardの実1H CSVと失敗JSON、coverage report、missing一覧をartifactに保存する。
2. 比較ワークフローはOLDの保存済みrun `34592896202` と、明示指定されたNEW runだけを使用する。各shardで同じ固定ゲートを再実行し、同じ取引日集合であることをSHAで確認する。
3. OLD、NEW retained、NEW added、NEW totalをレーン別・月別・市場別・価格帯別・流動性帯別に出す。5BDのn、平均、中央値、勝率、+10/+20%、-10%、最大上昇・下落と10/20/40BD補助結果、5BD >=20%の追加Monster捕捉を保存する。
4. 本比較は現行JPX月末リストを過去へ当てるretrospective比較。過去上場廃止銘柄がNEWから除かれ、OLDにのみ残る銘柄もある。survivorship-bias-freeや完全point-in-time検証とは呼ばない。

## 1H不調日の運用境界

- 日次の対象1Hが1銘柄でも欠ける、または該当日の取得失敗がある場合、その日**全体の新規検出を停止**する。`daily_data_policy.py` の `new_detection_allowed=false` とmissing/failed一覧に記録する。日足で候補足を埋めない。
- 既存シグナルの5BD確定は別経路。既知の `exit_date` に一致するYahoo Chart API `interval=1d` の**実終値**のみで確定し、取得元を残す。指定日が欠けたら補間・前後日価格の代入をせず `unresolved` にする。
- これは研究側の運用契約であり、本番の日次ランナー、Discord、Spreadsheetには接続していない。
