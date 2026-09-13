from __future__ import annotations

import argparse
import glob
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.utils.class_weight import compute_sample_weight

EXPECTED_DAILY_SHA = "6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0"
CHANGE_DATE = "2024-11-05"
FEATURES = [
    "bar_log_return","range_pct","upper_wick_pct","lower_wick_pct","close_location",
    "prev4_log_return_mean","prev4_range_mean","bb_position","bb_width_pct","rsi12",
    "rsi_delta","atr_pct","dist_prior5_low_atr","prior5_rsi_min","prior5_band_min",
    "log_volume_rel20","trigger_rsi_recovery","trigger_trend_flip","trigger_emergency_reversal",
]
TOP_NS = [1,2,3,5]
BINS = ["AM_09_13","PM_13_CLOSE"]
PARAMS = dict(
    learning_rate=0.05,max_iter=150,max_leaf_nodes=15,min_samples_leaf=100,
    l2_regularization=1.0,max_bins=63,early_stopping=False,random_state=0,
)

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1<<20),b""): h.update(block)
    return h.hexdigest()

def build_bins_fast(pattern: str, max_date: str="2025-06-30") -> pd.DataFrame:
    parts=[]
    for fp in sorted(glob.glob(pattern)):
        raw=pd.read_csv(fp,dtype={"symbol":"string"})
        ts=raw["timestamp"].astype(str)
        raw["date"]=ts.str.slice(0,10)
        raw=raw[raw["date"]<=max_date].copy()
        raw["hour"]=pd.to_numeric(ts.loc[raw.index].str.slice(11,13),errors="coerce")
        raw["symbol"]=raw["symbol"].astype(str).str.replace(r"\.0$","",regex=True).str.upper()
        pre=raw["date"]<CHANGE_DATE
        am=raw["hour"].isin([9,10,11,12])
        pm=(pre & raw["hour"].isin([13,14])) | (~pre & raw["hour"].isin([13,14,15]))
        raw=raw[am|pm].copy()
        raw["bin_name"]=np.where(raw["hour"].isin([9,10,11,12]),"AM_09_13","PM_13_CLOSE")
        raw["_ord"]=np.arange(len(raw))
        raw=raw.sort_values(["symbol","date","_ord"],kind="stable")
        out=raw.groupby(["symbol","date","bin_name"],sort=False).agg(
            row_count=("hour","size"),open=("open","first"),high=("high","max"),
            low=("low","min"),close=("close","last"),volume=("volume","sum")
        ).reset_index()
        expected=np.where(out["bin_name"].eq("AM_09_13"),4,np.where(out["date"]<CHANGE_DATE,2,3))
        parts.append(out[out["row_count"].eq(expected)].copy())
    if not parts: raise FileNotFoundError(pattern)
    bins=pd.concat(parts,ignore_index=True)
    bins["bin_ord"]=bins["bin_name"].map({"AM_09_13":0,"PM_13_CLOSE":1})
    return bins.sort_values(["symbol","date","bin_ord"],kind="stable").reset_index(drop=True)

def indicators(close,high,low):
    n=len(close); s=pd.Series(close)
    mid=s.rolling(20,min_periods=20).mean().to_numpy()
    std=s.rolling(20,min_periods=20).std(ddof=0).to_numpy()
    rsi=np.full(n,np.nan)
    if n>12:
        d=np.diff(close); gains=np.maximum(d,0.0); losses=np.maximum(-d,0.0)
        ag=gains[:12].mean(); al=losses[:12].mean()
        rsi[12]=100.0 if al==0 and ag>0 else (50.0 if al==0 else 100.0-100.0/(1.0+ag/al))
        for i in range(13,n):
            ag=(ag*11.0+gains[i-1])/12.0; al=(al*11.0+losses[i-1])/12.0
            rsi[i]=100.0 if al==0 and ag>0 else (50.0 if al==0 else 100.0-100.0/(1.0+ag/al))
    tr=np.empty(n,float); tr[0]=high[0]-low[0]
    if n>1:
        tr[1:]=np.maximum.reduce([high[1:]-low[1:],np.abs(high[1:]-close[:-1]),np.abs(low[1:]-close[:-1])])
    atr=np.full(n,np.nan)
    if n>=14:
        v=tr[:14].mean(); atr[13]=v
        for i in range(14,n):
            v=(v*13.0+tr[i])/14.0; atr[i]=v
    width=4.0*std; lower=mid-2.0*std
    band=np.where(width>0,(close-lower)/width,np.nan)
    p5low=np.full(n,np.nan); p5rsi=np.full(n,np.nan); p5band=np.full(n,np.nan)
    for i in range(5,n):
        p5low[i]=np.min(low[i-5:i])
        rv=rsi[i-5:i]; bv=band[i-5:i]
        if np.isfinite(rv).any(): p5rsi[i]=np.nanmin(rv)
        if np.isfinite(bv).any(): p5band[i]=np.nanmin(bv)
    return mid,std,rsi,atr,p5low,p5rsi,p5band

