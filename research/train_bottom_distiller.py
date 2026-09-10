from __future__ import annotations

import json, math, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

import numpy as np
import pandas as pd
import requests
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import optimize_screener as opt

OUT=Path("research_artifacts/no_tv_distiller")
FEATURES=[
 "ret1","ret2","ret3","ret5","ret10","body","range","close_loc","upper_wick","lower_wick",
 "vol3","vol10","vol20","atr_pct","rsi12","bb_pos","bb_width","mid_slope1","mid_slope3",
 "dist_mid","day_gap","day_ret_sofar","prev_day_ret1","prev_day_ret3","prev_day_ret5",
 "prev_day_vol_ratio20","session13"
]
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"

_ORIG_FETCH=opt.fetch
def retry_fetch(svc,sheet):
    for attempt in range(6):
        try:return _ORIG_FETCH(svc,sheet)
        except Exception:
            if attempt==5:raise
            time.sleep(2**attempt)
opt.fetch=retry_fetch

def fetch_yahoo(symbol):
    url=f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.T"
    for attempt in range(4):
        try:
            r=requests.get(url,params={"range":"1y","interval":"1h"},headers={"User-Agent":UA},timeout=25)
            if r.status_code in (429,502,503,504):
                time.sleep(.8*(attempt+1));continue
            r.raise_for_status();p=r.json()
            res=p["chart"]["result"][0];q=res["indicators"]["quote"][0]
            ts=res.get("timestamp") or []
            rows=[]
            for i,t in enumerate(ts):
                vals=[q.get(k,[None]*len(ts))[i] for k in ("open","high","low","close","volume")]
                if any(v is None for v in vals):continue
                o,h,l,c,v=map(float,vals)
                if c<=0 or h<=0 or l<=0 or h<l:continue
                dt=pd.to_datetime(int(t),unit="s",utc=True).tz_convert("Asia/Tokyo")
                rows.append((dt,o,h,l,c,v))
            if len(rows)<100:return None
            x=pd.DataFrame(rows,columns=["ts","open","high","low","close","volume"])
            x["date"]=x.ts.dt.date.astype(str)
            return x
        except Exception:
            time.sleep(.5*(attempt+1))
    return None

def pine_rsi(vals,n=12):
    s=pd.Series(vals,dtype=float);d=s.diff();up=d.clip(lower=0);dn=(-d.clip(upper=0))
    au=up.ewm(alpha=1/n,adjust=False,min_periods=n).mean()
    ad=dn.ewm(alpha=1/n,adjust=False,min_periods=n).mean()
    rs=au/ad.replace(0,np.nan)
    return (100-100/(1+rs)).fillna(100).to_numpy()

def build_sessions(hourly):
    x=hourly.copy();mins=x.ts.dt.hour*60+x.ts.dt.minute
    x["session"]=np.where(mins<13*60,9,13)
    s=x.groupby(["date","session"],sort=True).agg(
      ts=("ts","last"),open=("open","first"),high=("high","max"),low=("low","min"),
      close=("close","last"),volume=("volume","sum")
    ).reset_index()
    c=s.close.astype(float);o=s.open.astype(float);h=s.high.astype(float);l=s.low.astype(float);v=s.volume.astype(float)
    for n in (1,2,3,5,10):s[f"ret{n}"]=c/c.shift(n)-1
    prev=c.shift(1);cr=(h-l).replace(0,np.nan)
    s["body"]=(c-o)/prev;s["range"]=(h-l)/prev
    s["close_loc"]=((c-l)/cr).clip(0,1).fillna(.5)
    s["upper_wick"]=((h-np.maximum(o,c))/cr).clip(0,1).fillna(0)
    s["lower_wick"]=((np.minimum(o,c)-l)/cr).clip(0,1).fillna(0)
    for n in (3,10,20):
        s[f"vol{n}"]=v/v.shift(1).rolling(n,min_periods=n).mean()
    tr=pd.concat([(h-l),(h-prev).abs(),(l-prev).abs()],axis=1).max(axis=1)
    s["atr_pct"]=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean()/c
    s["rsi12"]=pine_rsi(c.to_numpy(),12)/100
    mid=c.rolling(20,min_periods=20).mean();sd=c.rolling(20,min_periods=20).std(ddof=0)
    s["bb_pos"]=(c-(mid-2*sd))/(4*sd.replace(0,np.nan));s["bb_width"]=4*sd/mid.replace(0,np.nan)
    s["mid_slope1"]=mid/mid.shift(1)-1;s["mid_slope3"]=mid/mid.shift(3)-1;s["dist_mid"]=c/mid-1

    d=hourly.groupby("date",sort=True).agg(open=("open","first"),close=("close","last"),volume=("volume","sum")).reset_index()
    dc=d.close.astype(float);dv=d.volume.astype(float)
    d["prev_close"]=dc.shift(1);d["prev_day_ret1"]=dc.shift(1)/dc.shift(2)-1
    d["prev_day_ret3"]=dc.shift(1)/dc.shift(4)-1;d["prev_day_ret5"]=dc.shift(1)/dc.shift(6)-1
    d["prev_day_vol_ratio20"]=dv.shift(1)/dv.shift(2).rolling(20,min_periods=10).mean()
    ctx=d[["date","prev_close","prev_day_ret1","prev_day_ret3","prev_day_ret5","prev_day_vol_ratio20"]]
    s=s.merge(ctx,on="date",how="left")
    s["day_gap"]=s.open/s.prev_close-1
    # partial day return at each session close, causal
    day_open=s.groupby("date",sort=False).open.transform("first")
    s["day_ret_sofar"]=s.close/day_open-1
    s["session13"]=(s.session==13).astype(float)
    return s

