# 検出日実終値と検出から6営業日後始値の移行

通常の `daily` は今後の `FORWARD_CAUSAL` 検出に独立した実価格証跡を記録する。
検出日の翌営業日が入口、検出から5営業日後の終値が D5、6営業日後の始値が D6。
日本の銀行営業日カレンダーを使用し、価格がない日を飛ばして出口をずらさない。

`signal_close` と canonical の D5 経済は既存の参考価格・金額のまま保持する。
表示上限の実終値判定には `signal_actual_close_verified(row)` を通った
`signal_actual_close` だけを使う。D6 の無料公開解禁は
`sixth_endpoint_verified(row)` を使用し、単なる予定日到来や D5 損益確定では解禁しない。
未取得価格は空欄。`pending` / `missing` / `quarantined` は確定を意味しない。

実価格証跡には取得時刻、元データ SHA-256、調整価格、分割係数、検算後実価格、
価格・企業行動の版、基準日を保存する。D6 損益は別の入口価格・原株数・原価と
`entry_date < effective_date <= D6` の分割・併合を使用する。
`sixth_economics_verified(row)` を通らない損益は集計しない。
端株処分の未実装や入口価格不足でも、取得・検証できた D6 実始値は保持できる。
D5 で凍結した分割・併合履歴と、新しいデータの D5 までの履歴が一致しない場合も
D6 損益を保留する。未来の取得時刻や、予定営業日と異なる日付では確定扱いにしない。

今後 D5 実経済を新たに確定した時点では `d5_price_observed_at` に実際の取込時刻を記録する。
既存 D5 凍結行の取得時刻は推測して補完しないため空欄のまま。新しい日付を使って
古い結果通知を送信対象へ変えることはできない。

## 明示バックフィル

この改修中、実台帳に対するバックフィルはまだ実行していない。
Library の正規取得・サイズ・SHA 確認後、対象の価格・企業行動・同一銘柄性を検算し、
その検算済みの日次 CSV を入力する。研究 HTML に埋め込まれた集計値や
canonical の `signal_close` を実終値の代わりに使用してはいけない。

`backfill-endpoints` は入力を変更せず、明示した新しい台帳と監査 JSON を作る。
入力元・出力先の一致、既存出力の上書き、本番 `weak_early_beta/state/` 内への出力を拒否する。
通知、レポート生成、デプロイは呼ばない。canonical の通常 upsert 保護も変更しない。

対象 ID の例（`review/identities.json`、実際の検算対象へ置換する）:

```json
["2026-09-01|9999|volr20_low"]
```

PowerShell での再現例。パス・SHA・取得時刻は実際に確認した値へ置換する。

```powershell
python -B -m weak_early_beta.cli backfill-endpoints `
  --ledger review/detections_input.csv `
  --daily-corpus review/verified_daily.csv `
  --source-sha256 <検算済みCSVの64桁SHA256> `
  --identities review/identities.json `
  --observed-at <実際の取込時刻とタイムゾーン> `
  --output review/detections_with_endpoints.csv `
  --audit review/endpoint_backfill_audit.json
```

監査 JSON の `changed_count` と `changes` を確認し、既存 D5 の全列・検出モデル・
通知証跡が不変であることを比較する。同じデータで二度目を別の出力先へ生成すると、
取得済み証跡は保存され `changed_count` が 0 になる。
出力を本番へ採用する操作は、このサブコマンドの対象外。

検証コマンド:

```powershell
python -B -m unittest tests.test_weak_early_beta_endpoint_receipts tests.test_weak_early_beta_model tests.test_weak_early_beta_trade_basis
```
