#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""候補A(超攻め) vol12+body2+atr5+stoch75+rsi4060+gap_up の全検出銘柄一覧（読み取り専用）"""
import math
from datetime import datetime
import numpy as np
import pandas as pd
import optimize_screener as opt

CAND_A = ["vol12", "body2", "atr5", "stoch75", "rsi4060", "gap_up"]
WIN40, BIG50, BIG100 = 0.20, 0.50, 1.00
TODAY = pd.Timestamp.today().normalize()

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
    d = pd.to_datetime(r["date"], errors="coerce")
    rec["days"] = int((TODAY - d).days) if pd.notna(d) else -1
    rec["src"] = "arch" if r.get("_from_archive") else "raw"
    rows.append(rec)
df = pd.DataFrame(rows)
for c in [x for x in opt.BOOL_CONDS if x in df.columns]:
    df[c] = df[c].astype(bool)

def apply_filter(frame):
    m = np.ones(len(frame), dtype=bool)
    for c in CAND_A:
        m &= frame[c].to_numpy(dtype=bool)
    return frame[m].copy()

def pf(v):
    return f"{v*100:+.1f}%" if pd.notna(v) else "  --"

hit = apply_filter(df)
conf = hit[hit["perf_40bd"].notna()].sort_values("perf_40bd", ascending=False)
unconf = hit[hit["perf_40bd"].isna()].sort_values("cur_perf", ascending=False, na_position="last")

print("=" * 84)
print("候補A(超攻め)  vol12+body2+atr5+stoch75+rsi4060+gap_up  全検出銘柄")
print("=" * 84)
print(f"総検出 {len(hit)}件 = 40BD確定 {len(conf)}件 + 40BD未確定 {len(unconf)}件")

p40 = conf["perf_40bd"].to_numpy(dtype=float)
print(f"\n■ 40BD確定 {len(conf)}件  "
      f"平均{p40.mean()*100:+.1f}% 中央{np.median(p40)*100:+.1f}% "
      f"+20%率{(p40>=WIN40).mean()*100:.0f}% +50%{int((p40>=BIG50).sum())}件 "
      f"+100%{int((p40>=BIG100).sum())}件")
print(f"  {'日付':<11}{'銘柄':<6}{'社名':<22}{'5BD':>7}{'10BD':>7}{'20BD':>7}{'40BD':>8}")
for _, r in conf.iterrows():
    nm = (r["name"] or "")[:20]
    print(f"  {r['date']:<11}{r['symbol']:<6}{nm:<22}"
          f"{pf(r['perf_5bd']):>7}{pf(r['perf_10bd']):>7}{pf(r['perf_20bd']):>7}{pf(r['perf_40bd']):>8}")

cv = unconf["cur_perf"].dropna().to_numpy()
print(f"\n■ 40BD未確定 {len(unconf)}件（現在値=最新終値/entry-1）  "
      f"暫定平均{cv.mean()*100:+.1f}% 暫定+20%率{(cv>=WIN40).mean()*100:.0f}% "
      f"暫定+50%{int((cv>=BIG50).sum())}件 最大{cv.max()*100:+.0f}%")
print(f"  {'日付':<11}{'銘柄':<6}{'社名':<20}{'経過':>4}{'5BD':>7}{'10BD':>7}{'20BD':>7}{'現在値':>8}")
for _, r in unconf.iterrows():
    nm = (r["name"] or "")[:18]
    print(f"  {r['date']:<11}{r['symbol']:<6}{nm:<20}{r['days']:>3}d"
          f"{pf(r['perf_5bd']):>7}{pf(r['perf_10bd']):>7}{pf(r['perf_20bd']):>7}{pf(r['cur_perf']):>8}")
