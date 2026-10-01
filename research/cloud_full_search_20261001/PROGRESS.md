# Cloud 全面探索の進捗

更新（UTC）: 2026-10-01T16:33:10.163873+00:00

状態: **IN_PROGRESS**。本番条件の変更なし。

- 入力準備: 完了
- 同一入力での本番再計算: PASS
- 現在の段階: SCREEN
- 完了fit: 26
- 4月の開発比較を完了した学習設定: 6 / 864
- 全24月・検出政策の再評価完了: 0

途中経過から最善条件や採用可否を断定しません。選抜手順と限界は [PROTOCOL.md](PROTOCOL.md) に記載しています。

再現コマンド（リポジトリ直下、PowerShell）:

```powershell
& '.cache/weak_early_beta/venv/Scripts/python.exe' -B -m unittest discover -s research/cloud_full_search_20261001 -p test_search.py -v
& '.cache/weak_early_beta/venv/Scripts/python.exe' -B research/cloud_full_search_20261001/prepare.py
& '.cache/weak_early_beta/venv/Scripts/python.exe' -B research/cloud_full_search_20261001/parity.py
& '.cache/weak_early_beta/venv/Scripts/python.exe' -B research/cloud_full_search_20261001/search.py --max-fits 8 --max-seconds 480
py -3 -B research/cloud_full_search_20261001/status.py
```

準備・再計算・探索前に使用量を確認して15分のusage leaseを保存します。leaseが無い/期限切れ/STOP_REQUESTEDなら新しいfitを開始しません。
