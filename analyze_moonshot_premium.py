#!/usr/bin/env python3
"""
Moonshot Premium候補 — 少数精鋭バックテスト
件数を月1-3件レベルに絞り、Mega Hit率と地雷ゼロを両立する条件を探る。
"""
import math
import pandas as pd
import optimize_screener as opt

MEGA_THRESHOLD = 0.50
MEGA_PERF_COL = "perf_20bd"

# 各Premium候補 (6-8条件AND)
CANDIDATES = {
    "P1: 現案+雲基準線":      ["ema25","pre_down3","vol15","vol30","macdgc","stoch75","ich_price_kijun"],
    "P2: 現案/vol12緩め":     ["ema25","pre_down3","vol12","vol30","macdgc","stoch75"],
    "P3: 現案+BB上部":         ["ema25","pre_down3","vol15","vol30","macdgc","stoch75","bb80"],
    "P4: BIG単体":              ["ema25","body2","macdgc","atr5","stoch75","vol30"],
    "P5: BIG+押目+BB":          ["ema25","body2","macdgc","atr5","stoch75","vol30","pre_down3","bb80"],
    "P6: BIG+押目":             ["ema25","body2","macdgc","atr5","stoch75","vol30","pre_down3"],
    "P7: 現案":                 ["ema25","pre_down3","vol15","vol30","macdgc","stoch75"],
    "P8: BIG+vol15+押目":       ["ema25","body2","macdgc","atr5","stoch75","vol30","vol15","pre_down3"],
}

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
    df = df[df[MEGA_PERF_COL].apply(lambda v: isinstance(v,(int,float)) and math.isfinite(v))].reset_index(drop=True)
    df["is_mega"] = df[MEGA_PERF_COL] >= MEGA_THRESHOLD
    return df

def eval_combo(df, conds):
    for c in conds:
        df[c] = df[c].astype(bool)
    sc = sum(df[c].astype(int) for c in conds)
    s6 = df[sc == len(conds)].copy()
    return s6

def main():
    print("="*78)
    print("Moonshot Premium候補 — 少数精鋭バックテスト")
    print("="*78)
    df = load_df()
    total = len(df)
    total_mega = int(df["is_mega"].sum())
    print(f"  確定母数: {total}件 / Mega Hit: {total_mega}件\n")

    # 各候補を評価
    print(f"{'─'*78}")
    print("📊 候補比較")
    print(f"{'─'*78}")
    print(f"  {'候補':<22} {'条件':>2} {'件数':>4} {'Mega':>5} {'Recall':>7} {'勝率':>5} {'平均':>7} {'+10%':>5} {'-10%':>5}  {'最大上':>7} {'最大下':>7}")
    print(f"  {'-'*22} {'-'*2} {'-'*4} {'-'*5} {'-'*7} {'-'*5} {'-'*7} {'-'*5} {'-'*5}  {'-'*7} {'-'*7}")
    results = {}
    for name, conds in CANDIDATES.items():
        s6 = eval_combo(df.copy(), conds)
        results[name] = (s6, conds)
        if len(s6) == 0:
            print(f"  {name:<22} {len(conds):>2} {0:>4} {0:>3}/{total_mega:<2} {'-':>6}% {'-':>4}% {'-':>6}% {'-':>5} {'-':>5}  {'-':>6}% {'-':>6}%")
            continue
        perf = s6[MEGA_PERF_COL].to_numpy()
        mega = int(s6["is_mega"].sum())
        recall = mega/max(total_mega,1)*100
        wr = (perf > 0).mean()*100
        avg = perf.mean()*100
        w10 = int((perf >= 0.10).sum())
        l10 = int((perf <= -0.10).sum())
        max_up = perf.max()*100
        max_dn = perf.min()*100
        print(f"  {name:<22} {len(conds):>2} {len(s6):>4} {mega:>3}/{total_mega:<2} {recall:>6.1f}% {wr:>4.1f}% {avg:>+6.1f}% {w10:>5} {l10:>5}  {max_up:>+6.1f}% {max_dn:>+6.1f}%")

    # 各候補の★6リスト
    for name, (s6, conds) in results.items():
        if len(s6) == 0: continue
        print(f"\n{'─'*78}")
        print(f"📋 {name} ({len(s6)}件)")
        print(f"   条件: {'+'.join(conds)}")
        print(f"{'─'*78}")
        s6_sorted = s6.sort_values("date", ascending=False)
        for _, r in s6_sorted.iterrows():
            p20 = r[MEGA_PERF_COL]
            tag = "🚀MEGA" if r["is_mega"] else ("✓" if p20>0 else "✗")
            print(f"  {r['date']:<12} {r['symbol']:<6} {r['name'][:24]:<24} {p20*100:+7.1f}% {tag}")

if __name__ == "__main__":
    main()
