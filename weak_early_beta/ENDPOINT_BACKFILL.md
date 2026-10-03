# 検出日実終値と検出から6営業日後始値の移行

通常の `daily` は今後の `FORWARD_CAUSAL` 検出に独立した実価格証跡を記録する。
検出日の翌営業日が入口、検出から5営業日後の終値が D5、6営業日後の始値が D6。
日本の銀行営業日カレンダーを使用し、価格がない日を飛ばして出口をずらさない。

`signal_close` と canonical の D5 経済は既存の参考価格・金額のまま保持する。
表示上限の実終値判定には `signal_actual_close_verified(row)` を通った
`signal_actual_close` だけを使う。D6 の無料公開解禁は
`sixth_endpoint_verified(row)` を使用し、単なる予定日到来や D5 損益確定では解禁しない。
未取得価格は空欄。`pending` / `missing` / `quarantined` は確定を意味しない。

今後の日次実価格証跡には取得時刻、元データ SHA-256、調整価格、分割係数、検算後実価格、
価格・企業行動の版、基準日を保存する。承認済み研究資料の名目実価格は後述の別証跡で扱い、
研究資料にない調整価格や係数を捏造しない。D6 損益は別の入口価格・原株数・原価と
`entry_date < effective_date <= D6` の分割・併合を使用する。
`sixth_economics_verified(row)` を通らない損益は集計しない。
端株処分の未実装や入口価格不足でも、取得・検証できた D6 実始値は保持できる。
D5 で凍結した分割・併合履歴と、新しいデータの D5 までの履歴が一致しない場合も
D6 損益を保留する。未来の取得時刻や、予定営業日と異なる日付では確定扱いにしない。

### D6価格と損益のソース整合

D6価格証跡は、そのソースが記録した入口翌日以降〜D6までの分割・併合履歴にも結び付ける。
保留中のD6損益を確定するときは、**同じ新しい日次ソース**の入口価格・D6実始値・
企業行動を一式で検証し、`sixth_economics_provenance_json` に保存する。
保存済みの古いD6始値へ、新しいソースの株数だけを掛けることはできない。

保存したD6実始値・当該期間の企業行動と新しい証拠が矛盾したら、完了済みD6であっても
価格を `quarantined`、損益を `review_required` とし、公開用の価格・損益は空欄にする。
無料公開判定もfalseになる。元の価格・損益と矛盾した新ソースの証跡は
`sixth_xtks_exit_provenance_json` 内の `quarantine` に残す。D5の凍結経済は変更しない。

この隔離は通常refresh・upsert・CSV再読込・汎用 `backfill-endpoints` では解除しない。
解消には、原ソース・企業行動・株式単位を確認したうえで別途明示的な訂正手順が必要であり、
この段階では隔離を強制解除するオプションを用意していない。
当該期間の企業行動や同じソースの価格証跡がない旧D6証跡も、新しい検証には使えない。

ソース全体のSHA変更だけでは隔離しない。後続日の追加やD6より後の分割で調整価格が
変わっていても、検算済み実始値と入口からD6までの企業行動が一致すれば同じ株式単位と
確認できる。正常な後続データの取得は継続できる。

今後 D5 実経済を新たに確定した時点では `d5_price_observed_at` に実際の取込時刻を記録する。
既存 D5 凍結行の取得時刻は推測して補完しないため空欄のまま。新しい日付を使って
古い結果通知を送信対象へ変えることはできない。

## 明示バックフィル

原本 `state/detections.csv` への書込みは行っていない。別出力CSVとprivate overlayの
研究資料による補完は後述する。日次CSVの経路では、入力のサイズ・SHA確認後に
対象の価格・企業行動・同一銘柄性を検算し、
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

## 承認済み研究資料と読み込み用の補完ファイル

ユーザー配置の価格比較ZIPと、保存一式から安全に復元した研究ZIPを使用した。
両ZIPの全体SHA、全メンバーのサイズ・SHA、全506件のBASE5/OPEN6取引、
48集計、営業日・企業行動・元本と株数を検算する。研究HTMLの固定集計値は使用しない。

| 入力 | SHA-256 |
| --- | --- |
| 価格比較ZIP | `481a688c76f6d86c3741b016de510ca2deb5f52a4c61ba4ccd91977ed55be37d` |
| 研究ZIP | `370e9c266319115b035808949b9fc5df3b2fe50f2f64b1dc9ce3f236714578d7` |
| 価格比較 `inputs.json` | `a388021bdc008975cbc442db38d2e3f319ac70baf6b27389180a3f070029ecae` |
| 研究 `compact_inputs.json` | `618cc3b0b5a71d6d60fa67cfa645bf6ae59aaac42cc5ebe01590c4c3ea91e849` |

