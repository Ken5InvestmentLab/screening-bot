#!/usr/bin/env python3
"""
Moonshot v2 — 4案バックテスト比較 (20BD × +50% Mega Hit 母集団10件基準)

A: アンサンブル方式 (3-5本の専用ロジック並列、いずれか1本で★6)
B: Method B型 重み付きスコア
C: ATR%低位フィルター (緩い構造で広く拾う)
D: 現案 #1 (AND型 ema25+pre_down3+vol15+vol30+macdgc+stoch75)
"""
import math
import pandas as pd
import numpy as np
from itertools import combinations
import optimize_screener as opt

MEGA_THRESHOLD = 0.50
MEGA_PERF_COL = "perf_20bd"

# === 各案の定義 ===

# A: アンサンブル — 3パターン専用ロジック
# 6217型 (大陽線爆発・出来高大噴出)
A_TYPE_BIG_CANDLE = ["ema25","body2","macdgc","atr5","stoch75","vol30"]
# 9256型 (低位出来高高吹き・bb下限離脱)
A_TYPE_LOW_PRICE_VOL = ["vol30","atr3","lower_wick50","bb_lower","cci_os","gap_up"]
# 8289型 (静かなMACD反発・押し目)
A_TYPE_QUIET_MACD = ["ema25","macdgc","stoch75","rsi4060","atr3","gap_up"]

# B: Method B型 — lift>=2.0 の指標に1点ずつ加算、5点以上で★6
B_INDICATORS = [
    ("pre_down3", 3),   # lift 3.19
    ("vol30",     3),   # lift 3.05
    ("macdgc",    3),   # lift 2.96
    ("cci_os",    2),   # lift 2.41
    ("stoch75",   2),   # lift 2.39
    ("pre_decline15", 2),
    ("bb_lower",  2),
    ("rci9_os",   2),
    ("vol20",     2),
    ("body2",     1),   # lift 1.75
    ("gap_up",    1),   # lift 1.74
    ("ema25",     1),   # lift 1.51
]
B_SCORE_THRESHOLD = 8  # 計23点満点中8点以上で★6

# C: ATR%低位フィルター — 必須3条件 + 任意1個以上で★6
C_MANDATORY = ["atr3"]   # ATR%<3%
C_OPTIONAL = ["vol20","vol30","macdgc","stoch75","stoch60","cci_os","bb_lower","rci9_os","gap_up","pre_down3"]
C_OPTIONAL_MIN = 2

# D: 現案 #1
D_CONDS = ["ema25","pre_down3","vol15","vol30","macdgc","stoch75"]


def load_df():
    print("📡 データ取得中...")
    svc = opt.get_service()
    ar = opt.fetch(svc, "alerts_raw")
    sa = opt.fetch(svc, "signals_archive")
    oh = opt.fetch(svc, "ohlcv_4h")
    ar_c = opt.parse_alerts(ar); ar_c['_from_archive']=False
    sa_c = opt.parse_alerts(sa); sa_c['_from_archive']=True
    alerts = pd.concat([ar_c, sa_c], ignore_index=True)
    if "alert_id" in alerts.columns:
        _h = alerts["alert_id"].astype(str) != ""
        alerts = pd.concat([
            alerts[_h].drop_duplicates(subset=["alert_id"], keep="first"),
            alerts[~_h]], ignore_index=True)
    ohlcv = opt.parse_ohlcv(oh)
    rows = []
    for _, r in alerts.iterrows():
        f = opt.get_features(ohlcv.get(r["symbol"], []), r["date"])
        if f: rows.append({**r.to_dict(), **f})
    df = pd.DataFrame(rows)
    # 母集団: perf_20bd 確定済みのみ
    df = df[df[MEGA_PERF_COL].apply(lambda v: isinstance(v,(int,float)) and math.isfinite(v))].reset_index(drop=True)
    df["is_mega"]   = df[MEGA_PERF_COL] >= MEGA_THRESHOLD
    df["perf_eval"] = df[MEGA_PERF_COL]
    return df

