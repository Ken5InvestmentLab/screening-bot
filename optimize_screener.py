#!/usr/bin/env python3
"""
optimize_screener.py — 天底極致スコアロジック自動最適化 + 自動デプロイ

使い方:
  py optimize_screener.py              # 通常実行（分析→更新→デプロイ）
  py optimize_screener.py --dry-run    # 分析のみ（ファイル更新・デプロイなし）
"""

import argparse, math, os, subprocess, sys
from datetime import datetime
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

SPREADSHEET_ID   = "1pcD6-462nyv1A1bcW5UeWwaxBr7A1RIJ6Ofixeo5Xb8"
SCOPES           = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

TARGET_WIN_RATE  = 0.55
TARGET_AVG_PERF  = 0.03
RECENCY_HALFLIFE = 90    # 近接性加重: 90日前のシグナルは重み0.5
BASELINE_DECAY   = 0.95  # 現行compositeの95%超えで採用（更新ゲート緩和）
MAX_WIN10_DROP   = 0.20  # ★6大幅上昇件数の許容減少率（20%超減でNG）

# 更新通知先Discord Webhook
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1479431524674965729/sRCEG2lmoBLpEtZCdbf5N4kg2zEI7LHjtxxHm9g2Y1rFXPwoFSPDxpnOjsP0HAObSdyZ"

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

