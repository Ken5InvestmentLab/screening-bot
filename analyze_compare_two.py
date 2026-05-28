#!/usr/bin/env python3
"""
2つの6条件ロジックを5BD/10BD/20BDの3軸で比較。
"""
import os, sys, math
import numpy as np
import pandas as pd

# ロジック定義
LOGIC_A = ("20BDベスト", ["ema25","body2","macdpos","atr5","bb80","pre_down3"])
LOGIC_B = ("新提案",     ["ema25","vol20","body2","macdgc","atr5","pre_down3"])
CURRENT = ("現行",       ["body1","stoch75","rsi5070","ich_price_kijun","pre_down3","gap_up"])

EVAL_MODULES = {
    "5BD":  "optimize_screener",
    "10BD": "optimize_screener_10bd",
    "20BD": "optimize_screener_20bd",
}

def load_data(module_name):
    mod = __import__(module_name)
    svc = mod.get_service()
    ar = mod.fetch(svc, "alerts_raw")
    sa = mod.fetch(svc, "signals_archive")
    oh = mod.fetch(svc, "ohlcv_4h")
    ar_c = mod.parse_alerts(ar); ar_c['_from_archive'] = False
    sa_c = mod.parse_alerts(sa); sa_c['_from_archive'] = True
    alerts = pd.concat([ar_c, sa_c], ignore_index=True)
    if "alert_id" in alerts.columns and len(alerts) > 0:
        _has = alerts["alert_id"].astype(str) != ""
        alerts = pd.concat([
            alerts[_has].drop_duplicates(subset=["alert_id"], keep="first"),
            alerts[~_has],
        ], ignore_index=True)
    ohlcv = mod.parse_ohlcv(oh)
    rows = []
    for _, r in alerts.iterrows():
        f = mod.get_features(ohlcv.get(r["symbol"], []), r["date"])
        if f: rows.append({**r.to_dict(), **f})
    return pd.DataFrame(rows), ohlcv

def eval_logic(df, combo):
    for c in combo:
        df[c] = df[c].astype(bool)
    sc = sum(df[c].astype(int) for c in combo)
    s6 = df[sc == 6].copy()
    n = len(s6)
    if n == 0:
        return {"n":0,"wr":0,"avg":0,"win10":0,"lose10":0,"composite":0,"s6":s6}
    perf = s6["perf_5bd"].to_numpy()  # 列名はperf_5bdだが、中身は評価軸に合わせて入れ替わってる
    win  = s6["win_5bd"].to_numpy().astype(float)
    win10 = (perf >= 0.10).astype(float).sum()
    lose10 = (perf <= -0.10).astype(float).sum()
    wr  = float(win.mean())
    avg = float(perf.mean())
    composite = wr*40 + avg*100 + (win10-lose10)/n*250
    return {"n":n,"wr":wr*100,"avg":avg*100,"win10":int(win10),"lose10":int(lose10),
            "composite":composite,"s6":s6}

