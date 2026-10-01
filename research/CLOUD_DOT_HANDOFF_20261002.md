# Cloud dot引き継ぎ — 2026-10-02

**引き継ぎ準備完了。** 実データは同じ非公開リポジトリの[研究用Release](https://github.com/Ken5InvestmentLab/screening-bot/releases/tag/research-cloud-dot-handoff-20261002)へ保存し、公開済みprereleaseの7 assetについてローカルとのサイズ・SHA-256一致を確認しました。チェックサム、全ファイルmanifest、検証結果はGitHubから再取得して一致を確認しています。ZIP全体の再ダウンロードは行わず、GitHubのasset digestとローカルで検証済みのZIP SHAを照合しました。

## 停止と保存

- 対象は日足Cloud `weak_early_beta`。スコアリングレポートやStable/Sniper/Megaは対象外です。
- 新バッチ起動を停止し、実行中のbounded batchは147 fitを保存して終了しました。探索Pythonプロセスなし、Windows OS lock解放を確認しています。
- `cloud-4` は **PAUSED**。V2の `STOP_REQUESTED.json` は `user_dot_handoff`、手動再開必須です。leaseは失効させてあります。朝7:30のユーザー停止指示も引き継ぎます。使用量回復だけで解除しません。
- 完了済みの元データ・モデル・予測・計算は削除していません。本番・配信設定、日次runner、Discord、GAS、Sheets、確定ledger/stateは変更・実行していません。
- ZIPの全1,200 payloadファイル（計3,225,606,944 bytes）をCRC/SHA-256で読み直し、固定入力・準備済み5配列・147 fitのモデル/予測hashを照合しました。作成中に元ファイルが変わっていないことも確認しています。
- 認証情報、APIキー、`.env`、秘密鍵、Windows venv、Git認証設定は含めません。選定した全payloadを秘密情報パターンでも検査しました。

## ブランチ・コミットと取得先

- ブランチ: `research/weak-early-beta`
- ZIP内コードとReleaseタグのsnapshotコミット: `9aa210136c3ad954955296745efdd02469a8449c`
- snapshot前HEAD: `fa3c685dca2c9da0b35e7d503a89e123335ea193`
- snapshot前の未コミット変更はsnapshotコミットに保存済みです。ZIPにも最新研究コードと参考差分 `handoff/uncommitted-before-checkpoint.patch` を同梱しました。差分をsnapshotへ再適用しないでください。
- このメモと[保存・取得の検証票](cloud_dot_handoff_20261002/RELEASE_VERIFICATION.json)はsnapshot後に同じブランチへ保存します。モデル・探索コードはsnapshotと同一です。最終ブランチHEADは `git ls-remote origin refs/heads/research/weak-early-beta`、Release固定SHAは `git rev-parse research-cloud-dot-handoff-20261002^{commit}` で取得できます。

| 実ファイル | GitHubから取得 | 内容 |
|---|---|---|
| ZIP（1,540,751,604 bytes / 約1.54 GB・1.43 GiB） | [cloud-dot-handoff-20261002.zip](https://github.com/Ken5InvestmentLab/screening-bot/releases/download/research-cloud-dot-handoff-20261002/cloud-dot-handoff-20261002.zip) | 指定元データ・全キャッシュ・コード・再開票 |
| ZIPチェックサム | [SHA-256](https://github.com/Ken5InvestmentLab/screening-bot/releases/download/research-cloud-dot-handoff-20261002/cloud-dot-handoff-20261002.zip.sha256) | `sha256sum -c`用 |
| 全1,200ファイルのhash | [MANIFEST.json](https://github.com/Ken5InvestmentLab/screening-bot/releases/download/research-cloud-dot-handoff-20261002/MANIFEST.json) | 相対パス・bytes・SHA-256 |
| ZIP検証 | [VERIFICATION.json](https://github.com/Ken5InvestmentLab/screening-bot/releases/download/research-cloud-dot-handoff-20261002/VERIFICATION.json) | CRC・SHA・入力とfit照合 |
| 停止地点 | [CHECKPOINT.json](https://github.com/Ken5InvestmentLab/screening-bot/releases/download/research-cloud-dot-handoff-20261002/CHECKPOINT.json) | 件数・次の設定・未完了項目 |
| 実行環境 | [ENVIRONMENT.json](https://github.com/Ken5InvestmentLab/screening-bot/releases/download/research-cloud-dot-handoff-20261002/ENVIRONMENT.json) | 全インストールパッケージの実測version |
| Linux初期依存 | [requirements-linux-core.txt](https://github.com/Ken5InvestmentLab/screening-bot/releases/download/research-cloud-dot-handoff-20261002/requirements-linux-core.txt) | 移植用の主要依存version |

ZIP SHA-256:

```text
4ea98a96a8128dee2efa93b118686f6b4a6c35bcef7cbf3c0646ccfde016f2b0
```

非公開リポジトリへのread権限が必要です。URLやメモに認証値を埋め込んでいません。大型ファイルをReleaseで配布する方式は[GitHub公式](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github#distributing-large-binaries)に沿っています。Gitへ大型データをcommitせずRelease assetへ保存しています。

## ZIP内の配置

リポジトリルートへ展開する相対パスです。

- `.cache/weak_early_beta/split_preflight_20261001/normalized_daily.csv`（848,694,126 bytes）
- `.cache/cloud_cap_corrected_v2_20261001/` 全581ファイル。必須の `actions.csv` も含みます。
- `.cache/cloud_full_search_v2_20261001/` 全561ファイル。147組のjoblib/npz/json、36 SCREEN結果、34設定の全政策/出口CSV、準備配列、固定除外コピー、進捗、STOP、lease、時刻停止票を含みます。
- `research/cloud_full_search_20261001/` 全26ファイル。最新コード・protocol・AGENTS・進捗・dashboard・監査票。
- `.cache/cloud_full_search_resume_20261001.json`、研究export/独立audit/renderer、固定hashの依存ソース、補足研究レポート。
- `handoff/` の環境・全パッケージ一覧、CHECKPOINT、SOURCE_CONTRACT、MANIFEST、停止確認、参考Git差分。

主要データSHA-256は次のとおりです。全件はMANIFEST、準備入力・配列の対応は同梱SOURCE_CONTRACT / prepared.jsonにあります。

| データ | SHA-256 |
|---|---|
| normalized_daily.csv | `cfc358198f07b29182da77eac5fccb6efe8d2c2450e79d2859cbd7a15f7d0c13` |
| actions.csv | `f53238a8322bc4677a1ae0124bac2bf1e94f62be2b7c0f4f13146cd10345ed80` |
| corrected V2 rows.pkl | `290e30536f8bb99190af4509fdf4ddb7d7153390ba66b5a2c34dfd2ba3ce7b36` |
| corrected V2 features.npy | `ef46fad051eac87b818c0cd786fa6f11f6430748632e4bd351090b1b0113c1af` |
| corrected V2 prices.pkl | `e178d9d46441e425d869f9dc616e2c26e40e415ac680c28e232e2ec02bfc87bd` |
| full-search V2 prepared.json | `3438df61532bd2f6ec7e02e2823b9ca0c178395584e7b2c66aef5e3a338d95cd` |

## 完了件数・未完了・失敗範囲

- 新探索V2: **147 fit、一次比較36/864設定**。36設定は各4月、次の1設定は3/4月完了です。
- 次: `xgb_small_win_h5_all45_cap1000` の **2024-09**。4月比較の残りは3,309 fit、設定としては828設定が未完了です。
- 34設定の全政策/20出口CSVをexport済み。完了SCREEN36設定のうち2設定のexportが未完了です。モデルを再fitする必要はありません。
- 独立監査PASSは **123 receipt / 6 model family / 19 DEV候補の算術再集計**。最新24 fitと新しいwin教師familyの独立再予測監査は未完了です。ZIP化では147 fit全部の保存ファイルhashを照合済みですが、モデル再予測の独立監査とは区別してください。
- 全24月REFINE: 0。短縮候補選抜、最大8候補固定、固定候補の2025検証、2026参考評価、最終結果・最善・採用判定は未完了です。
- V2に `error/failed/.tmp/.partial` 名の残留ファイルはありません。履歴上の失敗が一切なかったとの証明ではありません。旧比較cacheのログも原本として同梱しています。0件予測のfitもCHECKPOINTに記録し、失敗と混同しません。
- 旧270 fit・価格上限6群/20出口比較は完了済みで再実行しません。V1の17 architecture確認fitは新探索V2へ混ぜません。`prepared.identity` のV1表記は古いschemaラベルであり、実際の有効名前空間はV2です。
- 2025も前の研究で閲覧済み。新候補は2025結果を計算する前に固定しますが、完全未閲覧のOOSとは呼びません。2026は参考評価です。段階選抜した有限範囲の最善と、数学的な全条件の最適を区別します。
- 現行同入力・公開参考値の両方に比較します。補正研究baselineに勝つだけで採用せず、現行価格上限1,000円・signal+5終値を途中結果で変えません。

## Linuxでの取得・検証

既存GitHub認証を使い、リポジトリへのアクセスが可能な状態で実行します。新しい認証値をこのメモへ書き込みません。

```bash
gh repo clone Ken5InvestmentLab/screening-bot cloud-handoff -- --branch research/weak-early-beta
cd cloud-handoff
git fetch origin tag research-cloud-dot-handoff-20261002
git rev-parse research-cloud-dot-handoff-20261002^{commit}

gh release download research-cloud-dot-handoff-20261002 \
  --repo Ken5InvestmentLab/screening-bot \
  --pattern 'cloud-dot-handoff-20261002.zip' \
  --pattern 'cloud-dot-handoff-20261002.zip.sha256'
sha256sum -c cloud-dot-handoff-20261002.zip.sha256
python3 -m zipfile -e cloud-dot-handoff-20261002.zip .
python3 -B research/verify_cloud_dot_handoff_20261002.py .
```

ZIPは同じルートへ展開し、`.cache` を移動・名前変更しません。標準ライブラリのverifierは全manifest hashを検証し、学習や本番更新をしません。ブランチのGit blobとWindows実ファイルで改行が違う依存ソースも、ZIPには固定hashの実バイトを保存しています。hash照合前に改行を変換しないでください。

## 実行環境とLinux再開の制約

元環境: Windows 11 x64、Python **3.12.14**（`3.12.14 (main, Aug 25 2026, 14:01:42) [MSC v.1944 64 bit (AMD64)]`）。numpy 2.5.3、pandas 2.3.3、scikit-learn 1.9.1、xgboost 3.4.1、joblib 1.6.0、scipy 1.18.1、threadpoolctl 3.7.0。実測の全依存はENVIRONMENTにあります。

**現在のWindows探索コードをLinuxでそのまま新fitへ再開することはできません。** 未実施の移植事項です。

1. `common.locked()` はWindows `msvcrt.locking`。Linuxでは `fcntl.flock` 相当へ移植し、二重起動防止・解除・異常終了を検証します。
2. `verify_contract()` は `sys.version` 全文と依存versionを照合します。Linuxのコンパイラ文字列が違うため、同じPython小版本でも一致しません。新しいLinux名前空間・元環境との来歴と互換性監査が必要です。
3. 準備hashはengineの全 `*.py` とPROTOCOL・固定ソースを含みます。コードや環境を変更したcompleted cacheを元V2へ混ぜず、元receipt・prepared/runtime/hashを書き換えて回避しません。
4. `Scripts/python.exe`、PowerShellの `&`、ドライブ絶対パス、CRLFをLinuxへ読み替えます。大きいjoblib/pklの読み込みには元パッケージとの互換性確認が必要です。OSのBLAS/OpenMP差も考慮し、予測・CDFを独立照合してください。
5. V2を読取専用の原本として保持します。既存fitの再利用可否をまず監査し、互換性を証明して来歴を保存できるものを再利用します。移植後に無条件で147 fitを消したり再計算したりしません。新環境で必要な再計算は別名前空間で明示します。
6. STOP/失効lease/時刻停止票を同梱しています。人の明示再開、使用量実測、15分lease、OS lockが揃うまで新処理を起動しません。週間残20%以下はPAUSED・手動待ち、5時間残3%以下は時刻/引き継ぎ停止が無い場合だけ回復後retryという制約を保持します。

移植用環境の初期構築例です。これだけで本番等価性が確認できたとは扱いません。

```bash
python3.12 -m venv .venv-cloud-dot
. .venv-cloud-dot/bin/activate
python -m pip install -r handoff/requirements-linux-core.txt
```

元Windowsでの正確な再開コマンドは次です。現在は停止票により意図的に開始しません。

```powershell
& '.cache/weak_early_beta/venv/Scripts/python.exe' -X utf8 -B research/cloud_full_search_20261001/search.py --max-fits 8 --max-seconds 480
```

Linux版にOS lock・cache namespace・来歴/環境検証を実装して監査を通し、人が再開を指示した後、移植した `search.py` に同じ `--max-fits 8 --max-seconds 480` を渡します。現在存在しないLinux移植版を「実行済み・再開可能」とは報告しません。各バッチ後に保存済みDEV設定をexportし、新familyの独立監査、status、rendererを更新してください。探索モデルや旧比較を進捗確認のために再fitしません。

研究のルールは[PROTOCOL](cloud_full_search_20261001/PROTOCOL.md)と[AGENTS](cloud_full_search_20261001/AGENTS.md)にあります。営業日当時価格/出来高、実100株原価・保有中株数、端株/価格欠落の除外、固定約定困難・JPX因果ゲートを維持してください。

