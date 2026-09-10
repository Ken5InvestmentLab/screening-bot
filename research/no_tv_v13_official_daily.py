from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests

import no_tv_v10_standalone as base


def fetch_interval(code, interval, range_="730d"):
    last=None
    for attempt in range(4):
        try:
            r=requests.get(base.YAHOO.format(symbol=code),params={"range":range_,"interval":interval},headers={"User-Agent":base.UA,"Accept":"application/json,text/plain,*/*"},timeout=30)
            if r.status_code in {429,502,503,504}:
                last=f"http_{r.status_code}";time.sleep(.8*(attempt+1));continue
            r.raise_for_status();p=r.json();err=p.get("chart",{}).get("error")
            if err:return None,err.get("description") or "chart_error"
            res=p["chart"]["result"][0];q=res.get("indicators",{}).get("quote",[{}])[0];ts=res.get("timestamp") or []
            if not ts:return None,"empty_chart"
            return {"timestamp":ts,"open":q.get("open") or [],"high":q.get("high") or [],"low":q.get("low") or [],"close":q.get("close") or [],"volume":q.get("volume") or []},None
        except Exception as e:
            last=type(e).__name__;time.sleep(.5*(attempt+1))
    return None,last or "fetch_failed"


def parse_daily(chart):
    try:n=min(len(chart.get(k,[])) for k in ("timestamp","open","high","low","close","volume"))
    except Exception:return None
    rows=[]
    for i in range(n):
        vals=[chart[k][i] for k in ("open","high","low","close","volume")]
        if any(x is None for x in vals):continue
        o,h,l,c,v=map(float,vals)
        if c<=0 or h<=0 or l<=0 or h<l or v<0:continue
        dt=pd.to_datetime(int(chart["timestamp"][i]),unit="s",utc=True).tz_convert("Asia/Tokyo").date().isoformat()
        rows.append((dt,o,h,l,c,v))
    if len(rows)<80:return None
    return pd.DataFrame(rows,columns=["date","open","high","low","close","volume"]).drop_duplicates("date",keep="last").sort_values("date").reset_index(drop=True)


def build_asof_official(daily,sessions,upto_idx):
    cur=sessions.iloc[upto_idx];past=daily[daily.date<cur.date][["date","open","high","low","close","volume"]].copy()
    today=sessions.iloc[:upto_idx+1];today=today[today.date==cur.date]
    if today.empty:return None
    current=pd.DataFrame([{"date":cur.date,"open":float(today.iloc[0].open),"high":float(today.high.max()),"low":float(today.low.min()),"close":float(today.iloc[-1].close),"volume":float(today.volume.sum())}])
    return pd.concat([past,current],ignore_index=True)


def build_issue_candidates_v13(code,hour_chart,day_chart,start_date,end_date):
    hourly=base.parse_1h_chart(hour_chart)
    daily=parse_daily(day_chart)
    if hourly is None or daily is None or hourly.empty or daily.empty:return None
    sessions=base.synthetic_sessions(hourly).reset_index(drop=True)
    if len(daily)<90 or len(sessions)<120:return None
    d=daily.copy();d["day_index"]=np.arange(len(d));d["future_close_5"]=d.close.shift(-5);d["exit_date_5bd"]=d.date.shift(-5);daymap=d.set_index("date")
    svolume=sessions.volume.to_numpy(float);rows=[]
    for i,row in sessions.iterrows():
        dt=str(row.date)
        if dt<start_date or dt>end_date or dt not in daymap.index:continue
        di=int(daymap.loc[dt,"day_index"])
        if di<1:continue
        prev=d.iloc[di-1]
        if not (float(prev.close)<=1000 and float(prev.volume)>=10000 and float(row.volume)>=5000):continue
        asof=build_asof_official(daily,sessions,i)
        if asof is None:continue
        tf=base.technical_features(asof)
        if tf is None:continue
        prev20=svolume[max(0,i-20):i];svr=float(row.volume/np.mean(prev20)) if len(prev20)>=5 and np.mean(prev20)>0 else np.nan;rng=float(row.high-row.low)
        rec={"date":dt,"session":int(row.session),"symbol":str(code),"entry":float(row.close),"session_volume":float(row.volume),
             "session13":int(row.session==13),"log_price":float(np.log(max(float(row.close),1e-9))),"session_ret":float(row.close/row.open-1) if row.open else np.nan,
             "session_range_pct":float(rng/row.open) if row.open else np.nan,"session_body_pct":float((row.close-row.open)/row.open) if row.open else np.nan,
             "session_close_loc":float((row.close-row.low)/rng) if rng>0 else .5,"session_vol_ratio20":svr,**tf}
        fc=daymap.loc[dt,"future_close_5"];ex=daymap.loc[dt,"exit_date_5bd"]
        rec["perf_5bd"]=float(fc/row.close-1) if pd.notna(fc) and row.close else np.nan;rec["exit_date_5bd"]=str(ex) if pd.notna(ex) else "";rows.append(rec)
    return pd.DataFrame(rows)


def fetch_one(code,start_date,end_date):
    with ThreadPoolExecutor(max_workers=2) as ex:
        fh=ex.submit(fetch_interval,code,"1h","730d");fd=ex.submit(fetch_interval,code,"1d","730d")
        hc,he=fh.result();dc,de=fd.result()
    if he:return None,"1h_"+str(he)
    if de:return None,"1d_"+str(de)
    fr=build_issue_candidates_v13(code,hc or {},dc or {},start_date,end_date)
    return fr,None if fr is not None else "no_data"