def apply_logic_a(df):
    """A: いずれか1本でも★6なら採用"""
    for c in set(A_TYPE_BIG_CANDLE + A_TYPE_LOW_PRICE_VOL + A_TYPE_QUIET_MACD):
        if c in df.columns: df[c] = df[c].astype(bool)
    scA = sum(df[c].astype(int) for c in A_TYPE_BIG_CANDLE)
    scB = sum(df[c].astype(int) for c in A_TYPE_LOW_PRICE_VOL)
    scC = sum(df[c].astype(int) for c in A_TYPE_QUIET_MACD)
    hit = (scA == len(A_TYPE_BIG_CANDLE)) | (scB == len(A_TYPE_LOW_PRICE_VOL)) | (scC == len(A_TYPE_QUIET_MACD))
    # タグも付与
    tags = []
    for i in range(len(df)):
        t = []
        if scA.iloc[i] == len(A_TYPE_BIG_CANDLE): t.append("BIG")
        if scB.iloc[i] == len(A_TYPE_LOW_PRICE_VOL): t.append("LOW")
        if scC.iloc[i] == len(A_TYPE_QUIET_MACD): t.append("QUIET")
        tags.append("/".join(t) if t else "")
    df_hit = df[hit].copy()
    df_hit["tag"] = [t for h, t in zip(hit, tags) if h]
    return df_hit

def apply_logic_b(df):
    """B: 重み付きスコア計N点以上"""
    for c, w in B_INDICATORS:
        if c in df.columns: df[c] = df[c].astype(bool)
    score = sum(df[c].astype(int) * w for c, w in B_INDICATORS if c in df.columns)
    df_out = df[score >= B_SCORE_THRESHOLD].copy()
    df_out["b_score"] = score[score >= B_SCORE_THRESHOLD]
    return df_out

def apply_logic_c(df):
    """C: 必須 + 任意N個以上"""
    for c in C_MANDATORY + C_OPTIONAL:
        if c in df.columns: df[c] = df[c].astype(bool)
    mand = pd.Series([True]*len(df))
    for c in C_MANDATORY:
        if c in df.columns: mand = mand & df[c]
    opt_score = sum(df[c].astype(int) for c in C_OPTIONAL if c in df.columns)
    hit = mand & (opt_score >= C_OPTIONAL_MIN)
    df_out = df[hit].copy()
    df_out["c_opt"] = opt_score[hit]
    return df_out

def apply_logic_d(df):
    """D: AND型現案"""
    for c in D_CONDS:
        if c in df.columns: df[c] = df[c].astype(bool)
    sc = sum(df[c].astype(int) for c in D_CONDS)
    return df[sc == len(D_CONDS)].copy()

def stats(s6, total_mega, total_n):
    if len(s6) == 0:
        return dict(n=0, mega=0, recall=0, lift=0, wr=0, avg=0, win10=0, lose10=0, max_up=0, max_dn=0)
    perf_eval = s6["perf_eval"].to_numpy()
    mega_hits = int(s6["is_mega"].sum())
    recall = mega_hits / max(total_mega, 1)
    base_rate = total_mega / max(total_n, 1)
    s6_rate = mega_hits / len(s6)
    return dict(
        n=len(s6),
        mega=mega_hits,
        recall=recall*100,
        lift=s6_rate / base_rate if base_rate > 0 else 0,
        wr=(perf_eval > 0).mean()*100,
        avg=perf_eval.mean()*100,
        win10=int((perf_eval >= 0.10).sum()),
        lose10=int((perf_eval <= -0.10).sum()),
        max_up=perf_eval.max()*100,
        max_dn=perf_eval.min()*100,
    )

