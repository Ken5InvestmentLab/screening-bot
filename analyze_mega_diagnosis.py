#!/usr/bin/env python3
"""
Mega銘柄(6217/9256/8289)各々の指標値を確認し、
提案ロジックでどの条件が真/偽かを見て、漏れ原因を診断する。
"""
import math
import pandas as pd
import optimize_screener as opt

TARGETS = [
    ("6217", "2026/04/13"),  # 津田駒
    ("9256", "2026/04/28"),  # サクシード
    ("8289", "2026/03/26"),  # Olympic
]
# 候補#1の6条件
PROPOSED = ["ema25","pre_down3","vol15","vol30","macdgc","stoch75"]
# 全 BOOL_CONDS を見るのもあり

def main():
    print("="*78)
    print("Mega銘柄の指標診断")
    print("="*78)

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

    print(f"  alerts: {len(alerts)}件\n")
    for sym, date in TARGETS:
        target_rows = alerts[(alerts["symbol"]==sym) & (alerts["date"]==date)]
        if target_rows.empty:
            # 日付フォーマット違いを許容
            target_rows = alerts[alerts["symbol"]==sym]
            print(f"\n=== {sym} {date} ===")
            print(f"  完全一致なし。同銘柄の全アラート:")
            for _, r in target_rows.iterrows():
                print(f"    {r['date']:<12} {r['name']:<24} perf_10bd={r.get('perf_10bd')} perf_20bd={r.get('perf_20bd')}")
            continue

        r0 = target_rows.iloc[0]
        daily = ohlcv.get(sym, [])
        feat = opt.get_features(daily, r0["date"])

        print(f"\n=== {sym} {r0['name']} ({date}) ===")
        print(f"  perf_5bd={r0.get('perf_5bd')} perf_10bd={r0.get('perf_10bd')}"
              f" perf_20bd={r0.get('perf_20bd')} perf_40bd={r0.get('perf_40bd')}")

        if not feat:
            print(f"  ⚠ 指標計算失敗 (バー不足等)")
            continue

        # 提案6条件の真偽
        print(f"\n  ── 提案ロジック {'+'.join(PROPOSED)} ──")
        for c in PROPOSED:
            v = feat.get(c)
            mark = "✓" if v else "✗"
            print(f"    {mark} {c}: {v}")
        sc = sum(1 for c in PROPOSED if feat.get(c))
        print(f"    → スコア {sc}/6")

        # 全 BOOL_CONDS の真偽 (false のものだけハイライト)
        print(f"\n  ── 全BOOL_CONDS 通過状況 (true のみ列挙) ──")
        passed = [c for c in opt.BOOL_CONDS if feat.get(c)]
        print(f"    通過({len(passed)}個): {passed}")
        failed = [c for c in opt.BOOL_CONDS if not feat.get(c)]
        print(f"    不通過({len(failed)}個): {failed}")

        # 連続値
        print(f"\n  ── 連続値 ──")
        for k in ["_vsurge","_atr","_body","_rsi","_stoch","_bbpct","_rci9","_rci26","_cci"]:
            v = feat.get(k)
            if v is not None:
                print(f"    {k}: {v:.2f}")

if __name__ == "__main__":
    main()
