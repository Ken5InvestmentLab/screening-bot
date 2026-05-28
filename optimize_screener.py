#!/usr/bin/env python3
"""
optimize_screener.py — 天底極致スコアロジック自動最適化 + 自動デプロイ

使い方:
  py optimize_screener.py              # 通常実行（分析→更新→デプロイ）
  py optimize_screener.py --dry-run    # 分析のみ（ファイル更新・デプロイなし）
"""

import argparse, json, math, os, subprocess, sys
from datetime import datetime, timedelta, timezone
from itertools import combinations

import numpy as np
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ══════════════════════════════════════════════════════════════
# パス設定（ローカル / VM 自動判別）
# ══════════════════════════════════════════════════════════════
import platform as _platform

_ON_GITHUB_ACTIONS = os.environ.get('GITHUB_ACTIONS') == 'true'
_ON_VM = not _ON_GITHUB_ACTIONS and _platform.system() == "Linux" and os.path.isdir("/home/ubuntu/screening-bot")

if _ON_GITHUB_ACTIONS:
    BASE_DIR           = os.path.dirname(os.path.abspath(__file__))
    CREDENTIALS_PATH   = BASE_DIR + "/credentials.json"
    SCREENER_JS_PATH   = BASE_DIR + "/screener.js"
    INDEX_JS_PATH      = BASE_DIR + "/index.js"
    CURRENT_LOGIC_PATH = BASE_DIR + "/current_logic.json"
    SSH_KEY_PATH       = "/tmp/ssh_key"
    VM_HOST            = "ubuntu@168.110.60.126"
    VM_DEST            = "~/screening-bot/"
elif _ON_VM:
    BASE_DIR           = "/home/ubuntu/screening-bot"
    CREDENTIALS_PATH   = BASE_DIR + "/credentials.json"
    SCREENER_JS_PATH   = BASE_DIR + "/screener.js"
    INDEX_JS_PATH      = BASE_DIR + "/index.js"
    CURRENT_LOGIC_PATH = BASE_DIR + "/current_logic.json"
    SSH_KEY_PATH       = None
    VM_HOST            = None
    VM_DEST            = None
else:
    BASE_DIR            = r"C:\Users\ken5\OneDrive\Desktop\Product\天底極致スコアリングBot\screening-bot"
    CREDENTIALS_PATH    = BASE_DIR + r"\credentials.json"
    SCREENER_JS_PATH    = BASE_DIR + r"\screener.js"
    INDEX_JS_PATH       = BASE_DIR + r"\index.js"
    CURRENT_LOGIC_PATH  = BASE_DIR + r"\current_logic.json"
    SSH_KEY_PATH        = r"C:\Users\ken5\OneDrive\Desktop\Product\ssh-key-2026-03-08.key"
    VM_HOST             = "ubuntu@168.110.60.126"
    VM_DEST             = "~/screening-bot/"

PENDING_LOGIC_PATH       = os.path.join(BASE_DIR, "pending_logic.json")
SNIPER_LOGIC_PATH        = os.path.join(BASE_DIR, "current_logic_sniper.json")
SNIPER_PENDING_PATH      = os.path.join(BASE_DIR, "pending_logic_sniper.json")
MOONSHOT_LOGIC_PATH      = os.path.join(BASE_DIR, "current_logic_moonshot.json")
MOONSHOT_PENDING_PATH    = os.path.join(BASE_DIR, "pending_logic_moonshot.json")
RESCUE_STATE_PATH        = os.path.join(BASE_DIR, "rescue_state.json")
CHAMPION_STATE_PATH      = os.path.join(BASE_DIR, "champion_state.json")
LOGIC_HISTORY_PATH       = os.path.join(BASE_DIR, "current_logic_history.jsonl")
SNIPER_WR_MIN            = 0.65   # Sniper採用の最低勝率
SNIPER_N_MIN             = 10     # Sniper採用の最低件数
SNIPER_WR_EPS            = 1e-12  # 浮動小数誤差を吸収しつつ、勝率はstrict改善のみ採用

# Moonshot (平均リターン特化): 勝率不問・検出数フリー・15%以上の平均リターンが採用条件
MOONSHOT_AVG_MIN              = 0.15   # 採用最低平均リターン（+15%）
MOONSHOT_N_MIN                = 3      # 最低件数（検出数フリー方針なので緩め）
MOONSHOT_AVG_EPS              = 1e-12  # 平均はstrict改善のみ採用
MOONSHOT_EVAL_DAYS_CANDIDATES = [10, 20, 40]  # 初回最適化での評価日候補
# ─── Moonshot 自動最適化のマスタースイッチ ───
# False の間は optimize.yml / --apply-pending どちらでも Moonshot は完全スキップされる:
#   - main() の _run_moonshot_optimization() 呼び出しを no-op 化
#   - pending_logic_moonshot.json は生成されない（Discord通知も飛ばない）
#   - 万一 pending_logic_moonshot.json が残っていても --apply-pending で無視される
# データ蓄積後にここを True に変更すれば、翌日の optimize.yml から自動最適化が走る。
MOONSHOT_AUTO_OPTIMIZE_ENABLED = False

SPREADSHEET_ID   = "1pcD6-462nyv1A1bcW5UeWwaxBr7A1RIJ6Ofixeo5Xb8"
SCOPES           = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

TARGET_WIN_RATE  = 0.55
TARGET_AVG_PERF  = 0.03
RECENCY_HALFLIFE = 90    # 近接性加重: 90日前のシグナルは重み0.5
BASELINE_DECAY   = 1.0   # 現行compositeを厳密に超えた場合のみ採用（同一・改悪は不採用）
WIN10_MIN_COUNT  = 5     # ★6内の+10%以上銘柄の最低件数
WIN10_RATE_FLOOR_RATIO = 0.90  # ★6内の+10%以上率が現行比90%以上ならOK

# 「大勝ち / 大負け」を定義する閾値（5BD騰落率）。
# --win-threshold / --win-threshold-sweep CLI フラグで上書き可能。
# Method B リフト分析、composite スコア、品質ゲート、上昇/下落表示に伝播する。
WIN_THRESHOLD  = 0.10
LOSE_THRESHOLD = -0.10

# Stable ★6 品質ゲート（過学習防止 + 劣化検知）
STABLE_WR_MIN          = 0.60  # 全件★6勝率の最低ライン
STABLE_S6_N_MIN        = 20    # 全件★6最低件数 (strict時) (40→20: 現行ロジック23件の実態に合わせて緩和)
RESCUE_STABLE_S6_N_MIN = 15    # rescue mode時の全件★6最低件数 (30→15)
STABLE_AVG_MIN         = 0.05  # 全件★6平均騰落率（最低5%要求）
STABLE_VALID_WR_MIN    = 0.55  # 直近検証側★6勝率は strict >
STABLE_VALID_S6_N_MIN  = 20    # 直近検証側★6最低件数 (strict時) (8→20)
STABLE_VALID_AVG_MIN   = 0.00  # 直近検証側★6平均騰落率
# 検証件数の相対ゲート（絶対閾値ではなく現行ロジック比で評価）
# 6条件AND型の自然な選択性（≈1-2%）に対応し、データ規模に応じてスケールする。
# baseline_validation_stats が渡された場合のみ有効。後方互換は絶対閾値を継続使用。
MIN_VALID_N_FLOOR     = 5     # 検証★6の絶対最低件数（これ未満は統計的意味なし）
VALID_N_RATIO_FLOOR   = 0.8   # 現行検証★6 × 0.8 以上を維持（WIN10_RATE_FLOOR_RATIOと同思想）

# ── 過渡期（archive 蓄積中）の緩和水準 ───────────────────────────────
# データが少ない期間は統計的厳格化を一時スキップし、pre-Tier-A 水準で運用。
# 統計検定 (Lockbox/Bootstrap CI/K-Fold) は n が小さいと逆に偽陽性/偽陰性を量産するため。
TRANSITION_STABLE_S6_N_MIN        = 15   # 過渡期: pre-Tier-A 水準 (25→15: 件数ゲート緩和に追随)
TRANSITION_RESCUE_STABLE_S6_N_MIN = 10   # 過渡期: pre-Tier-A 水準 (20→10)
TRANSITION_STABLE_VALID_S6_N_MIN  = 8    # 過渡期: pre-Tier-A 水準
MIN_TOTAL_FOR_STRICT_MODE         = 150  # strict mode に切り替える全件数の最低ライン
MIN_LOCKBOX_FOR_STRICT_MODE       = 25   # strict mode に切り替える lockbox 件数の最低ライン
RESCUE_REQUIRED_STREAK = 2     # rescueは劣化判定が連続した場合のみ起動
RESCUE_CURRENT_S6_N_MIN = 5    # 現在値の未確定★6を回復兆候として見る最低件数

# 現行ロジックが健全と判定するためのスキップ下限（満たしていれば最適化しない）
HEALTHY_SKIP_WR    = 0.65   # 全件★6勝率がこれ以上 → 更新不要
HEALTHY_SKIP_AVG   = 0.08   # 全件★6平均がこれ以上 → 更新不要
HEALTHY_SKIP_N_MIN = 25     # 全件★6件数がこれ以上 → 更新不要

# Sniperモードのスキップ下限（勝率特化のためavg不要・件数は少なくてOK）
SNIPER_HEALTHY_SKIP_WR    = 0.75   # Sniper全件勝率がこれ以上 → 更新不要
SNIPER_HEALTHY_SKIP_N_MIN = 15     # Sniper全件★6件数がこれ以上 → 更新不要

# Sniperモードのレスキュー閾値
# - SNIPER_RESCUE_TRIGGER_WR: 全件再計算 or ライブ実績がこの勝率を下回ったらレスキュー候補
# - SNIPER_RESCUE_TRIGGER_N : ライブ実績（採用日以降）がこの件数以上ならライブ単独でもレスキューを判定
# - SNIPER_LIVE_HEALTH_WR   : ライブ実績がこれ以上なら健全と判定して健全スキップを継続
# - SNIPER_RESCUE_WR_MIN    : レスキューモード時の採用最低勝率（normalの0.65から緩和）
SNIPER_RESCUE_TRIGGER_WR = 0.60
SNIPER_RESCUE_TRIGGER_N  = 10
SNIPER_LIVE_HEALTH_WR    = 0.60
SNIPER_RESCUE_WR_MIN     = 0.55
WALK_FORWARD_VALID_FRAC = 0.20  # 30%→20%: lockbox分を確保するため
LOCKBOX_FRAC            = 0.20  # 選別ループに一切触れない真のOOS
WALK_FORWARD_CANDIDATE_LIMIT = 20_000
FINAL_EVAL_CANDIDATE_LIMIT = 2_000
THRESHOLD_TUNE_CANDIDATE_LIMIT = 9

# composite バリアント: rate_adjusted=件数正規化(デフォルト) / snr=√n正規化 / legacy=旧来
COMPOSITE_VARIANT = "rate_adjusted"
STRICT_WR  = False  # 勝率フロアは >= (同一勝率でも他指標で勝てば採用。Phase 1緩和)
WR_FLOOR   = 0.0    # 勝率絶対下限 (0.0=無効)

# 更新通知先Discord Webhook
DISCORD_WEBHOOK_URL  = "https://discord.com/api/webhooks/1479431524674965729/sRCEG2lmoBLpEtZCdbf5N4kg2zEI7LHjtxxHm9g2Y1rFXPwoFSPDxpnOjsP0HAObSdyZ"
# 承認リクエスト送信先Discord Webhook（管理者チャンネル）
APPROVAL_WEBHOOK_URL = "https://discord.com/api/webhooks/1480211740007600351/OWog6gutSvvUfJN6vbZgzI3AsJjMeIdcw_ho0pEGqwHVd_RRMnstqvMg8WGaLnK5jHwO"

