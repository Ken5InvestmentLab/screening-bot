#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""最新Stableロジックを基準に 40BD ベースライン＆入れ替わりを取り直す（読み取り専用）"""
import math
import numpy as np
import pandas as pd
import optimize_screener as opt

WIN40, BIG50, BIG100 = 0.20, 0.50, 1.00
CUR_STABLE = ["ema25", "macdpos", "stoch75", "bb80", "pre_down3", "gap_up"]  # 2026-05-28デプロイ済み
CAND_Y = ["ema25", "atr7", "stoch75", "stoch60", "ich_price_tenkan", "gap_up"]
CAND_X = ["vol12", "sbull", "body2", "atr5", "stoch75", "gap_up"]

svc = opt.get_service()
ar = opt.fetch(svc, "alerts_raw")
try:
    sa = opt.fetch(svc, "signals_archive")
except Exception:
    sa = []
oh = opt.fetch(svc, "ohlcv_4h")
ohlcv = opt.parse_ohlcv(oh)
ar_all = opt.parse_alerts(ar, include_unconfirmed=True); ar_all["_from_archive"] = False
sa_all = opt.parse_alerts(sa, include_unconfirmed=True); sa_all["_from_archive"] = True
allsig = pd.concat([ar_all, sa_all], ignore_index=True)
has_id = allsig["alert_id"].astype(str) != ""
allsig = pd.concat([allsig[has_id].drop_duplicates(subset=["alert_id"], keep="first"),
                    allsig[~has_id]], ignore_index=True)
rows = []
for _, r in allsig.iterrows():
    daily = ohlcv.get(r["symbol"], [])
    f = opt.get_features(daily, r["date"])
    if not f:
        continue
    rec = {**r.to_dict(), **f}
    lc = opt.latest_close_for_signal(daily, r["date"])
    entry = r.get("entry", float("nan"))
    rec["cur_perf"] = (lc / entry - 1) if (lc and math.isfinite(entry) and entry > 0) else np.nan
    rows.append(rec)
df = pd.DataFrame(rows)
for c in [x for x in opt.BOOL_CONDS if x in df.columns]:
    df[c] = df[c].astype(bool)
df_conf = df[df["perf_40bd"].notna()].reset_index(drop=True)
perf40 = df_conf["perf_40bd"].to_numpy(dtype=float)

def all_pass_idx(frame, combo):
    m = np.ones(len(frame), dtype=bool)
    for c in combo:
        m &= frame[c].to_numpy(dtype=bool)
    return np.nonzero(m)[0]

def stats_of(idx):
    v = perf40[idx]; n = len(v)
    if n == 0:
        return "0件"
    return (f"{n}件 平均{v.mean()*100:+.1f}% 中央{np.median(v)*100:+.1f}% "
            f"+20%率{(v>=WIN40).mean()*100:.0f}% +50%{int((v>=BIG50).sum())}件 "
            f"+100%{int((v>=BIG100).sum())}件 最大{v.max()*100:+.0f}%")

print("最新Stable(ema25+macdpos+stoch75+bb80+pre_down3+gap_up) 40BD満点評価:")
cur_idx = all_pass_idx(df_conf, CUR_STABLE)
print("  " + stats_of(cur_idx))
cur_set = set(df_conf.iloc[cur_idx]["alert_id"])
print("  検出銘柄:")
for _, row in df_conf.iloc[cur_idx].sort_values("perf_40bd", ascending=False).iterrows():
    print(f"    {row['date']} {row['symbol']} {(row['name'] or '')[:18]} {row['perf_40bd']*100:+.1f}%")

for cand, label in [(CAND_X, "候補X (vol12+sbull+body2+atr5+stoch75+gap_up)"),
                    (CAND_Y, "候補Y (ema25+atr7+stoch75+stoch60+ich_price_tenkan+gap_up)")]:
    nidx = all_pass_idx(df_conf, cand)
    nset = set(df_conf.iloc[nidx]["alert_id"])
    print(f"\n{label} vs 最新Stable の入れ替わり(40BD確定):")
    print(f"  共通{len(cur_set & nset)} / 新規{len(nset - cur_set)} / 消失{len(cur_set - nset)}")
