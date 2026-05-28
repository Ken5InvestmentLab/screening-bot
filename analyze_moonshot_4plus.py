#!/usr/bin/env python3
"""
案A' = 案A + MID型 (4型アンサンブル) のバックテスト

MID型 (取りこぼし救済型):
  atr7 + atr5 + sbull + body1 + macdpos + gap_up
  → 7取りこぼしのうち 281A(6/6)・2195(6/6)・6480(5/6)・441A(5/6)・7375(5/6) が惜しい
  → 6/6 AND だと 281A と 2195 が取れる想定
"""
import math
import pandas as pd
import optimize_screener as opt

MEGA_THRESHOLD = 0.50
MEGA_PERF_COL = "perf_20bd"

A_TYPES = {
    "BIG":   ["ema25","body2","macdgc","atr5","stoch75","vol30"],
    "LOW":   ["vol30","atr3","lower_wick50","bb_lower","cci_os","gap_up"],
    "QUIET": ["ema25","macdgc","stoch75","rsi4060","atr3","gap_up"],
    "MID":   ["atr7","atr5","sbull","body1","macdpos","gap_up"],  # 新4型目
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

def apply_logic(df, types_dict):
    """types_dict の各型のうち1つでも満点なら hit。タグ付き"""
    for c in set(sum(types_dict.values(), [])):
        if c in df.columns: df[c] = df[c].astype(bool)
    scores = {name: sum(df[c].astype(int) for c in conds) for name, conds in types_dict.items()}
    hit_mask = pd.Series([False]*len(df))
    tags = [[] for _ in range(len(df))]
    for name, conds in types_dict.items():
        ok = scores[name] == len(conds)
        hit_mask = hit_mask | ok
        for i, v in enumerate(ok):
            if v: tags[i].append(name)
    df_hit = df[hit_mask].copy()
    df_hit["tag"] = ["/".join(t) for h, t in zip(hit_mask, tags) if h]
    return df_hit

def main():
    print("="*78)
    print("案A' (4型アンサンブル) — MID型を追加した版のバックテスト")
    print("="*78)
    df = load_df()
    total = len(df)
    mega_all = df[df["is_mega"]]
    total_mega = len(mega_all)
    print(f"  確定母数: {total}件 / Mega Hit: {total_mega}件")

    # 案A (3型) と 案A' (4型) を比較
    a3 = apply_logic(df.copy(), {k:v for k,v in A_TYPES.items() if k != "MID"})
    a4 = apply_logic(df.copy(), A_TYPES)

    def report(name, hit_df):
        if len(hit_df) == 0:
            print(f"  {name}: ★6なし"); return
        mega = int(hit_df["is_mega"].sum())
        perf = hit_df[MEGA_PERF_COL].to_numpy()
        wr = (perf > 0).mean()*100
        avg = perf.mean()*100
        w10 = int((perf >= 0.10).sum())
        l10 = int((perf <= -0.10).sum())
        print(f"  {name}: ★6 {len(hit_df)}件 / Mega {mega}/{total_mega} ({mega/total_mega*100:.1f}%)"
              f" / 勝率{wr:.1f}% / 平均{avg:+.2f}% / +10%{w10} / -10%{l10}")

    print(f"\n──── 案A (3型) vs 案A' (4型) ────")
    report("案A  (3型)", a3)
    report("案A' (4型)", a4)

    # Mega取得状況
    print(f"\n──── Mega Hit 取得状況 ────")
    print(f"  {'日付':<12} {'銘柄':<6} {'社名':<22} {'20BD':>8}  A(3)  A'(4)  差")
    for _, r in mega_all.sort_values(MEGA_PERF_COL, ascending=False).iterrows():
        in3 = ((a3["symbol"]==r["symbol"]) & (a3["date"]==r["date"])).any()
        in4 = ((a4["symbol"]==r["symbol"]) & (a4["date"]==r["date"])).any()
        m3 = "✓" if in3 else "✗"
        m4 = "✓" if in4 else "✗"
        diff = "🆕" if (in4 and not in3) else ("" if in4==in3 else "❌")
        print(f"  {r['date']:<12} {r['symbol']:<6} {r['name'][:22]:<22} {r[MEGA_PERF_COL]*100:+7.1f}%  {m3:>4}  {m4:>5}  {diff}")

    # MID型 単体で取れた銘柄
    print(f"\n──── MID型単体で新規追加された銘柄 ────")
    mid_only = a4[~a4["symbol"].isin(a3["symbol"]) | ~a4["date"].isin(a3["date"])]
    # 厳密に: (sym,date)ペアで判定
    a3_pairs = set(zip(a3["symbol"], a3["date"]))
    a4_pairs = set(zip(a4["symbol"], a4["date"]))
    new_pairs = a4_pairs - a3_pairs
    print(f"  新規追加: {len(new_pairs)}件")
    mid_new = a4[a4.apply(lambda r: (r["symbol"], r["date"]) in new_pairs, axis=1)]
    mid_new_sorted = mid_new.sort_values(MEGA_PERF_COL, ascending=False)
    for _, r in mid_new_sorted.iterrows():
        mega_tag = "🚀MEGA" if r["is_mega"] else ("✓" if r[MEGA_PERF_COL]>0 else "✗")
        print(f"  {r['date']:<12} {r['symbol']:<6} {r['name'][:24]:<24} {r[MEGA_PERF_COL]*100:+7.1f}% {mega_tag} [{r.get('tag','')}]")

    # 案A' 全★6シグナル
    print(f"\n──── 案A' (4型) 全★6シグナル一覧 ({len(a4)}件) ────")
    a4_sorted = a4.sort_values("date", ascending=False)
    for _, r in a4_sorted.iterrows():
        mega_tag = "🚀MEGA" if r["is_mega"] else ("✓" if r[MEGA_PERF_COL]>0 else "✗")
        print(f"  {r['date']:<12} {r['symbol']:<6} {r['name'][:24]:<24} {r[MEGA_PERF_COL]*100:+7.1f}% {mega_tag} [{r.get('tag','')}]")

if __name__ == "__main__":
    main()
