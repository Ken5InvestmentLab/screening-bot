#!/usr/bin/env python3
"""
20BD最良ロジック `ema25+body2+macdpos+atr5+bb80+pre_down3` で
20BDがまだ未確定の★6シグナルを抽出し、現在値ベースの暫定成績を表示。
"""
import os, sys
import numpy as np
import pandas as pd
import math

# 標準optimize_screenerをimport（perf_20bd列がそのまま読める）
import optimize_screener as opt

BEST_CONDS = ["ema25","body2","macdpos","atr5","bb80","pre_down3"]

def main():
    print("="*70)
    print("20BD最良ロジック — 未確定★6シグナル現状ウォッチ")
    print("="*70)
    print(f"条件: {'+'.join(BEST_CONDS)}")

    # 全BOTTOMアラート取得（confirmed_5bdベースの確定/未確定区別なし）
    print("\n📡 データ取得...")
    svc = opt.get_service()
    ar = opt.fetch(svc, "alerts_raw")
    sa = opt.fetch(svc, "signals_archive")
    oh = opt.fetch(svc, "ohlcv_4h")
    print(f"  alerts_raw: {len(ar)}行 / signals_archive: {len(sa)}行")

    # include_unconfirmed=True で5BD未確定も含めて全BOTTOM取得
    ar_all = opt.parse_alerts(ar, include_unconfirmed=True)
    sa_all = opt.parse_alerts(sa, include_unconfirmed=True)
    ar_all['_from_archive'] = False
    sa_all['_from_archive'] = True
    alerts = pd.concat([ar_all, sa_all], ignore_index=True)
    if "alert_id" in alerts.columns and len(alerts) > 0:
        _has_id = alerts["alert_id"].astype(str) != ""
        alerts = pd.concat([
            alerts[_has_id].drop_duplicates(subset=["alert_id"], keep="first"),
            alerts[~_has_id],
        ], ignore_index=True)
    print(f"  全BOTTOMシグナル: {len(alerts)}件")

    # 指標計算
    print("\n📊 指標計算...")
    ohlcv = opt.parse_ohlcv(oh)
    rows = []
    for _, r in alerts.iterrows():
        f = opt.get_features(ohlcv.get(r["symbol"], []), r["date"])
        if f: rows.append({**r.to_dict(), **f})
    df = pd.DataFrame(rows)
    print(f"  有効データ: {len(df)}件")

    # 20BD最良条件でフィルター
    for c in BEST_CONDS:
        df[c] = df[c].astype(bool)
    sc = sum(df[c].astype(int) for c in BEST_CONDS)
    s6_df = df[sc == 6].copy()
    print(f"\n  ★6シグナル(全期間): {len(s6_df)}件")

    # 20BD確定 / 未確定で分割
    s6_df["confirmed_20bd"] = s6_df["perf_20bd"].apply(lambda v: math.isfinite(v) if v is not None else False)
    confirmed = s6_df[s6_df["confirmed_20bd"]].sort_values("date", ascending=False)
    unconfirmed = s6_df[~s6_df["confirmed_20bd"]].sort_values("date", ascending=False)
    print(f"  → 20BD確定済み: {len(confirmed)}件 / 未確定: {len(unconfirmed)}件")

    # 未確定★6の現在値ベース暫定成績
    print(f"\n📈 20BD未確定★6 ({len(unconfirmed)}件) — 現在値ベース暫定成績")
    print(f"  {'日付':<12} {'銘柄':<8} {'社名':<24} {'5BD':>7} {'10BD':>7} {'現在値':>9} {'経過日':>5}")
    print(f"  {'-'*12} {'-'*8} {'-'*24} {'-'*7} {'-'*7} {'-'*9} {'-'*5}")

    today = pd.Timestamp("today").normalize()
    win5 = 0; win10 = 0; win_now = 0; lose_now = 0
    p5_sum = 0.0; p10_sum = 0.0; pnow_sum = 0.0
    n5 = 0; n10 = 0; nnow = 0
    for _, row in unconfirmed.iterrows():
        sym = row["symbol"]
        date = row["date"]
        name = row["name"]
        entry = row.get("entry", float("nan"))
        # 現在値（latest close）を取得
        daily = ohlcv.get(sym, [])
        latest_close = None
        if daily and math.isfinite(entry) and entry > 0:
            sig_dt = str(date).replace("/", "-")[:10]
            if daily[-1]["date"] >= sig_dt:
                lc = daily[-1].get("close")
                if lc is not None and math.isfinite(lc):
                    latest_close = lc
        p5  = row.get("perf_5bd")
        p10 = row.get("perf_10bd")
        # 5BD/10BD表示
        s5  = f"{p5*100:+.1f}%" if (p5 is not None and isinstance(p5,(int,float)) and math.isfinite(p5)) else "未確定"
        s10 = f"{p10*100:+.1f}%" if (p10 is not None and isinstance(p10,(int,float)) and math.isfinite(p10)) else "未確定"
        if latest_close is not None:
            pnow = latest_close / entry - 1
            spnow = f"{pnow*100:+.1f}%"
            pnow_sum += pnow; nnow += 1
            if pnow > 0: win_now += 1
            if pnow <= -0.10: lose_now += 1
        else:
            spnow = "n/a"
            pnow = None
        # 経過営業日（OHLCV実バーで正確にカウント）
        elapsed_bd = 0
        if daily:
            sig_dt_norm = str(date).replace("/", "-")[:10]
            # シグナル日より後のバー本数 = 経過BD
            elapsed_bd = sum(1 for b in daily if b["date"] > sig_dt_norm)
        if isinstance(p5,(int,float)) and math.isfinite(p5):
            p5_sum += p5; n5 += 1
            if p5 > 0: win5 += 1
        if isinstance(p10,(int,float)) and math.isfinite(p10):
            p10_sum += p10; n10 += 1
            if p10 > 0: win10 += 1
        print(f"  {date:<12} {sym:<8} {name:<24} {s5:>7} {s10:>7} {spnow:>9} {elapsed_bd:>3}BD")

    print(f"\n📊 集計")
    print(f"  確定済み5BD : 勝率{win5/max(n5,1)*100:5.1f}% 平均{p5_sum/max(n5,1)*100:+6.2f}% (n={n5})")
    print(f"  確定済み10BD: 勝率{win10/max(n10,1)*100:5.1f}% 平均{p10_sum/max(n10,1)*100:+6.2f}% (n={n10})")
    print(f"  現在値暫定  : 勝率{win_now/max(nnow,1)*100:5.1f}% 平均{pnow_sum/max(nnow,1)*100:+6.2f}% (n={nnow}) -10%以下{lose_now}件")

    # 確定済み★6も一応再掲（リファレンス）
    print(f"\n📚 参考: 20BD確定済み★6 ({len(confirmed)}件) — 確定成績")
    print(f"  {'日付':<12} {'銘柄':<8} {'社名':<24} {'20BD':>8}")
    for _, row in confirmed.iterrows():
        p20 = row.get("perf_20bd")
        s20 = f"{p20*100:+.1f}%" if (p20 is not None and math.isfinite(p20)) else "?"
        print(f"  {row['date']:<12} {row['symbol']:<8} {row['name']:<24} {s20:>8}")

if __name__ == "__main__":
    main()
