# Cloud 成績比較ダッシュボード

`index.html` をブラウザで開くと、株価上限6群と売却20時点の監査済み比較を操作できます。データ・CSS・JavaScriptを1ファイルに内包し、ネットワーク接続や外部ライブラリなしで動作します。

- 期間、5モード、銘柄均等／モード別積上げ、表示指標を切り替え。
- ヒートマップとグラフの点を押して条件を選択。
- 平均・勝率・中央値・大敗率・上位利益除外・100株損益を表示。
- 2023〜2024年だけで選んだ上限・出口を2025／2026年に固定した成績を表示。
- 5日終値の価格上限比較と最大必要資金を別集合の表に表示。
- 選択中の20出口の集計値をCSVで保存。全取引CSVは内包しません。
- 本番Cloudの保存履歴との不一致を冒頭に表示。公開ページと保存ledgerを読み取り専用で照合した固定snapshotです。

## 再生成

リポジトリ直下で実行します。

```powershell
py -3 research/cloud_comparison_dashboard_20261001/generate.py
node --check research/cloud_comparison_dashboard_20261001/dashboard.js
```

`generate.py` は完成済みCSVと独立監査receiptだけを読み、完全な格子・単位変換・20時点の同一集合・DEV限定選択を検証します。モデル学習、銘柄検出、日次runner、通知、公開ledger更新を実行しません。`manifest.json` に入力、生成ソース、完成HTMLのSHA-256を保存します。

集計入力のhashはCRLFをLFへ正規化して計算し、GitのWindows改行変換でも一致させます。生成ソース・HTMLはLFに固定した実ファイルのhashです。本番stateの監査前後hashと元の価格・企業行動hashは、元ファイルのバイト列をそのまま使います。

編集対象は `template.html` / `style.css` / `dashboard.js` / `generate.py`。`index.html` と `manifest.json` は再生成します。株価上限CSVの騰落・勝率は小数比率、出口CSVは百分率のため、生成時に前者だけ100倍して統一しています。

5日売却比較と20出口共通集合は異なります。ダッシュボード上でも別セクションにし、混ぜません。価格上限・出口の現行設定は変更していません。これはローカルの研究用ダッシュボードで、公開Cloud Workerのページではありません。

## 本番との照合

全期間・銘柄均等・1,000円以下・5日終値では、本番248件／平均+5.49%／勝率49.19%、研究252件／+0.08%／40.08%です。共通116件の騰落率は一致しましたが、本番だけ132件、研究だけ136件あり、同じ検出集合ではありません。上限撤廃による研究内の差を、そのまま本番改善幅として解釈できません。

`production_public_snapshot.json` は2026-10-01 18:15:40 JST更新の公開HTMLから取得した表、`production_reference.json` は同じ保存ledgerの35集計を再計算して確認した固定参照値です。通常のHTML再生成はこのsnapshotを使い、本番stateへアクセスしません。明示的に再照合するときだけ、公開snapshotを取り直したうえで次を実行します。

```powershell
py -3 research/cloud_comparison_dashboard_20261001/audit_production.py --capture
```

このコマンドも本番CSVを読み取るだけで、ファイルhashが変わっていないことを検証します。今回のsnapshot用に日付・期待件数を固定しているため、新しい基準日の再照合では契約を見直してください。