def save_current_logic(method, conditions, thresholds=None):
    """デプロイ成功後に現行ロジックを保存する。"""
    import json
    data = {
        "method": method,
        "conditions": conditions,
        "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    if thresholds:
        data["thresholds"] = thresholds
    try:
        with open(CURRENT_LOGIC_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  ✅ current_logic.json 更新完了")
    except Exception as e:
        print(f"  ⚠ current_logic.json 保存エラー: {e}")

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

def parse_alerts(rows):
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
        p5 = parse_perf(g("perf_5bd"))
        if math.isnan(p5): continue
        recs.append({
            "symbol": sym, "name": g("symbol_name").strip(),
            "date": g("signal_date").strip(),
            "entry": float(str(g("entry_price")).replace(",", "") or 0),
            "perf_5bd": p5,
            "win_5bd": p5 > 0  # win_flag_5bdはGAS取得タイミング次第でズレるため自力判定
        })
    df = pd.DataFrame(recs)
    if df.empty: return df
    df["win10"]  = df["perf_5bd"] >= 0.10
    df["lose10"] = df["perf_5bd"] <= -0.10
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

    m12 = ema_arr(C, 12); m26 = ema_arr(C, 26)
    ml  = [a - b for a, b in zip(m12, m26) if a is not None and b is not None]
    sig = ema_arr(ml, 9)
    gc3 = False
    if len(ml) >= 12 and len(sig) >= 4:
        for i in range(min(3, len(sig) - 1)):
            hn = ml[len(ml)-1-i] - sig[len(sig)-1-i]
            hp = ml[len(ml)-2-i] - sig[len(sig)-2-i]
            if hn > 0 and hp <= 0: gc3 = True; break
    macd_pos = len(ml) > 0 and len(sig) > 0 and ml[-1] > sig[-1]

    d = [C[i] - C[i-1] for i in range(1, len(C))]
    ag = sum(x for x in d[-14:] if x > 0) / 14 if len(d) >= 14 else 0
    al = sum(-x for x in d[-14:] if x < 0) / 14 if len(d) >= 14 else 0
    rsi = 100 - 100 / (1 + ag/al) if al > 0 else 100

    hi20 = max(H[max(0, last-20):last]) if last > 0 else lc
    hb20 = lc > hi20

    lo14 = min(L[max(0, last-13):last+1])
    hi14 = max(H[max(0, last-13):last+1])
    stoch = (lc - lo14) / (hi14 - lo14) * 100 if (hi14 - lo14) > 0 else 50

    bb = C[max(0, last-19):last+1]
    bm = sum(bb) / len(bb)
    bs = (sum((x - bm)**2 for x in bb) / len(bb)) ** 0.5
    bbpct = max(0, min(1, ((lc - (bm - 2*bs)) / (4*bs)) if bs > 0 else 0.5))

    return dict(
        ema75=e75 is not None and lc > e75, ema25=lc > e25,
        vol20=vsurge >= 2.0, vol15=vsurge >= 1.5, vol12=vsurge >= 1.2,
        sbull=body_pct >= 0.5, body1=body_pct >= 1.0,
        macdgc=gc3, macdpos=macd_pos,
        atr5=atr_pct < 5.0, atr3=atr_pct < 3.0, atr7=atr_pct < 7.0,
        hb20=hb20,
        stoch75=stoch >= 75, stoch60=stoch >= 60,
        rsi5070=50 <= rsi < 70, rsi4060=40 <= rsi < 60,
        bb80=bbpct >= 0.80,
        _vsurge=vsurge, _atr=atr_pct, _body=body_pct,
        _rsi=rsi, _stoch=stoch, _bbpct=bbpct,
    )

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
                composite=wr*50 + avg*100 + (w10-l10)*3)

def check_criteria(stats, baseline):
    if stats["n"] < 5: return False, ["★6件数5件未満"]
    threshold = baseline["composite"] * BASELINE_DECAY
    ok_comp = stats["composite"] > threshold
    # 絶対条件②: 勝率が現行以上（最重要）
    ok_wr = stats["wr_raw"] >= baseline["wr_raw"]
    # 絶対条件③: ★6大幅上昇件数が MAX_WIN10_DROP 以上減っていたらNG
    win10_floor = baseline["win10_raw"] * (1 - MAX_WIN10_DROP)
    ok_win10 = stats["win10_raw"] >= win10_floor
    ok = ok_comp and ok_wr and ok_win10
    # 表示は非加重の実カウント値を使用
    res = [
        f"{'✓' if ok_comp else '✗'} 絶対条件①: composite {stats['composite']:.1f} {'>' if ok_comp else '≤'} 現行{baseline['composite']:.1f}×{BASELINE_DECAY}={threshold:.1f}",
        f"{'✓' if ok_wr else '✗'} 絶対条件②: 勝率 {stats['wr_raw']*100:.1f}% {'≥' if ok_wr else '<'} 現行{baseline['wr_raw']*100:.1f}%",
        f"{'✓' if ok_win10 else '✗'} 絶対条件③: 大幅上昇 {stats['win10_raw']:.0f}件 {'≥' if ok_win10 else '<'} 現行{baseline['win10_raw']:.0f}件×{1-MAX_WIN10_DROP:.2f}={win10_floor:.1f}件",
        f"{'✓' if stats['wr_raw']>=TARGET_WIN_RATE else '△'} 努力①勝率 {stats['wr_raw']*100:.1f}% (≥55%)",
        f"{'✓' if stats['avg_raw']>=TARGET_AVG_PERF else '△'} 努力②平均 {stats['avg_raw']*100:.1f}% (>+3%)",
        f"{'✓' if stats['win10_raw']>stats['lose10_raw'] else '△'} 努力③上昇{stats['win10_raw']:.0f}件>下落{stats['lose10_raw']:.0f}件",
    ]
    return ok, res

# ══════════════════════════════════════════════════════════════
# 方式A: C(N,6) 組み合わせ探索
# ══════════════════════════════════════════════════════════════
BOOL_CONDS = [
    "ema75","ema25","vol20","vol15","vol12","sbull","body1",
    "macdgc","macdpos","atr5","atr3","atr7","hb20",
    "stoch75","stoch60","rsi5070","rsi4060","bb80",
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
}

# 連続値列 → 閾値候補
PARAM_CANDIDATES = {
    "_vsurge": [1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0],
    "_body":   [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0],
    "_atr":    [2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
    "_stoch":  [40, 45, 50, 55, 60, 65, 70, 75, 80, 85],
    "_bbpct":  [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95],
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
}

def score_with_thresholds(df, combo, thresholds):
    """comboの条件でスコア列を計算（パラメーター化条件には thresholds の値を使用）"""
    scores = pd.Series(0, index=df.index)
    for c in combo:
        if c in thresholds and c in COND_PARAM:
            raw_col, _, direction = COND_PARAM[c]
            th = thresholds[c]
            scores += (df[raw_col] >= th).astype(int) if direction == ">=" else (df[raw_col] < th).astype(int)
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

def search_combinations(df, baseline):
    conds = [c for c in BOOL_CONDS if c in df.columns]
    for c in conds: df[c] = df[c].astype(bool)
    total = sum(1 for _ in combinations(conds, 6))
    print(f"  探索数: C({len(conds)},6) = {total:,}通り")
    best = []
    for combo in combinations(conds, 6):
        scores = sum(df[c].astype(int) for c in combo)
        s6 = df[scores == 6]
        if len(s6) < 5: continue
        st6 = calc_stats(s6)
        if st6["composite"] <= baseline["composite"] * BASELINE_DECAY: continue
        # 勝率が現行未満なら除外（最重要）
        if st6["wr_raw"] < baseline["wr_raw"]: continue
        # ★6大幅上昇件数が MAX_WIN10_DROP 以上減っていたら除外
        if st6["win10_raw"] < baseline["win10_raw"] * (1 - MAX_WIN10_DROP): continue
        # ★5/★4 もタイブレーカー用に計算（各ランク単独・悪化してもOK）
        st5 = calc_stats(df[scores == 5])
        st4 = calc_stats(df[scores == 4])
        best.append((st6["composite"], st5["composite"], st4["composite"],
                     list(combo), st6, st5, st4))
    best.sort(reverse=True)  # (★6, ★5, ★4) タプルで比較
    return best

# ══════════════════════════════════════════════════════════════
# 方式B: +10%銘柄共通点分析 → 重み付きスコア自動設計
# ══════════════════════════════════════════════════════════════
def analyze_winners(df, baseline):
    winners = df[df["win10"] == True]
    n_all = len(df); n_win = len(winners)
    if n_win < 5:
        print("  +10%銘柄5件未満のためスキップ"); return None
    print(f"  +10%以上: {n_win}件 / 全体: {n_all}件 ({n_win/n_all*100:.1f}%)")

    conds = [c for c in BOOL_CONDS if c in df.columns]
    lifts = []
    for c in conds:
        ra = df[c].astype(bool).mean()
        rw = winners[c].astype(bool).mean()
        lift = rw / ra if ra > 0 else 1.0
        lifts.append((lift, c, rw, ra))
    lifts.sort(reverse=True)

    print(f"\n  【+10%銘柄への識別力（リフト値上位10）】")
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
    if len(s6) < 5: print("  方式B: ★6件数不足"); return None

    st6 = calc_stats(s6)
    ok, _ = check_criteria(st6, baseline)
    st5 = calc_stats(df[df["score_b"] == 5])
    st4 = calc_stats(df[df["score_b"] == 4])
    print(f"  方式B ★6: {st6['n']}件 勝率{st6['wr_raw']*100:.1f}% 平均{st6['avg_raw']*100:.1f}%"
          f" 上昇{st6['win10_raw']:.0f} 下落{st6['lose10_raw']:.0f} → {'✓絶対条件OK' if ok else '✗絶対条件NG'}")
    return (scheme, st6, st5, st4) if ok else None

# ══════════════════════════════════════════════════════════════
# Stage 2: 閾値最適化
# ══════════════════════════════════════════════════════════════
def tune_thresholds(df_train, df_test, combo, baseline):
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
            if len(s6) < 5: continue
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
                if len(s6) < 5: continue
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
        passed = test_stats["n"] >= 2 and test_stats["composite"] > test_cur_stats["composite"]
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
  const hiBrk20 = latestClose > hi20v;"""

EXTRA_JS_RETURN = """    macdPos,
    rsi14:    +rsi14.toFixed(2),
    stochK:   +stochK.toFixed(2),
    bbPct:    +bbPct.toFixed(4),
    hiBrk20,"""


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

    with open(SCREENER_JS_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    return True

def update_index_js_help(conditions, method):
    """/helpのスコアリング条件テキストをindex.jsで更新"""
    if not os.path.exists(INDEX_JS_PATH):
        print(f"  ⚠ index.js が見つかりません: {INDEX_JS_PATH}"); return False
    with open(INDEX_JS_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    NUMS_FULL = ["①","②","③","④","⑤","⑥"]
    new_lines = []
    if method == "A":
        for i, c in enumerate(conditions):
            desc = JS_IMPL[c][0] if c in JS_IMPL else c
            new_lines.append(f"'{NUMS_FULL[i]} {desc}    1点\\n' +")
    else:
        for i, (c, w, lift) in enumerate(conditions):
            desc = JS_IMPL[c][0] if c in JS_IMPL else c
            new_lines.append(f"'{NUMS_FULL[min(i,5)]} {desc}    {w}点\\n' +")

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
def notify_discord_update(best_method, best_combo, st6, st5, st4, base, n_total, what_changed="conditions"):
    """スコアロジック更新をDiscordに通知
    what_changed: "conditions" | "thresholds" | "both"
    """
    import urllib.request, json as _json

    NL = "\n"  # 改行文字（文字列連結で使う）

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

    # 条件テキスト
    NUMS_FULL = ["①","②","③","④","⑤","⑥"]
    if best_method == "A":
        cond_lines = [f"{NUMS_FULL[i]} {JS_IMPL.get(c,('',))[0] or c}  1点"
                      for i, c in enumerate(best_combo)]
    else:
        cond_lines = [f"{NUMS_FULL[min(i,5)]} {JS_IMPL.get(c,('',))[0] or c}  {w}点"
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
                "name": f"📈 バックテスト結果（{n_total}シグナル検証）",
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
            ("③ pm2 restart",
             ["ssh", "-i", SSH_KEY_PATH, "-o", "StrictHostKeyChecking=no",
              VM_HOST, "pm2 restart screening-bot"]),
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
    else:
        # ローカルWindows: PowerShell経由でscp/ssh
        steps = [
            ("① scp転送(screener.js)",
             f'scp -i "{SSH_KEY_PATH}" "{SCREENER_JS_PATH}" {VM_HOST}:{VM_DEST}'),
            ("② scp転送(index.js)",
             f'scp -i "{SSH_KEY_PATH}" "{INDEX_JS_PATH}" {VM_HOST}:{VM_DEST}'),
            ("③ pm2 restart",
             f'ssh -i "{SSH_KEY_PATH}" -o StrictHostKeyChecking=no {VM_HOST} "pm2 restart screening-bot"'),
        ]
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

# ══════════════════════════════════════════════════════════════
# メイン
# ══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", "--no-apply", action="store_true")
    parser.add_argument("--yes", "-y", action="store_true", help="確認プロンプトをスキップして自動デプロイ")
    args = parser.parse_args()

    print("=" * 62)
    print("天底極致 スコアロジック自動最適化")
    print("=" * 62)

    print("\n📡 Step 1: データ取得...")
    try:
        svc = get_service()
        print("  接続OK...")
        ar = fetch(svc, "alerts_raw")
        oh = fetch(svc, "ohlcv_4h")
        print(f"  alerts_raw: {len(ar)}行 / ohlcv_4h: {len(oh)}行")
    except Exception as e:
        print(f"❌ 取得エラー: {e}"); sys.exit(1)

    print("\n🔧 Step 2: 解析...")
    alerts = parse_alerts(ar)
    ohlcv  = parse_ohlcv(oh)
    print(f"  BOTTOMシグナル確定済み: {len(alerts)}件")
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
        baseline = calc_stats(df[df["sc_v14"] == 6])
        print(f"  v14.1★6: {baseline['n']}件 勝率{baseline['wr_raw']*100:.1f}%"
              f" 平均{baseline['avg_raw']*100:.2f}% 上昇{baseline['win10_raw']:.0f}件 下落{baseline['lose10_raw']:.0f}件")

    print("\n🔍 Step 5a: 方式A（組み合わせ探索）...")
    cands_a = search_combinations(df.copy(), baseline)
    print(f"  絶対条件クリア: {len(cands_a)}通り")

    print("\n🔍 Step 5b: 方式B（+10%共通点分析）...")
    result_b = analyze_winners(df.copy(), baseline)

    print(f"\n🏆 Step 6: 候補一覧（上位10）")
    print(f"  {'#':<3} {'方式':<4} {'★6勝率':>7} {'★6平均':>8} {'上昇':>4} {'下落':>4} {'件数':>4} {'努力':>4}  条件")
    all_cands = []
    for sc6, sc5, sc4, combo, st6, st5, st4 in cands_a[:9]:
        all_cands.append(("A", sc6, sc5, sc4, combo, st6, st5, st4))
    if result_b:
        scheme_b, stats_b6, stats_b5, stats_b4 = result_b
        all_cands.append(("B", stats_b6["composite"], stats_b5["composite"],
                          stats_b4["composite"], scheme_b, stats_b6, stats_b5, stats_b4))
    # ★6総合スコア → 順序スコア(努力義務) → ★5 → ★4 の順でソート
    all_cands.sort(key=lambda x: (-x[1], -calc_ordering_score(x[5], x[6], x[7]), -x[2], -x[3]))

    for i, (method, sc6, sc5, sc4, combo, st6, st5, st4) in enumerate(all_cands[:10]):
        e = ("✓" if st6["wr_raw"] >= TARGET_WIN_RATE else "△") + \
            ("✓" if st6["avg_raw"] >= TARGET_AVG_PERF else "△") + \
            ("✓" if st6["win10_raw"] > st6["lose10_raw"] else "△")
        label = "+".join(combo) if method == "A" else " ".join(f"{c}({w}pt)" for c, w, _ in combo)
        print(f"  #{i+1:<2} {method:<4} {st6['wr_raw']*100:>6.1f}%  {st6['avg_raw']*100:>+7.1f}%"
              f"  {st6['win10_raw']:>3.0f}件  {st6['lose10_raw']:>3.0f}件  {st6['n']:>3}件  {e}  {label}")

    # ── Step 5c: 閾値最適化（train/test split） ──────────────
    best_thresholds = {}
    if not all_cands:
        # 新しい組み合わせなし → 現行条件の閾値だけ最適化を試みる
        if not (current_logic and current_logic["method"] == "A"):
            print("\n✅ 現行ロジックが最良。更新しません。"); return
        print(f"\n🔍 組み合わせ変更なし → 閾値最適化のみ試みます")
        cur_conds = current_logic["conditions"]
        df_sorted = df.sort_values("date").reset_index(drop=True)
        split_idx = int(len(df_sorted) * 0.8)
        df_train  = df_sorted.iloc[:split_idx].copy()
        df_test   = df_sorted.iloc[split_idx:].copy()
        print(f"📐 train/test split: 訓練{len(df_train)}件 / 検証{len(df_test)}件")
        tuned_ths, _, _, tune_passed = tune_thresholds(df_train, df_test, cur_conds, baseline)
        if not (tune_passed and tuned_ths):
            print("\n✅ 現行ロジックが最良。更新しません。"); return
        best_thresholds = tuned_ths
        s_full = score_with_thresholds(df, cur_conds, best_thresholds)
        best_method  = "A"
        best_combo   = cur_conds
        best_stats   = calc_stats(df[s_full == 6])
        best_stats5  = calc_stats(df[s_full == 5])
        best_stats4  = calc_stats(df[s_full == 4])
    else:
        best_method_pre, _, _, _, best_combo_pre = all_cands[0][:5]
        if best_method_pre == "A":
            df_sorted = df.sort_values("date").reset_index(drop=True)
            split_idx = int(len(df_sorted) * 0.8)
            df_train  = df_sorted.iloc[:split_idx].copy()
            df_test   = df_sorted.iloc[split_idx:].copy()
            print(f"\n📐 train/test split: 訓練{len(df_train)}件 / 検証{len(df_test)}件")
            tuned_ths, _, _, tune_passed = tune_thresholds(df_train, df_test, best_combo_pre, baseline)
            if tune_passed and tuned_ths:
                best_thresholds = tuned_ths
                s_full = score_with_thresholds(df, best_combo_pre, best_thresholds)
                st6f = calc_stats(df[s_full == 6])
                st5f = calc_stats(df[s_full == 5])
                st4f = calc_stats(df[s_full == 4])
                all_cands[0] = ("A", st6f["composite"], st5f["composite"],
                                st4f["composite"], best_combo_pre, st6f, st5f, st4f)
        best_method, _, _, _, best_combo, best_stats, best_stats5, best_stats4 = all_cands[0]
    ok, check_res = check_criteria(best_stats, baseline)
    print(f"\n🎯 Step 7: 採用判断 — 方式{best_method}")
    for line in check_res: print(f"  {line}")
    ord_sc = calc_ordering_score(best_stats, best_stats5, best_stats4)
    ord_lb = ordering_label(best_stats, best_stats5, best_stats4)
    print(f"  {'✓' if ord_sc >= 1 else '△'} 努力④順序: {ord_lb}")
    print(f"  タイブレーカー参照:")
    print(f"    ★5: {best_stats5['n']}件 勝率{best_stats5['wr_raw']*100:.1f}% 平均{best_stats5['avg_raw']*100:.1f}%")
    print(f"    ★4: {best_stats4['n']}件 勝率{best_stats4['wr_raw']*100:.1f}% 平均{best_stats4['avg_raw']*100:.1f}%")

    if not ok:
        print("\n❌ 絶対条件未達。更新しません。"); return

    new_code = (build_func_a(best_combo, best_stats, baseline, len(df), best_thresholds)
                if best_method == "A"
                else build_func_b(best_combo, best_stats, baseline, len(df)))

    if args.dry_run:
        print(f"\n🔍 Dry-run: 更新・デプロイをスキップ")
        print(f"  採用予定: 方式{best_method} / "
              f"{best_combo if best_method == 'A' else [c for c, w, _ in best_combo]}")
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
    if update_index_js_help(best_combo, best_method):
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

        # Discord更新通知（全シグナル点灯地点で集計 → /helpと同じ母集団）
        s_all = score_with_thresholds(df, best_combo, new_ths)
        nt6 = calc_stats(df[s_all == 6])
        nt5 = calc_stats(df[s_all == 5])
        nt4 = calc_stats(df[s_all == 4])
        base_all = dict(n=len(df), wr=df["win_5bd"].mean(), avg=df["perf_5bd"].mean())
        notify_discord_update(best_method, best_combo, nt6, nt5, nt4, base_all, len(df), what_changed)
    else:
        print("\n⚠ デプロイ失敗。手動でscp & pm2 restartしてください")

    print(f"\n{'=' * 62}")
    print(f"完了 — 方式{best_method}")
    print(f"★6: {best_stats['n']}件 勝率{best_stats['wr_raw']*100:.1f}%"
          f" 平均{best_stats['avg_raw']*100:.1f}% 上昇{best_stats['win10_raw']:.0f}件 下落{best_stats['lose10_raw']:.0f}件")
    print("=" * 62)

if __name__ == "__main__":
    main()