# ══════════════════════════════════════════════════════════════
# 現行ロジック永続化
# ══════════════════════════════════════════════════════════════
def load_current_logic():
    """デプロイ済みの最新スコアロジックを読み込む。未保存ならNoneを返す。"""
    import json
    if not os.path.exists(CURRENT_LOGIC_PATH):
        return None
    try:
        with open(CURRENT_LOGIC_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  ⚠ current_logic.json 読み込みエラー: {e}")
        return None

def save_current_logic(method, conditions, thresholds=None, backtest=None):
    """デプロイ成功後に現行ロジックを保存する。"""
    import json
    data = {
        "method": method,
        "conditions": conditions,
        "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    if thresholds:
        data["thresholds"] = thresholds
    if backtest:
        data["backtest"] = backtest
    try:
        with open(CURRENT_LOGIC_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  ✅ current_logic.json 更新完了")
    except Exception as e:
        print(f"  ⚠ current_logic.json 保存エラー: {e}")

def load_champion_state():
    """champion_state.json を読み込む。存在しない場合は空の状態を返す。"""
    if not os.path.exists(CHAMPION_STATE_PATH):
        return {}
    try:
        with open(CHAMPION_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  ⚠ champion_state.json 読み込みエラー: {e}")
        return {}

def save_champion_state(state):
    """champion_state.json を保存する。"""
    try:
        with open(CHAMPION_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        print("  ✅ champion_state.json 更新完了")
    except Exception as e:
        print(f"  ⚠ champion_state.json 保存エラー: {e}")

def promote_to_champion(method, conditions, thresholds, backtest, deployed_at=None):
    """新ロジックを Champion に昇格し、旧 Champion を prev_champion に降格する。
    live_log はリセットされ、次回以降のシグナルから prev_champion スコアを並走計算する。"""
    old_state = load_champion_state()
    old_champion = old_state.get("champion")
    now_str = deployed_at or datetime.utcnow().isoformat().replace("+00:00", "Z")
    new_state = {
        "champion": {
            "method": method,
            "conditions": list(conditions),
            "thresholds": thresholds or {},
            "deployed_at": now_str,
            "backtest_snapshot": backtest or {},
        },
        "prev_champion": None,
        "live_log": [],
    }
    if old_champion:
        new_state["prev_champion"] = {
            **old_champion,
            "demoted_at": now_str,
        }
    save_champion_state(new_state)
    # ロジック履歴（最大20件）に追記
    _append_logic_history(method, conditions, thresholds, backtest, now_str)

def _append_logic_history(method, conditions, thresholds, backtest, deployed_at):
    """current_logic_history.jsonl にロジック変更履歴を追記する（最大20件保持）。"""
    entry = {
        "deployed_at": deployed_at,
        "method": method,
        "conditions": list(conditions),
        "thresholds": thresholds or {},
        "backtest": backtest or {},
    }
    existing = []
    if os.path.exists(LOGIC_HISTORY_PATH):
        try:
            with open(LOGIC_HISTORY_PATH, "r", encoding="utf-8") as f:
                existing = [json.loads(line) for line in f if line.strip()]
        except Exception:
            existing = []
    existing.append(entry)
    existing = existing[-20:]  # 最大20件
    try:
        with open(LOGIC_HISTORY_PATH, "w", encoding="utf-8") as f:
            for e in existing:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    except Exception as ex:
        print(f"  ⚠ 履歴追記エラー: {ex}")

def load_current_logic_sniper():
    """デプロイ済みのSniperロジックを読み込む。未保存ならNoneを返す。"""
    import json
    if not os.path.exists(SNIPER_LOGIC_PATH):
        return None
    try:
        with open(SNIPER_LOGIC_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data.get("conditions"):
            return None  # 空のプレースホルダー → 未初期化
        return data
    except Exception as e:
        print(f"  ⚠ current_logic_sniper.json 読み込みエラー: {e}")
        return None

def save_current_logic_sniper(conditions, thresholds=None, wr_raw=None, backtest_stats=None,
                              preserve_updated_at=False):
    """デプロイ成功後にSniperロジックを保存する。
    preserve_updated_at=True なら既存ファイルの updated_at を引き継ぐ
    （統計だけリフレッシュする用途。ライブ実績集計の起点日を維持するため）。"""
    import json
    updated_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    if preserve_updated_at and os.path.exists(SNIPER_LOGIC_PATH):
        try:
            with open(SNIPER_LOGIC_PATH, "r", encoding="utf-8") as _ef:
                _existing = json.load(_ef)
            _ex_updated = _existing.get("updated_at")
            if _ex_updated:
                updated_at = _ex_updated
        except Exception:
            pass
    data = {
        "method": "sniper",
        "conditions": conditions,
        "updated_at": updated_at,
        "thresholds": thresholds or {},
    }
    if backtest_stats:
        wr_raw = backtest_stats.get("wr_raw", wr_raw)
        data["backtest"] = {
            "source": "all",
            "n": int(backtest_stats.get("n", 0)),
            "wr": round(float(backtest_stats.get("wr_raw", 0)) * 100, 1),
            "avg": round(float(backtest_stats.get("avg_raw", 0)) * 100, 1),
        }
    if wr_raw is not None:
        data["wr_raw"] = float(wr_raw)
    try:
        with open(SNIPER_LOGIC_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  ✅ current_logic_sniper.json 更新完了")
    except Exception as e:
        print(f"  ⚠ current_logic_sniper.json 保存エラー: {e}")

def compute_current_sniper_backtest_stats(df, sniper_logic):
    """現行Sniper条件に対して df 全体（alerts_raw + signals_archive）の
    全通過統計を再計算する。current_logic_sniper.json の凍結数値を
    最新化するために毎回の最適化で呼ぶ。"""
    if not sniper_logic or df is None or len(df) == 0:
        return None
    conditions = sniper_logic.get("conditions") or []
    if not conditions:
        return None
    missing = [c for c in conditions if c not in df.columns]
    if missing:
        print(f"  ⚠ Sniperバックテスト再計算: 条件列が見つかりません: {missing}")
        return None
    mask_pass = pd.Series(True, index=df.index)
    for c in conditions:
        mask_pass &= df[c].astype(bool)
    return calc_stats(df[mask_pass])

def compute_live_sniper_stats(df, sniper_logic):
    """current_logic_sniper.json の updated_at 以降に発生したシグナルに対し、
    現行Sniper条件全通過の勝率/平均/件数を返す（採用後のライブ実績）。
    対象0件のときは n=0 の calc_stats 辞書、計算不能なら None。"""
    if not sniper_logic or df is None or len(df) == 0:
        return None
    conditions = sniper_logic.get("conditions") or []
    if not conditions:
        return None
    updated_at = sniper_logic.get("updated_at")
    if not updated_at:
        return None
    try:
        adopted_ts = pd.to_datetime(updated_at, errors="coerce", utc=True)
    except Exception:
        return None
    if pd.isna(adopted_ts):
        return None
    # df["date"] は "YYYY/MM/DD" 文字列で tz-naive。比較のために adopted も tz-naive 化。
    adopted_date = adopted_ts.tz_convert("UTC").tz_localize(None).normalize()
    df_dates = pd.to_datetime(df["date"], errors="coerce")
    mask_recent = df_dates >= adopted_date
    df_live = df[mask_recent]
    if len(df_live) == 0:
        return calc_stats(pd.DataFrame())
    missing = [c for c in conditions if c not in df_live.columns]
    if missing:
        print(f"  ⚠ Sniperライブ集計: 条件列が見つかりません: {missing}")
        return None
    mask_pass = pd.Series(True, index=df_live.index)
    for c in conditions:
        mask_pass &= df_live[c].astype(bool)
    return calc_stats(df_live[mask_pass])

def load_current_logic_moonshot():
    """デプロイ済みのMoonshotロジックを読み込む。conditions空 or eval_days未設定はNone扱い。"""
    import json
    if not os.path.exists(MOONSHOT_LOGIC_PATH):
        return None
    try:
        with open(MOONSHOT_LOGIC_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data.get("conditions"):
            return None  # 空のプレースホルダー → 未初期化
        return data
    except Exception as e:
        print(f"  ⚠ current_logic_moonshot.json 読み込みエラー: {e}")
        return None

def save_current_logic_moonshot(conditions, eval_days, thresholds=None, avg_raw=None,
                                 backtest_stats=None):
    """Moonshotロジックを保存。eval_days は初回決定後は固定（外側で同じ値を渡す）。"""
    import json
    data = {
        "method": "moonshot",
        "conditions": conditions,
        "eval_days": int(eval_days) if eval_days is not None else None,
        "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "thresholds": thresholds or {},
    }
    if backtest_stats:
        avg_raw = backtest_stats.get("avg_raw", avg_raw)
        data["backtest"] = {
            "source": "all",
            "eval_days": int(eval_days) if eval_days is not None else None,
            "n": int(backtest_stats.get("n", 0)),
            "wr": round(float(backtest_stats.get("wr_raw", 0)) * 100, 1),
            "avg": round(float(backtest_stats.get("avg_raw", 0)) * 100, 1),
        }
    if avg_raw is not None:
        data["avg_raw"] = float(avg_raw)
    try:
        with open(MOONSHOT_LOGIC_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  ✅ current_logic_moonshot.json 更新完了")
    except Exception as e:
        print(f"  ⚠ current_logic_moonshot.json 保存エラー: {e}")

# ══════════════════════════════════════════════════════════════
# Google Sheets
# ══════════════════════════════════════════════════════════════
def get_service():
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)

def fetch(service, sheet):
    res = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=sheet).execute()
    return res.get("values", [])

# ══════════════════════════════════════════════════════════════
# データ解析
# ══════════════════════════════════════════════════════════════
def parse_perf(v):
    if v is None or str(v).strip() == "": return float("nan")
    s = str(v).replace("%", "").strip()
    try:
        n = float(s)
        return n / 100 if "%" in str(v) else n
    except ValueError:
        return float("nan")

def parse_price(v):
    if v is None or str(v).strip() == "":
        return float("nan")
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return float("nan")

def parse_alerts(rows, include_unconfirmed=False):
    if len(rows) < 5: return pd.DataFrame()
    header = [h.lower().strip() for h in rows[3]]
    def idx(n): return header.index(n) if n in header else -1
    recs = []
    for r in rows[4:]:
        if not r: continue
        def g(col):
            i = idx(col); return r[i] if 0 <= i < len(r) else ""
        if g("signal_type").strip().upper() != "BOTTOM": continue
        sym = g("symbol_code").strip()
        sym = sym.split(":")[-1] if ":" in sym else sym
        if not sym: continue
        entry = parse_price(g("entry_price"))
        p5 = parse_perf(g("perf_5bd"))
        # Moonshot 用: 10/20/40 BD 後の騰落率（スプシに未配置のときは NaN）
        p10 = parse_perf(g("perf_10bd"))
        p20 = parse_perf(g("perf_20bd"))
        p40 = parse_perf(g("perf_40bd"))
        confirmed = math.isfinite(p5)
        if not confirmed and not include_unconfirmed: continue
        if not math.isfinite(entry) or entry <= 0:
            if not confirmed:
                continue
            entry = 0.0
        recs.append({
            "alert_id": g("alert_id").strip(),  # signals_archive と alerts_raw の統合時に重複除去キーとして使う
            "symbol": sym, "name": g("symbol_name").strip(),
            "date": g("signal_date").strip(),
            "entry": entry,
            "perf_5bd": p5 if confirmed else np.nan,
            "perf_10bd": p10 if math.isfinite(p10) else np.nan,
            "perf_20bd": p20 if math.isfinite(p20) else np.nan,
            "perf_40bd": p40 if math.isfinite(p40) else np.nan,
            "win_5bd": p5 > 0 if confirmed else False,  # win_flag_5bdはGAS取得タイミング次第でズレるため自力判定
            "confirmed_5bd": confirmed,
        })
    df = pd.DataFrame(recs)
    if df.empty: return df
    df["win10"]  = df["perf_5bd"] >= WIN_THRESHOLD
    df["lose10"] = df["perf_5bd"] <= LOSE_THRESHOLD
    return df

def aggregate_daily(bars):
    dm = {}
    for b in bars:
        k = b["date"][:10]
        if k not in dm:
            dm[k] = dict(date=k, open=b["open"], high=b["high"],
                         low=b["low"], close=b["close"], volume=b["volume"])
        else:
            d = dm[k]
            d["high"]    = max(d["high"], b["high"])
            d["low"]     = min(d["low"],  b["low"])
            d["close"]   = b["close"]
            d["volume"] += b["volume"]
    return sorted(dm.values(), key=lambda x: x["date"])

def parse_ohlcv(rows):
    if len(rows) < 2: return {}
    hdr = [h.lower().strip() for h in rows[0]]
    def idx(n): return hdr.index(n) if n in hdr else -1
    iS=idx("symbol"); iT=idx("timestamp"); iO=idx("open")
    iH=idx("high");   iL=idx("low");       iC=idx("close"); iV=idx("volume")
    sm = {}
    for r in rows[1:]:
        if not r: continue
        raw = r[iS] if 0 <= iS < len(r) else ""
        sym = raw.split(":")[-1].strip() if raw else ""
        if not sym: continue
        def fv(i):
            try: return float(r[i]) if 0 <= i < len(r) else float("nan")
            except: return float("nan")
        ts = (r[iT].replace("/", "-") if 0 <= iT < len(r) else "")[:10]
        if not ts: continue
        bar = dict(date=ts, open=fv(iO), high=fv(iH), low=fv(iL),
                   close=fv(iC), volume=fv(iV))
        if not math.isfinite(bar["close"]): continue
        sm.setdefault(sym, []).append(bar)
    return {s: aggregate_daily(sorted(b, key=lambda x: x["date"]))
            for s, b in sm.items()}

# ══════════════════════════════════════════════════════════════
# 指標計算
# ══════════════════════════════════════════════════════════════
def ema_arr(vals, p):
    if len(vals) < p: return [None] * len(vals)
    k = 2 / (p + 1)
    res = [None] * (p - 1)
    e = sum(vals[:p]) / p
    res.append(e)
    for v in vals[p:]:
        e = v * k + e * (1 - k)
        res.append(e)
    return res

def get_features(daily, sig_date):
    # 日付フォーマット統一: alerts='2026/03/05', ohlcv='2026-03-05'
    sig_dt = sig_date.replace('/', '-')[:10]
    bars = [b for b in daily if b["date"] <= sig_dt]
    if len(bars) < 30: return None
    last = len(bars) - 1
    C = [b["close"]  for b in bars]
    H = [b["high"]   for b in bars]
    L = [b["low"]    for b in bars]
    O = [b["open"]   for b in bars]
    V = [b["volume"] for b in bars]
    lc, lo = C[last], O[last]

    e25 = ema_arr(C, 25)[last]
    e75 = ema_arr(C, 75)[last]
    if e25 is None: return None

    tr = [max(H[i]-L[i], abs(H[i]-C[i-1]), abs(L[i]-C[i-1]))
          for i in range(max(1, last-27), last+1)]
    atr = sum(tr[-14:]) / min(14, len(tr))
    atr_pct = atr / lc * 100 if lc > 0 else 999

    v20 = (sum(V[max(0, last-20):last]) / 20 if last >= 20
           else sum(V[:last]) / max(1, last))
    vsurge = V[last] / v20 if v20 > 0 else 0
    body_pct = (lc - lo) / lc * 100 if lc > 0 else 0
    lower_wick = min(lc, lo) - L[last]
    lower_wick50 = lower_wick >= abs(lc - lo) and lower_wick > 0

    m12 = ema_arr(C, 12); m26 = ema_arr(C, 26)
    ml  = [a - b for a, b in zip(m12, m26) if a is not None and b is not None]
    sig = ema_arr(ml, 9)
    gc3 = False
    if len(ml) >= 12 and len(sig) >= 4:
        for i in range(min(3, len(sig) - 1)):
            hn = ml[len(ml)-1-i] - sig[len(sig)-1-i]
            hp = ml[len(ml)-2-i] - sig[len(sig)-2-i]
            if hn > 0 and hp <= 0: gc3 = True; break
    macd_pos = len(ml) > 0 and len(sig) > 0 and sig[-1] is not None and ml[-1] > sig[-1]

    d = [C[i] - C[i-1] for i in range(1, len(C))]
    ag = sum(x for x in d[-14:] if x > 0) / 14 if len(d) >= 14 else 0
    al = sum(-x for x in d[-14:] if x < 0) / 14 if len(d) >= 14 else 0
    rsi = 100 - 100 / (1 + ag/al) if al > 0 else 100

    hi20 = max(H[max(0, last-20):last]) if last > 0 else lc
    hb20 = lc > hi20
    pre_decline15 = hi20 > 0 and (lc / hi20 - 1) <= -0.15

    def _rci(prices, period):
        if len(prices) < period: return None
        p = prices[-period:]
        n = period
        sorted_desc = sorted(p, reverse=True)
        d_sq = sum((i+1 - (sorted_desc.index(p[i])+1))**2 for i in range(n))
        return (1 - 6*d_sq / (n*(n**2-1))) * 100

    rci9  = _rci(C[:last+1], 9)
    rci26 = _rci(C[:last+1], 26)
    rci9_prev = _rci(C[:last], 9) if last >= 9 else None
    rci9_os  = rci9  is not None and rci9  <= -50
    rci26_os = rci26 is not None and rci26 <= -50
    rci9_up  = (rci9 is not None and rci9_prev is not None
                and rci9 > rci9_prev and rci9 < 0)

    pre_down3 = (last >= 3 and C[last-1] < C[last-2] and C[last-2] < C[last-3])
    gap_up    = (last > 0 and lo > C[last-1])

    # 連続小陽線（シグナル前に body 0〜1% の陽線が連続）
    def _is_small_bull(i):
        if i < 0 or i >= len(C): return False
        bp = (C[i] - O[i]) / C[i] * 100 if C[i] > 0 else 0
        return 0 < bp < 1.0
    smbull_seq2 = last >= 2 and _is_small_bull(last-1) and _is_small_bull(last-2)
    smbull_seq3 = last >= 3 and _is_small_bull(last-1) and _is_small_bull(last-2) and _is_small_bull(last-3)

    cci_start = max(0, last-13)
    tp_cci = [(H[i]+L[i]+C[i])/3 for i in range(cci_start, last+1)]
    tp_mean_cci = sum(tp_cci)/len(tp_cci)
    tp_md_cci   = sum(abs(x-tp_mean_cci) for x in tp_cci)/len(tp_cci)
    cci = (tp_cci[-1]-tp_mean_cci)/(0.015*tp_md_cci) if tp_md_cci > 0 else 0
    cci_os = cci <= -100

    lo14 = min(L[max(0, last-13):last+1])
    hi14 = max(H[max(0, last-13):last+1])
    stoch = (lc - lo14) / (hi14 - lo14) * 100 if (hi14 - lo14) > 0 else 50

    bb = C[max(0, last-19):last+1]
    bm = sum(bb) / len(bb)
    bs = (sum((x - bm)**2 for x in bb) / len(bb)) ** 0.5
    bbpct = max(0, min(1, ((lc - (bm - 2*bs)) / (4*bs)) if bs > 0 else 0.5))
    bb_lower = bbpct <= 0.20

    def ichimoku_mid(end, period):
        if end is None or end - period + 1 < 0:
            return None
        return (max(H[end-period+1:end+1]) + min(L[end-period+1:end+1])) / 2

    tenkan = ichimoku_mid(last, 9)
    kijun = ichimoku_mid(last, 26)
    span_a_future = (tenkan + kijun) / 2 if tenkan is not None and kijun is not None else None
    span_b_future = ichimoku_mid(last, 52)

    def visible_ichimoku_cloud(end):
        # Signal-date cloud values are the spans calculated 26 bars earlier.
        base = end - 26
        t = ichimoku_mid(base, 9)
        k = ichimoku_mid(base, 26)
        b = ichimoku_mid(base, 52)
        if t is None or k is None or b is None:
            return None, None, None
        a = (t + k) / 2
        return a, b, max(a, b)

    cloud_a, cloud_b, cloud_top = visible_ichimoku_cloud(last)
    _, _, cloud_top_prev = visible_ichimoku_cloud(last - 1)

    ich_tk = tenkan is not None and kijun is not None and tenkan > kijun
    ich_price_tenkan = tenkan is not None and lc > tenkan
    ich_price_kijun = kijun is not None and lc > kijun
    ich_cloud_above = cloud_top is not None and lc > cloud_top
    ich_cloud_green = span_a_future is not None and span_b_future is not None and span_a_future > span_b_future
    ich_chikou = last >= 26 and lc > C[last-26]
    ich_kumo_break = (
        cloud_top is not None and cloud_top_prev is not None
        and C[last-1] <= cloud_top_prev and lc > cloud_top
    )

    return dict(
        ema75=e75 is not None and lc > e75, ema25=lc > e25,
        vol20=vsurge >= 2.0, vol15=vsurge >= 1.5, vol12=vsurge >= 1.2, vol30=vsurge >= 3.0,
        sbull=body_pct >= 0.5, body1=body_pct >= 1.0, body2=body_pct >= 2.0,
        macdgc=gc3, macdpos=macd_pos,
        atr5=atr_pct < 5.0, atr3=atr_pct < 3.0, atr7=atr_pct < 7.0,
        hb20=hb20, lower_wick50=lower_wick50, pre_decline15=pre_decline15,
        stoch75=stoch >= 75, stoch60=stoch >= 60,
        rsi5070=50 <= rsi < 70, rsi4060=40 <= rsi < 60,
        bb80=bbpct >= 0.80,
        ich_tk=ich_tk, ich_price_tenkan=ich_price_tenkan,
        ich_price_kijun=ich_price_kijun, ich_cloud_above=ich_cloud_above,
        ich_cloud_green=ich_cloud_green, ich_chikou=ich_chikou,
        ich_kumo_break=ich_kumo_break,
        rci9_os=rci9_os, rci26_os=rci26_os, rci9_up=rci9_up,
        pre_down3=pre_down3, gap_up=gap_up, bb_lower=bb_lower, cci_os=cci_os,
        smbull_seq2=smbull_seq2, smbull_seq3=smbull_seq3,
        _vsurge=vsurge, _atr=atr_pct, _body=body_pct,
        _rsi=rsi, _stoch=stoch, _bbpct=bbpct,
        _rci9=rci9 if rci9 is not None else 0.0,
        _rci26=rci26 if rci26 is not None else 0.0,
        _cci=cci,
    )

def latest_close_for_signal(daily, sig_date):
    """シグナル日以降の最新終値を返す。未確定5日後成績の現在値代替に使う。"""
    if not daily:
        return None
    sig_dt = sig_date.replace("/", "-")[:10]
    if daily[-1]["date"] < sig_dt:
        return None
    latest = daily[-1].get("close")
    return latest if latest is not None and math.isfinite(latest) else None

def build_unconfirmed_current_df(alerts_all, ohlcv):
    """perf_5bd未確定のBOTTOMを、現在値ベースの暫定perfで評価可能なDataFrameにする。"""
    if alerts_all is None or alerts_all.empty or "confirmed_5bd" not in alerts_all.columns:
        return pd.DataFrame()

    pending = alerts_all[~alerts_all["confirmed_5bd"].astype(bool)].copy()
    rows = []
    for _, r in pending.iterrows():
        daily = ohlcv.get(r["symbol"], [])
        features = get_features(daily, r["date"])
        latest_close = latest_close_for_signal(daily, r["date"])
        entry = r.get("entry", float("nan"))
        if not features or latest_close is None or not math.isfinite(entry) or entry <= 0:
            continue

        perf = latest_close / entry - 1
        rows.append({
            **r.to_dict(),
            **features,
            "perf_5bd": perf,
            "win_5bd": perf > 0,
            "win10": perf >= WIN_THRESHOLD,
            "lose10": perf <= LOSE_THRESHOLD,
            "latest_close": latest_close,
        })
    return pd.DataFrame(rows)

# ══════════════════════════════════════════════════════════════
# 評価
# ══════════════════════════════════════════════════════════════
def calc_stats(df_s6):
    n = len(df_s6)
    if n == 0: return dict(n=0, wr=0, avg=0, win10=0, lose10=0,
                           wr_raw=0, avg_raw=0, win10_raw=0, lose10_raw=0,
                           composite=-9999)
    # 近接性加重: 直近シグナルを重視（古いデータの影響を指数減衰）
    today = pd.Timestamp.today()
    dates = pd.to_datetime(df_s6["date"], errors="coerce").fillna(today)
    days_old = (today - dates).dt.days.clip(lower=0)
    w = np.exp(-days_old / RECENCY_HALFLIFE)
    W = w.sum()
    wr  = float((df_s6["win_5bd"]  * w).sum() / W)
    avg = float((df_s6["perf_5bd"] * w).sum() / W)
    w10 = float((df_s6["win10"]    * w).sum())
    l10 = float((df_s6["lose10"]   * w).sum())
    # 非加重（実カウント）: 表示用
    wr_raw  = float(df_s6["win_5bd"].mean())
    avg_raw = float(df_s6["perf_5bd"].mean())
    win10_raw  = float(df_s6["win10"].sum())
    lose10_raw = float(df_s6["lose10"].sum())
    return dict(n=n, wr=wr, avg=avg, win10=w10, lose10=l10,
                wr_raw=wr_raw, avg_raw=avg_raw,
                win10_raw=win10_raw, lose10_raw=lose10_raw,
                composite=_calc_composite(wr, avg, w10, l10, W, n))

def _prepare_stats_arrays(df_eval):
    """組み合わせ探索用に、calc_stats相当の入力をNumPy配列へ変換する。"""
    today = pd.Timestamp.today()
    dates = pd.to_datetime(df_eval["date"], errors="coerce").fillna(today)
    days_old = (today - dates).dt.days.clip(lower=0).to_numpy(dtype=float)
    return {
        "w": np.exp(-days_old / RECENCY_HALFLIFE),
        "win": df_eval["win_5bd"].to_numpy(dtype=float),
        "perf": df_eval["perf_5bd"].to_numpy(dtype=float),
        "win10": df_eval["win10"].to_numpy(dtype=float),
        "lose10": df_eval["lose10"].to_numpy(dtype=float),
    }

def _calc_stats_mask(mask, arrays):
    """Boolean maskからcalc_stats()と同じ統計辞書を返す。"""
    mask = np.asarray(mask, dtype=bool)
    n = int(mask.sum())
    if n == 0:
        return dict(n=0, wr=0, avg=0, win10=0, lose10=0,
                    wr_raw=0, avg_raw=0, win10_raw=0, lose10_raw=0,
                    composite=-9999)
    w = arrays["w"][mask]
    W = float(w.sum())
    wr  = float((arrays["win"][mask]  * w).sum() / W) if W > 0 else 0
    avg = float((arrays["perf"][mask] * w).sum() / W) if W > 0 else 0
    w10 = float((arrays["win10"][mask]  * w).sum())
    l10 = float((arrays["lose10"][mask] * w).sum())
    wr_raw  = float(arrays["win"][mask].mean())
    avg_raw = float(arrays["perf"][mask].mean())
    win10_raw  = float(arrays["win10"][mask].sum())
    lose10_raw = float(arrays["lose10"][mask].sum())
    return dict(n=n, wr=wr, avg=avg, win10=w10, lose10=l10,
                wr_raw=wr_raw, avg_raw=avg_raw,
                win10_raw=win10_raw, lose10_raw=lose10_raw,
                composite=_calc_composite(wr, avg, w10, l10, W, n))

def _combo_all_mask(matrix, idxs):
    """6条件すべてを満たす行のmaskを返す。"""
    mask = matrix[:, idxs[0]].copy()
    for i in idxs[1:]:
        mask &= matrix[:, i]
    return mask

def _combo_score(matrix, idxs):
    return matrix[:, list(idxs)].sum(axis=1)

def calc_score_b_series(df, scheme):
    """Method BのスコアをSeriesで返す（表示用集計）。"""
    def score_row(row):
        return min(sum(int(bool(row[c])) * w for c, w, _ in scheme if c in row.index), 6)
    return df.apply(score_row, axis=1)

def calc_backtest_display_stats(df_eval, method, combo, thresholds=None):
    """通知や/helpに出すバックテスト結果を全件データで集計する。"""
    thresholds = thresholds or {}
    if df_eval is None or len(df_eval) == 0:
        empty = calc_stats(df_eval if df_eval is not None else pd.DataFrame())
        return empty, empty, empty, empty, 0

    if method == "A":
        scores = score_with_thresholds(df_eval, combo, thresholds)
    else:
        scores = calc_score_b_series(df_eval, combo)

    st6 = calc_stats(df_eval[scores == 6])
    st5 = calc_stats(df_eval[scores == 5])
    st4 = calc_stats(df_eval[scores == 4])
    base = calc_stats(df_eval)
    return st6, st5, st4, base, int(len(df_eval))

def calc_candidate_tiers(df_eval, method, combo, thresholds=None):
    """候補ロジックの★6/★5/★4を任意データセット上で集計する。"""
    thresholds = thresholds or {}
    if df_eval is None or len(df_eval) == 0:
        empty = calc_stats(pd.DataFrame())
        return empty, empty, empty

    if method == "A":
        scores = score_with_thresholds(df_eval, combo, thresholds)
    else:
        scores = calc_score_b_series(df_eval, combo)

    return (
        calc_stats(df_eval[scores == 6]),
        calc_stats(df_eval[scores == 5]),
        calc_stats(df_eval[scores == 4]),
    )

def calc_score_series_for_logic(df_eval, method, combo, thresholds=None):
    """任意ロジックのスコアSeriesを返す。"""
    thresholds = thresholds or {}
    if method == "A":
        return score_with_thresholds(df_eval, combo, thresholds)
    return calc_score_b_series(df_eval, combo)

def selected_signal_indices(df_eval, method, combo, thresholds=None, target_score=6):
    """指定スコアに該当するシグナル行indexの集合を返す。"""
    if df_eval is None or len(df_eval) == 0:
        return set()
    scores = calc_score_series_for_logic(df_eval, method, combo, thresholds)
    return set(df_eval.index[scores == target_score].tolist())

def all_pass_signal_indices(df_eval, conditions, thresholds=None):
    """Sniperなど、全条件通過が採用条件のシグナル行index集合を返す。"""
    conditions = conditions or []
    if not conditions:
        return set()
    return selected_signal_indices(
        df_eval, "A", conditions, thresholds or {}, target_score=len(conditions)
    )

def _normalize_thresholds_for_compare(thresholds=None):
    normalized = []
    for k, v in (thresholds or {}).items():
        try:
            v = float(v)
        except (TypeError, ValueError):
            v = str(v)
        normalized.append((str(k), v))
    return tuple(sorted(normalized))

def logic_signature(method, combo, thresholds=None):
    """条件順序差を無視して、同一ロジックか比較できる形に正規化する。"""
    if method == "A":
        return (
            "A",
            tuple(sorted(str(c) for c in combo)),
            _normalize_thresholds_for_compare(thresholds),
        )

    scheme = []
    for c, w, lift in combo:
        scheme.append((str(c), int(w), round(float(lift), 10)))
    return ("B", tuple(sorted(scheme)), ())

def _calc_composite(wr, avg, w10, l10, W, n):
    """composite スコア計算（COMPOSITE_VARIANT で切り替え）"""
    if COMPOSITE_VARIANT == "rate_adjusted":
        # 過学習抑制のため avg の影響を半減し勝率重視に変更
        # (avg×200 はアウトライヤー1件で10pt動くため過学習の温床)
        rate = (w10 / W - l10 / W) * 250 if W > 0 else 0
        return wr * 40 + avg * 100 + rate
    elif COMPOSITE_VARIANT == "snr":
        import math
        return wr * 50 + avg * 100 + (w10 - l10) / math.sqrt(max(n, 1)) * 15
    else:  # legacy
        return wr * 50 + avg * 100 + (w10 - l10) * 3

def _complexity_penalty(thresholds):
    """非デフォルト閾値の数 × 0.5 の過学習ペナルティ。
    6条件全部にカスタム閾値を当てるほど過学習しやすいため、
    同等composite ならシンプルな組み合わせを優先する（Occam's Razor）。"""
    if not thresholds:
        return 0.0
    return len(thresholds) * 0.5

def is_data_sufficient(df, df_wf_lockbox):
    """過学習抑制ゲート（Lockbox / Bootstrap CI / K-Fold）を意味のあるレベルで
    動作させるのに十分なデータがあるか判定する。

    不足時は「過渡期モード（transition）」で動作し、pre-Tier-A 水準の緩和ゲートに
    フォールバックする。
    - 統計手法は n が小さいと偽陽性/偽陰性を量産するため、厳格適用は逆効果。
    - archive 蓄積中（signals_archive 統合直後など）でも更新が止まらないようにする。
    """
    total_n   = len(df) if df is not None else 0
    lockbox_n = len(df_wf_lockbox) if df_wf_lockbox is not None else 0
    return (
        total_n   >= MIN_TOTAL_FOR_STRICT_MODE
        and lockbox_n >= MIN_LOCKBOX_FOR_STRICT_MODE
    )

def _quality_gate_lines(stats, validation_stats=None, mode="normal", data_mode="strict",
                        baseline_validation_stats=None):
    """Stable ★6の絶対品質ゲートを評価する。

    data_mode: "strict" (通常時、Tier A 強化済み水準) / "transition" (archive 蓄積中、pre-Tier-A 水準)
    baseline_validation_stats: 現行ロジックの検証★6統計。指定時は絶対件数ゲートを
        相対ゲート(現行比VALID_N_RATIO_FLOOR以上)に切り替える。"""
    validation_stats = validation_stats or calc_stats(pd.DataFrame())
    if data_mode == "transition":
        stable_s6_n_min = TRANSITION_RESCUE_STABLE_S6_N_MIN if mode == "rescue" else TRANSITION_STABLE_S6_N_MIN
    else:
        stable_s6_n_min = RESCUE_STABLE_S6_N_MIN if mode == "rescue" else STABLE_S6_N_MIN

    if baseline_validation_stats is not None:
        baseline_valid_n = max(int(baseline_validation_stats.get("n", 0)), 0)
        valid_n_min = max(MIN_VALID_N_FLOOR, math.ceil(baseline_valid_n * VALID_N_RATIO_FLOOR))
        valid_n_label = (f"≥ max({MIN_VALID_N_FLOOR}, 現行{baseline_valid_n}件"
                         f"×{VALID_N_RATIO_FLOOR}) = {valid_n_min}件")
    else:
        valid_n_min = TRANSITION_STABLE_VALID_S6_N_MIN if data_mode == "transition" else STABLE_VALID_S6_N_MIN
        valid_n_label = f"≥ {valid_n_min}件"

    checks = [
        (stats["n"] >= stable_s6_n_min,
         f"全件★6件数 {stats['n']}件 ≥ {stable_s6_n_min}件"),
        (stats["wr_raw"] >= STABLE_WR_MIN,
         f"全件★6勝率 {stats['wr_raw']*100:.1f}% ≥ {STABLE_WR_MIN*100:.0f}%"),
        (stats["avg_raw"] > STABLE_AVG_MIN,
         f"全件★6平均 {stats['avg_raw']*100:+.1f}% > {STABLE_AVG_MIN*100:+.0f}%"),
        (validation_stats["n"] >= valid_n_min,
         f"検証★6件数 {validation_stats['n']}件 {valid_n_label}"),
        (validation_stats["wr_raw"] > STABLE_VALID_WR_MIN,
         f"検証★6勝率 {validation_stats['wr_raw']*100:.1f}% > {STABLE_VALID_WR_MIN*100:.0f}%"),
        (validation_stats["avg_raw"] >= STABLE_VALID_AVG_MIN,
         f"検証★6平均 {validation_stats['avg_raw']*100:+.1f}% ≥ {STABLE_VALID_AVG_MIN*100:+.0f}%"),
    ]
    lines = [f"{'✓' if ok else '✗'} 品質: {label}" for ok, label in checks]
    return all(ok for ok, _ in checks), lines

# ══════════════════════════════════════════════════════════════
# 過学習抑制: Bootstrap CI / Lockbox / Permutation / K-Fold
# ══════════════════════════════════════════════════════════════

def bootstrap_wr_ci(df_s6, n_iter=1000, alpha=0.05, seed=42):
    """★6サンプルから Bootstrap して wr_raw の (1-alpha) CI を返す。
    サンプル不足（<5件）の場合は (0.0, 1.0) を返す。"""
    n = len(df_s6)
    if n < 5:
        return (0.0, 1.0)
    wins = df_s6["win_5bd"].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, (n_iter, n))
    sample_wrs = wins[idx].mean(axis=1)
    lo = float(np.percentile(sample_wrs, alpha * 50))
    hi = float(np.percentile(sample_wrs, 100 - alpha * 50))
    return (lo, hi)

def lockbox_gate_ok(lockbox_stats, baseline_lockbox_stats, adoption_mode="normal"):
    """Lockbox（真のOOS）での過度な劣化を検出する。
    現行ロジックの lockbox baseline より一定以上の勝率下落、
    または平均が床を下回るなら過学習と判断して不採用。

    勝率差ゲートは lockbox ★6件数に応じて階層的に変動する:
    - 30件以上: -5pt (データ十分、統計的有意差を要求)
    - 15-29件: -8pt (中位データ、適度な許容)
    - 8-14件:  -15pt (低位データ、ノイズ吸収)
    - 8件未満: 自動fail
    標準誤差が 1/sqrt(n) で増大することを踏まえた緩和。

    平均床は二段構え（通常モード）:
    - 絶対床 -2% と 現行lockbox平均-3pt の「緩い方」を採用
    - ベア相場で現行も赤字の局面では絶対床だけだと全候補が落ちるため

    adoption_mode="rescue" の場合は現行劣化中なのでさらに緩和:
    - 件数floor: 8→5件
    - 勝率gap: 階層に +5pt 追加許容
    - 平均: 絶対床なし、現行lockbox平均-5pt の相対比較のみ
    """
    is_rescue = (adoption_mode == "rescue")
    min_n = 5 if is_rescue else 8
    if lockbox_stats["n"] < min_n:
        return False, f"lockbox★6件数不足（<{min_n}件{'/rescue' if is_rescue else ''}）"

    n_cand = lockbox_stats["n"]
    if n_cand >= 30:
        wr_gap = 0.05    # 5pt
    elif n_cand >= 15:
        wr_gap = 0.08    # 8pt
    else:
        wr_gap = 0.15    # 15pt (低サンプル時はノイズ許容)
    if is_rescue:
        wr_gap += 0.05   # rescue時はさらに5pt許容

    base_wr = baseline_lockbox_stats.get("wr_raw", 0.0)
    if lockbox_stats["wr_raw"] < base_wr - wr_gap:
        return False, (
            f"lockbox勝率 {lockbox_stats['wr_raw']*100:.1f}% < "
            f"現行lockbox {base_wr*100:.1f}% - {wr_gap*100:.0f}pt "
            f"(n={n_cand}, 階層ゲート{'/rescue' if is_rescue else ''})"
        )

    base_avg = baseline_lockbox_stats.get("avg_raw", 0.0)
    if is_rescue:
        # rescue時は相対比較のみ: 現行lockbox平均 -5pt まで許容
        avg_floor = base_avg - 0.05
        if lockbox_stats["avg_raw"] < avg_floor:
            return False, (
                f"lockbox平均 {lockbox_stats['avg_raw']*100:+.1f}% < "
                f"現行{base_avg*100:+.1f}% − 5pt = {avg_floor*100:+.1f}% (rescue相対)"
            )
    else:
        # 通常時は絶対床-2%と相対床（現行-3pt）の緩い方
        avg_floor = min(-0.02, base_avg - 0.03)
        if lockbox_stats["avg_raw"] < avg_floor:
            return False, (
                f"lockbox平均 {lockbox_stats['avg_raw']*100:+.1f}% < "
                f"床{avg_floor*100:+.1f}% "
                f"(絶対-2% と 現行{base_avg*100:+.1f}%−3pt の緩い方)"
            )

    return True, (
        f"lockbox★6 {lockbox_stats['n']}件 "
        f"勝率{lockbox_stats['wr_raw']*100:.1f}% "
        f"平均{lockbox_stats['avg_raw']*100:+.1f}% "
        f"(gap許容=−{wr_gap*100:.0f}pt"
        f"{'/rescue相対' if is_rescue else ''})"
    )

def permutation_pvalue(df, method, combo, thresholds, observed_composite, n_perm=200, seed=42):
    """win/loss ラベルをランダムシャッフルして observed_composite 以上が出る確率を返す。
    p 値が低いほど偶然ではなく真のエッジがある可能性が高い。
    採用後の最終候補にのみ実行（計算コスト節約）。"""
    if len(df) < 10:
        return 1.0  # サンプル不足なら常に不採用方向
    base_wins = df["win_5bd"].to_numpy(dtype=float).copy()
    rng = np.random.default_rng(seed)
    better = 0
    df_perm = df.copy()
    for _ in range(n_perm):
        df_perm["win_5bd"] = rng.permutation(base_wins)
        try:
            st6 = calc_candidate_tiers(df_perm, method, combo, thresholds)[0]
            if st6["composite"] >= observed_composite:
                better += 1
        except Exception:
            pass
    df_perm["win_5bd"] = base_wins  # restore
    return better / n_perm

def time_series_kfold_passes(df, method, combo, thresholds, baseline_wr, k=3):
    """時系列K-Foldで候補が baseline_wr を超えるフォールド数を返す。
    特定期間に過剰適合している「局所過学習」候補を排除する。"""
    df_s = df.sort_values("date").reset_index(drop=True)
    n = len(df_s)
    if n < k * 5:
        return k  # サンプル不足なら全通過扱い（制限しない）
    fold_size = n // k
    wins = 0
    for i in range(k):
        start = i * fold_size
        end = (start + fold_size) if i < k - 1 else n
        df_test = df_s.iloc[start:end]
        try:
            st6 = calc_candidate_tiers(df_test, method, combo, thresholds)[0]
            if st6["n"] >= 5 and st6["wr_raw"] > baseline_wr:
                wins += 1
        except Exception:
            pass
    return wins

def detect_rescue_mode(current_stats, current_validation_stats):
    """現行Stable ★6が劣化している場合にrescue modeを起動する。"""
    reasons = []
    if current_stats["wr_raw"] < STABLE_WR_MIN:
        reasons.append(
            f"現行 全件★6勝率 {current_stats['wr_raw']*100:.1f}% < {STABLE_WR_MIN*100:.0f}%"
        )

    if current_validation_stats["n"] >= STABLE_VALID_S6_N_MIN:
        if current_validation_stats["wr_raw"] <= STABLE_VALID_WR_MIN:
            reasons.append(
                f"現行 検証★6勝率 {current_validation_stats['wr_raw']*100:.1f}% <= {STABLE_VALID_WR_MIN*100:.0f}%"
            )
        if current_validation_stats["avg_raw"] < STABLE_VALID_AVG_MIN:
            reasons.append(
                f"現行 検証★6平均 {current_validation_stats['avg_raw']*100:+.1f}% < {STABLE_VALID_AVG_MIN*100:+.0f}%"
            )
    return bool(reasons), reasons

def _jst_today_key():
    return (datetime.now(timezone.utc) + timedelta(hours=9)).date().isoformat()

def _utc_now_z():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _previous_date_key(date_key):
    try:
        return (datetime.fromisoformat(date_key).date() - timedelta(days=1)).isoformat()
    except (TypeError, ValueError):
        return None

def load_rescue_state():
    if not os.path.exists(RESCUE_STATE_PATH):
        return {}
    try:
        with open(RESCUE_STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"  ⚠ rescue_state.json 読み込みエラー: {e}")
        return {}

def _jsonable_stats(stats):
    return {
        k: int(v) if k == "n" else float(v)
        for k, v in (stats or {}).items()
        if isinstance(v, (int, float, np.integer, np.floating))
    }

def save_rescue_state(state):
    try:
        with open(RESCUE_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        print("  ✅ rescue_state.json 更新完了")
    except Exception as e:
        print(f"  ⚠ rescue_state.json 保存エラー: {e}")

def rescue_projection_wait_reasons(unconfirmed_stats, projected_stats):
    """未確定の現在値を加味した投影が回復を示すならrescueを待機する。"""
    if (unconfirmed_stats or {}).get("n", 0) < RESCUE_CURRENT_S6_N_MIN:
        return []

    projected_ok = (
        projected_stats["n"] >= STABLE_S6_N_MIN
        and projected_stats["wr_raw"] >= STABLE_WR_MIN
        and projected_stats["avg_raw"] > STABLE_AVG_MIN
    )
    if not projected_ok:
        return []

    return [
        (
            f"未確定★6（現在値）{unconfirmed_stats['n']}件: "
            f"勝率{unconfirmed_stats['wr_raw']*100:.1f}% "
            f"平均{unconfirmed_stats['avg_raw']*100:+.1f}%"
        ),
        (
            f"確定済み+未確定現在値の★6投影: {projected_stats['n']}件 "
            f"勝率{projected_stats['wr_raw']*100:.1f}% "
            f"平均{projected_stats['avg_raw']*100:+.1f}% "
            f"（通常ライン 勝率{STABLE_WR_MIN*100:.0f}% / 平均{STABLE_AVG_MIN*100:+.0f}% を回復）"
        ),
    ]

def resolve_rescue_mode(raw_reasons, current_stats, current_validation_stats,
                        unconfirmed_current_stats, projected_current_stats,
                        persist_state=False):
    """回復投影と連続日数を加味して、最終的にrescueを使うか決める。"""
    raw_reasons = raw_reasons or []
    today_key = _jst_today_key()
    state = load_rescue_state()
    # Sniperレスキュー状態は独立管理。Stable側で state を再構築する際に
    # 上書きされないよう、ここで保持して各分岐で書き戻す。
    sniper_carry = state.get("sniper") if isinstance(state, dict) else None
    wait_reasons = rescue_projection_wait_reasons(
        unconfirmed_current_stats, projected_current_stats
    )

    if not raw_reasons:
        new_state = {
            "updated_at": _utc_now_z(),
            "last_checked_date": today_key,
            "status": "healthy",
            "streak": 0,
            "current_stats6": _jsonable_stats(current_stats),
            "current_validation_stats6": _jsonable_stats(current_validation_stats),
            "unconfirmed_current_stats6": _jsonable_stats(unconfirmed_current_stats),
            "projected_current_stats6": _jsonable_stats(projected_current_stats),
        }
        if sniper_carry is not None:
            new_state["sniper"] = sniper_carry
        if persist_state:
            save_rescue_state(new_state)
        return False, [], 0

    if wait_reasons:
        reasons = [
            *raw_reasons,
            "未確定分の現在値が回復を示しているため、rescue更新は今回スルー",
            *wait_reasons,
        ]
        new_state = {
            "updated_at": _utc_now_z(),
            "last_checked_date": today_key,
            "status": "deferred_by_current_projection",
            "streak": 0,
            "raw_rescue_reasons": raw_reasons,
            "defer_reasons": wait_reasons,
            "current_stats6": _jsonable_stats(current_stats),
            "current_validation_stats6": _jsonable_stats(current_validation_stats),
            "unconfirmed_current_stats6": _jsonable_stats(unconfirmed_current_stats),
            "projected_current_stats6": _jsonable_stats(projected_current_stats),
        }
        if sniper_carry is not None:
            new_state["sniper"] = sniper_carry
        if persist_state:
            save_rescue_state(new_state)
        return False, reasons, 0

    last_breach_date = state.get("last_breach_date")
    prev_key = _previous_date_key(today_key)
    if last_breach_date == today_key:
        streak = max(1, int(state.get("streak", 1) or 1))
    elif last_breach_date == prev_key:
        streak = int(state.get("streak", 0) or 0) + 1
    else:
        streak = 1

    new_state = {
        "updated_at": _utc_now_z(),
        "last_checked_date": today_key,
        "last_breach_date": today_key,
        "status": "rescue_active" if streak >= RESCUE_REQUIRED_STREAK else "breach_observed",
        "streak": streak,
        "raw_rescue_reasons": raw_reasons,
        "current_stats6": _jsonable_stats(current_stats),
        "current_validation_stats6": _jsonable_stats(current_validation_stats),
        "unconfirmed_current_stats6": _jsonable_stats(unconfirmed_current_stats),
        "projected_current_stats6": _jsonable_stats(projected_current_stats),
    }
    if sniper_carry is not None:
        new_state["sniper"] = sniper_carry
    if persist_state:
        save_rescue_state(new_state)

    if streak < RESCUE_REQUIRED_STREAK:
        reasons = [
            *raw_reasons,
            (
                f"rescue対象 {streak}/{RESCUE_REQUIRED_STREAK}日目のため、"
                "今回はnormal判定で様子見"
            ),
        ]
        return False, reasons, streak

    reasons = [
        *raw_reasons,
        f"rescue対象が{streak}日連続のためrescue modeを使用",
    ]
    return True, reasons, streak

def detect_rescue_mode_sniper(refreshed_stats, live_stats):
    """現行Sniper★6が劣化している場合にrescue modeを起動する。
    refreshed_stats: df全体（alerts_raw + signals_archive）での現行条件の統計
    live_stats     : 採用日以降のライブ実績
    どちらかが SNIPER_RESCUE_TRIGGER_WR を下回れば breach 扱い。
    ライブ件数が SNIPER_RESCUE_TRIGGER_N 未満ならライブ単独では breach 判定しない。"""
    reasons = []
    if refreshed_stats and refreshed_stats.get("n", 0) >= SNIPER_N_MIN:
        if refreshed_stats["wr_raw"] < SNIPER_RESCUE_TRIGGER_WR:
            reasons.append(
                f"現行 全件★6勝率 {refreshed_stats['wr_raw']*100:.1f}% "
                f"< {SNIPER_RESCUE_TRIGGER_WR*100:.0f}% "
                f"(n={int(refreshed_stats['n'])})"
            )
    if live_stats and live_stats.get("n", 0) >= SNIPER_RESCUE_TRIGGER_N:
        if live_stats["wr_raw"] < SNIPER_RESCUE_TRIGGER_WR:
            reasons.append(
                f"採用後ライブ★6勝率 {live_stats['wr_raw']*100:.1f}% "
                f"< {SNIPER_RESCUE_TRIGGER_WR*100:.0f}% "
                f"(n={int(live_stats['n'])})"
            )
    return bool(reasons), reasons

def resolve_sniper_rescue_mode(raw_reasons, refreshed_stats, live_stats, persist_state=False):
    """連続日数を加味してSniperのrescue mode利用可否を決める。
    rescue_state.json の "sniper" キー配下に状態を保存する（Stable側とは独立）。"""
    raw_reasons = raw_reasons or []
    today_key = _jst_today_key()
    prev_key = _previous_date_key(today_key)
    state = load_rescue_state()
    sniper_state = state.get("sniper") if isinstance(state, dict) else None
    sniper_state = sniper_state if isinstance(sniper_state, dict) else {}

    if not raw_reasons:
        new_sniper_state = {
            "updated_at": _utc_now_z(),
            "last_checked_date": today_key,
            "status": "healthy",
            "streak": 0,
            "raw_rescue_reasons": [],
            "refreshed_stats": _jsonable_stats(refreshed_stats or {}),
            "live_stats": _jsonable_stats(live_stats or {}),
        }
        state["sniper"] = new_sniper_state
        if persist_state:
            save_rescue_state(state)
        return False, [], 0

    last_breach_date = sniper_state.get("last_breach_date")
    if last_breach_date == today_key:
        streak = max(1, int(sniper_state.get("streak", 1) or 1))
    elif last_breach_date == prev_key:
        streak = int(sniper_state.get("streak", 0) or 0) + 1
    else:
        streak = 1

    new_sniper_state = {
        "updated_at": _utc_now_z(),
        "last_checked_date": today_key,
        "last_breach_date": today_key,
        "status": "rescue_active" if streak >= RESCUE_REQUIRED_STREAK else "breach_observed",
        "streak": streak,
        "raw_rescue_reasons": raw_reasons,
        "refreshed_stats": _jsonable_stats(refreshed_stats or {}),
        "live_stats": _jsonable_stats(live_stats or {}),
    }
    state["sniper"] = new_sniper_state
    if persist_state:
        save_rescue_state(state)

    if streak < RESCUE_REQUIRED_STREAK:
        reasons = [
            *raw_reasons,
            (
                f"Sniper rescue対象 {streak}/{RESCUE_REQUIRED_STREAK}日目のため、"
                "今回はnormal判定で様子見"
            ),
        ]
        return False, reasons, streak

    reasons = [
        *raw_reasons,
        f"Sniper rescue対象が{streak}日連続のためrescue modeを使用",
    ]
    return True, reasons, streak

def is_current_healthy(stats, validation_stats):
    """現行ロジックが更新不要な水準かどうかを判定する。
    勝率・平均・件数・検証平均の4条件をすべて満たせばTrue。"""
    return (
        stats["n"] >= HEALTHY_SKIP_N_MIN
        and stats["wr_raw"] >= HEALTHY_SKIP_WR
        and stats["avg_raw"] >= HEALTHY_SKIP_AVG
        and validation_stats["avg_raw"] >= 0.0
    )

def validation_gate_ok(validation_stats, data_mode="strict", baseline_validation_stats=None):
    if baseline_validation_stats is not None:
        baseline_n = max(int(baseline_validation_stats.get("n", 0)), 0)
        valid_n_min = max(MIN_VALID_N_FLOOR, math.ceil(baseline_n * VALID_N_RATIO_FLOOR))
    else:
        valid_n_min = (TRANSITION_STABLE_VALID_S6_N_MIN
                       if data_mode == "transition" else STABLE_VALID_S6_N_MIN)
    return (
        validation_stats["n"] >= valid_n_min
        and validation_stats["wr_raw"] > STABLE_VALID_WR_MIN
        and validation_stats["avg_raw"] >= STABLE_VALID_AVG_MIN
    )

def win10_rate(stats):
    n = stats.get("n", 0) or 0
    return (stats.get("win10_raw", 0) or 0) / n if n > 0 else 0

def win10_guard_details(stats, baseline):
    cand_rate = win10_rate(stats)
    base_rate = win10_rate(baseline)
    rate_floor = base_rate * WIN10_RATE_FLOOR_RATIO
    ok_count = stats["win10_raw"] >= WIN10_MIN_COUNT
    ok_rate = cand_rate >= rate_floor
    return ok_count, ok_rate, cand_rate, base_rate, rate_floor

def win10_guard_ok(stats, baseline):
    ok_count, ok_rate, _, _, _ = win10_guard_details(stats, baseline)
    return ok_count and ok_rate

def check_criteria(stats, baseline, validation_stats=None, mode="normal", thresholds=None,
                   data_mode="strict", baseline_validation_stats=None):
    validation_stats = validation_stats or calc_stats(pd.DataFrame())
    quality_ok, quality_lines = _quality_gate_lines(stats, validation_stats, mode, data_mode,
                                                     baseline_validation_stats=baseline_validation_stats)

    # 複雑さペナルティ: 非デフォルト閾値を多用した候補は composite を減点して評価
    penalty = _complexity_penalty(thresholds)
    adj_composite = stats["composite"] - penalty

    threshold = baseline["composite"] * BASELINE_DECAY
    ok_comp = adj_composite > threshold
    # 絶対条件②: 勝率（strict時は等号排除、floor追加）
    ok_wr = (stats["wr_raw"] > baseline["wr_raw"]) if STRICT_WR else (stats["wr_raw"] >= baseline["wr_raw"])
    ok_wr_floor = stats["wr_raw"] >= WR_FLOOR
    # 絶対条件③: ★6内の大幅上昇は「最低件数」と「現行比率」を両方見る
    ok_win10_count, ok_win10_rate, cand_win10_rate, base_win10_rate, win10_rate_floor = \
        win10_guard_details(stats, baseline)
    relative_ok = ok_comp and ok_wr and ok_wr_floor and ok_win10_count and ok_win10_rate
    ok = quality_ok and (relative_ok if mode == "normal" else True)
    op_wr = ">" if STRICT_WR else "≥"
    penalty_str = f" - penalty{penalty:.1f}" if penalty > 0 else ""
    res = [
        f"{'✓' if ok_comp else '✗'} 通常条件①: composite {stats['composite']:.1f}{penalty_str}={adj_composite:.1f} {'>' if ok_comp else '≤'} 現行{baseline['composite']:.1f}×{BASELINE_DECAY}={threshold:.1f}",
        f"{'✓' if ok_wr else '✗'} 通常条件②: 勝率 {stats['wr_raw']*100:.1f}% {op_wr} 現行{baseline['wr_raw']*100:.1f}%",
        f"{'✓' if ok_wr_floor else '✗'} 通常条件②-b: 勝率 {stats['wr_raw']*100:.1f}% ≥ 下限{WR_FLOOR*100:.0f}%",
        f"{'✓' if ok_win10_count else '✗'} 通常条件③-a: 大幅上昇 {stats['win10_raw']:.0f}件 ≥ 最低{WIN10_MIN_COUNT}件",
        f"{'✓' if ok_win10_rate else '✗'} 通常条件③-b: 大幅上昇率 {cand_win10_rate*100:.1f}% ≥ 現行{base_win10_rate*100:.1f}%×{WIN10_RATE_FLOOR_RATIO:.2f}={win10_rate_floor*100:.1f}%",
        f"{'✓' if mode == 'rescue' else ' '} rescue mode: {'現行超え条件を免除' if mode == 'rescue' else '未使用'}",
        *quality_lines,
        f"{'✓' if stats['wr_raw']>=TARGET_WIN_RATE else '△'} 努力①勝率 {stats['wr_raw']*100:.1f}% (≥55%)",
        f"{'✓' if stats['avg_raw']>=TARGET_AVG_PERF else '△'} 努力②平均 {stats['avg_raw']*100:.1f}% (>+3%)",
        f"{'✓' if stats['win10_raw']>stats['lose10_raw'] else '△'} 努力③上昇{stats['win10_raw']:.0f}件>下落{stats['lose10_raw']:.0f}件",
    ]
    adoption_reasons = []
    if mode == "rescue":
        adoption_reasons.append("rescue: 現行劣化のため現行超え条件を免除")
    else:
        adoption_reasons.append("normal: 現行composite・勝率・大幅上昇率ガードを通過")
    adoption_reasons.append("Stable品質ゲートを通過")
    adoption_reasons.append("直近30% walk-forward検証を通過")
    return ok, res, adoption_reasons

# ══════════════════════════════════════════════════════════════
# 方式A: C(N,6) 組み合わせ探索
# ══════════════════════════════════════════════════════════════
BOOL_CONDS = [
    "ema75","ema25","vol20","vol15","vol12","vol30","sbull","body1","body2",
    "macdgc","macdpos","atr5","atr3","atr7","hb20","lower_wick50","pre_decline15",
    "stoch75","stoch60","rsi5070","rsi4060","bb80",
    "ich_tk","ich_price_tenkan","ich_price_kijun","ich_cloud_above",
    "ich_cloud_green","ich_chikou","ich_kumo_break",
    "rci9_os","rci26_os","rci9_up","pre_down3","gap_up","bb_lower","cci_os",
    "smbull_seq2","smbull_seq3",
]

# ── Stage 2: 閾値パラメーター定義 ────────────────────────────
# 条件名 → (連続値列, デフォルト閾値, 方向)
COND_PARAM = {
    "vol20":   ("_vsurge", 2.00, ">="),
    "vol15":   ("_vsurge", 1.50, ">="),
    "vol12":   ("_vsurge", 1.20, ">="),
    "sbull":   ("_body",   0.50, ">="),
    "body1":   ("_body",   1.00, ">="),
    "atr5":    ("_atr",    5.00, "<"),
    "atr3":    ("_atr",    3.00, "<"),
    "atr7":    ("_atr",    7.00, "<"),
    "stoch75": ("_stoch",  75.0, ">="),
    "stoch60": ("_stoch",  60.0, ">="),
    "bb80":    ("_bbpct",  0.80, ">="),
    "rci9_os":  ("_rci9",   -50.0, "<="),
    "rci26_os": ("_rci26",  -50.0, "<="),
    "cci_os":   ("_cci",   -100.0, "<="),
}

# 連続値列 → 閾値候補
PARAM_CANDIDATES = {
    "_vsurge": [1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0],
    "_body":   [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0],
    "_atr":    [2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
    "_stoch":  [40, 45, 50, 55, 60, 65, 70, 75, 80, 85],
    "_bbpct":  [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95],
    "_rci9":   [-80, -70, -60, -50, -40, -30, -20, -10, 0],
    "_rci26":  [-80, -70, -60, -50, -40, -30, -20, -10, 0],
    "_cci":    [-200, -150, -100, -50, 0],
}

# JS生成テンプレート (raw_col → (desc_fn, cond_fn, label_fn))
PARAM_JS_TPL = {
    "_vsurge": (
        lambda t: f"当日出来高≥20日×{t:.2f}",
        lambda t: f"ind.volSurge >= {t:.2f}",
        lambda t: "vol急増(${ind.volSurge}x)",
    ),
    "_body": (
        lambda t: f"強い陽線（実体≥{t:.2f}%）",
        lambda t: f"ind.bodyPct >= {t:.2f}",
        lambda t: "強陽線(${ind.bodyPct.toFixed(2)}%)",
    ),
    "_atr": (
        lambda t: f"ATR% < {t:.1f}%",
        lambda t: f"ind.atrPct < {t:.1f}",
        lambda t: "ATR(${ind.atrPct}%)",
    ),
    "_stoch": (
        lambda t: f"ストキャス≥{t:.0f}",
        lambda t: f"ind.stochK >= {t:.0f}",
        lambda t: "STOCH(${ind.stochK.toFixed(0)})",
    ),
    "_bbpct": (
        lambda t: f"BB位置≥{t*100:.0f}%",
        lambda t: f"ind.bbPct >= {t:.2f}",
        lambda t: "BB上部(${(ind.bbPct*100).toFixed(0)}%)",
    ),
    "_rci9": (
        lambda t: f"RCI(9) ≤ {t:.0f}",
        lambda t: f"ind.rci9 !== null && ind.rci9 <= {t:.0f}",
        lambda t: "RCI9(${ind.rci9 !== null ? ind.rci9.toFixed(0) : 'N/A'})",
    ),
    "_rci26": (
        lambda t: f"RCI(26) ≤ {t:.0f}",
        lambda t: f"ind.rci26 !== null && ind.rci26 <= {t:.0f}",
        lambda t: "RCI26(${ind.rci26 !== null ? ind.rci26.toFixed(0) : 'N/A'})",
    ),
    "_cci": (
        lambda t: f"CCI(14) ≤ {t:.0f}",
        lambda t: f"ind.cciVal <= {t:.0f}",
        lambda t: "CCI(${ind.cciVal.toFixed(0)})",
    ),
}

def score_with_thresholds(df, combo, thresholds):
    """comboの条件でスコア列を計算（パラメーター化条件には thresholds の値を使用）"""
    scores = pd.Series(0, index=df.index)
    for c in combo:
        if c in thresholds and c in COND_PARAM:
            raw_col, _, direction = COND_PARAM[c]
            th = thresholds[c]
            if direction == ">=":
                scores += (df[raw_col] >= th).astype(int)
            elif direction == "<=":
                scores += (df[raw_col] <= th).astype(int)
            else:
                scores += (df[raw_col] < th).astype(int)
        elif c in df.columns:
            scores += df[c].astype(int)
    return scores

def calc_ordering_score(st6, st5, st4):
    """
    ★6 > ★5 > ★4 の順序スコアを返す
      2: 勝率も平均騰落率も ★6 > ★5 > ★4 （最良）
      1: 勝率のみ ★6 > ★5 > ★4
      0.5: 勝率が ★6 > ★5 または ★5 > ★4 の片方だけ成立
      0: 順序なし
    """
    wr6, wr5, wr4 = st6["wr"], st5["wr"], st4["wr"]
    av6, av5, av4 = st6["avg"], st5["avg"], st4["avg"]
    wr_full = wr6 > wr5 > wr4
    av_full = av6 > av5 > av4
    if wr_full and av_full: return 2
    if wr_full:              return 1
    # 部分的な順序（片方だけ成立）
    partial = (1 if wr6 > wr5 else 0) + (1 if wr5 > wr4 else 0)
    return partial * 0.25

def ordering_label(st6, st5, st4):
    """表示用ラベル"""
    sc = calc_ordering_score(st6, st5, st4)
    if sc == 2:   return "✓ 勝率＆平均 ★6>★5>★4"
    if sc == 1:   return "✓ 勝率のみ  ★6>★5>★4"
    if sc >= 0.5: return "△ 部分的に順序あり"
    return         "✗ 順序なし"

def search_combinations(df, baseline, mode="normal"):
    conds = [c for c in BOOL_CONDS if c in df.columns]
    for c in conds: df[c] = df[c].astype(bool)
    total = sum(1 for _ in combinations(conds, 6))
    print(f"  探索数: C({len(conds)},6) = {total:,}通り")
    matrix = df[conds].to_numpy(dtype=np.bool_)
    arrays = _prepare_stats_arrays(df)
    best = []
    for idxs in combinations(range(len(conds)), 6):
        s6_mask = _combo_all_mask(matrix, idxs)
        if int(s6_mask.sum()) < 10: continue
        st6 = _calc_stats_mask(s6_mask, arrays)
        if mode == "normal":
            if st6["composite"] <= baseline["composite"] * BASELINE_DECAY: continue
            # 勝率フロア（strict時は等号排除）
            wr_ok = (st6["wr_raw"] > baseline["wr_raw"]) if STRICT_WR else (st6["wr_raw"] >= baseline["wr_raw"])
            if not wr_ok: continue
            if st6["wr_raw"] < WR_FLOOR: continue
            if not win10_guard_ok(st6, baseline): continue
        else:
            # rescue modeでは現行超え条件を緩め、後段の全件/検証品質ゲートで絞る。
            if st6["wr_raw"] < TARGET_WIN_RATE: continue
        # ★5/★4 もタイブレーカー用に計算（各ランク単独・悪化してもOK）
        scores = _combo_score(matrix, idxs)
        st5 = _calc_stats_mask(scores == 5, arrays)
        st4 = _calc_stats_mask(scores == 4, arrays)
        combo = [conds[i] for i in idxs]
        best.append((st6["composite"], st5["composite"], st4["composite"],
                     combo, st6, st5, st4))
    best.sort(key=lambda x: (x[0], x[1], x[2], x[3]), reverse=True)
    return best

def search_combinations_sniper(df, wr_floor=None):
    """Sniperモード: 勝率最大化の組み合わせ探索 (C(N,6), 全条件通過)。
    wr_floor を指定するとそれを採用最低勝率として使う（rescue時 = SNIPER_RESCUE_WR_MIN）。"""
    if wr_floor is None:
        wr_floor = SNIPER_WR_MIN
    conds = [c for c in BOOL_CONDS if c in df.columns]
    for c in conds:
        df[c] = df[c].astype(bool)
    total = sum(1 for _ in combinations(conds, 6))
    print(f"  探索数: C({len(conds)},6) = {total:,}通り (最低勝率 {wr_floor*100:.0f}%)")
    matrix = df[conds].to_numpy(dtype=np.bool_)
    arrays = _prepare_stats_arrays(df)
    best = []
    for idxs in combinations(range(len(conds)), 6):
        s6_mask = _combo_all_mask(matrix, idxs)
        if int(s6_mask.sum()) < SNIPER_N_MIN:
            continue
        st6 = _calc_stats_mask(s6_mask, arrays)
        if st6["wr_raw"] < wr_floor:
            continue
        combo = [conds[i] for i in idxs]
        best.append((st6["wr_raw"], st6["n"], list(combo), st6))
    best.sort(key=lambda x: (-x[0], -x[1]))  # 勝率降順・件数降順
    return best

def search_combinations_moonshot(df, perf_col):
    """Moonshotモード: 平均リターン最大化の組み合わせ探索 (C(N,6), 全条件通過)。
    perf_col は perf_10bd / perf_20bd / perf_40bd のいずれか。
    perf_col が NaN の行は探索対象から除外する（評価日未確定）。"""
    if perf_col not in df.columns:
        return []
    df_eval = df.dropna(subset=[perf_col]).copy()
    if df_eval.empty:
        return []
    conds = [c for c in BOOL_CONDS if c in df_eval.columns]
    for c in conds:
        df_eval[c] = df_eval[c].astype(bool)
    total = sum(1 for _ in combinations(conds, 6))
    print(f"  探索数: C({len(conds)},6) = {total:,}通り (perf={perf_col}, 対象{len(df_eval)}件)")
    matrix = df_eval[conds].to_numpy(dtype=np.bool_)
    perf_arr = df_eval[perf_col].to_numpy(dtype=float)
    win_arr  = (perf_arr > 0).astype(float)
    best = []
    for idxs in combinations(range(len(conds)), 6):
        s6_mask = _combo_all_mask(matrix, idxs)
        n_hit = int(s6_mask.sum())
        if n_hit < MOONSHOT_N_MIN:
            continue
        avg_raw = float(perf_arr[s6_mask].mean())
        if avg_raw < MOONSHOT_AVG_MIN:
            continue
        wr_raw = float(win_arr[s6_mask].mean())
        combo = [conds[i] for i in idxs]
        best.append((avg_raw, n_hit, list(combo),
                     {"n": n_hit, "avg_raw": avg_raw, "wr_raw": wr_raw}))
    best.sort(key=lambda x: (-x[0], -x[1]))  # 平均降順・件数降順
    return best, df_eval

# ══════════════════════════════════════════════════════════════
# 方式B: +10%銘柄共通点分析 → 重み付きスコア自動設計
# ══════════════════════════════════════════════════════════════
def analyze_winners(df, baseline, mode="normal"):
    winners = df[df["win10"] == True]
    n_all = len(df); n_win = len(winners)
    if n_win < 5:
        print(f"  +{WIN_THRESHOLD*100:.0f}%銘柄5件未満のためスキップ"); return None
    print(f"  +{WIN_THRESHOLD*100:.0f}%以上: {n_win}件 / 全体: {n_all}件 ({n_win/n_all*100:.1f}%)")

    conds = [c for c in BOOL_CONDS if c in df.columns]
    lifts = []
    for c in conds:
        ra = df[c].astype(bool).mean()
        rw = winners[c].astype(bool).mean()
        lift = rw / ra if ra > 0 else 1.0
        lifts.append((lift, c, rw, ra))
    lifts.sort(reverse=True)

    print(f"\n  【+{WIN_THRESHOLD*100:.0f}%銘柄への識別力（リフト値上位10）】")
    print(f"  {'指標':<12} {'リフト':>6}  {'winner率':>8}  {'全体率':>8}")
    for lift, c, rw, ra in lifts[:10]:
        print(f"  {c:<12} {lift:>6.2f}   {rw*100:>6.1f}%    {ra*100:>6.1f}%")

    scheme = []
    remaining = 6
    for lift, c, rw, ra in lifts:
        if remaining <= 0: break
        if lift >= 2.0 and remaining >= 2:
            scheme.append((c, 2, f"{lift:.2f}x")); remaining -= 2
        elif lift >= 1.3 and remaining >= 1:
            scheme.append((c, 1, f"{lift:.2f}x")); remaining -= 1

    if scheme and remaining > 0:
        c0, w0, l0 = scheme[0]
        if w0 < 2: scheme[0] = (c0, min(2, w0+remaining), l0)

    if not scheme: return None

    def score_row(row):
        return min(sum(int(bool(row[c]))*w for c,w,_ in scheme if c in row.index), 6)

    df["score_b"] = df.apply(score_row, axis=1)
    s6 = df[df["score_b"] == 6]
    if len(s6) < 10: print("  方式B: ★6件数不足"); return None

    st6 = calc_stats(s6)
    wr_ok = (st6["wr_raw"] > baseline["wr_raw"]) if STRICT_WR else (st6["wr_raw"] >= baseline["wr_raw"])
    relative_ok = (
        st6["composite"] > baseline["composite"] * BASELINE_DECAY
        and wr_ok
        and st6["wr_raw"] >= WR_FLOOR
        and win10_guard_ok(st6, baseline)
    )
    rescue_ok = st6["wr_raw"] >= TARGET_WIN_RATE
    ok = relative_ok if mode == "normal" else rescue_ok
    st5 = calc_stats(df[df["score_b"] == 5])
    st4 = calc_stats(df[df["score_b"] == 4])
    print(f"  方式B ★6: {st6['n']}件 勝率{st6['wr_raw']*100:.1f}% 平均{st6['avg_raw']*100:.1f}%"
          f" 上昇{st6['win10_raw']:.0f} 下落{st6['lose10_raw']:.0f} → {'✓候補OK' if ok else '✗候補NG'}")
    return (scheme, st6, st5, st4) if ok else None

# ══════════════════════════════════════════════════════════════
# Stage 2: 閾値最適化
# ══════════════════════════════════════════════════════════════
def tune_thresholds(df_train, df_test, combo, baseline, data_mode="strict",
                    baseline_validation_stats=None):
    """
    Stage 2: 選ばれた6条件の閾値をグリッドサーチで最適化し、
    テストデータ（直近20%）で検証する。
    Returns: (best_thresholds, train_stats, test_stats, passed)
    """
    from itertools import product as iproduct

    paramable = [c for c in combo if c in COND_PARAM]
    if not paramable:
        s = score_with_thresholds(df_train, combo, {})
        return {}, calc_stats(df_train[s == 6]), None, False

    print(f"\n🔬 Step 5c: 閾値最適化（Stage 2）...")
    print(f"  パラメーター化対象: {paramable}")

    param_list = [(c, PARAM_CANDIDATES[COND_PARAM[c][0]]) for c in paramable]
    total = 1
    for _, cands in param_list:
        total *= len(cands)
    print(f"  探索数: {total:,}通り")

    best_composite = -9999
    best_thresholds = {}
    best_train_stats = None

    if total <= 200_000:
        # フルグリッドサーチ
        for vals in iproduct(*[cands for _, cands in param_list]):
            thresholds = {c: v for (c, _), v in zip(param_list, vals)}
            s = score_with_thresholds(df_train, combo, thresholds)
            s6 = df_train[s == 6]
            if len(s6) < 10: continue
            st = calc_stats(s6)
            if st["composite"] > best_composite:
                best_composite = st["composite"]
                best_thresholds = thresholds.copy()
                best_train_stats = st
    else:
        # 独立最適化（条件ごとに個別スキャン）
        print(f"  組み合わせ数超過 → 独立最適化に切り替え")
        cur_thresholds = {}
        for c, cands in param_list:
            best_c_th = COND_PARAM[c][1]
            best_c_comp = -9999
            for th in cands:
                t = dict(cur_thresholds, **{c: th})
                s = score_with_thresholds(df_train, combo, t)
                s6 = df_train[s == 6]
                if len(s6) < 10: continue
                st = calc_stats(s6)
                if st["composite"] > best_c_comp:
                    best_c_comp = st["composite"]
                    best_c_th = th
            cur_thresholds[c] = best_c_th
        best_thresholds = cur_thresholds
        s = score_with_thresholds(df_train, combo, best_thresholds)
        best_train_stats = calc_stats(df_train[s == 6])

    if not best_thresholds or best_train_stats is None:
        print("  閾値最適化: 改善なし（デフォルト閾値を使用）")
        return {}, calc_stats(df_train[score_with_thresholds(df_train, combo, {}) == 6]), None, False

    # テストデータで検証
    passed = False
    test_stats = None
    if df_test is not None and len(df_test) >= 10:
        s_test = score_with_thresholds(df_test, combo, best_thresholds)
        test_stats = calc_stats(df_test[s_test == 6])
        # 現行閾値（最適化前）でテストセットを評価してベースラインとする
        s_test_cur = score_with_thresholds(df_test, combo, {})
        test_cur_stats = calc_stats(df_test[s_test_cur == 6])
        passed = (
            validation_gate_ok(test_stats, data_mode=data_mode,
                               baseline_validation_stats=baseline_validation_stats)
            and test_stats["composite"] > test_cur_stats["composite"]
        )
        result_str = "✅ 通過" if passed else "⚠ 不合格（デフォルト閾値を使用）"
        print(f"  訓練★6: {best_train_stats['n']}件 勝率{best_train_stats['wr_raw']*100:.1f}% 平均{best_train_stats['avg_raw']*100:.1f}%")
        if test_cur_stats["n"] > 0:
            print(f"  検証現行★6: {test_cur_stats['n']}件 勝率{test_cur_stats['wr_raw']*100:.1f}% 平均{test_cur_stats['avg_raw']*100:.1f}%")
        if test_stats["n"] > 0:
            print(f"  検証最適化★6: {test_stats['n']}件 勝率{test_stats['wr_raw']*100:.1f}% 平均{test_stats['avg_raw']*100:.1f}%")
        print(f"  検証結果: {result_str}")
        if passed:
            for c, th in best_thresholds.items():
                default_th = COND_PARAM[c][1]
                tag = " ← 変更" if abs(th - default_th) > 0.001 else ""
                print(f"    {c}: {default_th} → {th}{tag}")
    else:
        print("  検証データ不足 → 閾値最適化をスキップ")

    return (best_thresholds if passed else {}), best_train_stats, test_stats, passed

# ══════════════════════════════════════════════════════════════
# screener.js 生成
# ══════════════════════════════════════════════════════════════
NUMS = ["①","②","③","④","⑤","⑥"]
JS_IMPL = {
    "ema75":   ("close > EMA75（長期上昇トレンド）","ind.ema75 !== null && ind.close > ind.ema75","EMA75順張り"),
    "ema25":   ("close > EMA25（中期トレンド）","ind.ema25 !== null && ind.close > ind.ema25","EMA25順張り"),
    "vol20":   ("当日出来高≥20日×2.0","ind.volSurge >= 2.0","vol急増(${ind.volSurge}x)"),
    "vol15":   ("当日出来高≥20日×1.5","ind.volSurge >= 1.5","vol急増(${ind.volSurge}x)"),
    "vol12":   ("当日出来高≥20日×1.2","ind.volSurge >= 1.2","vol急増(${ind.volSurge}x)"),
    "sbull":   ("強い陽線（実体≥0.5%）","ind.isStrongBull","強陽線(${ind.bodyPct.toFixed(1)}%)"),
    "body1":   ("強い陽線（実体≥1.0%）","ind.bodyPct >= 1.0","強陽線(${ind.bodyPct.toFixed(1)}%)"),
    "macdgc":  ("MACD GC（3日以内）","ind.macdGC3d","MACD-GC"),
    "macdpos": ("MACD hist > 0","ind.macdPos","MACD上昇"),
    "atr5":    ("ATR% < 5.0%","ind.atrPct < 5.0","ATR(${ind.atrPct}%)"),
    "atr3":    ("ATR% < 3.0%","ind.atrPct < 3.0","ATR(${ind.atrPct}%)"),
    "atr7":    ("ATR% < 7.0%","ind.atrPct < 7.0","ATR(${ind.atrPct}%)"),
    "hb20":    ("直近20日高値更新","ind.hiBrk20","高値更新"),
    "stoch75": ("ストキャス≥75","ind.stochK >= 75","STOCH(${ind.stochK.toFixed(0)})"),
    "stoch60": ("ストキャス≥60","ind.stochK >= 60","STOCH(${ind.stochK.toFixed(0)})"),
    "rsi5070": ("RSI 50〜70","!isNaN(ind.rsi14) && ind.rsi14 >= 50 && ind.rsi14 < 70","RSI(${ind.rsi14.toFixed(0)})"),
    "rsi4060": ("RSI 40〜60","!isNaN(ind.rsi14) && ind.rsi14 >= 40 && ind.rsi14 < 60","RSI(${ind.rsi14.toFixed(0)})"),
    "bb80":    ("BB位置≥80%","ind.bbPct >= 0.80","BB上部(${(ind.bbPct*100).toFixed(0)}%)"),
    "ich_tk":            ("一目: 転換線 > 基準線","ind.ichTenkan !== null && ind.ichKijun !== null && ind.ichTenkan > ind.ichKijun","一目TK"),
    "ich_price_tenkan":  ("一目: close > 転換線","ind.ichTenkan !== null && ind.close > ind.ichTenkan","一目>転換"),
    "ich_price_kijun":   ("一目: close > 基準線","ind.ichKijun !== null && ind.close > ind.ichKijun","一目>基準"),
    "ich_cloud_above":   ("一目: close > 雲上限","ind.ichCloudTop !== null && ind.close > ind.ichCloudTop","一目雲上"),
    "ich_cloud_green":   ("一目: 先行雲が陽転","ind.ichCloudGreen","一目雲陽転"),
    "ich_chikou":        ("一目: close > 26日前終値","ind.ichChikou","一目遅行"),
    "ich_kumo_break":    ("一目: 雲上抜け","ind.ichKumoBreak","一目雲抜け"),
    "vol30":         ("当日出来高≥20日×3.0","ind.volSurge >= 3.0","vol急増(${ind.volSurge}x)"),
    "body2":         ("強い陽線（実体≥2.0%）","ind.bodyPct >= 2.0","強陽線(${ind.bodyPct.toFixed(1)}%)"),
    "lower_wick50":  ("下ヒゲ優位（下ヒゲ長 ≥ 実体長）","ind.lowerWick50","下ヒゲ優位"),
    "pre_decline15": ("直近20日押し≥15%","ind.preDecline15","深押し"),
    "rci9_os":  ("RCI(9) ≤ -50（短期売られすぎ）","ind.rci9 !== null && ind.rci9 <= -50","RCI9(${ind.rci9 !== null ? ind.rci9.toFixed(0) : 'N/A'})"),
    "rci26_os": ("RCI(26) ≤ -50（中期売られすぎ）","ind.rci26 !== null && ind.rci26 <= -50","RCI26(${ind.rci26 !== null ? ind.rci26.toFixed(0) : 'N/A'})"),
    "rci9_up":  ("RCI(9) 底打ち転換（負→上昇中）","ind.rci9 !== null && ind.rci9Prev !== null && ind.rci9 > ind.rci9Prev && ind.rci9 < 0","RCI9転換"),
    "pre_down3":("直近3日連続下落後","ind.preDown3","3連陰後"),
    "gap_up":   ("ギャップアップ（始値>前終値）","ind.gapUp","GAP-UP"),
    "bb_lower": ("BB位置≤20%（下バンド付近）","ind.bbPct <= 0.20","BB下部"),
    "cci_os":   ("CCI(14) ≤ -100（売られすぎ）","ind.cciVal <= -100","CCI売られ"),
    "smbull_seq2": ("直近2日連続小陽線後（body 0〜1%）","ind.smbullSeq2","2連小陽後"),
    "smbull_seq3": ("直近3日連続小陽線後（body 0〜1%）","ind.smbullSeq3","3連小陽後"),
}

EXTRA_JS_BLOCK = """
  // ── 追加指標（optimize_screener.pyが使用する可能性のある条件）───────
  // MACD hist > 0
  const macdHistVal = (validMacd.length > 0 && macdSignalArr.length > 0)
    ? validMacd[validMacd.length-1] - macdSignalArr[macdSignalArr.length-1] : 0;
  const macdPos = macdHistVal > 0;

  // RSI(14)
  let rsiSumG = 0, rsiSumL = 0;
  for (let i = Math.max(1, last-13); i <= last; i++) {
    const d = closes[i] - closes[i-1];
    if (d > 0) rsiSumG += d; else rsiSumL -= d;
  }
  const rsiLen14 = Math.min(14, last);
  const rsi14 = (rsiSumL/rsiLen14) > 0
    ? 100 - 100 / (1 + (rsiSumG/rsiLen14) / (rsiSumL/rsiLen14)) : 100;

  // Stochastic K(14)
  const stochLo = Math.min(...lows.slice(Math.max(0, last-13), last+1));
  const stochHi = Math.max(...highs.slice(Math.max(0, last-13), last+1));
  const stochK  = (stochHi - stochLo) > 0
    ? (latestClose - stochLo) / (stochHi - stochLo) * 100 : 50;

  // BB位置（20日）
  const bbSlc   = closes.slice(Math.max(0, last-19), last+1);
  const bbMean_ = bbSlc.reduce((a, b) => a + b, 0) / bbSlc.length;
  const bbStd_  = Math.sqrt(bbSlc.reduce((a, b) => a + (b - bbMean_) ** 2, 0) / bbSlc.length);
  const bbPct   = bbStd_ > 0
    ? Math.min(1, Math.max(0, (latestClose - (bbMean_ - 2 * bbStd_)) / (4 * bbStd_))) : 0.5;

  // 直近20日高値更新
  const hi20Arr = highs.slice(Math.max(0, last-20), last);
  const hi20v   = hi20Arr.length > 0 ? Math.max(...hi20Arr) : latestClose;
  const hiBrk20 = latestClose > hi20v;

  // 一目均衡表
  function ichimokuMid(end, period) {
    if (end == null || end - period + 1 < 0) return null;
    const h = highs.slice(end - period + 1, end + 1);
    const l = lows.slice(end - period + 1, end + 1);
    return (Math.max(...h) + Math.min(...l)) / 2;
  }

  const ichTenkan = ichimokuMid(last, 9);
  const ichKijun  = ichimokuMid(last, 26);
  const ichSpanAFuture = (ichTenkan !== null && ichKijun !== null) ? (ichTenkan + ichKijun) / 2 : null;
  const ichSpanBFuture = ichimokuMid(last, 52);

  function visibleIchimokuCloud(end) {
    const base = end - 26;
    const t = ichimokuMid(base, 9);
    const k = ichimokuMid(base, 26);
    const b = ichimokuMid(base, 52);
    if (t === null || k === null || b === null) return { spanA: null, spanB: null, top: null };
    const a = (t + k) / 2;
    return { spanA: a, spanB: b, top: Math.max(a, b) };
  }

  const ichCloud = visibleIchimokuCloud(last);
  const ichCloudPrev = visibleIchimokuCloud(last - 1);
  const ichCloudGreen = ichSpanAFuture !== null && ichSpanBFuture !== null && ichSpanAFuture > ichSpanBFuture;
  const ichChikou = last >= 26 && latestClose > closes[last - 26];
  const ichKumoBreak = ichCloud.top !== null && ichCloudPrev.top !== null
    && closes[last - 1] <= ichCloudPrev.top && latestClose > ichCloud.top;

  // 下ヒゲ優位（下ヒゲ長 ≥ 実体長）
  const lowerWick = Math.min(latestClose, latestOpen) - lows[last];
  const lowerWick50 = lowerWick >= Math.abs(latestClose - latestOpen) && lowerWick > 0;

  // 直近20日高値から15%以上の押し
  const preDecline15 = hi20v > 0 && (latestClose / hi20v - 1) <= -0.15;

  // RCI (Rank Correlation Index)
  function calcRCI(arr, period) {
    if (arr.length < period) return null;
    const p = arr.slice(-period);
    const n = period;
    const sorted = [...p].sort((a, b) => b - a);
    const priceRank = p.map(v => sorted.indexOf(v) + 1);
    const dSq = priceRank.reduce((sum, pr, i) => sum + Math.pow((i + 1) - pr, 2), 0);
    return (1 - 6 * dSq / (n * (n * n - 1))) * 100;
  }
  const rci9     = calcRCI(closes.slice(0, last + 1), 9);
  const rci9Prev = last >= 9 ? calcRCI(closes.slice(0, last), 9) : null;
  const rci26    = calcRCI(closes.slice(0, last + 1), 26);

  // 直近3日連続下落（押し目確認）
  const preDown3 = last >= 3
    && closes[last-1] < closes[last-2]
    && closes[last-2] < closes[last-3];

  // ギャップアップ（当日始値 > 前日終値）
  const gapUp = last > 0 && opens[last] > closes[last - 1];

  // CCI(14)
  const cciStart_ = Math.max(0, last - 13);
  const tp14_ = [];
  for (let i = cciStart_; i <= last; i++) tp14_.push((highs[i]+lows[i]+closes[i])/3);
  const tpMean_ = tp14_.reduce((a,b)=>a+b,0)/tp14_.length;
  const tpMd_   = tp14_.reduce((a,v)=>a+Math.abs(v-tpMean_),0)/tp14_.length;
  const cciVal  = tpMd_ > 0 ? (tp14_[tp14_.length-1]-tpMean_)/(0.015*tpMd_) : 0;

  // 連続小陽線（シグナル前に body 0〜1% の陽線が連続）
  function _isSmBull(i) {
    if (i < 0) return false;
    const bp = closes[i] > 0 ? (closes[i] - opens[i]) / closes[i] * 100 : 0;
    return bp > 0 && bp < 1.0;
  }
  const smbullSeq2 = last >= 2 && _isSmBull(last-1) && _isSmBull(last-2);
  const smbullSeq3 = last >= 3 && _isSmBull(last-1) && _isSmBull(last-2) && _isSmBull(last-3);"""

EXTRA_JS_RETURN = """    macdPos,
    rsi14:    +rsi14.toFixed(2),
    stochK:   +stochK.toFixed(2),
    bbPct:    +bbPct.toFixed(4),
    hiBrk20,
    ichTenkan:    ichTenkan !== null ? +ichTenkan.toFixed(2) : null,
    ichKijun:     ichKijun !== null ? +ichKijun.toFixed(2) : null,
    ichCloudTop:  ichCloud.top !== null ? +ichCloud.top.toFixed(2) : null,
    ichCloudGreen,
    ichChikou,
    ichKumoBreak,
    lowerWick50,
    preDecline15,
    rci9:     rci9 !== null ? +rci9.toFixed(1) : null,
    rci9Prev: rci9Prev !== null ? +rci9Prev.toFixed(1) : null,
    rci26:    rci26 !== null ? +rci26.toFixed(1) : null,
    preDown3,
    gapUp,
    cciVal:   +cciVal.toFixed(1),
    smbullSeq2,
    smbullSeq3,"""


def build_func_a(conditions, stats, baseline, n, thresholds=None):
    thresholds = thresholds or {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    tuned_note = " +閾値最適化" if thresholds else ""
    lines = [
        f"// 自動最適化(方式A{tuned_note}) {now} / {n}件データ",
        f"// ★6: {stats['n']}件 勝率{stats['wr_raw']*100:.1f}% 平均{stats['avg_raw']*100:.1f}% 上昇{stats['win10_raw']:.0f}件 下落{stats['lose10_raw']:.0f}件",
        f"// 現行: 勝率{baseline['wr_raw']*100:.1f}% 平均{baseline['avg_raw']*100:.1f}%",
        "// 【6条件（各1点）】",
    ]
    for i, c in enumerate(conditions):
        if c in thresholds and c in COND_PARAM:
            raw_col = COND_PARAM[c][0]
            desc = PARAM_JS_TPL[raw_col][0](thresholds[c])
        else:
            desc = JS_IMPL.get(c, ('',))[0] or c
        lines.append(f"//   {NUMS[i]} {desc}")
    lines += ["", "function calculateScore(ind) {", "  if (!ind) return null;",
              "  const filters = [];", "  let score = 0;", ""]
    for i, c in enumerate(conditions):
        num = NUMS[i]
        if c in thresholds and c in COND_PARAM:
            raw_col = COND_PARAM[c][0]
            th = thresholds[c]
            desc  = PARAM_JS_TPL[raw_col][0](th)
            cond  = PARAM_JS_TPL[raw_col][1](th)
            label = PARAM_JS_TPL[raw_col][2](th)
        elif c in JS_IMPL:
            desc, cond, label = JS_IMPL[c]
        else:
            continue
        lines += [f"  // {num} {desc}", f"  if ({cond}) {{",
                  f"    score++;", f"    filters.push(`{num}{label}`);", f"  }}", ""]
    lines += ["  return { score, filters };", "}"]
    return "\n".join(lines)

def build_func_b(scheme, stats, baseline, n):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"// 自動最適化(方式B・重み付き) {now} / {n}件データ",
        f"// ★6: {stats['n']}件 勝率{stats['wr_raw']*100:.1f}% 平均{stats['avg_raw']*100:.1f}% 上昇{stats['win10_raw']:.0f}件 下落{stats['lose10_raw']:.0f}件",
        f"// 現行: 勝率{baseline['wr_raw']*100:.1f}% 平均{baseline['avg_raw']*100:.1f}%",
        "// 【スコア設計（+10%銘柄共通点から自動導出）】",
    ]
    for c,w,lift in scheme:
        lines.append(f"//   {JS_IMPL.get(c,('',))[0] or c} → {w}点 (リフト{lift})")
    lines += ["","function calculateScore(ind) {","  if (!ind) return null;",
              "  const filters = [];","  let score = 0;",""]
    for i,(c,w,lift) in enumerate(scheme):
        if c not in JS_IMPL: continue
        desc,cond,label = JS_IMPL[c]; num = NUMS[min(i,5)]
        lines += [f"  // {num} {desc}（{w}点・リフト{lift}）",f"  if ({cond}) {{",
                  f"    score += {w};",f"    filters.push(`{num}{label}({w}pt)`);",f"  }}",""]
    lines += ["  score = Math.min(score, 6);","  return { score, filters };","}"]
    return "\n".join(lines)

def build_func_sniper(conditions, stats, n, thresholds=None):
    """calculateScoreSniper() の JS コードを生成"""
    thresholds = thresholds or {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"// Sniperモード自動最適化 {now} / {n}件データ",
        f"// Sniper: {stats['n']}件 勝率{stats['wr_raw']*100:.1f}% 平均{stats['avg_raw']*100:.1f}%",
        f"// 【Sniper条件（全6条件通過で採択）】",
    ]
    for i, c in enumerate(conditions):
        if c in thresholds and c in COND_PARAM:
            raw_col = COND_PARAM[c][0]
            desc = PARAM_JS_TPL[raw_col][0](thresholds[c])
        else:
            desc = JS_IMPL.get(c, ('',))[0] or c
        lines.append(f"//   {NUMS[i]} {desc}")
    lines += ["", "function calculateScoreSniper(ind) {",
              "  if (!ind) return null;",
              "  const filters = [];",
              "  let score = 0;", ""]
    for i, c in enumerate(conditions):
        num = NUMS[i]
        if c in thresholds and c in COND_PARAM:
            raw_col = COND_PARAM[c][0]
            th = thresholds[c]
            desc  = PARAM_JS_TPL[raw_col][0](th)
            cond  = PARAM_JS_TPL[raw_col][1](th)
            label = PARAM_JS_TPL[raw_col][2](th)
        elif c in JS_IMPL:
            desc, cond, label = JS_IMPL[c]
        else:
            continue
        lines += [f"  // {num} {desc}", f"  if ({cond}) {{",
                  f"    score++;", f"    filters.push(`{num}{label}`);", f"  }}", ""]
    lines += ["  return { score, filters };", "}"]
    return "\n".join(lines)

def update_screener_js_sniper(new_code):
    """calculateScoreSniper() を置換"""
    if not os.path.exists(SCREENER_JS_PATH):
        print(f"  ⚠ 見つかりません: {SCREENER_JS_PATH}"); return False
    with open(SCREENER_JS_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    start = content.find("function calculateScoreSniper(ind)")
    if start < 0:
        print("  ⚠ calculateScoreSniper関数が見つかりません"); return False
    block_start = start
    for marker in ["// Sniperモード自動最適化", "// Sniper:", "// 【Sniper条件"]:
        pos = content.rfind(marker, 0, start)
        if 0 < pos and pos > start - 400:
            block_start = min(block_start, pos)
    depth = 0; end = start
    for i in range(start, len(content)):
        if content[i] == "{": depth += 1
        elif content[i] == "}":
            depth -= 1
            if depth == 0: end = i + 1; break
    content = content[:block_start] + new_code + "\n" + content[end:]
    with open(SCREENER_JS_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    return True

def build_func_moonshot(conditions, stats, eval_days, n, thresholds=None):
    """calculateScoreMoonshot() の JS コードを生成"""
    thresholds = thresholds or {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"// Moonshotモード自動最適化 {now} / {n}件データ / 評価日 {eval_days}BD後",
        f"// Moonshot: {stats['n']}件 平均{stats['avg_raw']*100:.1f}% 勝率{stats['wr_raw']*100:.1f}%",
        f"// 【Moonshot条件（全6条件通過で採択・平均リターン特化）】",
    ]
    for i, c in enumerate(conditions):
        if c in thresholds and c in COND_PARAM:
            raw_col = COND_PARAM[c][0]
            desc = PARAM_JS_TPL[raw_col][0](thresholds[c])
        else:
            desc = JS_IMPL.get(c, ('',))[0] or c
        lines.append(f"//   {NUMS[i]} {desc}")
    lines += ["", "function calculateScoreMoonshot(ind) {",
              "  if (!ind) return null;",
              "  const filters = [];",
              "  let score = 0;", ""]
    for i, c in enumerate(conditions):
        num = NUMS[i]
        if c in thresholds and c in COND_PARAM:
            raw_col = COND_PARAM[c][0]
            th = thresholds[c]
            desc  = PARAM_JS_TPL[raw_col][0](th)
            cond  = PARAM_JS_TPL[raw_col][1](th)
            label = PARAM_JS_TPL[raw_col][2](th)
        elif c in JS_IMPL:
            desc, cond, label = JS_IMPL[c]
        else:
            continue
        lines += [f"  // {num} {desc}", f"  if ({cond}) {{",
                  f"    score++;", f"    filters.push(`{num}{label}`);", f"  }}", ""]
    lines += ["  return { score, filters };", "}"]
    return "\n".join(lines)

def update_screener_js_moonshot(new_code):
    """calculateScoreMoonshot() を置換"""
    if not os.path.exists(SCREENER_JS_PATH):
        print(f"  ⚠ 見つかりません: {SCREENER_JS_PATH}"); return False
    with open(SCREENER_JS_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    start = content.find("function calculateScoreMoonshot(ind)")
    if start < 0:
        print("  ⚠ calculateScoreMoonshot関数が見つかりません"); return False
    block_start = start
    for marker in ["// Moonshotモード自動最適化", "// Moonshot:", "// 【Moonshot条件",
                   "// Moonshotモード採点", "// 平均騰落率重視", "// 平均リターン重視"]:
        pos = content.rfind(marker, 0, start)
        if 0 < pos and pos > start - 800:
            block_start = min(block_start, pos)
    # `// ===` の罫線は generic すぎるので採用しない。block_start の手前に罫線が
    # 残っても害はないので無視する（最初の最適化で1度だけ）。
    depth = 0; end = start
    for i in range(start, len(content)):
        if content[i] == "{": depth += 1
        elif content[i] == "}":
            depth -= 1
            if depth == 0: end = i + 1; break
    content = content[:block_start] + new_code + "\n" + content[end:]
    with open(SCREENER_JS_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    return True

def update_screener_js(new_code):
    """calculateScore() 置換 + computeIndicators() に追加指標を注入"""
    if not os.path.exists(SCREENER_JS_PATH):
        print(f"  ⚠ 見つかりません: {SCREENER_JS_PATH}"); return False
    with open(SCREENER_JS_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. calculateScore() を置換
    start = content.find("function calculateScore(ind)")
    if start < 0: print("  ⚠ calculateScore関数が見つかりません"); return False
    block_start = start
    for marker in ["// 自動最適化", "// ★6:", "// 現行:", "// 【"]:
        pos = content.rfind(marker, 0, start)
        if 0 < pos and pos > start - 400: block_start = min(block_start, pos)
    depth = 0; end = start
    for i in range(start, len(content)):
        if content[i] == "{": depth += 1
        elif content[i] == "}":
            depth -= 1
            if depth == 0: end = i + 1; break
    content = content[:block_start] + new_code + "\n" + content[end:]

    # 2. computeIndicators() に追加指標を注入（初回のみ）
    if "const macdPos" not in content:  # calculateScore内ではなくcomputeIndicators内の宣言で判定
        old_return = (
            "    isStrongBull,\n"
            "    macdGC3d,\n"
            "  };\n"
            "}"
        )
        new_return = (
            EXTRA_JS_BLOCK + "\n\n"
            "  return {\n"
            "    close:       latestClose,\n"
            "    ema25:       ema25 !== null ? +ema25.toFixed(2) : null,\n"
            "    ema75:       ema75 !== null ? +ema75.toFixed(2) : null,\n"
            "    atrPct:      +atrPct.toFixed(2),\n"
            "    volSurge:    +volSurge.toFixed(2),\n"
            "    bodyPct:     +bodyPct.toFixed(2),\n"
            "    isStrongBull,\n"
            "    macdGC3d,\n"
            + EXTRA_JS_RETURN + "\n"
            "  };\n"
            "}"
        )
        if old_return in content:
            ret_start = content.rfind("  return {", 0, content.find(old_return))
            ret_end   = content.find(old_return) + len(old_return)
            content   = content[:ret_start] + new_return + content[ret_end:]
            print("  ✅ computeIndicators() に追加指標を注入")
        else:
            print("  ⚠ computeIndicators()のreturnパターンが見つかりません")

    # 既に追加指標ブロックが入っている環境にも、一目均衡表だけを追加入力する。
    if "ichTenkan:" not in content:
        ich_block_anchor = "  const hiBrk20 = latestClose > hi20v;"
        ich_return_anchor = "    hiBrk20,"
        ich_block = """

  // 一目均衡表
  function ichimokuMid(end, period) {
    if (end == null || end - period + 1 < 0) return null;
    const h = highs.slice(end - period + 1, end + 1);
    const l = lows.slice(end - period + 1, end + 1);
    return (Math.max(...h) + Math.min(...l)) / 2;
  }

  const ichTenkan = ichimokuMid(last, 9);
  const ichKijun  = ichimokuMid(last, 26);
  const ichSpanAFuture = (ichTenkan !== null && ichKijun !== null) ? (ichTenkan + ichKijun) / 2 : null;
  const ichSpanBFuture = ichimokuMid(last, 52);

  function visibleIchimokuCloud(end) {
    const base = end - 26;
    const t = ichimokuMid(base, 9);
    const k = ichimokuMid(base, 26);
    const b = ichimokuMid(base, 52);
    if (t === null || k === null || b === null) return { spanA: null, spanB: null, top: null };
    const a = (t + k) / 2;
    return { spanA: a, spanB: b, top: Math.max(a, b) };
  }

  const ichCloud = visibleIchimokuCloud(last);
  const ichCloudPrev = visibleIchimokuCloud(last - 1);
  const ichCloudGreen = ichSpanAFuture !== null && ichSpanBFuture !== null && ichSpanAFuture > ichSpanBFuture;
  const ichChikou = last >= 26 && latestClose > closes[last - 26];
  const ichKumoBreak = ichCloud.top !== null && ichCloudPrev.top !== null
    && closes[last - 1] <= ichCloudPrev.top && latestClose > ichCloud.top;"""
        ich_return = """
    ichTenkan:    ichTenkan !== null ? +ichTenkan.toFixed(2) : null,
    ichKijun:     ichKijun !== null ? +ichKijun.toFixed(2) : null,
    ichCloudTop:  ichCloud.top !== null ? +ichCloud.top.toFixed(2) : null,
    ichCloudGreen,
    ichChikou,
    ichKumoBreak,"""
        if ich_block_anchor in content and ich_return_anchor in content:
            content = content.replace(ich_block_anchor, ich_block_anchor + ich_block, 1)
            content = content.replace(ich_return_anchor, ich_return_anchor + ich_return, 1)
            print("  ✅ computeIndicators() に一目均衡表指標を注入")
        else:
            print("  ⚠ computeIndicators()の一目注入パターンが見つかりません")

    # 既に一目が入っている環境に、下ヒゲ・深押し指標を追加注入する。
    if "const lowerWick50" not in content:
        lw_block_anchor = "    && closes[last - 1] <= ichCloudPrev.top && latestClose > ichCloud.top;"
        lw_return_anchor = "    ichKumoBreak,"
        lw_block = """

  // 下ヒゲ優位（下ヒゲ長 ≥ 実体長）
  const lowerWick = Math.min(latestClose, latestOpen) - lows[last];
  const lowerWick50 = lowerWick >= Math.abs(latestClose - latestOpen) && lowerWick > 0;

  // 直近20日高値から15%以上の押し
  const preDecline15 = hi20v > 0 && (latestClose / hi20v - 1) <= -0.15;"""
        lw_return = """
    lowerWick50,
    preDecline15,"""
        if lw_block_anchor in content and lw_return_anchor in content:
            content = content.replace(lw_block_anchor, lw_block_anchor + lw_block, 1)
            content = content.replace(lw_return_anchor, lw_return_anchor + lw_return, 1)
            print("  ✅ computeIndicators() に下ヒゲ・深押し指標を注入")
        else:
            print("  ⚠ computeIndicators()の下ヒゲ注入パターンが見つかりません")

    # RCI / 押し目 / CCI 指標を注入する。
    if "const rci9 " not in content:
        rci_block_anchor = "  const preDecline15 = hi20v > 0 && (latestClose / hi20v - 1) <= -0.15;"
        rci_return_anchor = "    preDecline15,"
        rci_block = """

  // RCI (Rank Correlation Index)
  function calcRCI(arr, period) {
    if (arr.length < period) return null;
    const p = arr.slice(-period);
    const n = period;
    const sorted = [...p].sort((a, b) => b - a);
    const priceRank = p.map(v => sorted.indexOf(v) + 1);
    const dSq = priceRank.reduce((sum, pr, i) => sum + Math.pow((i + 1) - pr, 2), 0);
    return (1 - 6 * dSq / (n * (n * n - 1))) * 100;
  }
  const rci9     = calcRCI(closes.slice(0, last + 1), 9);
  const rci9Prev = last >= 9 ? calcRCI(closes.slice(0, last), 9) : null;
  const rci26    = calcRCI(closes.slice(0, last + 1), 26);

  // 直近3日連続下落（押し目確認）
  const preDown3 = last >= 3
    && closes[last-1] < closes[last-2]
    && closes[last-2] < closes[last-3];

  // ギャップアップ（当日始値 > 前日終値）
  const gapUp = last > 0 && opens[last] > closes[last - 1];

  // CCI(14)
  const cciStart_ = Math.max(0, last - 13);
  const tp14_ = [];
  for (let i = cciStart_; i <= last; i++) tp14_.push((highs[i]+lows[i]+closes[i])/3);
  const tpMean_ = tp14_.reduce((a,b)=>a+b,0)/tp14_.length;
  const tpMd_   = tp14_.reduce((a,v)=>a+Math.abs(v-tpMean_),0)/tp14_.length;
  const cciVal  = tpMd_ > 0 ? (tp14_[tp14_.length-1]-tpMean_)/(0.015*tpMd_) : 0;"""
        rci_return = """
    rci9:     rci9 !== null ? +rci9.toFixed(1) : null,
    rci9Prev: rci9Prev !== null ? +rci9Prev.toFixed(1) : null,
    rci26:    rci26 !== null ? +rci26.toFixed(1) : null,
    preDown3,
    gapUp,
    cciVal:   +cciVal.toFixed(1),"""
        if rci_block_anchor in content and rci_return_anchor in content:
            content = content.replace(rci_block_anchor, rci_block_anchor + rci_block, 1)
            content = content.replace(rci_return_anchor, rci_return_anchor + rci_return, 1)
            print("  ✅ computeIndicators() に RCI/押し目/CCI指標を注入")
        else:
            print("  ⚠ computeIndicators()のRCI注入パターンが見つかりません")

    with open(SCREENER_JS_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    return True

def update_index_js_help(conditions, method, thresholds=None):
    """/helpのスコアリング条件テキストをindex.jsで更新"""
    if not os.path.exists(INDEX_JS_PATH):
        print(f"  ⚠ index.js が見つかりません: {INDEX_JS_PATH}"); return False
    with open(INDEX_JS_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    def _desc(c):
        # パラメーター化条件は実際の閾値を使った説明文を生成
        if thresholds and c in COND_PARAM and c in thresholds:
            raw_col = COND_PARAM[c][0]
            if raw_col in PARAM_JS_TPL:
                return PARAM_JS_TPL[raw_col][0](thresholds[c])
        return JS_IMPL[c][0] if c in JS_IMPL else c

    NUMS_FULL = ["①","②","③","④","⑤","⑥"]
    new_lines = []
    if method == "A":
        for i, c in enumerate(conditions):
            new_lines.append(f"'{NUMS_FULL[i]} {_desc(c)}    1点\\n' +")
    else:
        for i, (c, w, lift) in enumerate(conditions):
            new_lines.append(f"'{NUMS_FULL[min(i,5)]} {_desc(c)}    {w}点\\n' +")

    start_idx = content.find("'①")
    if start_idx < 0:
        print("  ⚠ index.js のスコアリング条件（①）が見つかりません"); return False
    line_start = content.rfind("\n", 0, start_idx) + 1
    end_idx = content.find("'⑥", start_idx)
    if end_idx < 0:
        print("  ⚠ index.js のスコアリング条件（⑥）が見つかりません"); return False
    line_end = content.find("\n", end_idx) + 1
    indent = content[line_start:start_idx]

    replacement = "".join(indent + line + "\n" for line in new_lines)
    new_content = content[:line_start] + replacement + content[line_end:]

    with open(INDEX_JS_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True

# ══════════════════════════════════════════════════════════════
# Discord更新通知
# ══════════════════════════════════════════════════════════════
def notify_discord_update(best_method, best_combo, st6, st5, st4, base, n_total, what_changed="conditions", thresholds=None):
    """スコアロジック更新をDiscordに通知
    what_changed: "conditions" | "thresholds" | "both"
    """
    import urllib.request, json as _json

    NL = "\n"  # 改行文字（文字列連結で使う）
    thresholds = thresholds or {}

    def _desc(c):
        if c in COND_PARAM and c in thresholds:
            raw_col = COND_PARAM[c][0]
            if raw_col in PARAM_JS_TPL:
                return PARAM_JS_TPL[raw_col][0](thresholds[c])
        return JS_IMPL.get(c, (c,))[0]

    # 変更タイプに応じたタイトル・説明
    if what_changed == "thresholds":
        title = "⚙️ スコアリング閾値を調整しました"
        description = (
            "最新データの検証により、現在の条件の最適な閾値を更新しました。\n"
            "採点条件（6項目）は変更ありません。"
        )
        cond_section_name = "📋 スコアリング条件（変更なし）"
    elif what_changed == "both":
        title = "📊 スコアリングロジックを更新しました（条件＋閾値）"
        description = (
            "最新データの分析により、採点条件と閾値を両方更新しました。"
        )
        cond_section_name = "🔬 新しいスコアリング条件（6点満点）"
    else:  # "conditions"
        title = "📊 スコアリング条件を更新しました"
        description = (
            "最新データの分析により、より精度の高い採点条件を発見し、"
            "スコアリングロジックを自動更新しました。"
        )
        cond_section_name = "🔬 新しいスコアリング条件（6点満点）"

    # 条件テキスト（閾値チューニング結果を反映）
    NUMS_FULL = ["①","②","③","④","⑤","⑥"]
    if best_method == "A":
        cond_lines = [f"{NUMS_FULL[i]} {_desc(c)}  1点"
                      for i, c in enumerate(best_combo)]
    else:
        cond_lines = [f"{NUMS_FULL[min(i,5)]} {_desc(c)}  {w}点"
                      for i,(c,w,_) in enumerate(best_combo)]

    def fmt(v):
        return ("+" if v >= 0 else "") + f"{v*100:.1f}%"

    stats_lines = [
        "```",
        f"Stable ★6: {st6['n']:3}件 勝率{st6['wr_raw']*100:5.1f}% 平均{fmt(st6['avg_raw'])}",
        f"Stable ★5: {st5['n']:3}件 勝率{st5['wr_raw']*100:5.1f}% 平均{fmt(st5['avg_raw'])}",
        f"Aggr.  ★4: {st4['n']:3}件 勝率{st4['wr_raw']*100:5.1f}% 平均{fmt(st4['avg_raw'])}",
        f"全シグナル: {n_total:3}件 勝率{base['wr_raw']*100:5.1f}%            平均{fmt(base['avg_raw'])}",
        "```",
    ]
    stats_text = NL.join(stats_lines)
    cond_text  = NL.join(["```"] + cond_lines + ["```"])

    embed = {
        "title": title,
        "color": 0x2ecc71 if what_changed != "thresholds" else 0x3498db,
        "description": description,
        "fields": [
            {
                "name": cond_section_name,
                "value": cond_text,
                "inline": False
            },
            {
                "name": f"📈 バックテスト結果（直近シグナル / {n_total}件検証）",
                "value": stats_text,
                "inline": False
            },
            {
                "name": "🔍 確認方法",
                "value": "`/scan` で最新のスクリーニング結果をご確認いただけます。",
                "inline": False
            }
        ],
        "footer": {"text": "Ken5 Investment Lab — 自動最適化システム"},
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    }

    payload = _json.dumps({"embeds": [embed]}).encode("utf-8")
    req = urllib.request.Request(
        DISCORD_WEBHOOK_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "DiscordBot (screening-bot, 1.0)",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if resp.status in (200, 204):
                print("  ✅ Discord通知送信完了")
            else:
                print(f"  ⚠ Discord通知: HTTP {resp.status} / {body[:200]}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  ⚠ Discord通知失敗: HTTP {e.code} / headers={dict(e.headers)} / body={body[:300]}")
    except Exception as e:
        print(f"  ⚠ Discord通知失敗: {e}")


def notify_discord_approval(best_method, best_combo, best_stats, baseline, thresholds,
                            validation_stats=None, current_stats=None,
                            current_validation_stats=None, adoption_reasons=None,
                            mode="normal"):
    """スコアリング更新候補の承認リクエストをDiscordに送信"""
    import urllib.request, json as _json

    if not APPROVAL_WEBHOOK_URL:
        return

    NL = "\n"
    NUMS_FULL = ["①","②","③","④","⑤","⑥"]
    thresholds = thresholds or {}

    def _desc(c):
        if c in COND_PARAM and c in thresholds:
            raw_col = COND_PARAM[c][0]
            if raw_col in PARAM_JS_TPL:
                return PARAM_JS_TPL[raw_col][0](thresholds[c])
        return JS_IMPL.get(c, (c,))[0]

    if best_method == "A":
        cond_lines = [f"{NUMS_FULL[i]} {_desc(c)}" for i, c in enumerate(best_combo)]
    else:
        cond_lines = [f"{NUMS_FULL[min(i,5)]} {_desc(c)}  ({w}点)"
                      for i, (c, w, _) in enumerate(best_combo)]

    validation_stats = validation_stats or calc_stats(pd.DataFrame())
    current_stats = current_stats or baseline
    current_validation_stats = current_validation_stats or calc_stats(pd.DataFrame())
    adoption_reasons = adoption_reasons or []

    wr_new  = best_stats['wr_raw'] * 100
    wr_old  = current_stats.get('wr_raw', 0) * 100
    avg_new = best_stats['avg_raw'] * 100
    avg_old = current_stats.get('avg_raw', 0) * 100
    mode_label = "rescue" if mode == "rescue" else "normal"

    def _stats_line(label, st):
        return (
            f"{label:<8} {int(st.get('n', 0)):3}件 "
            f"勝率{st.get('wr_raw', 0)*100:5.1f}% "
            f"平均{st.get('avg_raw', 0)*100:+5.1f}%"
        )

    payload = {
        "embeds": [{
            "title": f"📋 スコアリング条件の更新候補 ({mode_label})",
            "description": "新しい更新候補が見つかりました。承認するには `/approve-update` を実行してください。",
            "color": 0xE67E22 if mode == "rescue" else 0xFFA500,
            "fields": [
                {
                    "name": f"🔬 候補条件（方式{best_method}）",
                    "value": "```\n" + NL.join(cond_lines) + "\n```",
                    "inline": False
                },
                {
                    "name": "📊 候補成績",
                    "value": (
                        f"```\n"
                        f"{_stats_line('全件★6', best_stats)}\n"
                        f"{_stats_line('検証★6', validation_stats)}\n"
                        f"上昇 {int(best_stats['win10_raw'])}件 / 下落 {int(best_stats['lose10_raw'])}件\n"
                        f"```"
                    ),
                    "inline": False
                },
                {
                    "name": "📈 現行との比較",
                    "value": (
                        f"```\n"
                        f"{_stats_line('現行全件', current_stats)}\n"
                        f"{_stats_line('現行検証', current_validation_stats)}\n"
                        f"{_stats_line('候補全件', best_stats)}\n"
                        f"{_stats_line('候補検証', validation_stats)}\n"
                        f"```\n"
                        f"勝率: {wr_old:.1f}% → **{wr_new:.1f}%** ({wr_new-wr_old:+.1f}pt)\n"
                        f"平均: {avg_old:+.1f}% → **{avg_new:+.1f}%** ({avg_new-avg_old:+.1f}pt)"
                    ),
                    "inline": False
                },
                {
                    "name": "🧭 採用理由",
                    "value": "```\n" + NL.join(adoption_reasons or ["品質ゲート通過"]) + "\n```",
                    "inline": False
                },
                {
                    "name": "✅ 承認方法",
                    "value": "Discord で `/approve-update` を実行してください",
                    "inline": False
                }
            ],
            "footer": {"text": "承認するまで現行ロジックは変更されません"},
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }]
    }

    data = _json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        APPROVAL_WEBHOOK_URL,
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "DiscordBot (screening-bot, 1.0)"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status not in (200, 204):
                print(f"  ⚠ Discord承認通知失敗: HTTP {resp.status}")
    except Exception as e:
        print(f"  ⚠ Discord承認通知失敗: {e}")


def notify_discord_rescue_no_candidate(current_stats, current_validation_stats,
                                       rescue_reasons, n_total):
    """rescue mode発動時に更新候補が見つからなかったことを管理者へ通知する。"""
    import urllib.request, json as _json

    if not APPROVAL_WEBHOOK_URL:
        return

    def _stats_line(label, st):
        return (
            f"{label:<8} {int(st.get('n', 0)):3}件 "
            f"勝率{st.get('wr_raw', 0)*100:5.1f}% "
            f"平均{st.get('avg_raw', 0)*100:+5.1f}%"
        )

    payload = {
        "embeds": [{
            "title": "⚠ Stable現行ロジック劣化 / 更新候補なし",
            "description": (
                "Stable ★6 の劣化条件に該当しましたが、"
                "品質ゲートを満たす代替ロジックは見つかりませんでした。"
            ),
            "color": 0xE74C3C,
            "fields": [
                {
                    "name": "📉 現行成績",
                    "value": (
                        "```\n"
                        f"{_stats_line('全件★6', current_stats)}\n"
                        f"{_stats_line('検証★6', current_validation_stats)}\n"
                        f"全シグナル {n_total}件\n"
                        "```"
                    ),
                    "inline": False
                },
                {
                    "name": "🧯 rescue mode 発動理由",
                    "value": "```\n" + "\n".join(rescue_reasons) + "\n```",
                    "inline": False
                },
                {
                    "name": "判断",
                    "value": "品質条件を満たさない置き換えは行わず、人間判断に上げます。",
                    "inline": False
                },
            ],
            "footer": {"text": "pending_logic.json は作成していません"},
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }]
    }

    data = _json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        APPROVAL_WEBHOOK_URL,
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "DiscordBot (screening-bot, 1.0)"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status not in (200, 204):
                print(f"  ⚠ Discord rescue通知失敗: HTTP {resp.status}")
            else:
                print("  ✅ Discord rescue通知送信完了")
    except Exception as e:
        print(f"  ⚠ Discord rescue通知失敗: {e}")


def notify_discord_sniper_rescue_no_candidate(refreshed_stats, live_stats,
                                              rescue_reasons, n_total):
    """Sniper rescue mode 発動時に更新候補が見つからなかったことを管理者へ通知する。"""
    import urllib.request, json as _json
    if not APPROVAL_WEBHOOK_URL:
        return

    def _stats_line(label, st):
        if not st or st.get("n", 0) == 0:
            return f"{label:<10} (該当なし)"
        return (
            f"{label:<10} {int(st.get('n', 0)):3}件 "
            f"勝率{st.get('wr_raw', 0)*100:5.1f}% "
            f"平均{st.get('avg_raw', 0)*100:+5.1f}%"
        )

    payload = {
        "embeds": [{
            "title": "⚠ Sniper現行ロジック劣化 / 更新候補なし",
            "description": (
                "Sniper ★6 の劣化条件に該当しましたが、"
                f"勝率{SNIPER_RESCUE_WR_MIN*100:.0f}%以上の代替ロジックは"
                "見つかりませんでした。"
            ),
            "color": 0xE74C3C,
            "fields": [
                {
                    "name": "📉 現行成績",
                    "value": (
                        "```\n"
                        f"{_stats_line('全件★6', refreshed_stats)}\n"
                        f"{_stats_line('ライブ★6', live_stats)}\n"
                        f"全シグナル {n_total}件\n"
                        "```"
                    ),
                    "inline": False
                },
                {
                    "name": "🧯 rescue mode 発動理由",
                    "value": "```\n" + "\n".join(rescue_reasons) + "\n```",
                    "inline": False
                },
                {
                    "name": "判断",
                    "value": "品質条件を満たさない置き換えは行わず、人間判断に上げます。",
                    "inline": False
                },
            ],
            "footer": {"text": "pending_logic_sniper.json は作成していません"},
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }]
    }

    data = _json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        APPROVAL_WEBHOOK_URL,
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "DiscordBot (screening-bot, 1.0)"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status not in (200, 204):
                print(f"  ⚠ Discord Sniper rescue通知失敗: HTTP {resp.status}")
            else:
                print("  ✅ Discord Sniper rescue通知送信完了")
    except Exception as e:
        print(f"  ⚠ Discord Sniper rescue通知失敗: {e}")


def notify_discord_sniper_approval(conditions, stats, baseline_wr, thresholds):
    """Sniperロジック更新候補の承認リクエストをDiscordに送信"""
    import urllib.request, json as _json
    if not APPROVAL_WEBHOOK_URL:
        return
    thresholds = thresholds or {}
    NL = "\n"
    NUMS_FULL = ["①","②","③","④","⑤","⑥"]
    def _desc(c):
        if c in COND_PARAM and c in thresholds:
            raw_col = COND_PARAM[c][0]
            if raw_col in PARAM_JS_TPL:
                return PARAM_JS_TPL[raw_col][0](thresholds[c])
        return JS_IMPL.get(c, (c,))[0]
    cond_lines = [f"{NUMS_FULL[i]} {_desc(c)}" for i, c in enumerate(conditions)]
    wr_new  = stats["wr_raw"] * 100
    avg_new = stats["avg_raw"] * 100
    wr_old  = baseline_wr * 100
    payload = {
        "embeds": [{
            "title": "🎯 Sniperモード — スコアリング更新候補",
            "description": "勝率特化モードの更新候補が見つかりました。承認するには `/approve-update` を実行してください。",
            "color": 0xFF69B4,
            "fields": [
                {
                    "name": "🔬 Sniper条件（全通過で採択）",
                    "value": "```\n" + NL.join(cond_lines) + "\n```",
                    "inline": False
                },
                {
                    "name": "📊 バックテスト成績（全件データ）",
                    "value": (
                        f"```\nSniper: {int(stats['n'])}件  勝率 {wr_new:.1f}%  平均 {avg_new:+.1f}%\n"
                        f"上昇 {int(stats['win10_raw'])}件  下落 {int(stats['lose10_raw'])}件\n```"
                    ),
                    "inline": False
                },
                {
                    "name": "📈 現行との比較",
                    "value": f"勝率: {wr_old:.1f}% → **{wr_new:.1f}%** ({wr_new-wr_old:+.1f}pt)",
                    "inline": False
                },
                {
                    "name": "✅ 承認方法",
                    "value": "Discord で `/approve-update` を実行してください",
                    "inline": False
                }
            ],
            "footer": {"text": "承認するまで現行Sniperロジックは変更されません"},
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }]
    }
    data = _json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        APPROVAL_WEBHOOK_URL, data=data,
        headers={"Content-Type": "application/json; charset=utf-8",
                 "User-Agent": "DiscordBot (screening-bot, 1.0)"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status not in (200, 204):
                print(f"  ⚠ Discord Sniper承認通知失敗: HTTP {resp.status}")
    except Exception as e:
        print(f"  ⚠ Discord Sniper承認通知失敗: {e}")


def notify_discord_sniper_update(conditions, stats, thresholds):
    """Sniperロジック更新完了をDiscordに通知"""
    import urllib.request, json as _json
    thresholds = thresholds or {}
    NL = "\n"
    NUMS_FULL = ["①","②","③","④","⑤","⑥"]

    def _desc(c):
        if c in COND_PARAM and c in thresholds:
            raw_col = COND_PARAM[c][0]
            if raw_col in PARAM_JS_TPL:
                return PARAM_JS_TPL[raw_col][0](thresholds[c])
        return JS_IMPL.get(c, (c,))[0]

    cond_lines = [f"{NUMS_FULL[i]} {_desc(c)}" for i, c in enumerate(conditions)]
    wr = stats["wr_raw"] * 100
    avg = stats["avg_raw"] * 100

    payload = {
        "embeds": [{
            "title": "🎯 Sniperモードのスコアリング条件を更新しました",
            "description": "承認済みのSniperロジックをデプロイし、Botへ反映しました。",
            "color": 0x2ecc71,
            "fields": [
                {
                    "name": "🔬 新しいSniper条件（全通過で採択）",
                    "value": "```\n" + NL.join(cond_lines) + "\n```",
                    "inline": False
                },
                {
                    "name": "📊 バックテスト成績（全件データ）",
                    "value": (
                        f"```\nSniper: {int(stats['n'])}件  勝率 {wr:.1f}%  平均 {avg:+.1f}%\n"
                        f"上昇 {int(stats['win10_raw'])}件  下落 {int(stats['lose10_raw'])}件\n```"
                    ),
                    "inline": False
                },
                {
                    "name": "🔍 確認方法",
                    "value": "`/scan sniper` または `/help` で最新条件を確認できます。",
                    "inline": False
                }
            ],
            "footer": {"text": "Ken5 Investment Lab — 自動デプロイ完了"},
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }]
    }
    data = _json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        DISCORD_WEBHOOK_URL,
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "DiscordBot (screening-bot, 1.0)",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 204):
                print("  ✅ Discord Sniper更新通知送信完了")
            else:
                print(f"  ⚠ Discord Sniper更新通知失敗: HTTP {resp.status}")
    except Exception as e:
        print(f"  ⚠ Discord Sniper更新通知失敗: {e}")


def apply_sniper_pending():
    """pending_logic_sniper.json を読み込んで screener.js を更新する。
    デプロイは行わない（呼び出し元が deploy() を担当）。
    戻り値: {"combo": ..., "thresholds": ..., "stats": ...} or None"""
    import json as _pjson
    if not os.path.exists(SNIPER_PENDING_PATH):
        return None
    print("\n📋 Sniper: pending_logic_sniper.json を適用...")
    with open(SNIPER_PENDING_PATH, "r", encoding="utf-8") as _pf:
        _p = _pjson.load(_pf)
    _combo = _p["conditions"]
    _ths   = _p.get("thresholds", {})
    _code  = _p["sniper_code"]
    _st    = _p["stats"]
    print(f"  Sniper: 勝率{_st['wr_raw']*100:.1f}% 平均{_st['avg_raw']*100:.1f}% {int(_st['n'])}件")
    if not update_screener_js_sniper(_code):
        print("  ❌ calculateScoreSniper() 更新失敗")
        return None
    print("  ✅ calculateScoreSniper() 更新完了")
    return {"combo": _combo, "thresholds": _ths, "stats": _st}

def finalize_sniper_pending(sniper_data):
    """deploy()成功後にSniperロジックを確定（JSON保存 + pending削除）"""
    if sniper_data is None:
        return
    save_current_logic_sniper(sniper_data["combo"], sniper_data["thresholds"] or None,
                              backtest_stats=sniper_data["stats"])
    if os.path.exists(SNIPER_PENDING_PATH):
        os.remove(SNIPER_PENDING_PATH)
        print("  ✅ pending_logic_sniper.json 削除完了")


def notify_discord_moonshot_approval(conditions, stats, eval_days, baseline_avg, thresholds):
    """Moonshotロジック更新候補の承認リクエストをDiscordに送信"""
    import urllib.request, json as _json
    if not APPROVAL_WEBHOOK_URL:
        return
    thresholds = thresholds or {}
    NL = "\n"
    NUMS_FULL = ["①","②","③","④","⑤","⑥"]
    def _desc(c):
        if c in COND_PARAM and c in thresholds:
            raw_col = COND_PARAM[c][0]
            if raw_col in PARAM_JS_TPL:
                return PARAM_JS_TPL[raw_col][0](thresholds[c])
        return JS_IMPL.get(c, (c,))[0]
    cond_lines = [f"{NUMS_FULL[i]} {_desc(c)}" for i, c in enumerate(conditions)]
    avg_new = stats["avg_raw"] * 100
    wr_new  = stats["wr_raw"] * 100
    avg_old = baseline_avg * 100
    payload = {
        "embeds": [{
            "title": "🌙 Moonshotモード — スコアリング更新候補",
            "description": (
                "平均リターン特化モードの更新候補が見つかりました。"
                "承認するには `/approve-update` を実行してください。"
            ),
            "color": 0x9b59b6,
            "fields": [
                {
                    "name": "🔬 Moonshot条件（全通過で採択）",
                    "value": "```\n" + NL.join(cond_lines) + "\n```",
                    "inline": False
                },
                {
                    "name": f"📊 バックテスト成績（評価日 {eval_days}BD後）",
                    "value": (
                        f"```\nMoonshot: {int(stats['n'])}件  "
                        f"平均 {avg_new:+.1f}%  勝率 {wr_new:.1f}%\n```"
                    ),
                    "inline": False
                },
                {
                    "name": "📈 現行との比較",
                    "value": f"平均: {avg_old:+.1f}% → **{avg_new:+.1f}%** ({avg_new-avg_old:+.1f}pt)",
                    "inline": False
                },
                {
                    "name": "✅ 承認方法",
                    "value": "Discord で `/approve-update` を実行してください",
                    "inline": False
                }
            ],
            "footer": {"text": "承認するまで現行Moonshotロジックは変更されません"},
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }]
    }
    data = _json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        APPROVAL_WEBHOOK_URL, data=data,
        headers={"Content-Type": "application/json; charset=utf-8",
                 "User-Agent": "DiscordBot (screening-bot, 1.0)"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status not in (200, 204):
                print(f"  ⚠ Discord Moonshot承認通知失敗: HTTP {resp.status}")
    except Exception as e:
        print(f"  ⚠ Discord Moonshot承認通知失敗: {e}")


def notify_discord_moonshot_update(conditions, stats, eval_days, thresholds):
    """Moonshotロジック更新完了をDiscordに通知"""
    import urllib.request, json as _json
    thresholds = thresholds or {}
    NL = "\n"
    NUMS_FULL = ["①","②","③","④","⑤","⑥"]

    def _desc(c):
        if c in COND_PARAM and c in thresholds:
            raw_col = COND_PARAM[c][0]
            if raw_col in PARAM_JS_TPL:
                return PARAM_JS_TPL[raw_col][0](thresholds[c])
        return JS_IMPL.get(c, (c,))[0]

    cond_lines = [f"{NUMS_FULL[i]} {_desc(c)}" for i, c in enumerate(conditions)]
    avg = stats["avg_raw"] * 100
    wr  = stats["wr_raw"] * 100

    payload = {
        "embeds": [{
            "title": "🌙 Moonshotモードのスコアリング条件を更新しました",
            "description": "承認済みのMoonshotロジックをデプロイし、Botへ反映しました。",
            "color": 0x2ecc71,
            "fields": [
                {
                    "name": "🔬 新しいMoonshot条件（全通過で採択）",
                    "value": "```\n" + NL.join(cond_lines) + "\n```",
                    "inline": False
                },
                {
                    "name": f"📊 バックテスト成績（評価日 {eval_days}BD後）",
                    "value": (
                        f"```\nMoonshot: {int(stats['n'])}件  "
                        f"平均 {avg:+.1f}%  勝率 {wr:.1f}%\n```"
                    ),
                    "inline": False
                },
                {
                    "name": "🔍 確認方法",
                    "value": "`/scan moonshot` または `/help` で最新条件を確認できます。",
                    "inline": False
                }
            ],
            "footer": {"text": "Ken5 Investment Lab — 自動デプロイ完了"},
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }]
    }
    data = _json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        DISCORD_WEBHOOK_URL,
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "DiscordBot (screening-bot, 1.0)",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 204):
                print("  ✅ Discord Moonshot更新通知送信完了")
            else:
                print(f"  ⚠ Discord Moonshot更新通知失敗: HTTP {resp.status}")
    except Exception as e:
        print(f"  ⚠ Discord Moonshot更新通知失敗: {e}")


def apply_moonshot_pending():
    """pending_logic_moonshot.json を読み込んで screener.js を更新する。
    デプロイは行わない（呼び出し元が deploy() を担当）。
    戻り値: {"combo": ..., "thresholds": ..., "stats": ..., "eval_days": ...} or None"""
    import json as _pjson
    if not os.path.exists(MOONSHOT_PENDING_PATH):
        return None
    print("\n📋 Moonshot: pending_logic_moonshot.json を適用...")
    with open(MOONSHOT_PENDING_PATH, "r", encoding="utf-8") as _pf:
        _p = _pjson.load(_pf)
    _combo     = _p["conditions"]
    _ths       = _p.get("thresholds", {})
    _code      = _p["moonshot_code"]
    _st        = _p["stats"]
    _eval_days = _p.get("eval_days")
    print(f"  Moonshot: 平均{_st['avg_raw']*100:.1f}% 勝率{_st['wr_raw']*100:.1f}%"
          f" {int(_st['n'])}件 / 評価日 {_eval_days}BD")
    if not update_screener_js_moonshot(_code):
        print("  ❌ calculateScoreMoonshot() 更新失敗")
        return None
    print("  ✅ calculateScoreMoonshot() 更新完了")
    return {"combo": _combo, "thresholds": _ths, "stats": _st, "eval_days": _eval_days}

def finalize_moonshot_pending(moonshot_data):
    """deploy()成功後にMoonshotロジックを確定（JSON保存 + pending削除）"""
    if moonshot_data is None:
        return
    save_current_logic_moonshot(
        moonshot_data["combo"],
        moonshot_data["eval_days"],
        thresholds=moonshot_data["thresholds"] or None,
        backtest_stats=moonshot_data["stats"],
    )
    if os.path.exists(MOONSHOT_PENDING_PATH):
        os.remove(MOONSHOT_PENDING_PATH)
        print("  ✅ pending_logic_moonshot.json 削除完了")


# ══════════════════════════════════════════════════════════════
# 自動デプロイ
# ══════════════════════════════════════════════════════════════
def deploy():
    print("\n🚀 自動デプロイ...")
    if _ON_VM:
        # VM上で実行中: screener.jsはすでにローカルにあるのでpm2 restartのみ
        steps = [
            ("① pm2 restart",
             ["pm2", "restart", "screening-bot"]),
        ]
        for label, cmd in steps:
            print(f"  {label}...")
            r = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            if r.returncode == 0:
                print(f"     ✅ 完了")
                out = (r.stdout or "").strip()
                if out: print(f"     {out[:120]}")
            else:
                err = (r.stderr or "").strip()
                print(f"     ❌ エラー: {err[:200]}"); return False
    elif _ON_GITHUB_ACTIONS:
        # GitHub Actions (Linux): ssh/scpを直接呼び出す
        steps = [
            ("① scp転送(screener.js)",
             ["scp", "-i", SSH_KEY_PATH, "-o", "StrictHostKeyChecking=no",
              SCREENER_JS_PATH, f"{VM_HOST}:{VM_DEST}"]),
            ("② scp転送(index.js)",
             ["scp", "-i", SSH_KEY_PATH, "-o", "StrictHostKeyChecking=no",
              INDEX_JS_PATH, f"{VM_HOST}:{VM_DEST}"]),
            ("③ scp転送(current_logic_sniper.json)",
             ["scp", "-i", SSH_KEY_PATH, "-o", "StrictHostKeyChecking=no",
              SNIPER_LOGIC_PATH, f"{VM_HOST}:{VM_DEST}"]),
        ]
        # Moonshotファイルが存在する場合のみ転送（MOONSHOT_AUTO_OPTIMIZE_ENABLED=False の間は不在）
        if os.path.exists(MOONSHOT_LOGIC_PATH):
            steps.append(("④ scp転送(current_logic_moonshot.json)",
             ["scp", "-i", SSH_KEY_PATH, "-o", "StrictHostKeyChecking=no",
              MOONSHOT_LOGIC_PATH, f"{VM_HOST}:{VM_DEST}"]))
        else:
            print("  ⊘ current_logic_moonshot.json 不在 → SCPスキップ")
        steps.append(("⑤ pm2 restart",
             ["ssh", "-i", SSH_KEY_PATH, "-o", "StrictHostKeyChecking=no",
              VM_HOST, "pm2 restart screening-bot"]))
        for label, cmd in steps:
            print(f"  {label}...")
            r = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            if r.returncode == 0:
                print(f"     ✅ 完了")
                out = (r.stdout or "").strip()
                if out: print(f"     {out[:120]}")
            else:
                err = (r.stderr or "").strip()
                print(f"     ❌ エラー: {err[:200]}"); return False
    else:
        # ローカルWindows: PowerShell経由でscp/ssh
        steps = [
            ("① scp転送(screener.js)",
             f'scp -i "{SSH_KEY_PATH}" "{SCREENER_JS_PATH}" {VM_HOST}:{VM_DEST}'),
            ("② scp転送(index.js)",
             f'scp -i "{SSH_KEY_PATH}" "{INDEX_JS_PATH}" {VM_HOST}:{VM_DEST}'),
            ("③ scp転送(current_logic_sniper.json)",
             f'scp -i "{SSH_KEY_PATH}" "{SNIPER_LOGIC_PATH}" {VM_HOST}:{VM_DEST}'),
        ]
        # Moonshotファイルが存在する場合のみ転送（MOONSHOT_AUTO_OPTIMIZE_ENABLED=False の間は不在の可能性）
        if os.path.exists(MOONSHOT_LOGIC_PATH):
            steps.append(("④ scp転送(current_logic_moonshot.json)",
             f'scp -i "{SSH_KEY_PATH}" "{MOONSHOT_LOGIC_PATH}" {VM_HOST}:{VM_DEST}'))
        else:
            print("  ⊘ current_logic_moonshot.json 不在 → SCPスキップ")
        steps.append(("⑤ pm2 restart",
             f'ssh -i "{SSH_KEY_PATH}" -o StrictHostKeyChecking=no {VM_HOST} "pm2 restart screening-bot"'))
        for label, cmd in steps:
            print(f"  {label}...")
            r = subprocess.run(["powershell", "-Command", cmd],
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            if r.returncode == 0:
                print(f"     ✅ 完了")
                out = (r.stdout or "").strip()
                if out: print(f"     {out[:120]}")
            else:
                err = (r.stderr or "").strip()
                print(f"     ❌ エラー: {err[:200]}"); return False
    return True


def restart_bot_only():
    """ファイル転送なしで pm2 restart だけ実行する（ロジック更新なし再起動用）"""
    print("\n🔄 Bot 再起動（pm2 restart only）...")
    if _ON_VM:
        r = subprocess.run(["pm2", "restart", "screening-bot"],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    elif _ON_GITHUB_ACTIONS:
        r = subprocess.run(
            ["ssh", "-i", SSH_KEY_PATH, "-o", "StrictHostKeyChecking=no",
             VM_HOST, "pm2 restart screening-bot"],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    else:
        cmd = (f'ssh -i "{SSH_KEY_PATH}" -o StrictHostKeyChecking=no '
               f'{VM_HOST} "pm2 restart screening-bot"')
        r = subprocess.run(["powershell", "-Command", cmd],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    if r.returncode == 0:
        print("  ✅ pm2 restart 完了")
        out = (r.stdout or "").strip()
        if out:
            print(f"  {out[:120]}")
    else:
        err = (r.stderr or "").strip()
        print(f"  ⚠ pm2 restart 失敗: {err[:200]}")


# ══════════════════════════════════════════════════════════════
# Sniperモード最適化（勝率特化）
# ══════════════════════════════════════════════════════════════
def _run_sniper_optimization(df, args):
    """Sniperモード最適化（勝率特化）。
    --propose: pending_logic_sniper.json 保存 + Discord通知。
    --dry-run: 候補表示のみ。
    通常実行: screener.js + current_logic_sniper.json を直接更新（デプロイは main() が担当）。
    """
    import json as _json

    print("\n🎯 Step S1: Sniperモード最適化（勝率特化）...")
    sniper_logic = load_current_logic_sniper()
    baseline_wr  = sniper_logic.get("wr_raw", 0.0) if sniper_logic else 0.0

    # ── 現行条件の最新バックテスト + 採用後ライブ実績を毎回再計算 ────
    refreshed_stats = compute_current_sniper_backtest_stats(df, sniper_logic) if sniper_logic else None
    live_stats      = compute_live_sniper_stats(df, sniper_logic) if sniper_logic else None
    if refreshed_stats:
        print(f"  📈 現行条件の最新バックテスト: {int(refreshed_stats['n'])}件 "
              f"勝率{refreshed_stats['wr_raw']*100:.1f}% "
              f"平均{refreshed_stats['avg_raw']*100:.1f}%")
    if live_stats is not None:
        if live_stats.get("n", 0) > 0:
            print(f"  📊 採用日以降のライブ実績: {int(live_stats['n'])}件 "
                  f"勝率{live_stats['wr_raw']*100:.1f}% "
                  f"平均{live_stats['avg_raw']*100:.1f}%")
        else:
            print("  📊 採用日以降のライブ実績: 該当シグナルなし")

    # 統計だけリフレッシュして保存（updated_at は据え置き → ライブ集計の起点を維持）
    # --dry-run はファイル変更を伴わないため、メモリ上の baseline_wr のみ最新化する。
    if sniper_logic and refreshed_stats and refreshed_stats.get("n", 0) > 0:
        if not args.dry_run:
            save_current_logic_sniper(
                sniper_logic.get("conditions", []),
                sniper_logic.get("thresholds") or None,
                backtest_stats=refreshed_stats,
                preserve_updated_at=True,
            )
        baseline_wr = float(refreshed_stats.get("wr_raw", baseline_wr))

    # ── Sniper rescue mode 判定 ─────────────────────────────────
    raw_rescue, raw_rescue_reasons = detect_rescue_mode_sniper(refreshed_stats, live_stats)
    persist_rescue = (args.propose or not args.dry_run)
    rescue_mode, rescue_reasons, rescue_streak = resolve_sniper_rescue_mode(
        raw_rescue_reasons, refreshed_stats, live_stats,
        persist_state=persist_rescue,
    )
    if raw_rescue:
        print("  ⚠ Sniper rescue対象条件を検知:")
        for r in raw_rescue_reasons:
            print(f"    - {r}")
    if rescue_mode:
        print("  🧯 Sniper rescue mode 発動:")
        for r in rescue_reasons:
            print(f"    - {r}")
    elif raw_rescue and rescue_streak < RESCUE_REQUIRED_STREAK:
        print(f"  ℹ Sniper rescue streak {rescue_streak}/{RESCUE_REQUIRED_STREAK}: 様子見継続")

    # 現行Sniperが健全なら最適化をスキップ（rescue 中はスキップしない）
    if sniper_logic and not rescue_mode:
        sniper_n = int((refreshed_stats or {}).get("n", 0)
                       or sniper_logic.get("backtest", {}).get("n", 0))
        live_healthy = (
            live_stats is None
            or live_stats.get("n", 0) < SNIPER_RESCUE_TRIGGER_N
            or live_stats.get("wr_raw", 0) >= SNIPER_LIVE_HEALTH_WR
        )
        if (baseline_wr >= SNIPER_HEALTHY_SKIP_WR
                and sniper_n >= SNIPER_HEALTHY_SKIP_N_MIN
                and live_healthy):
            print(
                f"  ✅ Sniper健全のためスキップ: "
                f"勝率{baseline_wr*100:.1f}% ≥ {SNIPER_HEALTHY_SKIP_WR*100:.0f}%"
                f" / {sniper_n}件 ≥ {SNIPER_HEALTHY_SKIP_N_MIN}件"
            )
            if live_stats and live_stats.get("n", 0) >= SNIPER_RESCUE_TRIGGER_N:
                print(f"  ✅ ライブ実績も健全: "
                      f"{live_stats['wr_raw']*100:.1f}% ≥ {SNIPER_LIVE_HEALTH_WR*100:.0f}% "
                      f"(n={int(live_stats['n'])})")
            return

    # rescue mode 時は採用最低勝率を緩和
    wr_floor = SNIPER_RESCUE_WR_MIN if rescue_mode else SNIPER_WR_MIN
    valid_floor = wr_floor * 0.85

    # Walk-forward分割（70/30）
    df_sorted = df.sort_values("date").reset_index(drop=True)
    wf_split  = int(len(df_sorted) * 0.7)
    df_train  = df_sorted.iloc[:wf_split].copy()
    df_valid  = df_sorted.iloc[wf_split:].copy()
    print(f"  Walk-forward: train {len(df_train)}件 / validation {len(df_valid)}件"
          + ("  [rescue mode]" if rescue_mode else ""))

    cands = search_combinations_sniper(df_train.copy(), wr_floor=wr_floor)
    print(f"  勝率{wr_floor*100:.0f}%以上クリア(train): {len(cands)}通り")
    if not cands:
        print("  ✅ Sniper: 適合ロジックなし。現行を維持。")
        if rescue_mode and (args.propose or not args.dry_run):
            notify_discord_sniper_rescue_no_candidate(
                refreshed_stats, live_stats, rescue_reasons, len(df)
            )
        return

    # Walk-forward validation
    wf_validated = []
    for wr, n, combo, st6_train in cands[:50]:
        conds_in_valid = [c for c in combo if c in df_valid.columns]
        if len(conds_in_valid) < len(combo):
            continue
        scores_v = sum(df_valid[c].astype(int) for c in conds_in_valid)
        s6_v = df_valid[scores_v == 6]
        if len(s6_v) < 3:
            continue
        st6_v = calc_stats(s6_v)
        if st6_v["wr_raw"] >= valid_floor:
            wf_validated.append((wr, n, combo, st6_train, st6_v))
    print(f"  Walk-forward 通過: {len(wf_validated)}/{min(50, len(cands))}通り")
    if not wf_validated:
        print("  ✅ Sniper: Walk-forward 通過なし。現行を維持。")
        if rescue_mode and (args.propose or not args.dry_run):
            notify_discord_sniper_rescue_no_candidate(
                refreshed_stats, live_stats, rescue_reasons, len(df)
            )
        return

    best_wr, best_n, best_combo, _, st6_valid = wf_validated[0]

    # 全データで最終評価
    scores_full = sum(df[c].astype(int) for c in best_combo if c in df.columns)
    s6_full = df[scores_full == 6]
    st6_full = calc_stats(s6_full)
    print(f"  最良条件: {'+'.join(best_combo)}")
    print(f"  Sniper全体: {st6_full['n']}件 勝率{st6_full['wr_raw']*100:.1f}%"
          f" 平均{st6_full['avg_raw']*100:.1f}%")
    print(f"  Sniper検証: {st6_valid['n']}件 勝率{st6_valid['wr_raw']*100:.1f}%"
          f" 平均{st6_valid['avg_raw']*100:.1f}%")

    # Sniperは勝率特化のため、現行勝率をstrictに上回らない候補は通知しない。
    # rescue mode 中は現行が劣化しているので、baseline 超えは要求しない（候補側の
    # 全体勝率が rescue 下限 SNIPER_RESCUE_WR_MIN を満たしていれば通す）。
    if sniper_logic and not rescue_mode:
        if st6_full["wr_raw"] <= baseline_wr + SNIPER_WR_EPS:
            print(
                f"  ✅ Sniper: 勝率が現行以下 "
                f"({st6_full['wr_raw']*100:.1f}% ≤ {baseline_wr*100:.1f}%) のため更新しません。"
            )
            return
    elif rescue_mode:
        if st6_full["wr_raw"] < SNIPER_RESCUE_WR_MIN:
            print(
                f"  ✅ Sniper(rescue): 勝率が下限未満 "
                f"({st6_full['wr_raw']*100:.1f}% < {SNIPER_RESCUE_WR_MIN*100:.0f}%) "
                f"のため更新しません。"
            )
            return
        print(
            f"  🧯 Sniper(rescue): 現行劣化のため baseline 超え条件を免除 "
            f"(候補 {st6_full['wr_raw']*100:.1f}% / 現行 {baseline_wr*100:.1f}%)"
        )

    # 現行と同一条件、または条件が違っても対象シグナル集合が同一なら更新しない
    if sniper_logic:
        current_sniper_conditions = sniper_logic.get("conditions", [])
        current_sniper_thresholds = sniper_logic.get("thresholds", {}) or {}
        current_sniper_sig = logic_signature(
            "A", current_sniper_conditions, current_sniper_thresholds
        )
        candidate_sniper_sig = logic_signature("A", best_combo, {})
        if current_sniper_sig == candidate_sniper_sig:
            print("  ✅ Sniper: 条件が現行と同一。更新しません。")
            return

        current_targets = all_pass_signal_indices(
            df, current_sniper_conditions, current_sniper_thresholds
        )
        candidate_targets = set(s6_full.index.tolist())
        if candidate_targets == current_targets:
            print("  ✅ Sniper: 条件は異なるが抽出結果が現行と同一のため更新しません。")
            return

    sniper_code = build_func_sniper(best_combo, st6_full, len(df))

    # ── --propose: pending保存 + Discord通知 ────────────────────
    if args.propose:
        def _to_jsonable(d):
            return {k: float(v) if hasattr(v, 'item') else v for k, v in d.items()}
        _pending = {
            "conditions":  best_combo,
            "thresholds":  {},
            "sniper_code": sniper_code,
            "stats":       _to_jsonable(st6_full),
            "validation_stats": _to_jsonable(st6_valid),
            "proposed_at": datetime.utcnow().isoformat() + "Z"
        }
        with open(SNIPER_PENDING_PATH, "w", encoding="utf-8") as _f:
            _json.dump(_pending, _f, ensure_ascii=False, indent=2)
        print(f"  📋 pending_logic_sniper.json に保存しました")
        notify_discord_sniper_approval(best_combo, st6_full, baseline_wr, {})
        print("  ✅ Discord に Sniper承認リクエストを送信しました")
        return

    # ── --dry-run: 候補表示のみ ──────────────────────────────────
    if args.dry_run:
        print(f"  🔍 Sniper Dry-run: 更新・デプロイをスキップ")
        print(f"\n  ── Sniperシグナル候補（{len(s6_full)}件）──")
        print(f"  {'日付':<12} {'銘柄':<8} {'社名':<24} {'騰落率':>7}")
        for _, row in s6_full.sort_values("date", ascending=False).iterrows():
            sign = "+" if row["perf_5bd"] >= 0 else ""
            print(f"  {row['date']:<12} {row['symbol']:<8} {row['name']:<24}"
                  f" {sign}{row['perf_5bd']*100:.1f}%")
        return

    # ── 通常実行: screener.js 更新（デプロイは main() が担当）──────
    if not args.yes:
        try:
            ans = input(
                f"  Sniper: {'+'.join(best_combo)} 勝率{st6_full['wr_raw']*100:.1f}%"
                f" を更新しますか？ [y/N] → "
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "n"
        if ans != "y":
            print("  Sniper更新をキャンセルしました。")
            return

    if update_screener_js_sniper(sniper_code):
        print("  ✅ calculateScoreSniper() 更新完了")
        save_current_logic_sniper(best_combo, {}, backtest_stats=st6_full)
    else:
        print("  ❌ calculateScoreSniper() 更新失敗")


# ══════════════════════════════════════════════════════════════
# Moonshotモード最適化（平均リターン特化・評価日固定）
# ══════════════════════════════════════════════════════════════
def _moonshot_evaluate_one(df, perf_col):
    """指定の perf_col で Moonshot 探索 + Walk-forward 検証を行い、
    最良候補（avg_raw 最大）を1つ返す。なければ None。"""
    df_use = df.dropna(subset=[perf_col]).copy()
    if df_use.empty or len(df_use) < MOONSHOT_N_MIN * 2:
        print(f"  [{perf_col}] データ不足: {len(df_use)}件")
        return None

    df_sorted = df_use.sort_values("date").reset_index(drop=True)
    wf_split  = int(len(df_sorted) * 0.7)
    df_train  = df_sorted.iloc[:wf_split].copy()
    df_valid  = df_sorted.iloc[wf_split:].copy()
    print(f"  [{perf_col}] Walk-forward: train {len(df_train)}件 / valid {len(df_valid)}件")

    cands, _ = search_combinations_moonshot(df_train, perf_col)
    print(f"  [{perf_col}] 平均{MOONSHOT_AVG_MIN*100:.0f}%以上クリア(train): {len(cands)}通り")
    if not cands:
        return None

    # Walk-forward 検証: 検証側でも avg_raw が MOONSHOT_AVG_MIN × 0.7 以上を維持
    # 上位50だと訓練に過適合した尖った候補ばかりが検証で全滅するので、
    # プールを 1000 まで広げて「訓練15%ジャスト前後の素直な候補」も検証対象に入れる。
    MOONSHOT_VALID_POOL = 1000
    valid_floor = MOONSHOT_AVG_MIN * 0.7
    wf_validated = []
    for avg_t, n_t, combo, st_t in cands[:MOONSHOT_VALID_POOL]:
        conds_in_valid = [c for c in combo if c in df_valid.columns]
        if len(conds_in_valid) < len(combo):
            continue
        v_mask = df_valid[conds_in_valid].astype(bool).all(axis=1)
        s6_v = df_valid[v_mask].dropna(subset=[perf_col])
        if len(s6_v) < 2:
            continue
        avg_v = float(s6_v[perf_col].mean())
        n_v   = int(len(s6_v))
        wr_v  = float((s6_v[perf_col] > 0).mean())
        if avg_v >= valid_floor:
            wf_validated.append((avg_t, n_t, combo, st_t,
                                 {"n": n_v, "avg_raw": avg_v, "wr_raw": wr_v}))
    print(f"  [{perf_col}] Walk-forward 通過: {len(wf_validated)}/{min(MOONSHOT_VALID_POOL, len(cands))}通り")
    if not wf_validated:
        return None

    # 全データで最終評価（avg_raw / wr_raw / n）
    best_avg_t, best_n_t, best_combo, _, st_v = wf_validated[0]
    df_full = df.dropna(subset=[perf_col]).copy()
    f_mask = df_full[best_combo].astype(bool).all(axis=1)
    s6_full = df_full[f_mask]
    if len(s6_full) < MOONSHOT_N_MIN:
        return None
    avg_full = float(s6_full[perf_col].mean())
    wr_full  = float((s6_full[perf_col] > 0).mean())
    st_full  = {"n": int(len(s6_full)), "avg_raw": avg_full, "wr_raw": wr_full}
    return {
        "combo":   best_combo,
        "stats":   st_full,
        "valid":   st_v,
        "s6_full": s6_full,
        "perf_col": perf_col,
    }


def _run_moonshot_optimization(df, args):
    """Moonshotモード最適化（平均リターン特化・評価日1つ固定）。
    --propose: pending_logic_moonshot.json 保存 + Discord通知。
    --dry-run: 候補表示のみ。
    通常実行: screener.js + current_logic_moonshot.json を直接更新。
    """
    import json as _json

    print("\n🌙 Step M1: Moonshotモード最適化（平均リターン特化）...")
    moonshot_logic = load_current_logic_moonshot()
    baseline_avg = (moonshot_logic.get("avg_raw", 0.0) if moonshot_logic else 0.0)

    # 評価日: 既存JSONがあれば固定、なければ [10/20/40] 全部試して最良採用
    if moonshot_logic and moonshot_logic.get("eval_days") in (10, 20, 40):
        fixed_eval = int(moonshot_logic["eval_days"])
        eval_candidates = [fixed_eval]
        print(f"  評価日 固定: {fixed_eval}BD (current_logic_moonshot.json から)")
    else:
        eval_candidates = list(MOONSHOT_EVAL_DAYS_CANDIDATES)
        print(f"  評価日 未確定 → 初回最適化: {eval_candidates} を並列評価")

    best = None
    for eval_days in eval_candidates:
        perf_col = f"perf_{eval_days}bd"
        if perf_col not in df.columns:
            print(f"  [{perf_col}] カラムが DataFrame に存在しません — スキップ")
            continue
        result = _moonshot_evaluate_one(df, perf_col)
        if result is None:
            continue
        result["eval_days"] = eval_days
        st = result["stats"]
        print(f"  [{perf_col}] 候補★全: {st['n']}件 平均{st['avg_raw']*100:+.1f}%"
              f" 勝率{st['wr_raw']*100:.1f}% {'+'.join(result['combo'])}")
        if best is None or st["avg_raw"] > best["stats"]["avg_raw"]:
            best = result

    if best is None:
        print("  ✅ Moonshot: 適合ロジックなし。現行を維持。")
        return

    best_combo = best["combo"]
    st_full    = best["stats"]
    st_valid   = best["valid"]
    eval_days  = best["eval_days"]
    s6_full    = best["s6_full"]
    perf_col   = best["perf_col"]
    print(f"\n  🌙 最良: 評価日 {eval_days}BD / {'+'.join(best_combo)}")
    print(f"     全件: {st_full['n']}件 平均{st_full['avg_raw']*100:+.1f}%"
          f" 勝率{st_full['wr_raw']*100:.1f}%")
    print(f"     検証: {st_valid['n']}件 平均{st_valid['avg_raw']*100:+.1f}%"
          f" 勝率{st_valid['wr_raw']*100:.1f}%")

    # 採用ゲート①: 平均が MOONSHOT_AVG_MIN 以上
    if st_full["avg_raw"] < MOONSHOT_AVG_MIN:
        print(f"  ✅ Moonshot: 平均 {st_full['avg_raw']*100:+.1f}% < {MOONSHOT_AVG_MIN*100:.0f}% のため見送り")
        return

    # 採用ゲート②: 現行平均を strict に上回る
    if moonshot_logic and st_full["avg_raw"] <= baseline_avg + MOONSHOT_AVG_EPS:
        print(
            f"  ✅ Moonshot: 平均が現行以下 "
            f"({st_full['avg_raw']*100:+.1f}% ≤ {baseline_avg*100:+.1f}%) のため更新しません。"
        )
        return

    # 採用ゲート③: 現行と同一条件 or 抽出シグナル集合が同一なら更新しない
    if moonshot_logic:
        current_conds = moonshot_logic.get("conditions", [])
        current_ths   = moonshot_logic.get("thresholds", {}) or {}
        if logic_signature("A", current_conds, current_ths) == logic_signature("A", best_combo, {}):
            print("  ✅ Moonshot: 条件が現行と同一。更新しません。")
            return
        # 抽出集合の比較は perf_col 由来の df 全体で行う
        df_full = df.dropna(subset=[perf_col])
        cur_targets = set()
        if all(c in df_full.columns for c in current_conds) and current_conds:
            cur_mask = df_full[current_conds].astype(bool).all(axis=1)
            cur_targets = set(df_full[cur_mask].index.tolist())
        cand_targets = set(s6_full.index.tolist())
        if cur_targets and cand_targets == cur_targets:
            print("  ✅ Moonshot: 条件は異なるが抽出結果が現行と同一のため更新しません。")
            return

    moonshot_code = build_func_moonshot(best_combo, st_full, eval_days, len(df))

    # ── --propose: pending保存 + Discord通知 ────────────────────
    if args.propose:
        def _to_jsonable(d):
            return {k: float(v) if hasattr(v, 'item') else v for k, v in d.items()}
        _pending = {
            "conditions":      best_combo,
            "thresholds":      {},
            "eval_days":       int(eval_days),
            "moonshot_code":   moonshot_code,
            "stats":           _to_jsonable(st_full),
            "validation_stats": _to_jsonable(st_valid),
            "proposed_at":     datetime.utcnow().isoformat() + "Z"
        }
        with open(MOONSHOT_PENDING_PATH, "w", encoding="utf-8") as _f:
            _json.dump(_pending, _f, ensure_ascii=False, indent=2)
        print(f"  📋 pending_logic_moonshot.json に保存しました")
        notify_discord_moonshot_approval(best_combo, st_full, eval_days, baseline_avg, {})
        print("  ✅ Discord に Moonshot承認リクエストを送信しました")
        return

    # ── --dry-run: 候補表示のみ ──────────────────────────────────
    if args.dry_run:
        print(f"  🔍 Moonshot Dry-run: 更新・デプロイをスキップ")
        print(f"\n  ── Moonshotシグナル候補（{len(s6_full)}件・評価日 {eval_days}BD）──")
        print(f"  {'日付':<12} {'銘柄':<8} {'社名':<24} {'リターン':>9}")
        for _, row in s6_full.sort_values("date", ascending=False).iterrows():
            sign = "+" if row[perf_col] >= 0 else ""
            print(f"  {row['date']:<12} {row['symbol']:<8} {row['name']:<24}"
                  f" {sign}{row[perf_col]*100:.1f}%")
        return

    # ── 通常実行: screener.js 更新（デプロイは main() が担当）──────
    if not args.yes:
        try:
            ans = input(
                f"  Moonshot: {'+'.join(best_combo)} 平均{st_full['avg_raw']*100:+.1f}%"
                f" (評価日 {eval_days}BD) を更新しますか？ [y/N] → "
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "n"
        if ans != "y":
            print("  Moonshot更新をキャンセルしました。")
            return

    if update_screener_js_moonshot(moonshot_code):
        print("  ✅ calculateScoreMoonshot() 更新完了")
        save_current_logic_moonshot(best_combo, eval_days, thresholds=None,
                                     backtest_stats=st_full)
    else:
        print("  ❌ calculateScoreMoonshot() 更新失敗")


# ══════════════════════════════════════════════════════════════
# +X% 閾値スイープ（オーケストレータ）
# ══════════════════════════════════════════════════════════════
def _run_threshold_sweep(args):
    """各閾値で自身を --dry-run --win-threshold X として再帰実行し、
    出力をパースして比較表を表示する。--propose 併用時はゲートをクリアした
    閾値の中から最良を自動採用し、--propose --yes --win-threshold X として再実行する。"""
    import subprocess as _sp
    import re as _re

    sweep_arg = args.win_threshold_sweep

    # 閾値リストをパース
    try:
        thresholds = [float(x.strip()) for x in sweep_arg.split(",") if x.strip()]
    except ValueError:
        print(f"❌ --win-threshold-sweep の値が不正: {sweep_arg}")
        sys.exit(1)
    if not thresholds:
        print(f"❌ --win-threshold-sweep に閾値が指定されていません")
        sys.exit(1)
    for th in thresholds:
        if not (0.01 <= th <= 0.50):
            print(f"❌ 閾値 {th} は範囲外 (0.01〜0.50)")
            sys.exit(1)

    auto_propose = bool(args.propose)
    print(f"{'='*62}")
    print(f"  📊 +X% 閾値スイープ実行 — {len(thresholds)}個の閾値を比較")
    print(f"{'='*62}")
    print(f"  対象閾値: {', '.join(f'±{th*100:.1f}%' for th in thresholds)}")
    if auto_propose:
        print(f"  モード: 自動採用（ゲートクリアした最良閾値で --propose 実行）")
    else:
        print(f"  モード: 分析のみ（--propose 併用なし）")

    self_path = os.path.abspath(__file__)
    results = []

    for i, th in enumerate(thresholds, 1):
        print(f"\n{'='*62}")
        print(f"  [{i}/{len(thresholds)}] THRESHOLD = ±{th*100:.1f}% (dry-run)")
        print(f"{'='*62}\n")

        cmd = [sys.executable, self_path, "--dry-run", "--win-threshold", str(th)]
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"

        captured = []
        try:
            proc = _sp.Popen(cmd, stdout=_sp.PIPE, stderr=_sp.STDOUT,
                             text=True, encoding="utf-8", errors="replace",
                             env=env, bufsize=1)
            for line in proc.stdout:
                print(line, end="")
                captured.append(line)
            proc.wait()
            if proc.returncode != 0:
                print(f"⚠ subprocess returned exit code {proc.returncode}")
        except Exception as e:
            print(f"❌ subprocess error: {e}")
            results.append({"threshold": th, "error": str(e)})
            continue

        summary = _parse_sweep_output("".join(captured), th)
        results.append(summary)

    _print_sweep_summary(results)

    # ── 自動採用: --propose 併用時、ゲートクリアした閾値の最良を採用 ──
    if not auto_propose:
        return

    ok_results = [r for r in results if r.get("verdict") == "OK"]
    if not ok_results:
        print(f"\n💡 自動採用スキップ: ゲートをクリアした閾値がありませんでした")
        print(f"   pending_logic.json は作成されません")
        # 候補なしでも Bot を再起動して統計キャッシュ（refreshStats）を更新する
        if not args.dry_run:
            print(f"\n🔄 候補なし → SCP + pm2 restart で Bot を更新します")
            deploy()
        return

    # 採用基準: best_wr 降順 → 閾値昇順（低閾値優先で安全側）
    best = max(ok_results, key=lambda r: (r.get("best_wr", 0.0), -r["threshold"]))
    print(f"\n{'='*62}")
    print(f"  🎯 自動採用: ±{best['threshold']*100:.1f}%")
    print(f"{'='*62}")
    print(f"  候補★6: {best.get('best_n', '?')}件 "
          f"勝率{best.get('best_wr', 0):.1f}% 平均{best.get('best_avg', 0):+.1f}%")
    print(f"  条件: {best.get('best_combo', '?')}")
    print(f"  → --propose --yes --win-threshold {best['threshold']} を実行します")

    cmd = [sys.executable, self_path, "--propose", "--win-threshold", str(best['threshold'])]
    if args.yes:
        cmd.append("--yes")
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    try:
        proc = _sp.Popen(cmd, stdout=_sp.PIPE, stderr=_sp.STDOUT,
                         text=True, encoding="utf-8", errors="replace",
                         env=env, bufsize=1)
        for line in proc.stdout:
            print(line, end="")
        proc.wait()
        if proc.returncode != 0:
            print(f"⚠ propose subprocess returned exit code {proc.returncode}")
            sys.exit(proc.returncode)
    except Exception as e:
        print(f"❌ propose subprocess error: {e}")
        sys.exit(1)


def _parse_sweep_output(output, threshold):
    """subprocess出力からサマリ情報を抽出する。
    出力フォーマットが変わったら正規表現も更新が必要。"""
    import re as _re
    summary = {"threshold": threshold}

    # 現行★6: 26件 勝率57.7% 平均9.07% 上昇6件 下落0件
    m = _re.search(
        r"現行★6:\s*(\d+)件\s*勝率([\d.]+)%\s*平均([+-]?[\d.]+)%\s*上昇([\d.]+)件\s*下落([\d.]+)件",
        output)
    if m:
        summary["base_n"] = int(m.group(1))
        summary["base_wr"] = float(m.group(2))
        summary["base_avg"] = float(m.group(3))
        summary["base_up"] = int(float(m.group(4)))
        summary["base_down"] = int(float(m.group(5)))

    # +X%以上: 87件 / 全体: 1629件 (5.3%)
    m = _re.search(
        r"\+[\d.]+%以上:\s*(\d+)件\s*/\s*全体:\s*(\d+)件\s*\(([\d.]+)%\)",
        output)
    if m:
        summary["winx_n"] = int(m.group(1))
        summary["total_n"] = int(m.group(2))
        summary["winx_pct"] = float(m.group(3))

    # トップ候補: #1  A   69.2%  +14.0%   5件   2件  13件  ...  vol20+...+pre_down3
    m = _re.search(
        r"^\s*#1\s+([AB])\s+([\d.]+)%\s+([+-][\d.]+)%\s+(\d+)件\s+(\d+)件\s+(\d+)件.*?(\S+)\s*$",
        output, _re.MULTILINE)
    if m:
        summary["best_method"] = m.group(1)
        summary["best_wr"] = float(m.group(2))
        summary["best_avg"] = float(m.group(3))
        summary["best_up"] = int(m.group(4))
        summary["best_down"] = int(m.group(5))
        summary["best_n"] = int(m.group(6))
        summary["best_combo"] = m.group(7)

    # Lockbox 候補/現行 ★6 件数・勝率・平均
    m = _re.search(
        r"候補lockbox★6:\s*(\d+)件\s*勝率([\d.]+)%\s*平均([+-]?[\d.]+)%",
        output)
    if m:
        summary["lb_cand_n"] = int(m.group(1))
        summary["lb_cand_wr"] = float(m.group(2))
        summary["lb_cand_avg"] = float(m.group(3))
    m = _re.search(
        r"現行lockbox★6:\s*(\d+)件\s*勝率([\d.]+)%\s*平均([+-]?[\d.]+)%",
        output)
    if m:
        summary["lb_base_n"] = int(m.group(1))
        summary["lb_base_wr"] = float(m.group(2))
        summary["lb_base_avg"] = float(m.group(3))
    # Lockbox 詳細メッセージ
    m = _re.search(r"🔒 Lockbox OOS検証 — (✓ 通過|✗ 過学習検出)", output)
    if m:
        summary["lb_passed"] = (m.group(1) == "✓ 通過")
    m = _re.search(r"^\s*詳細:\s*(.+?)$", output, _re.MULTILINE)
    if m:
        summary["lb_detail"] = m.group(1).strip()

    # 採用判定（順序重要: skip_healthy → OK → 各種NG → no_cand → ?）
    if _re.search(r"現行ロジック健全のため最適化をスキップ", output):
        summary["verdict"] = "skip_healthy"
    elif _re.search(r"🔍 Dry-run: 更新・デプロイをスキップ", output) and \
         _re.search(r"採用予定:", output):
        # dry-runでゲート全てクリア = 採用される候補が見つかった
        summary["verdict"] = "OK"
        # 採用予定の閾値変更を捕捉
        m = _re.search(r"検証★6:\s*(\d+)件\s*勝率([\d.]+)%\s*平均([+-]?[\d.]+)%", output)
        if m:
            summary["valid_n"] = int(m.group(1))
            summary["valid_wr"] = float(m.group(2))
            summary["valid_avg"] = float(m.group(3))
    elif _re.search(r"✅\s*採用!", output):
        # 実デプロイフローの採用完了（dry-runではないが念のため）
        summary["verdict"] = "OK"
    elif _re.search(r"品質条件未達。更新しません", output):
        summary["verdict"] = "NG"
        summary["ng_kind"] = "quality"
    elif _re.search(r"Lockbox\(OOS\)で過学習を検出", output):
        summary["verdict"] = "NG"
        summary["ng_kind"] = "lockbox"
    elif _re.search(r"Bootstrap CI[:：]?\s*下限", output):
        summary["verdict"] = "NG"
        summary["ng_kind"] = "bootstrap"
    elif _re.search(r"K-Fold CV で局所過学習を検出", output):
        summary["verdict"] = "NG"
        summary["ng_kind"] = "kfold"
    elif _re.search(r"条件・閾値が現行と同一", output):
        summary["verdict"] = "NG"
        summary["ng_kind"] = "same"
    elif _re.search(r"条件は異なるが抽出結果が現行と同一", output):
        summary["verdict"] = "NG"
        summary["ng_kind"] = "same_result"
    elif _re.search(r"現行ロジックが最良。更新しません", output):
        summary["verdict"] = "NG"
        summary["ng_kind"] = "baseline_best"
    elif _re.search(r"勝率改善が軽微", output):
        # 通常モードの WR_SIGNIFICANT_IMPROVEMENT 未満で却下されたケース
        summary["verdict"] = "NG"
        summary["ng_kind"] = "minor"
    elif _re.search(r"alerts_rawベース★6勝率が現行以下", output):
        summary["verdict"] = "NG"
        summary["ng_kind"] = "ar_wr"
    elif _re.search(r"全件★6が不足|Step 5a.*候補クリア\(train/\w+\): 0通り", output):
        # 注: 単独「候補なし」は rescue mode の副作用メッセージ（"代替候補なし"）と
        # 衝突するため使わない。具体的なメッセージのみで判定。
        summary["verdict"] = "no_cand"
    else:
        summary["verdict"] = "?"

    # 採用NG時の最初の ✗ 理由（品質条件未達の場合のみ詳細化）
    if summary.get("verdict") == "NG" and summary.get("ng_kind") == "quality":
        m = _re.search(r"^\s*✗\s+(通常条件①|通常条件②|品質:[^\n]+)", output, _re.MULTILINE)
        if m:
            reason = m.group(1)
            if "通常条件①" in reason:
                summary["ng_reason"] = "composite"
            elif "通常条件②" in reason:
                summary["ng_reason"] = "勝率"
            elif "★6件数" in reason:
                summary["ng_reason"] = "★6件数"
            elif "★6勝率" in reason:
                summary["ng_reason"] = "★6勝率"
            elif "★6平均" in reason:
                summary["ng_reason"] = "★6平均"
            else:
                summary["ng_reason"] = reason[:20]
    elif summary.get("verdict") == "NG" and summary.get("ng_kind") == "minor":
        # 軽微スキップは改善幅を含めて表示（例: 軽微+3.1pp）
        m_imp = _re.search(r"勝率改善が軽微（\+([\d.]+)pt", output)
        if m_imp:
            summary["ng_reason"] = f"軽微+{m_imp.group(1)}pp"
        else:
            summary["ng_reason"] = "軽微"
    elif summary.get("verdict") == "NG":
        # quality 以外のNGは ng_kind をそのまま reason として表示
        summary["ng_reason"] = summary.get("ng_kind", "?")

    return summary


def _print_sweep_summary(results):
    """スイープ結果の比較表を表示"""
    print(f"\n\n{'='*100}")
    print(f"  📊 +X% 閾値スイープ比較結果")
    print(f"{'='*100}")

    # ヘッダー
    print(f"  {'閾値':<8} {'+X%母数':<10} {'★6件数':<8} {'★6勝率':<8} {'★6平均':<9} "
          f"{'上昇/下落':<11} {'候補★6':<22} {'判定':<14} {'候補条件'}")
    print(f"  {'-'*8} {'-'*10} {'-'*8} {'-'*8} {'-'*9} {'-'*11} {'-'*22} {'-'*14} {'-'*30}")

    for r in results:
        if "error" in r:
            print(f"  ±{r['threshold']*100:>4.1f}%  ERROR: {r['error']}")
            continue

        th_str = f"±{r['threshold']*100:.1f}%"
        winx = f"{r.get('winx_n', '-')}件" if 'winx_n' in r else "-"
        base_n_str = f"{r.get('base_n', '-')}件" if 'base_n' in r else "-"
        base_wr_str = f"{r.get('base_wr', 0):.1f}%" if 'base_wr' in r else "-"
        base_avg_str = f"{r.get('base_avg', 0):+.1f}%" if 'base_avg' in r else "-"
        up_down = f"{r.get('base_up', '-')}/{r.get('base_down', '-')}" if 'base_up' in r else "-"
        if 'best_wr' in r:
            best = f"{r['best_n']}件 {r['best_wr']:.1f}%/{r['best_avg']:+.1f}%"
        else:
            best = "-"
        verdict = r.get('verdict', '?')
        if verdict == "NG" and r.get('ng_reason'):
            verdict_str = f"✗ {r['ng_reason']}"
        elif verdict == "OK":
            verdict_str = "✓ OK"
        elif verdict == "skip_healthy":
            verdict_str = "skip:健全"
        elif verdict == "no_cand":
            verdict_str = "候補なし"
        else:
            verdict_str = verdict
        combo = r.get('best_combo', '-')
        if len(combo) > 60:
            combo = combo[:57] + "..."
        print(f"  {th_str:<8} {winx:<10} {base_n_str:<8} {base_wr_str:<8} {base_avg_str:<9} "
              f"{up_down:<11} {best:<22} {verdict_str:<14} {combo}")

    print(f"{'='*100}")
    print(f"  ※ ★6件数/勝率/平均: 現行ロジックの★6セットの統計 — 閾値非依存")
    print(f"  ※ 上昇/下落: ★6のうち perf > +X% / < -X% の件数 — ここだけ閾値依存")
    print(f"  ※ +X%母数: 全データ中で perf > +X% の銘柄数（方式Bリフト分析用）")
    print(f"  ※ 候補★6: 各閾値で見つかった上位候補の (件数 勝率/平均)")
    print(f"  ※ 判定: ✓OK=採用基準クリア / ✗XXX=不採用(理由) / skip:健全=現行健全のためスキップ")

    # Lockbox 詳細ブロック（候補が Lockbox(OOS) に到達した閾値のみ表示）
    lb_rows = [r for r in results if "lb_cand_n" in r]
    if lb_rows:
        print(f"\n🔒 Lockbox(OOS) 詳細 — 候補が訓練+検証ゲートを通過後の真の未見データ評価:")
        print(f"  {'閾値':<8} {'候補lockbox':<28} {'現行lockbox':<28} {'判定/詳細'}")
        print(f"  {'-'*8} {'-'*28} {'-'*28} {'-'*40}")
        for r in lb_rows:
            th_str = f"±{r['threshold']*100:.1f}%"
            cand = f"{r['lb_cand_n']}件 勝率{r['lb_cand_wr']:.1f}% 平均{r['lb_cand_avg']:+.1f}%"
            base = (f"{r['lb_base_n']}件 勝率{r['lb_base_wr']:.1f}% 平均{r['lb_base_avg']:+.1f}%"
                    if 'lb_base_n' in r else "-")
            mark = "✓" if r.get('lb_passed') else "✗"
            detail = r.get('lb_detail', '-')
            if len(detail) > 40:
                detail = detail[:37] + "..."
            print(f"  {th_str:<8} {cand:<28} {base:<28} {mark} {detail}")


# ══════════════════════════════════════════════════════════════
# メイン
# ══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", "--no-apply", action="store_true")
    parser.add_argument("--yes", "-y", action="store_true", help="確認プロンプトをスキップして自動デプロイ")
    parser.add_argument("--propose", action="store_true",
                        help="候補をpending_logic.jsonに保存してDiscord通知（デプロイしない）")
    parser.add_argument("--apply-pending", action="store_true",
                        help="pending_logic.jsonの承認済み候補をデプロイ")
    parser.add_argument("--composite-variant", default="rate_adjusted",
                        choices=["rate_adjusted", "snr", "legacy"],
                        help="composite計算方式 (default: rate_adjusted)")
    parser.add_argument("--baseline-decay", type=float, default=None,
                        help="ベースライン採用閾値 (default: 1.0)")
    parser.add_argument("--strict-wr", dest="strict_wr", action="store_true", default=None,
                        help="勝率フロアを厳格化: >= → > (モジュール定数を上書き)")
    parser.add_argument("--no-strict-wr", dest="strict_wr", action="store_false",
                        help="勝率フロアを緩和: > → >= (モジュール定数を上書き)")
    parser.add_argument("--wr-floor", type=float, default=0.0,
                        help="勝率絶対下限 (例: 0.55、default: 0.0=無効)")
    parser.add_argument("--win-threshold", type=float, default=None,
                        help="単発の +X%% 閾値上書き (例: 0.07)。"
                             "Method Bリフト分析・composite・採用ゲート全てに伝播。"
                             "--win-threshold-sweep と併用不可")
    parser.add_argument("--win-threshold-sweep", default=None,
                        help="カンマ区切り閾値リスト (例: 0.05,0.07,0.08,0.10)。"
                             "各値で自身を --dry-run --win-threshold X として再実行し比較表を表示。"
                             "実ファイル更新・デプロイは行わない")
    args = parser.parse_args()
    global COMPOSITE_VARIANT, BASELINE_DECAY, STRICT_WR, WR_FLOOR
    global WIN_THRESHOLD, LOSE_THRESHOLD
    COMPOSITE_VARIANT = args.composite_variant
    if args.baseline_decay is not None:
        BASELINE_DECAY = args.baseline_decay
    if args.strict_wr is not None:
        STRICT_WR = args.strict_wr
    WR_FLOOR  = args.wr_floor

    # --win-threshold と --win-threshold-sweep は排他
    if args.win_threshold is not None and args.win_threshold_sweep is not None:
        print("❌ --win-threshold と --win-threshold-sweep は併用できません")
        sys.exit(1)

    # --win-threshold-sweep: 各閾値で自身を再帰実行
    # --propose 併用時はゲートクリアした最良閾値を自動採用してpending_logic.json保存まで実行
    if args.win_threshold_sweep is not None:
        _run_threshold_sweep(args)
        return

    # --win-threshold: globals を上書きして通常フローへ
    if args.win_threshold is not None:
        if not (0.01 <= args.win_threshold <= 0.50):
            print(f"❌ --win-threshold は 0.01〜0.50 の範囲で指定してください (指定値: {args.win_threshold})")
            sys.exit(1)
        WIN_THRESHOLD  = args.win_threshold
        LOSE_THRESHOLD = -args.win_threshold
        print(f"⚙️ +X% 閾値オーバーライド: ±{args.win_threshold*100:.1f}%")

    # ─── --apply-pending: 承認済みロジックをデプロイして終了 ───────
    if args.apply_pending:
        import json as _pjson, shutil, time as _time, glob as _glob
        _has_main     = os.path.exists(PENDING_LOGIC_PATH)
        _has_sniper   = os.path.exists(SNIPER_PENDING_PATH)
        # マスタースイッチがOFFの間は pending_logic_moonshot.json が残っていても
        # apply 対象に入れない（誤って一緒にデプロイされるのを防ぐ）。
        _has_moonshot = (MOONSHOT_AUTO_OPTIMIZE_ENABLED
                         and os.path.exists(MOONSHOT_PENDING_PATH))
        if (not MOONSHOT_AUTO_OPTIMIZE_ENABLED
                and os.path.exists(MOONSHOT_PENDING_PATH)):
            print("ℹ️ pending_logic_moonshot.json は存在しますが "
                  "MOONSHOT_AUTO_OPTIMIZE_ENABLED=False のためスキップします。")
        if not _has_main and not _has_sniper and not _has_moonshot:
            print("ℹ️ pending_logic.json / pending_logic_sniper.json / pending_logic_moonshot.json"
                  " いずれも見つかりません。")
            print("   承認待ちロジックがないため、デプロイはスキップします。")
            return

        _method = _combo = _ths = _code = _st6 = _st5 = _st4 = _base = _n_total = None

        if _has_main:
            with open(PENDING_LOGIC_PATH, "r", encoding="utf-8") as _pf:
                _p = _pjson.load(_pf)
            _method  = _p["method"]
            _combo   = _p["conditions"]
            _ths     = _p.get("thresholds", {})
            _code    = _p["screener_code"]
            _st6     = _p["stats6"]
            _st5     = _p["stats5"]
            _st4     = _p["stats4"]
            _base    = _p.get("baseline", {})
            _n_total = _p.get("n_total", 0)
            print("=" * 62)
            print("承認済みロジックをデプロイします")
            print("=" * 62)
            print(f"  proposed_at : {_p.get('proposed_at', '不明')}")
            print(f"  方式{_method}: 勝率{_st6['wr_raw']*100:.1f}% 平均{_st6['avg_raw']*100:.1f}%"
                  f" ★6 {int(_st6['n'])}件")
        if _has_sniper:
            with open(SNIPER_PENDING_PATH, "r", encoding="utf-8") as _sf:
                _sp = _pjson.load(_sf)
            _sp_stats = _sp["stats"]
            print(f"  Sniper pending: 勝率{_sp_stats['wr_raw']*100:.1f}%"
                  f" 平均{_sp_stats['avg_raw']*100:.1f}% {int(_sp_stats['n'])}件")

            _current_sniper = load_current_logic_sniper()
            if _current_sniper:
                _current_sniper_wr = float(_current_sniper.get("wr_raw", 0.0))
                _pending_sniper_wr = float(_sp_stats.get("wr_raw", 0.0))
                if _pending_sniper_wr <= _current_sniper_wr + SNIPER_WR_EPS:
                    print(
                        f"  ✅ Sniper pending: 勝率が現行以下 "
                        f"({_pending_sniper_wr*100:.1f}% ≤ {_current_sniper_wr*100:.1f}%) "
                        "のため適用しません。"
                    )
                    _has_sniper = False

        if _has_moonshot:
            with open(MOONSHOT_PENDING_PATH, "r", encoding="utf-8") as _mf:
                _mp = _pjson.load(_mf)
            _mp_stats = _mp["stats"]
            _mp_eval  = _mp.get("eval_days")
            print(f"  Moonshot pending: 平均{_mp_stats['avg_raw']*100:+.1f}%"
                  f" 勝率{_mp_stats['wr_raw']*100:.1f}% {int(_mp_stats['n'])}件"
                  f" / 評価日 {_mp_eval}BD")

            _current_moonshot = load_current_logic_moonshot()
            if _current_moonshot:
                _current_moonshot_avg = float(_current_moonshot.get("avg_raw", 0.0))
                _pending_moonshot_avg = float(_mp_stats.get("avg_raw", 0.0))
                if _pending_moonshot_avg <= _current_moonshot_avg + MOONSHOT_AVG_EPS:
                    print(
                        f"  ✅ Moonshot pending: 平均が現行以下 "
                        f"({_pending_moonshot_avg*100:+.1f}% ≤ {_current_moonshot_avg*100:+.1f}%) "
                        "のため適用しません。"
                    )
                    _has_moonshot = False

        if not _has_main and not _has_sniper and not _has_moonshot:
            print("ℹ️ 適用対象のpendingロジックがないため、デプロイはスキップします。")
            return

        # バックアップ
        _backup_dir = os.path.join(BASE_DIR, "backups")
        os.makedirs(_backup_dir, exist_ok=True)
        _ts = _time.strftime("%Y%m%d_%H%M%S")
        try:
            shutil.copy2(SCREENER_JS_PATH,
                         os.path.join(_backup_dir, f"screener_backup_{_ts}.js"))
            print(f"  💾 バックアップ作成: screener_backup_{_ts}.js")
            _existing = sorted(_glob.glob(os.path.join(_backup_dir, "screener_backup_*.js")))
            for _old in _existing[:-30]:
                os.remove(_old)
        except Exception as _e:
            print(f"  ⚠ バックアップ失敗: {_e}")

        # screener.js 更新（main と sniper を両方適用してから1回だけデプロイ）
        if _has_main:
            if not update_screener_js(_code):
                print("❌ screener.js 更新失敗"); sys.exit(1)
            print("  ✅ screener.js (calculateScore) 更新完了")
            update_index_js_help(_combo, _method, _ths)
            print("  ✅ index.js /help 更新完了")

        _sniper_data = None
        if _has_sniper:
            _sniper_data = apply_sniper_pending()
            if _sniper_data is None:
                print("❌ calculateScoreSniper() 更新失敗"); sys.exit(1)
            save_current_logic_sniper(_sniper_data["combo"], _sniper_data["thresholds"] or None,
                                      backtest_stats=_sniper_data["stats"])

        _moonshot_data = None
        if _has_moonshot:
            _moonshot_data = apply_moonshot_pending()
            if _moonshot_data is None:
                print("❌ calculateScoreMoonshot() 更新失敗"); sys.exit(1)
            save_current_logic_moonshot(
                _moonshot_data["combo"], _moonshot_data["eval_days"],
                thresholds=_moonshot_data["thresholds"] or None,
                backtest_stats=_moonshot_data["stats"],
            )

        # デプロイ（1回）
        if deploy():
            if _has_main:
                _backtest_data = _p.get("backtest")
                save_current_logic(_method, _combo, _ths or None,
                                   backtest=_backtest_data)
                promote_to_champion(_method, _combo, _ths or {},
                                    backtest=_backtest_data)
                os.remove(PENDING_LOGIC_PATH)
                print("  ✅ pending_logic.json 削除完了")
                _wr  = _base.get('wr_raw', 0)
                _avg = _base.get('avg_raw', 0)
                _base_all = dict(n=_n_total, wr=_wr, avg=_avg, wr_raw=_wr, avg_raw=_avg)
                notify_discord_update(_method, _combo, _st6, _st5, _st4,
                                      _base_all, _n_total, "conditions", _ths)
            if _has_sniper:
                finalize_sniper_pending(_sniper_data)
                notify_discord_sniper_update(_sniper_data["combo"], _sniper_data["stats"],
                                             _sniper_data["thresholds"] or {})
            if _has_moonshot:
                finalize_moonshot_pending(_moonshot_data)
                notify_discord_moonshot_update(
                    _moonshot_data["combo"], _moonshot_data["stats"],
                    _moonshot_data["eval_days"], _moonshot_data["thresholds"] or {}
                )
            print("\n✅ 承認済みロジックのデプロイ完了")
        else:
            print("\n⚠ デプロイ失敗。手動でscp & pm2 restartしてください")
            sys.exit(1)
        return

    print("=" * 62)
    print("天底極致 スコアロジック自動最適化")
    print("=" * 62)
    print(f"  composite: {COMPOSITE_VARIANT} | decay: {BASELINE_DECAY} | strict_wr: {STRICT_WR} | wr_floor: {WR_FLOOR*100:.0f}%")

    print("\n📡 Step 1: データ取得...")
    try:
        svc = get_service()
        print("  接続OK...")
        ar = fetch(svc, "alerts_raw")
        # signals_archive は GAS が完了済みシグナルを移動するシート（最大365日保持）。
        # バックテストの母数を増やすために検証時のみ追加で読み込む。
        # シート未作成や API エラーでも本処理を止めない（空配列でフォールバック）。
        try:
            sa = fetch(svc, "signals_archive")
        except Exception as _sa_e:
            sa = []
            print(f"  signals_archive 取得スキップ: {_sa_e}")
        oh = fetch(svc, "ohlcv_4h")
        print(f"  alerts_raw: {len(ar)}行 / signals_archive: {len(sa)}行 / ohlcv_4h: {len(oh)}行")
    except Exception as e:
        print(f"❌ 取得エラー: {e}"); sys.exit(1)

    print("\n🔧 Step 2: 解析...")
    alerts_raw_confirmed = parse_alerts(ar)
    alerts_archive_confirmed = parse_alerts(sa)
    # alerts_raw 由来かどうかを追跡（通知表示で /help と件数・勝率を揃えるため）
    alerts_raw_confirmed['_from_archive'] = False
    alerts_archive_confirmed['_from_archive'] = True
    # alerts_raw を先に concat → 万一 alert_id が両方に存在しても alerts_raw 側が残る。
    # 時系列順 sort_values("date") は後段の Walk-forward 分割で行われるため、
    # ここではそのまま結合してよい。
    alerts = pd.concat([alerts_raw_confirmed, alerts_archive_confirmed], ignore_index=True)
    if "alert_id" in alerts.columns and len(alerts) > 0:
        _has_id = alerts["alert_id"].astype(str) != ""
        alerts = pd.concat([
            alerts[_has_id].drop_duplicates(subset=["alert_id"], keep="first"),
            alerts[~_has_id],
        ], ignore_index=True)
    # 未確定★6投影で使う alerts_all は alerts_raw 限定。
    # signals_archive は完了済みのみなので、include_unconfirmed=True で取り直しても意味がない。
    alerts_all = parse_alerts(ar, include_unconfirmed=True)
    ohlcv  = parse_ohlcv(oh)
    unconfirmed_count = max(0, len(alerts_all) - len(alerts_raw_confirmed))
    print(f"  BOTTOM確定済み合計: {len(alerts)}件 "
          f"(alerts_raw {len(alerts_raw_confirmed)} + archive {len(alerts_archive_confirmed)})")
    print(f"  5日後未確定: {unconfirmed_count}件")
    if len(alerts) < 30: print("❌ データ不足"); sys.exit(1)

    print("\n📊 Step 3: 指標計算...")
    rows = []; skipped = 0
    for _, r in alerts.iterrows():
        f = get_features(ohlcv.get(r["symbol"], []), r["date"])
        if f: rows.append({**r.to_dict(), **f})
        else: skipped += 1
    df = pd.DataFrame(rows)
    print(f"  有効データ: {len(df)}件（スキップ: {skipped}件）")
    if len(df) < 20: print("❌ 有効データ不足"); sys.exit(1)

    print("\n📏 Step 4: ベースライン計算...")
    print(f"  全体: {len(df)}件 勝率{df['win_5bd'].mean()*100:.1f}% 平均{df['perf_5bd'].mean()*100:.2f}%")
    current_logic = load_current_logic()
    if current_logic:
        print(f"  現行ロジック（方式{current_logic['method']} / {current_logic.get('updated_at','?')}）をベースラインとして使用")
        if current_logic["method"] == "A":
            cur_conds = current_logic["conditions"]
            cur_thresholds = current_logic.get("thresholds", {})
            for c in cur_conds:
                if c in df.columns: df[c] = df[c].astype(bool)
            df["sc_cur"] = score_with_thresholds(df, cur_conds, cur_thresholds)
            current_method = "A"
            current_combo = cur_conds
            current_thresholds = cur_thresholds
            label = "+".join(
                f"{c}({cur_thresholds[c]})" if c in cur_thresholds else c
                for c in cur_conds
            )
        else:
            scheme = [tuple(x) for x in current_logic["conditions"]]
            def score_row_cur(row):
                return min(sum(int(bool(row[c]))*w for c, w, _ in scheme if c in row.index), 6)
            df["sc_cur"] = df.apply(score_row_cur, axis=1)
            label = " ".join(f"{c}({w}pt)" for c, w, _ in scheme)
            cur_thresholds = {}
            current_method = "B"
            current_combo = scheme
            current_thresholds = {}
        baseline = calc_stats(df[df["sc_cur"] == 6])
        print(f"  現行★6: {baseline['n']}件 勝率{baseline['wr_raw']*100:.1f}%"
              f" 平均{baseline['avg_raw']*100:.2f}% 上昇{baseline['win10_raw']:.0f}件 下落{baseline['lose10_raw']:.0f}件")
        print(f"  条件: {label}")
        # ★6シグナル一覧（診断用）
        s6_df = df[df["sc_cur"] == 6].sort_values("date", ascending=False)
        print(f"\n  ── 現行★6シグナル一覧（確定済み perf_5bd あり）──")
        print(f"  {'日付':<12} {'銘柄':<8} {'社名':<24} {'騰落率':>7}")
        for _, row in s6_df.iterrows():
            sign = "+" if row["perf_5bd"] >= 0 else ""
            print(f"  {row['date']:<12} {row['symbol']:<8} {row['name']:<24} {sign}{row['perf_5bd']*100:.1f}%")
    else:
        print("  初回実行 — v14.1をベースラインとして使用")
        V14 = ["ema75", "vol20", "sbull", "macdgc", "atr5", "ema25"]
        for c in V14: df[c] = df[c].astype(bool)
        df["sc_v14"] = sum(df[c].astype(int) for c in V14)
        df["sc_cur"] = df["sc_v14"]
        cur_conds = V14
        cur_thresholds = {}
        current_method = "A"
        current_combo = V14
        current_thresholds = {}
        baseline = calc_stats(df[df["sc_v14"] == 6])
        print(f"  v14.1★6: {baseline['n']}件 勝率{baseline['wr_raw']*100:.1f}%"
              f" 平均{baseline['avg_raw']*100:.2f}% 上昇{baseline['win10_raw']:.0f}件 下落{baseline['lose10_raw']:.0f}件")

    # alerts_raw 由来のみ（通知表示・/help との整合用）
    df_alerts_raw = df[~df['_from_archive'].fillna(False)].copy() if '_from_archive' in df.columns else df
    baseline_ar = calc_stats(df_alerts_raw[df_alerts_raw["sc_cur"] == 6])
    print(f"  alerts_raw ★6（表示用）: {baseline_ar['n']}件 勝率{baseline_ar['wr_raw']*100:.1f}%"
          f" 平均{baseline_ar['avg_raw']*100:.2f}%")

    unconfirmed_current_df = build_unconfirmed_current_df(alerts_all, ohlcv)
    current_unconfirmed_stats6 = calc_stats(pd.DataFrame())
    current_projection_stats6 = baseline
    if len(unconfirmed_current_df) > 0:
        unconfirmed_current_df["sc_cur"] = calc_score_series_for_logic(
            unconfirmed_current_df, current_method, current_combo, current_thresholds
        )
        current_unconfirmed_s6 = unconfirmed_current_df[unconfirmed_current_df["sc_cur"] == 6]
        current_unconfirmed_stats6 = calc_stats(current_unconfirmed_s6)
        projected_s6 = pd.concat(
            [df[df["sc_cur"] == 6], current_unconfirmed_s6],
            ignore_index=True,
            sort=False,
        )
        current_projection_stats6 = calc_stats(projected_s6)

    print(f"  未確定★6（現在値）: {current_unconfirmed_stats6['n']}件 "
          f"勝率{current_unconfirmed_stats6['wr_raw']*100:.1f}% "
          f"平均{current_unconfirmed_stats6['avg_raw']*100:+.1f}%")
    print(f"  現行★6投影（確定+未確定現在値）: {current_projection_stats6['n']}件 "
          f"勝率{current_projection_stats6['wr_raw']*100:.1f}% "
          f"平均{current_projection_stats6['avg_raw']*100:+.1f}%")

    # Walk-forward: 60% 訓練 / 20% 検証 / 20% lockbox（真のOOS、選別ループに触れない）
    df_wf = df.sort_values("date").reset_index(drop=True)
    n_total = len(df_wf)
    n_train = int(n_total * (1.0 - WALK_FORWARD_VALID_FRAC - LOCKBOX_FRAC))
    n_valid = int(n_total * WALK_FORWARD_VALID_FRAC)
    df_wf_train   = df_wf.iloc[:n_train].copy()
    df_wf_valid   = df_wf.iloc[n_train:n_train + n_valid].copy()
    df_wf_lockbox = df_wf.iloc[n_train + n_valid:].copy()   # 採用直前まで絶対に使わない
    current_validation_stats6 = calc_stats(df_wf_valid[df_wf_valid["sc_cur"] == 6])
    # 現行ロジックの lockbox baseline（候補との比較用）
    baseline_lockbox_stats6 = calc_stats(df_wf_lockbox[df_wf_lockbox["sc_cur"] == 6]) \
        if "sc_cur" in df_wf_lockbox.columns else calc_stats(pd.DataFrame())
    print(f"  Walk-forward分割: 訓練{len(df_wf_train)}件 / 検証{len(df_wf_valid)}件 / lockbox{len(df_wf_lockbox)}件")

    # ── データ充足判定（archive 蓄積中は transition mode で動作） ────────
    data_mode = "strict" if is_data_sufficient(df, df_wf_lockbox) else "transition"
    if data_mode == "strict":
        print(f"  📊 データ充足判定: strict mode（全件{len(df)}≥{MIN_TOTAL_FOR_STRICT_MODE} / lockbox{len(df_wf_lockbox)}≥{MIN_LOCKBOX_FOR_STRICT_MODE}）")
        print(f"     → Tier B 統計検定（Lockbox / Bootstrap CI / K-Fold）を全面適用")
    else:
        print(f"  📊 データ充足判定: transition mode（全件{len(df)}<{MIN_TOTAL_FOR_STRICT_MODE} または lockbox{len(df_wf_lockbox)}<{MIN_LOCKBOX_FOR_STRICT_MODE}）")
        print(f"     → archive 蓄積中: 統計検定は参考表示のみ、pre-Tier-A 水準で品質ゲート評価")

    # 現行ロジックが健全なら最適化をスキップ（rescue含め更新不要）
    if is_current_healthy(baseline, current_validation_stats6):
        print(f"\n✅ 現行ロジック健全のため最適化をスキップ（更新不要）")
        print(f"   全件★6: {baseline['n']}件 勝率{baseline['wr_raw']*100:.1f}% 平均{baseline['avg_raw']*100:+.1f}%")
        print(f"   検証★6: {current_validation_stats6['n']}件 平均{current_validation_stats6['avg_raw']*100:+.1f}%")
        print(f"   (スキップ条件: 勝率≥{HEALTHY_SKIP_WR*100:.0f}% / 平均≥{HEALTHY_SKIP_AVG*100:.0f}% / ★6≥{HEALTHY_SKIP_N_MIN}件 / 検証平均≥0%)")
        if args.propose and not args.dry_run:
            save_rescue_state({
                "updated_at": _utc_now_z(),
                "last_checked_date": _jst_today_key(),
                "status": "healthy",
                "streak": 0,
                "current_stats6": _jsonable_stats(baseline),
                "current_validation_stats6": _jsonable_stats(current_validation_stats6),
            })
        return

    raw_rescue_mode, raw_rescue_reasons = detect_rescue_mode(baseline, current_validation_stats6)
    rescue_mode, rescue_reasons, rescue_streak = resolve_rescue_mode(
        raw_rescue_reasons,
        baseline,
        current_validation_stats6,
        current_unconfirmed_stats6,
        current_projection_stats6,
        persist_state=(args.propose and not args.dry_run),
    )
    adoption_mode = "rescue" if rescue_mode else "normal"
    print(f"  現行検証★6: {current_validation_stats6['n']}件 "
          f"勝率{current_validation_stats6['wr_raw']*100:.1f}% "
          f"平均{current_validation_stats6['avg_raw']*100:.1f}%")
    if raw_rescue_mode:
        print("  ⚠ rescue対象条件を検知:")
        for reason in raw_rescue_reasons:
            print(f"    - {reason}")
    if rescue_mode:
        print("  ⚠ rescue mode 発動:")
        for reason in rescue_reasons:
            print(f"    - {reason}")
    elif raw_rescue_mode:
        if rescue_streak == 0:
            print("  ✅ rescue mode 見送り（未確定現在値の回復投影を優先）:")
        else:
            print(f"  ✅ rescue mode 見送り（連続{rescue_streak}/{RESCUE_REQUIRED_STREAK}日）:")
        for reason in rescue_reasons:
            print(f"    - {reason}")
    else:
        print("  ✅ normal mode: 現行ロジックは劣化条件に該当しません")

    def handle_no_stable_candidate(message):
        print(f"\n✅ {message}")
        if rescue_mode:
            print("  ⚠ rescue mode: 品質ゲートを満たす代替候補なし")
            if args.propose and not args.dry_run:
                notify_discord_rescue_no_candidate(
                    baseline_ar, current_validation_stats6, rescue_reasons, len(df_alerts_raw)
                )
            else:
                print("  ℹ dry-run/通常実行では rescue候補なし通知を送信しません")
        if not args.dry_run:
            restart_bot_only()

    # ── Sniperモード最適化（Step 4完了後・Step 5a前） ─────────────
    _run_sniper_optimization(df, args)

    # ── Moonshotモード最適化（Sniperの直後） ─────────────────────
    # マスタースイッチがOFFの間は完全スキップ（pending生成・Discord通知も走らない）
    if MOONSHOT_AUTO_OPTIMIZE_ENABLED:
        _run_moonshot_optimization(df, args)
    else:
        print("\n🌙 Moonshot 自動最適化はスキップ "
              "(MOONSHOT_AUTO_OPTIMIZE_ENABLED=False / データ蓄積待ち)")

    print("\n🔍 Step 5a: 方式A（組み合わせ探索）...")
    print(f"  Walk-forward: train {len(df_wf_train)}件 / validation {len(df_wf_valid)}件")
    cands_a = search_combinations(df_wf_train.copy(), baseline, adoption_mode)
    print(f"  候補クリア(train/{adoption_mode}): {len(cands_a)}通り")
    if cands_a:
        wf_validated = []
        limit = min(WALK_FORWARD_CANDIDATE_LIMIT, len(cands_a))
        for item in cands_a[:limit]:
            combo = item[3]
            conds_in_valid = [c for c in combo if c in df_wf_valid.columns]
            if len(conds_in_valid) < len(combo):
                continue
            scores_v = sum(df_wf_valid[c].astype(int) for c in conds_in_valid)
            s6_v = df_wf_valid[scores_v == 6]
            st6_v = calc_stats(s6_v)
            if validation_gate_ok(st6_v, data_mode=data_mode,
                                   baseline_validation_stats=current_validation_stats6):
                wf_validated.append((*item, st6_v))
        print(f"  Walk-forward 品質ゲート通過: {len(wf_validated)}/{limit}通り")
        cands_a = wf_validated

    print(f"\n🔍 Step 5b: 方式B（+{WIN_THRESHOLD*100:.0f}%共通点分析）...")
    result_b = analyze_winners(df.copy(), baseline, adoption_mode)

    print(f"\n🏆 Step 6: 候補一覧（上位10）")
    print(f"  {'#':<3} {'方式':<4} {'★6勝率':>7} {'★6平均':>8} {'上昇':>4} {'下落':>4} {'件数':>4} {'努力':>4}  条件")
    candidate_pool = []
    final_eval_limit = min(FINAL_EVAL_CANDIDATE_LIMIT, len(cands_a))
    for sc6, sc5, sc4, combo, st6, st5, st4, st6_valid in cands_a[:final_eval_limit]:
        candidate_pool.append(("A", sc6, sc5, sc4, combo, st6, st5, st4, st6_valid))
    if len(cands_a) > final_eval_limit:
        print(f"  最終判定候補: {final_eval_limit}/{len(cands_a)}通りに制限")
    if result_b:
        scheme_b, stats_b6, stats_b5, stats_b4 = result_b
        stats_b6_valid, _, _ = calc_candidate_tiers(df_wf_valid, "B", scheme_b)
        if validation_gate_ok(stats_b6_valid, data_mode=data_mode,
                              baseline_validation_stats=current_validation_stats6):
            candidate_pool.append(("B", stats_b6["composite"], stats_b5["composite"],
                                   stats_b4["composite"], scheme_b, stats_b6, stats_b5,
                                   stats_b4, stats_b6_valid))
        else:
            print(f"  方式B: Walk-forward品質ゲートNG "
                  f"(検証★6 {stats_b6_valid['n']}件 勝率{stats_b6_valid['wr_raw']*100:.1f}% "
                  f"平均{stats_b6_valid['avg_raw']*100:.1f}%)")
    # ★6総合スコア → 順序スコア(努力義務) → ★5 → ★4 の順でソート
    candidate_pool.sort(key=lambda x: (-x[1], -calc_ordering_score(x[5], x[6], x[7]), -x[2], -x[3]))

    for i, (method, sc6, sc5, sc4, combo, st6, st5, st4, st6_valid) in enumerate(candidate_pool[:10]):
        e = ("✓" if st6["wr_raw"] >= TARGET_WIN_RATE else "△") + \
            ("✓" if st6["avg_raw"] >= TARGET_AVG_PERF else "△") + \
            ("✓" if st6["win10_raw"] > st6["lose10_raw"] else "△") + \
            ("✓" if validation_gate_ok(st6_valid, data_mode=data_mode,
                                       baseline_validation_stats=current_validation_stats6) else "△")
        label = "+".join(combo) if method == "A" else " ".join(f"{c}({w}pt)" for c, w, _ in combo)
        print(f"  #{i+1:<2} {method:<4} {st6['wr_raw']*100:>6.1f}%  {st6['avg_raw']*100:>+7.1f}%"
              f"  {st6['win10_raw']:>3.0f}件  {st6['lose10_raw']:>3.0f}件  {st6['n']:>3}件  {e}  {label}")

    # ── Step 5c: 閾値最適化（train/test split） ──────────────
    best_thresholds = {}
    if not candidate_pool:
        # 新しい組み合わせなし → 現行条件の閾値だけ最適化を試みる
        if not (current_logic and current_logic["method"] == "A"):
            handle_no_stable_candidate("現行ロジックが最良。更新しません。"); return
        print(f"\n🔍 組み合わせ変更なし → 閾値最適化のみ試みます")
        cur_conds = current_logic["conditions"]
        df_train  = df_wf_train.copy()
        df_test   = df_wf_valid.copy()
        print(f"📐 train/test split: 訓練{len(df_train)}件 / 検証{len(df_test)}件")
        tuned_ths, _, _, tune_passed = tune_thresholds(df_train, df_test, cur_conds, baseline,
                                                        data_mode=data_mode,
                                                        baseline_validation_stats=current_validation_stats6)
        if not (tune_passed and tuned_ths):
            handle_no_stable_candidate("現行ロジックが最良。更新しません。"); return
        best_thresholds = tuned_ths
        s_full = score_with_thresholds(df, cur_conds, best_thresholds)
        best_method  = "A"
        best_combo   = cur_conds
        best_stats   = calc_stats(df[s_full == 6])
        best_stats5  = calc_stats(df[s_full == 5])
        best_stats4  = calc_stats(df[s_full == 4])
        best_validation_stats6, _, _ = calc_candidate_tiers(df_wf_valid, "A", cur_conds, best_thresholds)
    else:
        df_train  = df_wf_train.copy()
        df_test   = df_wf_valid.copy()
        print(f"\n📐 train/test split: 訓練{len(df_train)}件 / 検証{len(df_test)}件")

        # 閾値最適化は重いため上位候補だけに適用し、最終判定は広い候補プールで行う。
        tune_cands = list(candidate_pool[:THRESHOLD_TUNE_CANDIDATE_LIMIT])
        print(f"\n🔬 Step 5c: 上位{len(tune_cands)}候補 閾値最適化...")
        print(f"  {'#':<3} {'★6勝率':>7} {'★6平均':>8} {'上昇':>4} {'下落':>4} {'件数':>4}  閾値変更  条件")
        tuned_pairs = []
        for i, (method_i, _, _, _, combo_i, _, _, _, validation_i) in enumerate(tune_cands):
            if method_i != "A":
                continue
            tuned_ths_i, _, _, tune_passed_i = tune_thresholds(df_train, df_test, combo_i, baseline,
                                                                data_mode=data_mode,
                                                                baseline_validation_stats=current_validation_stats6)
            if tune_passed_i and tuned_ths_i:
                s_full_i = score_with_thresholds(df, combo_i, tuned_ths_i)
                st6f = calc_stats(df[s_full_i == 6])
                st5f = calc_stats(df[s_full_i == 5])
                st4f = calc_stats(df[s_full_i == 4])
                st6vf, _, _ = calc_candidate_tiers(df_wf_valid, "A", combo_i, tuned_ths_i)
                tuned_cand = ("A", st6f["composite"], st5f["composite"],
                              st4f["composite"], combo_i, st6f, st5f, st4f, st6vf)
                tuned_pairs.append((tuned_cand, tuned_ths_i))
                changes = ", ".join(
                    f"{k}:{COND_PARAM[k][1]}→{v}" for k, v in tuned_ths_i.items()
                    if k in COND_PARAM and abs(v - COND_PARAM[k][1]) > 1e-9
                ) or "変更なし"
                print(f"  #{i+1:<2} {st6f['wr_raw']*100:>6.1f}%  {st6f['avg_raw']*100:>+7.1f}%"
                      f"  {st6f['win10_raw']:>3.0f}件  {st6f['lose10_raw']:>3.0f}件  {st6f['n']:>3}件"
                      f"  検証{st6vf['n']}件/{st6vf['wr_raw']*100:.1f}%  {changes}  {'+'.join(combo_i)}")
            else:
                print(f"  #{i+1:<2} (閾値最適化NG — デフォルト維持)  {'+'.join(combo_i)}")

        # 採用判定は必ず全件データで再評価する。
        # cands_a は walk-forward train 上の探索結果なので、そのまま使うと
        # 全件品質ゲートをすり抜ける可能性がある。
        final_pairs = []
        seen_signatures = set()

        def append_final_pair(cand, ths):
            method_i, _, _, _, combo_i, _, _, _, _ = cand
            eval_thresholds = (ths or {}) if method_i == "A" else {}
            sig = logic_signature(method_i, combo_i, eval_thresholds)
            if sig in seen_signatures:
                return
            seen_signatures.add(sig)
            st6f, st5f, st4f = calc_candidate_tiers(
                df, method_i, combo_i, eval_thresholds
            )
            st6vf, _, _ = calc_candidate_tiers(
                df_wf_valid, method_i, combo_i, eval_thresholds
            )
            final_pairs.append((
                (method_i, st6f["composite"], st5f["composite"], st4f["composite"],
                 combo_i, st6f, st5f, st4f, st6vf),
                ths,
            ))

        for cand, ths in tuned_pairs:
            append_final_pair(cand, ths)
        for cand in candidate_pool:
            append_final_pair(cand, None)

        # post-tune/full-data compositeで再ソート（複雑さペナルティを加味）
        paired = sorted(final_pairs,
                        key=lambda x: (-(x[0][1] - _complexity_penalty(x[1])),
                                       -calc_ordering_score(x[0][5], x[0][6], x[0][7]),
                                       -x[0][2], -x[0][3]))
        all_cands     = [p[0] for p in paired]
        tuned_ths_list = [p[1] for p in paired]

        selected = None
        for cand, ths in zip(all_cands, tuned_ths_list):
            ok_sel, _, reasons_sel = check_criteria(cand[5], baseline, cand[8], adoption_mode,
                                                     thresholds=ths, data_mode=data_mode,
                                                     baseline_validation_stats=current_validation_stats6)
            if ok_sel:
                selected = (cand, ths, reasons_sel)
                break
        if selected is None:
            best_thresholds = tuned_ths_list[0] or {}
            best_method, _, _, _, best_combo, best_stats, best_stats5, best_stats4, best_validation_stats6 = all_cands[0]
            preselected_adoption_reasons = []
        else:
            cand, ths, preselected_adoption_reasons = selected
            best_thresholds = ths or {}
            best_method, _, _, _, best_combo, best_stats, best_stats5, best_stats4, best_validation_stats6 = cand
    ok, check_res, adoption_reasons = check_criteria(best_stats, baseline, best_validation_stats6, adoption_mode,
                                                      thresholds=best_thresholds, data_mode=data_mode,
                                                      baseline_validation_stats=current_validation_stats6)
    if 'preselected_adoption_reasons' in locals() and preselected_adoption_reasons:
        adoption_reasons = preselected_adoption_reasons
    print(f"\n🎯 Step 7: 採用判断 — 方式{best_method}")
    for line in check_res: print(f"  {line}")
    ord_sc = calc_ordering_score(best_stats, best_stats5, best_stats4)
    ord_lb = ordering_label(best_stats, best_stats5, best_stats4)
    print(f"  {'✓' if ord_sc >= 1 else '△'} 努力④順序: {ord_lb}")
    print(f"  タイブレーカー参照:")
    print(f"    ★5: {best_stats5['n']}件 勝率{best_stats5['wr_raw']*100:.1f}% 平均{best_stats5['avg_raw']*100:.1f}%")
    print(f"    ★4: {best_stats4['n']}件 勝率{best_stats4['wr_raw']*100:.1f}% 平均{best_stats4['avg_raw']*100:.1f}%")
    print(f"  Walk-forward検証:")
    print(f"    現行★6: {current_validation_stats6['n']}件 勝率{current_validation_stats6['wr_raw']*100:.1f}% 平均{current_validation_stats6['avg_raw']*100:.1f}%")
    print(f"    候補★6: {best_validation_stats6['n']}件 勝率{best_validation_stats6['wr_raw']*100:.1f}% 平均{best_validation_stats6['avg_raw']*100:.1f}%")

    if not ok:
        handle_no_stable_candidate("品質条件未達。更新しません。"); return

    # ── 過学習抑制チェック（Tier B） ────────────────────────────────────
    # strict mode: 全ゲート適用 / transition mode: 参考表示のみで強制 reject しない
    strict_gates = (data_mode == "strict")
    if not strict_gates:
        print(f"\n⚠ transition mode: Tier B 統計検定は参考表示のみ（強制 reject しない）")

    # 1. Lockbox（真のOOS）ゲート
    lockbox_s6_stats, _, _ = calc_candidate_tiers(df_wf_lockbox, best_method, best_combo, best_thresholds)
    lb_ok, lb_reason = lockbox_gate_ok(lockbox_s6_stats, baseline_lockbox_stats6, adoption_mode)
    print(f"\n🔒 Lockbox OOS検証 — {'✓ 通過' if lb_ok else '✗ 過学習検出'}")
    print(f"   候補lockbox★6: {lockbox_s6_stats['n']}件 "
          f"勝率{lockbox_s6_stats['wr_raw']*100:.1f}% "
          f"平均{lockbox_s6_stats['avg_raw']*100:+.1f}% "
          f"上昇{int(lockbox_s6_stats.get('win10_raw', 0))}件 "
          f"下落{int(lockbox_s6_stats.get('lose10_raw', 0))}件")
    print(f"   現行lockbox★6: {baseline_lockbox_stats6['n']}件 "
          f"勝率{baseline_lockbox_stats6['wr_raw']*100:.1f}% "
          f"平均{baseline_lockbox_stats6['avg_raw']*100:+.1f}% "
          f"上昇{int(baseline_lockbox_stats6.get('win10_raw', 0))}件 "
          f"下落{int(baseline_lockbox_stats6.get('lose10_raw', 0))}件")
    print(f"   詳細: {lb_reason}")
    if strict_gates and not lb_ok:
        handle_no_stable_candidate(f"Lockbox(OOS)で過学習を検出。更新しません。({lb_reason})"); return

    # 2. Bootstrap CI（候補★6件数に応じて評価方式を切替）
    # n<30 では Bootstrap CI 幅が ~30-40pt と広く、相対比較が事実上機能しない。
    # n が大きい時のみ厳格 (現行勝率超え)、それ以外は絶対床35%でカタストロフィのみ防ぐ。
    cand_scores = calc_score_series_for_logic(df, best_method, best_combo, best_thresholds)
    cand_s6_df = df[cand_scores == 6]
    n_cand_full = len(cand_s6_df)
    wr_lo, wr_hi = bootstrap_wr_ci(cand_s6_df)
    if n_cand_full >= 30:
        bs_threshold = baseline["wr_raw"]              # 厳格: > 現行勝率
        bs_mode_label = f"現行{baseline['wr_raw']*100:.1f}% (n≥30 厳格)"
    else:
        bs_threshold = 0.35                            # 絶対床35%
        bs_mode_label = f"絶対床35% (n<30 はCI幅広く相対比較困難)"
    bs_ok = wr_lo > bs_threshold
    print(f"  Bootstrap CI(95%): [{wr_lo*100:.1f}%, {wr_hi*100:.1f}%] "
          f"→ CI下限 {wr_lo*100:.1f}% {'>' if bs_ok else '≤'} 閾値{bs_threshold*100:.1f}% "
          f"[{bs_mode_label}, n={n_cand_full}] "
          f"({'✓' if bs_ok else '✗ 統計的有意性なし'}"
          f"{' / rescue時はバイパス' if adoption_mode == 'rescue' and not bs_ok else ''})")
    if strict_gates and not bs_ok and adoption_mode != "rescue":
        handle_no_stable_candidate(
            f"Bootstrap CI: 下限{wr_lo*100:.1f}%が閾値{bs_threshold*100:.1f}%を下回ります。"
            f"({bs_mode_label}, n={n_cand_full})"
        ); return

    # 3. K-Fold 時系列CV（候補★6件数に応じて要求フォールド数を階層化）
    kfold_wins = time_series_kfold_passes(df, best_method, best_combo, best_thresholds, baseline["wr_raw"], k=3)
    if n_cand_full >= 30:
        kfold_min = 2    # 厳格: 2/3 fold
    elif n_cand_full >= 15:
        kfold_min = 1    # 緩和: 1/3 fold
    else:
        kfold_min = 0    # スキップ（サンプル過小でCV意味なし）
    kfold_ok = (kfold_min == 0) or (kfold_wins >= kfold_min)
    print(f"  K-Fold(k=3)安定性: {kfold_wins}/3 フォールドで現行超 "
          f"[要求{kfold_min}/3, n={n_cand_full}] "
          f"({'✓ 安定' if kfold_ok else '✗ 局所過学習の疑い'})")
    if strict_gates and not kfold_ok and adoption_mode != "rescue":
        handle_no_stable_candidate(
            f"K-Fold CV で局所過学習を検出。全期間での安定性が不十分。(要求{kfold_min}/3, n={n_cand_full})"
        ); return

    # 4. Permutation Test（strict / transition どちらでも参考表示のみ）
    perm_p = permutation_pvalue(df, best_method, best_combo, best_thresholds,
                                best_stats["composite"], n_perm=200)
    perm_ok = perm_p < 0.05
    print(f"  Permutation Test(n=200): p={perm_p:.3f} "
          f"({'✓ p<0.05' if perm_ok else '△ p≥0.05 (偶然の可能性あり)'})")
    # ── 過学習抑制チェックここまで ────────────────────────────────────────

    # 条件・閾値が現行と完全一致、または★6対象シグナル集合が同一なら更新不要
    if current_logic:
        current_sig = logic_signature(
            current_logic.get("method"),
            current_logic.get("conditions", []),
            current_logic.get("thresholds", {}),
        )
        candidate_sig = logic_signature(best_method, best_combo, best_thresholds)
        if current_sig == candidate_sig:
            handle_no_stable_candidate("条件・閾値が現行と同一のため更新しません。"); return

    current_targets = set(df.index[df["sc_cur"] == 6].tolist()) if "sc_cur" in df.columns else set()
    candidate_targets = selected_signal_indices(
        df, best_method, best_combo, best_thresholds, target_score=6
    )
    if candidate_targets == current_targets:
        print("\n✅ 条件は異なるが抽出結果が現行と同一のため更新しません。")
        if not args.dry_run:
            restart_bot_only()
        return

    new_code = (build_func_a(best_combo, best_stats, baseline, len(df), best_thresholds)
                if best_method == "A"
                else build_func_b(best_combo, best_stats, baseline, len(df)))

    # alerts_raw のみで表示用統計を計算（/help と件数・勝率を揃える）
    display_df = df_alerts_raw
    display_stats6, display_stats5, display_stats4, display_base, display_n_total = \
        calc_backtest_display_stats(display_df, best_method, best_combo, best_thresholds)
    training_stats6, training_stats5, training_stats4 = calc_candidate_tiers(
        df_wf_train, best_method, best_combo, best_thresholds
    )
    print(f"  表示用バックテスト（alerts_rawデータ / {display_n_total}件）: ★6 {display_stats6['n']}件 "
          f"勝率{display_stats6['wr_raw']*100:.1f}% 平均{display_stats6['avg_raw']*100:.1f}%")

    # ─── 通常モード時は中程度以上の改善（勝率+1pt以上）のみ提案する ───────────
    # rescue mode（streak >= RESCUE_REQUIRED_STREAK）は従来通り提案を通す。
    # 頻繁なロジック変更でユーザーが混乱しないよう、軽微な改善はスキップ。
    # ベア相場で +5pp 改善が出にくいため +4pp に緩和（2026-05-23）。
    # 統計検定（Lockbox/Bootstrap/K-Fold/Permutation）を全通過しても
    # +4pp 未満で却下されるケースが発生したため +1pp に緩和（2026-05-28）。
    WR_SIGNIFICANT_IMPROVEMENT = 0.01  # +1ppを「中程度以上」の閾値とする
    if adoption_mode == "normal":
        wr_improvement = best_stats["wr_raw"] - baseline["wr_raw"]
        if wr_improvement < WR_SIGNIFICANT_IMPROVEMENT:
            print(
                f"\n✅ 勝率改善が軽微（+{wr_improvement*100:.1f}pt < "
                f"+{WR_SIGNIFICANT_IMPROVEMENT*100:.0f}pt）のため更新をスキップします。"
            )
            print(
                f"   rescue modeまたは勝率+{WR_SIGNIFICANT_IMPROVEMENT*100:.0f}pt以上の"
                f"改善時のみ更新候補として提案します。"
            )
            if not args.dry_run:
                restart_bot_only()
            return

    # ─── 最終ゲート: alerts_raw★6勝率が現行を下回るなら提案しない ────────────
    # /help の表示勝率が下がる変更はユーザー体験の改悪になるため、
    # 全体データ（signals_archive込み）での改善があっても却下する。
    if display_stats6["wr_raw"] < baseline_ar["wr_raw"]:
        msg = (
            f"alerts_rawベース★6勝率が現行以下のため更新をスキップ"
            f"（候補{display_stats6['wr_raw']*100:.1f}%"
            f" < 現行{baseline_ar['wr_raw']*100:.1f}%）"
        )
        print(f"\n⛔ {msg}")
        handle_no_stable_candidate(msg)
        return

    # ─── --propose: pending_logic.json に保存して Discord通知して終了 ───
    if args.propose:
        import json as _pjson2
        def _to_jsonable(d):
            return {k: float(v) if hasattr(v, 'item') else v for k, v in d.items()}
        _pending = {
            "mode":         adoption_mode,
            "method":       best_method,
            "conditions":   best_combo if best_method == "A" else [[c, w, l] for c, w, l in best_combo],
            "thresholds":   best_thresholds or {},
            "screener_code": new_code,
            "stats6":       _to_jsonable(display_stats6),
            "stats5":       _to_jsonable(display_stats5),
            "stats4":       _to_jsonable(display_stats4),
            "training_stats6": _to_jsonable(training_stats6),
            "training_stats5": _to_jsonable(training_stats5),
            "training_stats4": _to_jsonable(training_stats4),
            "validation_stats6": _to_jsonable(best_validation_stats6),
            "current_stats6": _to_jsonable(baseline),
            "current_validation_stats6": _to_jsonable(current_validation_stats6),
            "adoption_reasons": adoption_reasons,
            "baseline":     {k: float(v) if hasattr(v, 'item') else v
                             for k, v in display_base.items()
                             if not isinstance(v, str)},
            "n_total":      display_n_total,
            "backtest_source": "alerts_raw",
            "proposed_at":  datetime.utcnow().isoformat() + "Z",
            "backtest": {
                "data_mode": data_mode,
                "train":   _to_jsonable(training_stats6),
                "valid":   _to_jsonable(best_validation_stats6),
                "lockbox": _to_jsonable(lockbox_s6_stats),
                "all":     _to_jsonable(display_stats6),
                "wr_95ci": [wr_lo, wr_hi],
                "permutation_pvalue": round(perm_p, 4),
                "kfold_wins": f"{kfold_wins}/3",
                "complexity": len(best_thresholds or {}),
                "n_total": int(len(df)),
                "n_lockbox": int(len(df_wf_lockbox)),
            },
        }
        with open(PENDING_LOGIC_PATH, "w", encoding="utf-8") as _pf2:
            _pjson2.dump(_pending, _pf2, ensure_ascii=False, indent=2)
        print(f"\n📋 pending_logic.json に保存しました")
        notify_discord_approval(
            best_method, best_combo, display_stats6, display_base, best_thresholds,
            validation_stats=best_validation_stats6,
            current_stats=baseline_ar,
            current_validation_stats=current_validation_stats6,
            adoption_reasons=adoption_reasons,
            mode=adoption_mode,
        )
        print("✅ Discord に承認リクエストを送信しました")
        print("（承認後、Discord で /approve-update を実行するとデプロイされます）")
        restart_bot_only()
        return

    if args.dry_run:
        print(f"\n🔍 Dry-run: 更新・デプロイをスキップ")
        print(f"  採用予定: {adoption_mode} / 方式{best_method} / "
              f"{best_combo if best_method == 'A' else [c for c, w, _ in best_combo]}")
        print(f"  検証★6: {best_validation_stats6['n']}件 "
              f"勝率{best_validation_stats6['wr_raw']*100:.1f}% "
              f"平均{best_validation_stats6['avg_raw']*100:.1f}%")
        # 採用候補の★6シグナル一覧を表示
        if best_method == "A":
            cand_scores = score_with_thresholds(df, best_combo, best_thresholds)
            cand_s6 = df[cand_scores == 6].sort_values("date", ascending=False)
            print(f"\n  ── 採用候補ロジックの★6シグナル一覧（{len(cand_s6)}件）──")
            print(f"  {'日付':<12} {'銘柄':<8} {'社名':<24} {'騰落率':>7}")
            for _, row in cand_s6.iterrows():
                sign = "+" if row["perf_5bd"] >= 0 else ""
                print(f"  {row['date']:<12} {row['symbol']:<8} {row['name']:<24} {sign}{row['perf_5bd']*100:.1f}%")
        return

    # 承認確認
    print(f"\n❓ screener.js を更新してデプロイしますか？")
    print(f"  方式{best_method}: 勝率{best_stats['wr_raw']*100:.1f}% 平均{best_stats['avg_raw']*100:.1f}%"
          f" 上昇{best_stats['win10_raw']:.0f}件 下落{best_stats['lose10_raw']:.0f}件")
    if args.yes:
        print("  --yes フラグにより自動承認")
    else:
        try:
            ans = input("  [y/N] → ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "n"
        if ans != "y":
            print("  キャンセルしました。"); return

    # バックアップ（backupsフォルダ・最大30ファイル）
    import shutil, time, glob
    backup_dir = os.path.join(BASE_DIR, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"screener_backup_{ts}.js")
    try:
        shutil.copy2(SCREENER_JS_PATH, backup_path)
        print(f"\n💾 バックアップ作成: backups\\screener_backup_{ts}.js")
        # 30ファイル超えたら古いものから削除
        existing = sorted(glob.glob(os.path.join(backup_dir, "screener_backup_*.js")))
        if len(existing) > 30:
            for old_file in existing[:-30]:
                os.remove(old_file)
                print(f"  🗑 古いバックアップ削除: {os.path.basename(old_file)}")
    except Exception as e:
        print(f"  ⚠ バックアップ失敗: {e}")
        try:
            ans2 = input("  バックアップなしで続行しますか？ [y/N] → ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans2 = "n"
        if ans2 != "y": return

    print(f"\n✏️  Step 8: screener.js + index.js 更新...")
    if not update_screener_js(new_code):
        print("❌ screener.js 更新失敗"); return
    print("  ✅ screener.js 更新完了")
    if update_index_js_help(best_combo, best_method, best_thresholds):
        print("  ✅ index.js /help 条件テキスト更新完了")
    else:
        print("  ⚠ index.js の更新に失敗（手動で修正してください）")
    print(f"  ↩️  元に戻す場合: backups\\screener_backup_{ts}.js を screener.js にコピー")

    if deploy():
        print("\n✅ デプロイ完了")
        # 変更タイプを判定（通知メッセージの文言に使う）
        prev_conds = current_logic["conditions"] if current_logic and current_logic.get("method") == "A" else []
        prev_ths   = current_logic.get("thresholds", {}) if current_logic else {}
        new_ths    = best_thresholds or {}
        conds_changed = (sorted(best_combo) != sorted(prev_conds)) if best_method == "A" else True
        ths_changed   = new_ths != prev_ths
        if conds_changed and ths_changed:
            what_changed = "both"
        elif conds_changed:
            what_changed = "conditions"
        elif ths_changed:
            what_changed = "thresholds"
        else:
            # 条件も閾値も変わっていない（再デプロイのみ）
            what_changed = "conditions"

        # 現行ロジックを保存（次回実行時のベースラインになる）
        if best_method == "A":
            save_current_logic("A", best_combo, new_ths or None)
        else:
            save_current_logic("B", [[c, w, lift] for c, w, lift in best_combo])

        # Discord更新通知は /scan 全期間と同じ全件データの成績を表示する
        notify_discord_update(best_method, best_combo,
                              display_stats6, display_stats5, display_stats4,
                              display_base, display_n_total, what_changed, new_ths)
    else:
        print("\n⚠ デプロイ失敗。手動でscp & pm2 restartしてください")

    print(f"\n{'=' * 62}")
    print(f"完了 — 方式{best_method}")
    print(f"★6: {best_stats['n']}件 勝率{best_stats['wr_raw']*100:.1f}%"
          f" 平均{best_stats['avg_raw']*100:.1f}% 上昇{best_stats['win10_raw']:.0f}件 下落{best_stats['lose10_raw']:.0f}件")
    print("=" * 62)

if __name__ == "__main__":
    main()
