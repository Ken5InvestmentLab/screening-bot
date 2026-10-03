# Cloud 改修のレビューと残作業

対象は `research/weak-early-beta` の `0dc12cb5d8a6acd226a830d3e83ebc84e368986e`。
専用ブランチ `codex/cloud-analytics-d6-member-preferences` で作業し、main・検出条件・
既存Discord送信処理・原台帳を変更しない。本番への反映はまだ行わない。

## 実装した境界

- 検出から1営業日後の始値が入口。D5は検出から5営業日後の終値、D6は6営業日後の実始値。
  D5経済を凍結したまま、D6の価格・取得状態・実取得時刻・価格来歴と、分割併合後の経済を独立記録する。
- canonicalの通常upsert保護を維持。明示バックフィルはSHAと対象IDを指定し、入力を上書きしない。
  詳細は [ENDPOINT_BACKFILL.md](ENDPOINT_BACKFILL.md)。
- 全ページの無料解禁は検証済みD6実始値だけで決定する。D5を選択しても公開基準は変わらない。
- 2022は表示・集計から除外する。元データは残す。過去再構成・実運用観測と、2026が既知の過去期間であることを明記する。
- 価格上限は検出日の検証済み名目実終値。初期1,000円、プリセット1,000/2,000/3,000/5,000円、上限なし、任意入力。
  1,500円専用プリセットは最新指示で除いたが、任意入力では指定できる。
  既存モデルは銘柄ごとの直前観測行の実終値1,000円以下という条件を維持する。
- 同じ上限・D5/D6選択から指標・グラフ・集計CSVを生成。集計切替データは匿名集計だけを個別圧縮し、生台帳を埋めない。
  履歴内のコード・日付・モード検索は履歴CSVにも適用する。
- 会員設定API、資格の追加検証、解除、無送信通知判定と配信台帳を用意した。
  設定不足・未連携・失効・API障害で新着や通知を許可しない。
  詳細・公式資料は [CLOUD_MEMBERSHIP_SETUP.md](../weak-early-beta-gate/CLOUD_MEMBERSHIP_SETUP.md)。

## 未完了の資料取得とバックフィル

指定Library資料は正規取得手順を実行したが、Windows Pythonの拡張属性処理
`os.setxattr` 非対応で終了し、最終保存先に完成ファイルは残っていない。
実バイト・サイズ・SHAを検証済みとは扱わない。署名URLの直接取得やhelper改造は行っていない。

また、`libfile_f1b1c738b584819197970aea26056d87` は指定ZIPそのものではなく
`旧Cloud_2022と条件数比例比較_保存一式_v01.json`（6,581,850 bytes）を返した。
保存用JSONの中身とZIP対応は未確認。

そのため、評判の良かった研究HTMLを実ブラウザで確認して忠実に移植する作業と、
検算済み資料から過去実価格をバックフィルする作業は未完了。
現プレビューは既存Cloudのデザインを保った機能改修版であり、研究HTML移植の完成版ではない。

原台帳の検出日実終値証跡がまだ無いため、初期の1,000円上限では対象0件となる。
これは未検証値を実価格として使用しない挙動である。「上限なし」では保存済みの参考成績を確認できる。
過去D6を検証するまでは無料版の該当銘柄も解禁しない。
バックフィルと無料/有料境界の再検査が完了するまで、この生成物を本番へ反映しない。

## 検証結果

- Python統合テスト153件成功。価格境界、休日・年跨ぎ、分割・併合、D5凍結後のD6追記、
  欠損・将来日時の拒否、冪等バックフィル、無料境界、通知候補生成を含む。
- gateの`npm run check`は135件成功、型検査とWranglerの無公開ビルドも成功。
- 仮想データの実ブラウザ操作115項目成功。任意価格、設定保存失敗、通知OFF、
  絞込後の全指標・グラフ・CSV一致、無料HTMLと圧縮データ内の識別子非公開を確認。
- 実台帳のプレビューをPC/スマホとライト/ダークの4構成で描画・操作。
  JS例外・横あふれなし。履歴ページ送り、分析ダイアログ、無料の未解禁識別子非公開を確認。
- 元台帳972行のSHA256は生成前後で
  `7574c18d72948e8faa3b1e0e8d718690242750f5459e68a3f98d7e18b9a55909`のまま。
  既存stateファイルとDiscord通知処理は未変更。送信件数0、デプロイなし。

テスト用会員とローカルAPI応答で検証しており、実Whopアカウントとの結合や実プッシュ配信は未検証。
研究HTMLとの見た目の一致も、上記の取得阻害により未検証。

## ローカル再現

既存workflowの固定Python依存を使用する。今回のローカル検証はPython 3.14.7、
NumPy 2.5.3、pandas 2.3.3、scikit-learn 1.9.1、XGBoost 3.4.1、Node 22.13.1。
workflow自体のPython指定は3.12であり、モデル再学習は実行していない。

```powershell
python -B -m unittest tests.test_weak_early_beta tests.test_weak_early_beta_corporate_actions tests.test_weak_early_beta_trade_basis tests.test_weak_early_beta_model tests.test_weak_early_beta_endpoint_receipts tests.test_weak_early_beta_report_preferences tests.test_cloud_notification_adapter
python -B weak_early_beta/scripts/build_review_preview.py --output ../review-cloud
python -m http.server 8765 --bind 127.0.0.1 --directory ../review-cloud
```

別のシェルで `weak-early-beta-gate` に移動し `npm ci`、`npm run check`。
checkは同期・認証テスト・型検査・dry-run buildであり、公開しない。
`build_review_preview.py` は原台帳を読み取り、metrics/HTML/補助アセットを指定した別フォルダへ出す。
原台帳のSHA不変を確認し、`review_receipt.json` を保存する。

本番D1、Whop/認証情報、Webhook、VAPID、プッシュ購読登録、候補取込、実送信は未設定・無効。
既存認証キーの新規発行、権限拡張、契約、merge、deployタグの発行はしていない。