def load_alert_labels():
    svc=opt.get_service();ar=opt.fetch(svc,"alerts_raw")
    try:sa=opt.fetch(svc,"signals_archive")
    except Exception:sa=[]
    lookup=opt.alert_received_at_lookup(ar,sa)
    a1=opt.attach_alert_received_at(opt.parse_alerts(ar),lookup)
    a2=opt.attach_alert_received_at(opt.parse_alerts(sa),lookup)
    alerts=pd.concat([a1,a2],ignore_index=True)
    if "alert_id" in alerts:
        has=alerts.alert_id.astype(str)!=""
        alerts=pd.concat([alerts[has].drop_duplicates("alert_id"),alerts[~has]],ignore_index=True)
    alerts["date"]=alerts.date.astype(str).str.replace("/","-",regex=False).str[:10]
    dt=pd.to_datetime(alerts["_received_at_dt"],errors="coerce")
    # production feature cutoff: received before 14:00 -> 09 session, else 13 session
    alerts["session"]=np.where(dt.dt.hour<14,9,13)
    return alerts[["symbol","date","session"]].drop_duplicates()

def build_symbol_samples(symbol,positive_keys):
    h=fetch_yahoo(symbol)
    if h is None:return None
    s=build_sessions(h)
    keys={(d,int(sess)) for d,sess in positive_keys}
    target_dates={d for d,_ in keys}
    rows=[]
    for _,r in s[s.date.isin(target_dates)].iterrows():
        key=(str(r.date),int(r.session))
        label=int(key in keys)
        # only same-day paired sessions around known monitored positive days
        rec={"symbol":symbol,"date":str(r.date),"session":int(r.session),"label":label}
        for f in FEATURES:rec[f]=r.get(f,np.nan)
        rows.append(rec)
    return pd.DataFrame(rows)

def metrics(y,p,thr=.5):
    y=np.asarray(y,int);pred=(p>=thr).astype(int)
    return {"n":int(len(y)),"pos":int(y.sum()),
      "auc":float(roc_auc_score(y,p)) if len(np.unique(y))==2 else None,
      "accuracy":float(accuracy_score(y,pred)),
      "precision":float(precision_score(y,pred,zero_division=0)),
      "recall":float(recall_score(y,pred,zero_division=0))}

def finite(frame):
    return frame[FEATURES].apply(pd.to_numeric,errors="coerce").replace([np.inf,-np.inf],np.nan)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    labels=load_alert_labels()
    grouped={sym:list(zip(g.date,g.session)) for sym,g in labels.groupby("symbol")}
    print(f"teacher labels={len(labels)} symbols={len(grouped)}",flush=True)
    frames=[];errors=0
    with ThreadPoolExecutor(max_workers=24) as ex:
        fut={ex.submit(build_symbol_samples,sym,keys):sym for sym,keys in grouped.items()}
        for n,f in enumerate(as_completed(fut),1):
            try:x=f.result()
            except Exception:x=None
            if x is not None and not x.empty:frames.append(x)
            else:errors+=1
            if n%200==0:print(f"progress {n}/{len(fut)} frames={len(frames)}",flush=True)
    df=pd.concat(frames,ignore_index=True)
    df["date_dt"]=pd.to_datetime(df.date)
    # dates are predefined before seeing classification outcomes.
    train=df[df.date_dt<"2026-06-01"].copy()
    valid=df[(df.date_dt>="2026-06-01")&(df.date_dt<"2026-07-01")].copy()
    test=df[(df.date_dt>="2026-07-01")&(df.date_dt<="2026-08-31")].copy()

    lin=Pipeline([("imp",SimpleImputer(strategy="median")),("sc",StandardScaler()),
                  ("m",LogisticRegression(max_iter=500,class_weight="balanced",C=.5))])
    hgb=Pipeline([("imp",SimpleImputer(strategy="median")),
                  ("m",HistGradientBoostingClassifier(max_iter=250,learning_rate=.05,max_leaf_nodes=15,min_samples_leaf=30,l2_regularization=1.5,random_state=91))])
    X=finite(train);y=train.label.astype(int)
    lin.fit(X,y);hgb.fit(X,y)
    def pred(frame):
        X=finite(frame)
        return .35*lin.predict_proba(X)[:,1]+.65*hgb.predict_proba(X)[:,1]
    pv=pred(valid);pt=pred(test)
    # threshold chosen only on June validation: maximize balanced mean of precision/recall.
    best=None
    for th in np.arange(.35,.71,.025):
        m=metrics(valid.label,pv,float(th));score=.5*m["precision"]+.5*m["recall"]
        if best is None or score>best["score"]:best={"threshold":float(th),"score":float(score),"metrics":m}
    result={
      "label_rows":int(len(df)),"positive_labels":int(df.label.sum()),"symbols":int(df.symbol.nunique()),"fetch_errors":errors,
      "train":metrics(train.label,pred(train),best["threshold"]),
      "validation":best["metrics"],"threshold":best["threshold"],
      "test":metrics(test.label,pt,best["threshold"]),
      "test_default_05":metrics(test.label,pt,.5),
    }
    # logistic coefficient ranking for interpretability
    coef=lin.named_steps["m"].coef_[0]
    result["linear_feature_coefficients"]=dict(sorted(zip(FEATURES,map(float,coef)),key=lambda x:abs(x[1]),reverse=True))
    df.to_csv(OUT/"bottom_distillation_samples.csv",index=False,encoding="utf-8-sig")
    (OUT/"bottom_distillation_summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__":raise SystemExit(main())
