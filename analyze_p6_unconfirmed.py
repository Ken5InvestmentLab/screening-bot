#!/usr/bin/env python3
"""
P6 = ema25+body2+macdgc+atr5+stoch75+vol30+pre_down3
で 20BD未確定の★6シグナルを抽出し、現在値ベースで暫定成績を表示。
"""
import math
import pandas as pd
import optimize_screener as opt

P6_CONDS = ["ema25","body2","macdgc","atr5","stoch75","vol30","pre_down3"]

def main():
    print("="*78)
    print(f"P6 = {'+'.join(P6_CONDS)} — 未確定★6現状ウォッチ")
    print("="*78)

    print("\n📡 データ取得...")
    svc = opt.get_service()
    ar = opt.fetch(svc, "alerts_raw")
    sa = opt.fetch(svc, "signals_archive")
    oh = opt.fetch(svc, "ohlcv_4h")
    # include_unconfirmed=True で全BOTTOM取得
    ar_all = opt.parse_alerts(ar, include_unconfirmed=True)
    sa_all = opt.parse_alerts(sa, include_unconfirmed=True)
    ar_all['_from_archive'] = False
    sa_all['_from_archive'] = True
    alerts = pd.concat([ar_all, sa_all], ignore_index=True)
    if "alert_id" in alerts.columns:
        _h = alerts["alert_id"].astype(str) != ""
        alerts = pd.concat([
            alerts[_h].drop_duplicates(subset=["alert_id"], keep="first"),
            alerts[~_h]], ignore_index=True)
    print(f"  全BOTTOM: {len(alerts)}件")

    ohlcv = opt.parse_ohlcv(oh)
    rows = []
    for _, r in alerts.iterrows():
        f = opt.get_features(ohlcv.get(r["symbol"], []), r["date"])
        if f: rows.append({**r.to_dict(), **f})
    df = pd.DataFrame(rows)
    print(f"  有効データ: {len(df)}件")

    # P6条件で★6抽出
    for c in P6_CONDS:
        df[c] = df[c].astype(bool)
    sc = sum(df[c].astype(int) for c in P6_CONDS)
    s6 = df[sc == len(P6_CONDS)].copy()
    print(f"\n  P6 ★6シグナル(全期間): {len(s6)}件")

    # 20BD確定/未確定で分割
    s6["confirmed_20bd"] = s6["perf_20bd"].apply(
        lambda v: isinstance(v,(int,float)) and math.isfinite(v))
    confirmed = s6[s6["confirmed_20bd"]].sort_values("date", ascending=False)
    unconfirmed = s6[~s6["confirmed_20bd"]].sort_values("date", ascending=False)
    print(f"  → 20BD確定: {len(confirmed)}件 / 未確定: {len(unconfirmed)}件")

    # 未確定★6 現状ウォッチ
    print(f"\n📈 20BD未確定★6 ({len(unconfirmed)}件) — 現在値ベース暫定成績")
    if len(unconfirmed) == 0:
        print("  (該当なし)")
    else:
        print(f"  {'日付':<12} {'銘柄':<6} {'社名':<24} {'5BD':>7} {'10BD':>7} {'現在値':>9} {'経過':>6}")
        print(f"  {'-'*12} {'-'*6} {'-'*24} {'-'*7} {'-'*7} {'-'*9} {'-'*6}")
        for _, r in unconfirmed.iterrows():
            sym = r["symbol"]; date = r["date"]
            entry = r.get("entry", float("nan"))
            daily = ohlcv.get(sym, [])
            latest_close = None
            if daily and isinstance(entry,(int,float)) and math.isfinite(entry) and entry > 0:
                sig_dt = str(date).replace("/","-")[:10]
                if daily[-1]["date"] >= sig_dt:
                    lc = daily[-1].get("close")
                    if lc is not None and math.isfinite(lc):
                        latest_close = lc
            p5 = r.get("perf_5bd"); p10 = r.get("perf_10bd")
            def fmt(v):
                if isinstance(v,(int,float)) and math.isfinite(v):
                    return f"{v*100:+.1f}%"
                return "未確定"
            s5 = fmt(p5); s10 = fmt(p10)
            if latest_close is not None:
                pnow = latest_close / entry - 1
                spnow = f"{pnow*100:+.1f}%"
            else:
                spnow = "n/a"
            # 正確な経過BD (OHLCV実バー)
            elapsed_bd = 0
            if daily:
                sig_dt_norm = str(date).replace("/","-")[:10]
                elapsed_bd = sum(1 for b in daily if b["date"] > sig_dt_norm)
            print(f"  {date:<12} {sym:<6} {r['name'][:24]:<24} {s5:>7} {s10:>7} {spnow:>9} {elapsed_bd:>4}BD")

    # 確定済み★6も再掲
    print(f"\n📚 確定済み★6 ({len(confirmed)}件) — 過去実績")
    print(f"  {'日付':<12} {'銘柄':<6} {'社名':<24} {'20BD':>8}")
    for _, r in confirmed.iterrows():
        p20 = r["perf_20bd"]
        s20 = f"{p20*100:+.1f}%" if isinstance(p20,(int,float)) and math.isfinite(p20) else "?"
        tag = " 🚀MEGA" if (isinstance(p20,(int,float)) and p20 >= 0.50) else ""
        print(f"  {r['date']:<12} {r['symbol']:<6} {r['name'][:24]:<24} {s20:>8}{tag}")

if __name__ == "__main__":
    main()