def add_state_and_features(bins: pd.DataFrame) -> pd.DataFrame:
    x=bins.copy(); n=len(x)
    arr=[np.full(n,np.nan) for _ in range(7)]
    for _,g in x.groupby("symbol",sort=False):
        idx=g.index.to_numpy()
        vals=indicators(g["close"].to_numpy(float),g["high"].to_numpy(float),g["low"].to_numpy(float))
        for a,v in zip(arr,vals): a[idx]=v
    x["bb_mid"],x["bb_std"],x["rsi12"],x["atr14"],x["prior5_low"],x["prior5_rsi_min"],x["prior5_band_min"]=arr
    x["bb_slope"]=x.groupby("symbol",sort=False)["bb_mid"].diff()
    x["prev_bb_slope"]=x.groupby("symbol",sort=False)["bb_slope"].shift(1)
    x["prev_rsi12"]=x.groupby("symbol",sort=False)["rsi12"].shift(1)
    x["setup"]=(x["prior5_rsi_min"]<=35.0)|(x["prior5_band_min"]<=0.18)
    x["rsi_recovery"]=(x["rsi12"]>35.0)&(x["prev_rsi12"]<=35.0)
    x["trend_flip"]=(x["bb_slope"]>0)&(x["prev_bb_slope"]<=0)&(x["rsi12"]>50.0)&(x["prev_rsi12"]<=50.0)
    x["emergency_reversal"]=x["close"]>x["prior5_low"]+2.5*x["atr14"]
    x["signal"]=x["setup"]&(x["rsi_recovery"]|x["trend_flip"]|x["emergency_reversal"])

    base=x["open"].where(x["open"]>0)
    x["bar_log_return"]=np.log(x["close"]/base)
    x["range_pct"]=(x["high"]-x["low"])/base
    x["upper_wick_pct"]=(x["high"]-np.maximum(x["open"],x["close"]))/base
    x["lower_wick_pct"]=(np.minimum(x["open"],x["close"])-x["low"])/base
    span=x["high"]-x["low"]
    x["close_location"]=np.where(span>0,(x["close"]-x["low"])/span,0.5)
    x["prev4_log_return_mean"]=x.groupby("symbol",sort=False)["bar_log_return"].transform(lambda s:s.shift(1).rolling(4,min_periods=4).mean())
    x["prev4_range_mean"]=x.groupby("symbol",sort=False)["range_pct"].transform(lambda s:s.shift(1).rolling(4,min_periods=4).mean())
    width=4.0*x["bb_std"]; lower=x["bb_mid"]-2.0*x["bb_std"]
    x["bb_position"]=np.where(width>0,(x["close"]-lower)/width,np.nan)
    x["bb_width_pct"]=np.where(x["bb_mid"]>0,width/x["bb_mid"],np.nan)
    x["rsi_delta"]=x["rsi12"]-x["prev_rsi12"]
    x["atr_pct"]=np.where(x["close"]>0,x["atr14"]/x["close"],np.nan)
    x["dist_prior5_low_atr"]=np.where(x["atr14"]>0,(x["close"]-x["prior5_low"])/x["atr14"],np.nan)
    med=x.groupby(["symbol","bin_name"],sort=False)["volume"].transform(lambda s:s.shift(1).rolling(20,min_periods=20).median())
    x["log_volume_rel20"]=np.where(med>0,np.log1p(x["volume"]/med),np.nan)
    x["trigger_rsi_recovery"]=x["rsi_recovery"].astype(float)
    x["trigger_trend_flip"]=x["trend_flip"].astype(float)
    x["trigger_emergency_reversal"]=x["emergency_reversal"].astype(float)
    return x

