# Cloud価格上限比較

`compare.py` は分割・併合情報付きの固定された日足ファイルだけを読む独立研究runnerです。GAS、Google Sheets、Discord、公開HTML、通常Cloudのledger/stateを更新せず、ネットワーク取得もしません。出力は既定でGit対象外の `.cache/cloud_cap_corrected_v2_20261001/` です。

価格上限は1,000円、1,500円、2,000円、3,000円、5,000円、上限なしの6群です。各群で訓練・予測eligibilityと同日上位0.25%教師ラベルを作り直し、固定45特徴量・V7モデル・月次因果時点・Tail≥0.999・5選定条件を維持します。上限以外を結果に合わせて調整しません。

必須入力は、Cloud専用の正規化検証を通り `actual_*`、`split_factor`、`basis_asof`、`source_usable` がある固定日足CSVと、同じsnapshot基準の `actions.csv` です。不正価格と未確認の価格基準は供給元の品質フラグで隔離し、日付の行を残してOHLCVをNaNにします。株価・出来高の絶対条件は当時単位の `actual_*` を使います。

通常の実行例：

```powershell
.cache/weak_early_beta/venv/Scripts/python.exe -B -u research/cloud_cap_comparison_20261001/compare.py run --daily .cache/weak_early_beta/split_preflight_20261001/normalized_daily.csv --actions .cache/weak_early_beta/split_preflight_20261001/actions.csv
```

既定は2023年1月〜2026年9月の45か月、価格評価cutoffは2026年9月30日です。snapshotに10月1日の途中価格が含まれても、評価には使いません。2workerが読み取り専用memmapの特徴量を共有し、各workerは元モデルどおり4threadsです。各cap/月のCSVとSHA receiptは原子的に保存され、同じ入力・期間・部品hashなら途中から再開できます。OSファイルロックで同じ出力/同じcapの二重起動を拒否します。入力や期間、runnerや依存部品が変わった場合は別出力ディレクトリが必要です。

V2では市場全体の陽線比率と移動平均上方比率について、品質隔離によるNaNを分母から除きます。中央値の計算は従来どおりです。旧V1の104 fitは `.cache/cloud_cap_corrected_20261001/` に参考途中結果として保存し、V2へ混ぜません。

利用残量が週間20%以下、または5時間3%以下になった場合は、出力内へ `STOP_REQUESTED.json` を保存します。workerは進行中のfitを保存してから次のfit前に停止します。回復後の明示再開では同じ実行コマンドに `--clear-stop` を付けます。停止中も完了済み月のreceiptが残り、再学習を避けて続行できます。`run_status.json` と標準出力ログで進行を確認できます。

途中成果の集計：

```powershell
.cache/weak_early_beta/venv/Scripts/python.exe -B research/cloud_cap_comparison_20261001/compare.py aggregate
```

主な出力は `prepared.json`（入力・部品hash、モデルparams、単位不変性、方法）、`progress_cap*.json`、`selected_cap*.csv`、`trades_cap*.csv`、`metrics.csv`、`summary.json` です。首位同順位は任意の銘柄を選ばず、その日の候補証跡を保存して全6群/全モードの共通除外日にします。全群終了後のunionを最終成績に使います。

`prepared.json` の `model_parameters` は教師 `[0,1]` を渡した共通テンプレートです。実学習の `scale_pos_weight` はcap/月の教師クラス比率で動的に決まります。`audit_weights.py` が各群の教師ラベルと因果時点を再計算して `actual_monthly_model_weights.csv` と補足metadataへ教師クラス数・実重みを保存し、完了済み月の学習行数と照合します。凍結した研究runnerはこの補足のために変更しません。

売買はシグナル翌銀行営業日始値から5銀行営業日目終値まで。予定日の価格が欠けた場合、後の価格へ売買日を移動しません。実100株の損益は `build_trade_economics` で保有中のイベントを順に適用し、途中で端株が出る場合は現金精算を推測せず理由付きで計測対象外にします。必要元金は同日始値の購入が終値の売却より先に起きる同時保有計算です。

現行の約定困難エントリー規則と、読取済みJPX整理銘柄の指定日による因果除外を成績へ適用します。勝率の分母は0%を含む全確定取引です。銘柄均等（同日・同銘柄1回）とモード別積上げの双方、各年、各条件、平均・中央値・最悪・−10%以下・最大3勝ち取引除外平均・実100株損益・必要元金を出します。

現在JPXの生存銘柄に基づく研究であり、約定や将来の収益性を保証しません。コストは0%。供給元企業行動の完全性は独立には認証されていません。既存の公開/確定ledgerはこの研究のために変更しません。旧価格基準だけの初回比較は [LEGACY_REFERENCE.md](LEGACY_REFERENCE.md) に明示して区別しています。
