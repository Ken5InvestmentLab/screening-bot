#!/usr/bin/env python3
"""Reconstruct two JPX session bars/day from genuine Yahoo 1H data and compare with known 4H research baselines.

Research-only. Tests predeclared session split schemes; does not touch production.
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd


def load(patterns):
    files=[]
    for pat in patterns:
        files.extend(glob.glob(pat, recursive=True))
    files=sorted(dict.fromkeys(files))
    if not files:
        raise SystemExit("no inputs")
    frames=[]
    for p in files:
        q=pd.read_csv(p, dtype={"symbol":"string"}, low_memory=False)
        if not q.empty:
            frames.append(q)
    d=pd.concat(frames, ignore_index=True)
    d["symbol"]=d["symbol"].astype("string").str.replace(".T","",regex=False)
    d["timestamp"]=pd.to_datetime(d["timestamp"],utc=True,errors="coerce").dt.tz_convert("Asia/Tokyo")
    for c in ["open","high","low","close","volume"]:
        d[c]=pd.to_numeric(d[c],errors="coerce")
    d=d.dropna(subset=["symbol","timestamp","open","high","low","close"])
    d=d.sort_values(["symbol","timestamp"]).drop_duplicates(["symbol","timestamp"],keep="last")
    flat=(d["open"]==d["high"])&(d["high"]==d["low"])&(d["low"]==d["close"])
    late=((d["timestamp"].dt.hour==15)&(d["timestamp"].dt.minute>=30))|(d["timestamp"].dt.hour>=16)
    d=d[~((d["volume"].fillna(0)==0)&flat&late)].copy()
    d["date"]=d["timestamp"].dt.date.astype(str)
    d["minute_of_day"]=d["timestamp"].dt.hour*60+d["timestamp"].dt.minute
    return d


def rsi_wilder(c,p=12):
    delta=c.diff()
    gain=delta.clip(lower=0)
    loss=-delta.clip(upper=0)
    ag=gain.ewm(alpha=1/p,adjust=False,min_periods=p).mean()
    al=loss.ewm(alpha=1/p,adjust=False,min_periods=p).mean()
    rs=ag/al.replace(0,np.nan)
    return 100-100/(1+rs)


def aggregate(d, split_min):
    x=d.copy()
    x["session"]=np.where(x["minute_of_day"]<split_min,"AM","PM")
    s=(x.sort_values("timestamp")
       .groupby(["symbol","date","session"],as_index=False)
       .agg(open=("open","first"),high=("high","max"),low=("low","min"),
            close=("close","last"),volume=("volume","sum"),
            first_ts=("timestamp","first"),last_ts=("timestamp","last"),bars=("timestamp","size")))
    s["session_order"]=s["session"].map({"AM":0,"PM":1})
    s=s.sort_values(["symbol","date","session_order"]).copy()
    # Stable research labels matching prior 4H/session convention.
    s["session_time"]=pd.to_datetime(s["date"]+" "+s["session"].map({"AM":"09:00:00","PM":"13:00:00"}))
    s["session_time"]=s["session_time"].dt.tz_localize("Asia/Tokyo")
    return s


def enrich_session(s):
    outs=[]
    for _,g in s.groupby("symbol",sort=False):
        g=g.sort_values(["date","session_order"]).copy()
        c=g["close"]
        h=g["high"]
        l=g["low"]
        g["ema75"]=c.ewm(span=75,adjust=False).mean()
        e12=c.ewm(span=12,adjust=False).mean()
        e26=c.ewm(span=26,adjust=False).mean()
        macd=e12-e26
        g["macd_hist"]=macd-macd.ewm(span=9,adjust=False).mean()
        g["rsi12"]=rsi_wilder(c,12)
        mid=c.rolling(20,min_periods=20).mean()
        sd=c.rolling(20,min_periods=20).std(ddof=0)
        g["bb_mid"]=mid
        prev=c.shift(1)
        tr=pd.concat([(h-l),(h-prev).abs(),(l-prev).abs()],axis=1).max(axis=1)
        g["atr14_pct"]=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean()/c.replace(0,np.nan)
        g["range_pct"]=(h-l)/c.replace(0,np.nan)
        g["pre_down3"]=(c.shift(1)<c.shift(2))&(c.shift(2)<c.shift(3))
        outs.append(g)
    return pd.concat(outs,ignore_index=True)


def add_daily_context(s,d):
    daily=(d.sort_values("timestamp")
           .groupby(["symbol","date"],as_index=False)
           .agg(daily_close=("close","last"),daily_volume=("volume","sum"))
           .sort_values(["symbol","date"]))
    daily["prev_daily_close"]=daily.groupby("symbol")["daily_close"].shift(1)
    daily["prev_daily_volume"]=daily.groupby("symbol")["daily_volume"].shift(1)
    dates=sorted(daily["date"].unique().tolist())
    target_map={v:(dates[i+5] if i+5<len(dates) else None) for i,v in enumerate(dates)}
    target=daily[["symbol","date","daily_close"]].rename(columns={"date":"target_date","daily_close":"target_close"})
    s=s.merge(daily[["symbol","date","prev_daily_close","prev_daily_volume"]],on=["symbol","date"],how="left")
    s["target_date"]=s["date"].map(target_map)
    s=s.merge(target,on=["symbol","target_date"],how="left")
    s["ret5bd"]=s["target_close"]/s["close"]-1
    return s,dates


def cooldown(q,dates,n=5):
    pos={d:i for i,d in enumerate(dates)}
    keep=[]; last={}
    for idx,r in q.sort_values(["session_time","symbol"]).iterrows():
        di=pos.get(r["date"])
        if di is None: continue
        p=last.get(str(r["symbol"]))
        if p is None or di-p>=n:
            keep.append(idx); last[str(r["symbol"])]=di
    return q.loc[keep].sort_values(["session_time","symbol"]).copy()


def metrics(q):
    r=q["ret5bd"].dropna().astype(float)
    if r.empty:
        return {"n":0}
    rs=r.sort_values(ascending=False)
    return {
        "n":int(len(r)),"mean":float(r.mean()),"median":float(r.median()),"win":float((r>0).mean()),
        "ge10":float((r>=.10).mean()),"ge20":float((r>=.20).mean()),"ge30":float((r>=.30).mean()),
        "le10":float((r<=-.10).mean()),"max":float(r.max()),
        "top1_removed":float(rs.iloc[1:].mean()) if len(rs)>1 else None,
        "top3_removed":float(rs.iloc[3:].mean()) if len(rs)>3 else None,
        "top5_removed":float(rs.iloc[5:].mean()) if len(rs)>5 else None,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--inputs",action="append",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)
    raw=load(a.inputs)

    time_counts=(raw.assign(clock=raw["timestamp"].dt.strftime("%H:%M"))
                 .groupby("clock").size().rename("rows").reset_index())
    time_counts.to_csv(out/"one_hour_clock_counts.csv",index=False)

    schemes={"split_1200":720,"split_1230":750,"split_1300":780}
    rows=[]; candidates=[]
    known={"tail":{"n":215,"mean":0.0220},"monster_40":{"n":23,"mean":0.0594}}

    for scheme,split_min in schemes.items():
        s=aggregate(raw,split_min)
        s=enrich_session(s)
        s,dates=add_daily_context(s,raw)
        eligible=s[(s["prev_daily_close"]<=1000)&(s["prev_daily_volume"]>=10000)&(s["volume"]>=5000)].copy()

        base=(eligible["close"]<=eligible["ema75"])&(eligible["macd_hist"]<=0)&(eligible["close"]>eligible["bb_mid"])&(eligible["close"]<=eligible["open"])
        for thr in [0.02,0.025,0.03,0.035,0.04,0.045,0.05]:
            q=eligible[base&(eligible["range_pct"]>=thr)].copy()
            q=cooldown(q,dates,5)
            m=metrics(q)
            label="tail" if thr==0.02 else f"monster_{int(thr*1000):02d}"
            row={"scheme":scheme,"split_minute":split_min,"threshold":thr,"label":label,
                 "session_rows":int(len(s)),"eligible_rows":int(len(eligible)),**m}
            if thr==0.02:
                row["target_n"]=known["tail"]["n"]; row["target_mean"]=known["tail"]["mean"]
                row["n_abs_diff"]=abs(m.get("n",0)-known["tail"]["n"])
                row["mean_abs_diff"]=abs(m.get("mean",0)-known["tail"]["mean"]) if m.get("mean") is not None else None
            if thr==0.04:
                row["target_n"]=known["monster_40"]["n"]; row["target_mean"]=known["monster_40"]["mean"]
                row["n_abs_diff"]=abs(m.get("n",0)-known["monster_40"]["n"])
                row["mean_abs_diff"]=abs(m.get("mean",0)-known["monster_40"]["mean"]) if m.get("mean") is not None else None
            rows.append(row)
            if thr in (0.02,0.04):
                z=q.copy(); z["scheme"]=scheme; z["threshold"]=thr; candidates.append(z)

    report=pd.DataFrame(rows)
    report.to_csv(out/"session_reconstruction_sweep.csv",index=False)
    if candidates:
        pd.concat(candidates,ignore_index=True).to_csv(out/"session_reconstruction_candidates.csv",index=False)

    # Predeclared closeness score uses only known aggregate baselines, not individual future returns.
    score=[]
    for scheme,g in report[report["threshold"].isin([0.02,0.04])].groupby("scheme"):
        nerr=0.0; merr=0.0
        for _,r in g.iterrows():
            nerr += abs(float(r["n"])-float(r["target_n"])) / max(float(r["target_n"]),1.0)
            merr += abs(float(r["mean"])-float(r["target_mean"]))
        score.append({"scheme":scheme,"relative_n_error_sum":nerr,"mean_abs_error_sum":merr,
                      "combined":nerr+merr})
    score=pd.DataFrame(score).sort_values("combined")
    score.to_csv(out/"session_reconstruction_score.csv",index=False)

    print("1H CLOCK COUNTS")
    print(time_counts.to_string(index=False))
    print("\nRECONSTRUCTION SWEEP")
    print(report.to_string(index=False))
    print("\nSCHEME SCORE")
    print(score.to_string(index=False))


if __name__=="__main__":
    main()
