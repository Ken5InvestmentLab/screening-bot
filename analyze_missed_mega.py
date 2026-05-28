#!/usr/bin/env python3
"""
案A (アンサンブル) で取りこぼした Mega Hit 7銘柄の指標クロス分析。
共通している true 指標を見つけ、新しい「4型目」を設計できるか調査する。
"""
import math
import pandas as pd
import numpy as np
import optimize_screener as opt

# 案Aの3型
A_TYPES = {
    "BIG (6217型)":   ["ema25","body2","macdgc","atr5","stoch75","vol30"],
    "LOW (9256型)":   ["vol30","atr3","lower_wick50","bb_lower","cci_os","gap_up"],
    "QUIET (8289型)": ["ema25","macdgc","stoch75","rsi4060","atr3","gap_up"],
}

# 取りこぼし7銘柄
MISSED = [
    ("6217", "2026/03/24", "津田駒工業(2)",     "+187.7%"),
    ("6480", "2026/04/08", "日本トムソン",        "+90.7%"),
    ("441A", "2026/04/06", "NE",                "+78.0%"),
    ("5341", "2026/04/03", "ASAHI EITO",        "+73.5%"),
    ("281A", "2026/03/16", "インフォメティス",      "+63.1%"),
    ("2195", "2026/03/18", "アミタHD",           "+59.0%"),
    ("7375", "2026/03/10", "リファインバース",      "+53.5%"),
]

def main():
    print("="*100)
    print("案A (アンサンブル) 取りこぼしMega 7銘柄 — クロス指標分析")
    print("="*100)

    print("\n📡 データ取得...")
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

    # 各銘柄の特徴量取得
    feats = {}
    for sym, date, name, perf in MISSED:
        rows = alerts[(alerts["symbol"]==sym) & (alerts["date"]==date)]
        if rows.empty:
            print(f"  ⚠ {sym} {date} ({name}) はalerts内に見つからない")
            continue
        r = rows.iloc[0]
        f = opt.get_features(ohlcv.get(sym, []), r["date"])
        if f:
            feats[(sym, date, name, perf)] = f
        else:
            print(f"  ⚠ {sym} ({name}) 指標計算失敗")

    if not feats:
        print("該当データなし")
        return

    # 案A各型のスコア状況
    print(f"\n──── 案Aの3型に対する通過状況 ────")
    print(f"  {'銘柄':<22} {'BIG':>5} {'LOW':>5} {'QUIET':>5}")
    print(f"  {'-'*22} {'-'*5} {'-'*5} {'-'*5}")
    for (sym, date, name, perf), f in feats.items():
        scores = {}
        for tname, conds in A_TYPES.items():
            s = sum(1 for c in conds if f.get(c))
            scores[tname.split()[0]] = f"{s}/{len(conds)}"
        print(f"  {sym} {name[:15]:<15} {scores['BIG']:>5} {scores['LOW']:>5} {scores['QUIET']:>5}")

    # 全BOOL_CONDS の通過マトリクス
    print(f"\n──── 全BOOL_CONDS 通過マトリクス ────")
    header = "  指標".ljust(20) + " | " + " | ".join(f"{sym}" for sym,_,_,_ in feats)
    print(header)
    print("  " + "-"*(len(header)-2))
    common_true = []
    for c in opt.BOOL_CONDS:
        marks = []
        true_count = 0
        for (sym, _, _, _), f in feats.items():
            if f.get(c):
                marks.append("✓")
                true_count += 1
            else:
                marks.append(" ")
        if true_count >= 4:  # 過半数で通過しているもの
            common_true.append((c, true_count))
        bar = " | ".join(f"{m:>4}" for m in marks)
        flag = " ⭐" if true_count >= 5 else (" *" if true_count >= 4 else "")
        print(f"  {c:<18} | {bar}{flag}")

    print(f"\n──── 過半数(4/7以上)で通過している共通指標 ────")
    for c, n in sorted(common_true, key=lambda x: -x[1]):
        print(f"  {c:<20} {n}/7 銘柄")

    # 連続値
    print(f"\n──── 連続値マトリクス ────")
    cont_keys = ["_vsurge","_atr","_body","_rsi","_stoch","_bbpct","_rci9","_rci26","_cci"]
    header = "  指標".ljust(20) + " | " + " | ".join(f"{sym:>9}" for sym,_,_,_ in feats)
    print(header)
    print("  " + "-"*(len(header)-2))
    for ck in cont_keys:
        vals = []
        for (sym, _, _, _), f in feats.items():
            v = f.get(ck)
            vals.append(f"{v:>9.2f}" if v is not None else "      n/a")
        print(f"  {ck:<18} | {' | '.join(vals)}")

    # 連続値の範囲分析（提案条件のヒント）
    print(f"\n──── 連続値範囲（最小〜最大）— 共通レンジを探す ────")
    for ck in cont_keys:
        vals = [f.get(ck) for f in feats.values() if f.get(ck) is not None]
        if vals:
            print(f"  {ck:<18}  min={min(vals):>8.2f}  max={max(vals):>8.2f}  mean={sum(vals)/len(vals):>8.2f}")

if __name__ == "__main__":
    main()