def load_daily_window(path: Path, min_date="2024-08-01", max_date="2025-07-10") -> pd.DataFrame:
    parts=[]
    for c in pd.read_csv(path,dtype={"symbol":"string"},usecols=["date","open","close","volume","symbol"],chunksize=400000,low_memory=False):
        c["date"]=c["date"].astype(str).str[:10]
        c=c[(c["date"]>=min_date)&(c["date"]<=max_date)].copy()
        if len(c): parts.append(c)
    d=pd.concat(parts,ignore_index=True)
    d["symbol"]=d["symbol"].astype(str).str.replace(r"\.0$","",regex=True).str.upper()
    for col in ["open","close","volume"]: d[col]=pd.to_numeric(d[col],errors="coerce")
    return d

def attach_gates_labels(events: pd.DataFrame,daily: pd.DataFrame):
    sessions=sorted(daily["date"].dropna().unique().tolist())
    idx={d:i for i,d in enumerate(sessions)}
    prior={sessions[i]:sessions[i-1] for i in range(1,len(sessions))}
    entry={sessions[i]:sessions[i+1] for i in range(len(sessions)-5)}
    exit_={sessions[i]:sessions[i+5] for i in range(len(sessions)-5)}
    x=events.copy(); x["date"]=x["date"].astype(str)
    x["prior_date"]=x["date"].map(prior)
    p=daily[["symbol","date","close","volume"]].rename(columns={"date":"prior_date","close":"prior_daily_close","volume":"prior_daily_volume"})
    x=x.merge(p,on=["symbol","prior_date"],how="left")
    x=x[(x["prior_daily_close"]<=1000)&(x["prior_daily_volume"]>=10000)].copy()
    x["entry_date"]=x["date"].map(entry); x["exit_date"]=x["date"].map(exit_)
    en=daily[["symbol","date","open"]].rename(columns={"date":"entry_date","open":"entry_open"})
    ex=daily[["symbol","date","close"]].rename(columns={"date":"exit_date","close":"exit_close"})
    x=x.merge(en,on=["symbol","entry_date"],how="left").merge(ex,on=["symbol","exit_date"],how="left")
    ok=np.isfinite(x["entry_open"])&(x["entry_open"]>0)&np.isfinite(x["exit_close"])&(x["exit_close"]>0)
    x["endpoint_status"]=np.where(ok,"RESOLVED","UNRESOLVED_ENDPOINT")
    x["ret5bd_gross"]=np.where(ok,x["exit_close"]/x["entry_open"]-1.0,np.nan)
    return x,idx

def fit_prob(train,valid,target):
    y=train[target].to_numpy(int)
    w=compute_sample_weight(class_weight="balanced",y=y)
    m=HistGradientBoostingClassifier(**PARAMS)
    m.fit(train[FEATURES],y,sample_weight=w)
    return m.predict_proba(valid[FEATURES])[:,1]

def pareto(group):
    g=group.sort_values(["p_tail20","p_loss10","symbol"],ascending=[False,True,True],kind="stable").copy()
    keep=np.zeros(len(g),bool); best=np.inf; last=None
    for i,pair in enumerate(zip(g["p_tail20"].to_numpy(float),g["p_loss10"].to_numpy(float))):
        t,l=pair
        if l<best: keep[i]=True; best=l
        elif last is not None and pair==last: keep[i]=True
        last=pair
    return g.loc[keep]

def select(scored,session_idx,n):
    fronts=[pareto(g) for _,g in scored.groupby(["date","bin_name"],sort=False)]
    x=pd.concat(fronts,ignore_index=True) if fronts else scored.iloc[0:0].copy()
    x=x.sort_values(["date","bin_name","p_tail20","p_loss10","symbol"],ascending=[True,True,False,True,True],kind="stable")
    groups={(d,b):g.to_dict("records") for (d,b),g in x.groupby(["date","bin_name"],sort=False)}
    blocked={}; rows=[]
    for day in sorted(scored["date"].unique()):
        di=session_idx[day]
        for bn in BINS:
            picked=0
            for r in groups.get((day,bn),()):
                sym=r["symbol"]
                if blocked.get(sym,-999999)>di: continue
                rows.append(r); blocked[sym]=di+5; picked+=1
                if picked>=n: break
    return pd.DataFrame(rows)

