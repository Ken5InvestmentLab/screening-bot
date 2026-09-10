from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import requests

import no_tv_v10_standalone as base
import audit_yahoo_stable_feature_parity as v1

BITS = v1.BITS


def fetch_daily(code):
    last=None
    for attempt in range(4):
        try:
            r=requests.get(base.YAHOO.format(symbol=code),params={"range":"730d","interval":"1d"},headers={"User-Agent":base.UA,"Accept":"application/json,text/plain,*/*"},timeout=30)
            if r.status_code in {429,502,503,504}:
                last=f"http_{r.status_code}";time.sleep(.8*(attempt+1));continue
            r.raise_for_status();p=r.json();err=p.get("chart",{}).get("error")
            if err:return None,err.get("description") or "chart_error"
            res=p["chart"]["result"][0];q=res.get("indicators",{}).get("quote",[{}])[0];ts=res.get("timestamp") or []
            rows=[]
            for i,t in enumerate(ts):
                vals=[q.get(k,[None]*len(ts))[i] for k in ("open","high","low","close","volume")]
                if any(x is None for x in vals):continue
                o,h,l,c,v=map(float,vals)
                if c<=0 or h<=0 or l<=0 or h<l or v<0:continue
                dt=pd.to_datetime(int(t),unit="s",utc=True).tz_convert("Asia/Tokyo").date().isoformat()
                rows.append((dt,o,h,l,c,v))
            if len(rows)<80:return None,"too_few_daily"
            return pd.DataFrame(rows,columns=["date","open","high","low","close","volume"]),None
        except Exception as e:
            last=type(e).__name__;time.sleep(.5*(attempt+1))
    return None,last or "daily_fetch_failed"


def hybrid_asof(daily,sessions,target_date,session):
    past=daily[daily.date<target_date][["date","open","high","low","close","volume"]].copy()
    today=sessions[(sessions.date==target_date)&(sessions.session<=session)].copy()
    if today.empty:return None
    current=pd.DataFrame([{
        "date":target_date,"open":float(today.iloc[0].open),"high":float(today.high.max()),"low":float(today.low.min()),
        "close":float(today.iloc[-1].close),"volume":float(today.volume.sum())
    }])
    return pd.concat([past,current],ignore_index=True)


def bits_from_tf(tf):
    return {
        "ema25":bool(tf["stable_ema25"]),"macdpos":bool(tf["stable_macdpos"]),"stoch75":bool(tf["stable_stoch75"]),
        "bb80":bool(tf["stable_bb80"]),"pre_down3":bool(tf["stable_pre_down3"]),"gap_up":bool(tf["stable_gap_up"]),
    }


def bits_rounded(asof,tick):
    z=asof.copy()
    for c in ("open","high","low","close"):
        z[c]=np.round(pd.to_numeric(z[c],errors="coerce")/tick)*tick
    tf=base.technical_features(z)
    return bits_from_tf(tf) if tf else None


def process_code(code, rows):
    chart,err=base.fetch_chart(code)
    if err:return None,err
    hourly=base.parse_1h_chart(chart or {})
    if hourly is None:return None,"hourly_parse_failed"
    sessions=base.synthetic_sessions(hourly).reset_index(drop=True)
    daily,derr=fetch_daily(code)
    if derr:return None,derr
    out=[]
    for _,r in rows.iterrows():
        asof=hybrid_asof(daily,sessions,r.date_norm,int(r.session))
        if asof is None or len(asof)<80:continue
        tf=base.technical_features(asof)
        if tf is None:continue
        raw=bits_from_tf(tf);r01=bits_rounded(asof,.1);r1=bits_rounded(asof,1.0)
        rec={"key":r.key}
        for k,v in raw.items():rec[f"hyb_{k}"]=v
        for k,v in (r01 or {}).items():rec[f"r01_{k}"]=v
        for k,v in (r1 or {}).items():rec[f"r1_{k}"]=v
        rec["hyb_score"]=sum(int(x) for x in raw.values())
        rec["r01_score"]=sum(int(x) for x in (r01 or {}).values()) if r01 else -1
        rec["r1_score"]=sum(int(x) for x in (r1 or {}).values()) if r1 else -1
        out.append(rec)
    return pd.DataFrame(out),None


def summarize(m,prefix):
    result={"bits":{}}
    for tc in BITS:
        result["bits"][tc]=v1.bit_metrics(m,tc,f"{prefix}_{tc}")
    tscore=m.teacher_score_calc.to_numpy(int);yscore=m[f"{prefix}_score"].to_numpy(int)
    ts6=tscore==6;ys6=yscore==6
    result["score_exact"]=float(np.mean(tscore==yscore));result["score_mae"]=float(np.mean(np.abs(tscore-yscore)))
    result["stable6"]={"teacher":int(ts6.sum()),"yahoo":int(ys6.sum()),"overlap":int(np.sum(ts6&ys6)),"recall":float(np.sum(ts6&ys6)/max(1,ts6.sum())),"precision":float(np.sum(ts6&ys6)/max(1,ys6.sum()))}
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--teacher",required=True);ap.add_argument("--start",default="2026-07-01");ap.add_argument("--end",default="2026-08-31");ap.add_argument("--max-symbols",type=int,default=200);ap.add_argument("--max-workers",type=int,default=20);ap.add_argument("--output-dir",default="research_artifacts/stable_feature_parity_v2")
    a=ap.parse_args();t=v1.load_teacher(a.teacher,a.start,a.end)
    stable_syms=set(t.loc[t.teacher_stable6_calc,"symbol"]);freq=t.groupby("symbol").size().sort_values(ascending=False);codes=(list(stable_syms)+[s for s in freq.index if s not in stable_syms])[:a.max_symbols];t=t[t.symbol.isin(codes)].copy()
    frames=[];errors={}
    with ThreadPoolExecutor(max_workers=a.max_workers) as ex:
        fut={ex.submit(process_code,c,t[t.symbol==c].copy()):c for c in codes}
        for i,f in enumerate(as_completed(fut),1):
            try:fr,err=f.result()
            except Exception as e:fr,err=None,type(e).__name__
            if fr is not None and not fr.empty:frames.append(fr)
            elif err:errors[err]=errors.get(err,0)+1
            if i%50==0:print(f"progress {i}/{len(codes)}",flush=True)
    if not frames:raise RuntimeError("no matched rows")
    y=pd.concat(frames,ignore_index=True);m=t.merge(y,on="key",how="inner")
    result={"teacher_rows":int(len(t)),"matched":int(len(m)),"symbols":len(codes),"errors":errors,"variants":{}}
    for p in ("hyb","r01","r1"):result["variants"][p]=summarize(m,p)
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/"stable_feature_parity_v2.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