def main():
    print("="*78)
    print("2ロジック比較: 5BD / 10BD / 20BD 全評価軸")
    print("="*78)
    print(f"  A: {LOGIC_A[0]:<10} {'+'.join(LOGIC_A[1])}")
    print(f"  B: {LOGIC_B[0]:<10} {'+'.join(LOGIC_B[1])}")
    print(f"  ★現行 {'+'.join(CURRENT[1])}")
    print(f"  差分: A→Bで [macdpos,bb80] → [vol20,macdgc] に入替")

    results = {}  # results[eval_label][logic_label] = stats
    for eval_label, mod_name in EVAL_MODULES.items():
        print(f"\n📡 {eval_label}データ取得中...")
        df, ohlcv = load_data(mod_name)
        print(f"  有効データ: {len(df)}件")
        results[eval_label] = {}
        for label, combo in [LOGIC_A, LOGIC_B, CURRENT]:
            results[eval_label][label] = eval_logic(df.copy(), combo)

    # サマリーテーブル
    print("\n" + "="*78)
    print("📊 サマリー: ★6成績")
    print("="*78)
    header = f"  {'評価':<6} {'ロジック':<12} {'件数':>5} {'勝率':>6} {'平均':>8} {'+10%':>5} {'-10%':>5} {'composite':>10}"
    print(header)
    print("  " + "-"*(len(header)-2))
    for eval_label in EVAL_MODULES:
        for label, _ in [LOGIC_A, LOGIC_B, CURRENT]:
            r = results[eval_label][label]
            print(f"  {eval_label:<6} {label:<12} {r['n']:>5} {r['wr']:>5.1f}% {r['avg']:>+7.2f}%"
                  f" {r['win10']:>5} {r['lose10']:>5} {r['composite']:>10.2f}")
        print()

    # 軸別優劣判定
    print("="*78)
    print("🏆 軸別優劣（A vs B / 各指標どちらが上か）")
    print("="*78)
    for eval_label in EVAL_MODULES:
        ra = results[eval_label]["20BDベスト"]
        rb = results[eval_label]["新提案"]
        print(f"\n  【{eval_label}】")
        print(f"   件数      : A={ra['n']:>3}件  B={rb['n']:>3}件  → {'B優' if rb['n']>ra['n'] else ('A優' if ra['n']>rb['n'] else '同点')}")
        print(f"   勝率      : A={ra['wr']:>5.1f}% B={rb['wr']:>5.1f}% → {'B優' if rb['wr']>ra['wr'] else ('A優' if ra['wr']>rb['wr'] else '同点')}")
        print(f"   平均      : A={ra['avg']:>+6.2f}% B={rb['avg']:>+6.2f}% → {'B優' if rb['avg']>ra['avg'] else ('A優' if ra['avg']>rb['avg'] else '同点')}")
        print(f"   +10%上昇  : A={ra['win10']:>3}件  B={rb['win10']:>3}件  → {'B優' if rb['win10']>ra['win10'] else ('A優' if ra['win10']>rb['win10'] else '同点')}")
        print(f"   -10%下落  : A={ra['lose10']:>3}件  B={rb['lose10']:>3}件  → {'B優(少)' if rb['lose10']<ra['lose10'] else ('A優(少)' if ra['lose10']<rb['lose10'] else '同点')}")
        print(f"   composite : A={ra['composite']:>7.2f} B={rb['composite']:>7.2f} → {'B優' if rb['composite']>ra['composite'] else ('A優' if ra['composite']>rb['composite'] else '同点')}")

    # 20BD評価での★6一覧（両方）
    print("\n" + "="*78)
    print("📋 20BD評価での★6一覧（A=20BDベスト vs B=新提案）")
    print("="*78)
    for label, _ in [LOGIC_A, LOGIC_B]:
        r = results["20BD"][label]
        cur = results["20BD"]["現行"]
        s6 = r["s6"].sort_values("date", ascending=False)
        cur_pairs = set(zip(cur["s6"]["symbol"], cur["s6"]["date"]))
        new_pairs = set(zip(s6["symbol"], s6["date"]))
        print(f"\n── 【{label}】★6 {len(s6)}件 (現行と比べて: 継続{len(cur_pairs & new_pairs)} 新規{len(new_pairs-cur_pairs)} 脱落{len(cur_pairs-new_pairs)}) ──")
        print(f"  {'日付':<12} {'銘柄':<8} {'社名':<24} {'20BD騰落':>9}")
        for _, row in s6.iterrows():
            p20 = row["perf_5bd"]  # 20BD評価モードではperf_5bd列に20BD値が入ってる
            sign = "+" if p20 >= 0 else ""
            print(f"  {row['date']:<12} {row['symbol']:<8} {row['name']:<24} {sign}{p20*100:>7.1f}%")

    # A∩B / A only / B only
    print("\n" + "="*78)
    print("🔀 20BD評価★6 — A∩B / Aのみ / Bのみ")
    print("="*78)
    sa = results["20BD"]["20BDベスト"]["s6"]
    sb = results["20BD"]["新提案"]["s6"]
    pa = set(zip(sa["symbol"], sa["date"]))
    pb = set(zip(sb["symbol"], sb["date"]))
    both = pa & pb
    a_only = pa - pb
    b_only = pb - pa
    print(f"  A∩B: {len(both)}件 / Aのみ: {len(a_only)}件 / Bのみ: {len(b_only)}件")

if __name__ == "__main__":
    main()