def main():
    print("="*78)
    print("Moonshot v2 — 4案バックテスト比較 (20BD × +50% Mega母集団基準)")
    print("="*78)
    df = load_df()
    print(f"  確定母数: {len(df)}件")

    mega_all = df[df[MEGA_PERF_COL] >= MEGA_THRESHOLD]
    print(f"  Mega Hit (≥+50%): {len(mega_all)}件")
    for _, r in mega_all.sort_values(MEGA_PERF_COL, ascending=False).iterrows():
        print(f"    {r['date']:<12} {r['symbol']:<6} {r['name']:<24} {r[MEGA_PERF_COL]*100:+8.1f}%")
    total_mega = len(mega_all)

    print(f"\n{'─'*78}")
    print(f"📋 各案の定義")
    print(f"{'─'*78}")
    print(f"  A: アンサンブル (3型いずれか満点)")
    print(f"     6217型 (大陽線爆発): {'+'.join(A_TYPE_BIG_CANDLE)}")
    print(f"     9256型 (低位出来高): {'+'.join(A_TYPE_LOW_PRICE_VOL)}")
    print(f"     8289型 (静かMACD)  : {'+'.join(A_TYPE_QUIET_MACD)}")
    print(f"  B: 重み付き計{B_SCORE_THRESHOLD}点以上 (lift>=1.5指標を重み配分)")
    print(f"     {[(c,w) for c,w in B_INDICATORS]}")
    print(f"  C: 必須{C_MANDATORY} + 任意{C_OPTIONAL_MIN}個以上")
    print(f"     任意プール: {C_OPTIONAL}")
    print(f"  D: AND型 (現案#1): {'+'.join(D_CONDS)}")

    # 各案を実行
    results = {}
    df_copy = df.copy()
    results["A"] = (apply_logic_a(df_copy.copy()), "アンサンブル")
    results["B"] = (apply_logic_b(df_copy.copy()), f"重み付き>={B_SCORE_THRESHOLD}pt")
    results["C"] = (apply_logic_c(df_copy.copy()), "ATR低位+任意2")
    results["D"] = (apply_logic_d(df_copy.copy()), "AND型現案")

    # サマリー
    print(f"\n{'─'*78}")
    print(f"📊 サマリー比較")
    print(f"{'─'*78}")
    print(f"  {'案':<3} {'手法':<18} {'件数':>5} {'Mega':>5} {'Recall':>7} {'勝率':>5} {'平均':>7} {'+10%':>5} {'-10%':>5} {'最大上':>8} {'最大下':>8}")
    print(f"  {'-'*3} {'-'*18} {'-'*5} {'-'*5} {'-'*7} {'-'*5} {'-'*7} {'-'*5} {'-'*5} {'-'*8} {'-'*8}")
    for k in ["A","B","C","D"]:
        s6_df, label = results[k]
        st = stats(s6_df, total_mega, len(df))
        print(f"  {k:<3} {label:<18} {st['n']:>5} {st['mega']:>3}/{total_mega:<2}"
              f" {st['recall']:>6.1f}% {st['wr']:>4.1f}% {st['avg']:>+6.1f}%"
              f" {st['win10']:>5} {st['lose10']:>5} {st['max_up']:>+7.1f}% {st['max_dn']:>+7.1f}%")

    # Mega Hit取得状況比較
    print(f"\n{'─'*78}")
    print(f"🎯 各案がMega Hit 10件のうちどれを取れたか")
    print(f"{'─'*78}")
    print(f"  {'日付':<12} {'銘柄':<6} {'社名':<22} {'20BD':>8}  A  B  C  D")
    for _, r in mega_all.sort_values(MEGA_PERF_COL, ascending=False).iterrows():
        marks = []
        for k in ["A","B","C","D"]:
            s6, _ = results[k]
            in_set = ((s6["symbol"]==r["symbol"]) & (s6["date"]==r["date"])).any()
            marks.append("✓" if in_set else "✗")
        print(f"  {r['date']:<12} {r['symbol']:<6} {r['name'][:22]:<22} {r[MEGA_PERF_COL]*100:+7.1f}%  "
              + "  ".join(marks))

    # 各案の★6リスト表示
    for k in ["A","B","C","D"]:
        s6_df, label = results[k]
        print(f"\n{'─'*78}")
        print(f"📋 案{k} ({label}) の★6 シグナル一覧 ({len(s6_df)}件)")
        print(f"{'─'*78}")
        if len(s6_df) == 0:
            print("  (該当なし)")
            continue
        s6_sorted = s6_df.sort_values("date", ascending=False)
        extra = "tag" if k=="A" else ("b_score" if k=="B" else ("c_opt" if k=="C" else None))
        for _, r in s6_sorted.iterrows():
            p20 = r[MEGA_PERF_COL]
            tag = "🚀MEGA" if p20 >= MEGA_THRESHOLD else ("✓" if p20>0 else "✗")
            extra_str = f" [{r[extra]}]" if extra else ""
            print(f"  {r['date']:<12} {r['symbol']:<6} {r['name'][:24]:<24} {p20*100:+7.1f}% {tag}{extra_str}")

if __name__ == "__main__":
    main()