**検証の範囲:** `REVIEWED_RESEARCH_NOMINAL_V1` は固定された研究明細の名目実価格・
企業行動・経済計算の再検算を表す。元のprepared市場価格・企業行動ファイル自体は
この資料に含まれず、源泉市場データの再取得・独立再検証は行っていない。
二つの資料は同じ上流データを使用しており、独立した二系統の市況証拠ではない。
証跡に `raw_market_refetched:false` と検証範囲を明記し、観測時刻は今回の取込時刻とする。
歴史上の価格取得時刻は推測しない。既知の2026期間も過去の再利用として扱う。

253件の研究検出は、現行254銘柄日・972モード行のうち253銘柄日・967モード行と一致する。
資料にない `2026-09-30|4052` の5モードは補完しない。研究mode identity/scope/statusと
現行972行は一致。二資料で取引明細を照合できる範囲は218件、残る35件は価格比較資料の
上限なし明細を検算している。研究253件を972件の別々の検出と表現してはいけない。

D5の既存金額と研究名目金額には46銘柄日・164モードの差がある。原D5経済は変更せず、
検証済み検出日終値とD6の独立列だけを追加する。D6は原入口価格・100株から、D6までの
分割・併合を適用する（8894の10株、3997/6085の1,000株を含む）。

研究専用の別CSV・監査・照合一覧を生成する。入力も既存出力も上書きしない。

```powershell
python -B -m weak_early_beta.research_endpoint_backfill `
  --ledger weak_early_beta/state/detections.csv `
  --price-comparison-zip <承認済み価格比較ZIP> `
  --mode-research-zip <承認済み研究ZIP> `
  --output review/detections_with_research_receipts.csv `
  --audit review/backfill_audit.json `
  --coverage review/identity_coverage.csv
```

出力直前にCSVを再読込し、全行の終値・D6価格・D6経済の検証判定が一致することを必須とする。
endpoint数値列は17桁で保存する。D5の既存12桁書式は維持する。
7138の1591.0000610351562円のような実価格も、利益の差分丸めで失効しない。

原台帳を変更せず、上記の別CSV・監査をprivate補完ファイルへ変換する。

```powershell
python -B -m weak_early_beta.reviewed_endpoint_overlay `
  --ledger weak_early_beta/state/detections.csv `
  --reviewed-ledger review/detections_with_research_receipts.csv `
  --audit review/backfill_audit.json `
  --output review/reviewed_endpoint_receipts.v1.json `
  --manifest review/reviewed_endpoint_receipts.v1.manifest.json
```

採用済みprivate sidecarは `state/reviewed_endpoint_receipts.v1.json`、対応manifestも同じ場所。
253銘柄日へ証跡を重複排除し、967対象モードのimmutable baseline SHAを持つ。
モジュールの固定SHAと一致するsidecarだけを読み込む。新しい資料の採用は再レビューとSHA更新が必要。
原台帳SHAは `7574c18d72948e8faa3b1e0e8d718690242750f5459e68a3f98d7e18b9a55909` のまま。

`read_ledger()` の既定動作は原台帳の読込だけ。daily/modelへ暗黙適用せず、
レポート生成時に一度読み込んだsidecarを明示的に結合する。

```python
overlay = load_reviewed_endpoint_overlay()
report_ledger, overlay_audit = apply_reviewed_endpoint_overlay(read_ledger(), overlay)
```

入力DataFrameとD5等の既存列は不変、未照合・将来行は変更しない。
対象モードの検出時点・スコア・D5等のbaselineが変わったら生成を停止する。
既存の検証済み証跡を優先して保持し、矛盾は例外で停止、review/quarantineは解除しない。
sidecarには識別子と生の明細があるため**公開assetsへコピーしない**。
HTML/JS/CSVは通常の無料解禁・上限・履歴区分を適用した派生データから生成する。
元の研究ZIPはリポジトリへ含めない。

検証コマンド:

```powershell
python -B -m unittest tests.test_weak_early_beta_endpoint_receipts tests.test_weak_early_beta_research_backfill tests.test_weak_early_beta_reviewed_overlay tests.test_weak_early_beta_model tests.test_weak_early_beta_trade_basis
```