def metrics(sel,cost=.005):
    if sel.empty: return {"requested":0,"resolved":0,"unresolved":0}
    r=sel[sel["endpoint_status"]=="RESOLVED"].copy()
    out={"requested":int(len(sel)),"resolved":int(len(r)),"unresolved":int(len(sel)-len(r))}
    if r.empty: return out
    v=r["ret5bd_gross"].to_numpy(float); net=v-cost; desc=np.sort(net)[::-1]
    out.update(
        net_mean=float(net.mean()),net_median=float(np.median(net)),net_win_rate=float((net>0).mean()),
        gross_ge20_rate=float((v>=.20).mean()),gross_le10_rate=float((v<=-.10).mean()),
        top1_removed_net_mean=float(desc[1:].mean()) if len(desc)>1 else None,
        top3_removed_net_mean=float(desc[3:].mean()) if len(desc)>3 else None,
    )
    return out

def passes(m):
    return m.get("resolved",0)>=30 and m.get("net_mean",-999)>0 and m.get("gross_ge20_rate",-1)>=.10 and m.get("top1_removed_net_mean",-999)>0 and m.get("gross_le10_rate",999)<=.40

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--raw-glob",required=True); ap.add_argument("--daily",required=True); ap.add_argument("--output",required=True); a=ap.parse_args()
    daily_path=Path(a.daily); actual=sha256_file(daily_path)
    if actual!=EXPECTED_DAILY_SHA: raise RuntimeError(f"daily SHA mismatch {actual}")
    bins=build_bins_fast(a.raw_glob,"2025-06-30")
    events=add_state_and_features(bins)
    events=events[events["signal"]].copy()
    daily=load_daily_window(daily_path)
    events,session_idx=attach_gates_labels(events,daily)
    pre2025_pool=events[events["date"]<"2025-01-01"].copy()
    h1_pool=events[(events["date"]>="2025-03-01")&(events["date"]<="2025-06-30")].copy()
    if len(pre2025_pool)!=7099 or pre2025_pool["symbol"].nunique()!=1065:
        raise RuntimeError(f"pre-2025 candidate receipt mismatch rows={len(pre2025_pool)} symbols={pre2025_pool['symbol'].nunique()}")
    if len(h1_pool)!=8245:
        raise RuntimeError(f"H1 candidate receipt mismatch rows={len(h1_pool)}")
    finite=np.isfinite(events[FEATURES]).all(axis=1)
    events=events.loc[finite].copy()
    train=events[(events["date"]<"2025-01-01")&(events["exit_date"]<"2025-01-01")&(events["endpoint_status"]=="RESOLVED")].copy()
    train["target_tail20"]=(train["ret5bd_gross"]>=.20).astype(int)
    train["target_loss10"]=(train["ret5bd_gross"]<=-.10).astype(int)
    valid=events[(events["date"]>="2025-03-01")&(events["date"]<="2025-06-30")].copy()
    valid["p_tail20"]=fit_prob(train,valid,"target_tail20")
    valid["p_loss10"]=fit_prob(train,valid,"target_loss10")
    out={"experiment_id":"TENTEI-INSPIRED-4H-V14-PRE2025-DUAL-CLASSIFIER-20260913","replay":"FAST_EQUIVALENT_TIMESTAMP_PARSER","daily_sha256":actual,"pre2025_candidate_rows":len(pre2025_pool),"pre2025_candidate_symbols":int(pre2025_pool["symbol"].nunique()),"h1_candidate_rows_before_feature_finiteness":len(h1_pool),"train_rows":len(train),"train_symbols":int(train["symbol"].nunique()),"train_tail20_rate":float(train["target_tail20"].mean()),"train_loss10_rate":float(train["target_loss10"].mean()),"valid_rows":len(valid),"2025_labels_used_for_fit":False,"2026_outcomes_opened":False,"results":{}}
    for n in TOP_NS:
        s=select(valid,session_idx,n); m=metrics(s,.005); m["passes_v14_gate"]=passes(m); m["cost0"]=metrics(s,0); m["cost1pct"]=metrics(s,.01); out["results"][str(n)]=m
    Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
