from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tvfree_screener.batch02 import eval_tentei_inspired_4h_v14_fast_replay as base

RETAINED = [
    "bar_log_return","upper_wick_pct","close_location","prev4_log_return_mean",
    "bb_position","rsi12","rsi_delta","log_volume_rel20",
]
RANK_MAP = {
    "range_pct":"xrank_range_pct",
    "prev4_range_mean":"xrank_prev4_range_mean",
    "bb_width_pct":"xrank_bb_width_pct",
    "atr_pct":"xrank_atr_pct",
    "lower_wick_pct":"xrank_lower_wick_pct",
    "dist_prior5_low_atr":"xrank_dist_prior5_low_atr",
    "prior5_rsi_min":"xrank_prior5_rsi_min",
    "prior5_band_min":"xrank_prior5_band_min",
}
FEATURES = RETAINED + list(RANK_MAP.values())
TRIGGERS = ["rsi_recovery","trend_flip","emergency_reversal"]


def load_gate_daily(path: Path, min_date="2025-02-01", max_date="2026-01-10") -> pd.DataFrame:
    parts=[]
    for c in pd.read_csv(
        path,dtype={"symbol":"string"},
        usecols=["date","close","volume","symbol"],
        chunksize=400000,low_memory=False,
    ):
        c["date"]=c["date"].astype(str).str[:10]
        c=c[(c["date"]>=min_date)&(c["date"]<=max_date)].copy()
        if len(c):
            parts.append(c)
    d=pd.concat(parts,ignore_index=True)
    d["symbol"]=d["symbol"].astype(str).str.replace(r"\.0$","",regex=True).str.upper()
    d["close"]=pd.to_numeric(d["close"],errors="coerce")
    d["volume"]=pd.to_numeric(d["volume"],errors="coerce")
    return d


def gate_and_rank(bins: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    sessions=sorted(daily["date"].dropna().unique().tolist())
    prior={sessions[i]:sessions[i-1] for i in range(1,len(sessions))}
    x=bins.copy()
    x["date"]=x["date"].astype(str)
    x["prior_date"]=x["date"].map(prior)
    p=daily[["symbol","date","close","volume"]].rename(
        columns={"date":"prior_date","close":"prior_daily_close","volume":"prior_daily_volume"}
    )
    x=x.merge(p,on=["symbol","prior_date"],how="left")
    x=x[(x["prior_daily_close"]<=1000)&(x["prior_daily_volume"]>=10000)].copy()
    src=list(RANK_MAP.keys())
    x=x.loc[np.isfinite(x[src]).all(axis=1)].copy()
    for s,d in RANK_MAP.items():
        x[d]=x.groupby(["date","bin_name"],sort=False)[s].rank(
            method="average",pct=True,ascending=True
        )
    return x


def ks_stat(a,b):
    a=np.sort(np.asarray(a,float)); b=np.sort(np.asarray(b,float))
    vals=np.sort(np.unique(np.concatenate([a,b])))
    ca=np.searchsorted(a,vals,side="right")/len(a)
    cb=np.searchsorted(b,vals,side="right")/len(b)
    return float(np.max(np.abs(ca-cb)))


def psi(train,test,eps=1e-6):
    t=np.asarray(train,float); h=np.asarray(test,float)
    edges=np.unique(np.quantile(t,np.arange(.1,1.0,.1)))
    if len(edges)<1:
        return None
    bins=np.concatenate(([-np.inf],edges,[np.inf]))
    tc,_=np.histogram(t,bins); hc,_=np.histogram(h,bins)
    tp=np.clip(tc/tc.sum(),eps,None); hp=np.clip(hc/hc.sum(),eps,None)
    return float(np.sum((hp-tp)*np.log(hp/tp)))


def tier(k,p,s):
    if k>=.20 or (p is not None and p>=.25) or abs(s)>=.50:
        return "SEVERE"
    if k>=.10 or (p is not None and p>=.10) or abs(s)>=.25:
        return "MODERATE"
    return "LOW"


def trigger_tier(delta):
    a=abs(delta)
    if a>=.10:
        return "SEVERE"
    if a>=.05:
        return "MODERATE"
    return "LOW"


def diag(df):
    active=df["date"].nunique()
    return {
        "rows":int(len(df)),
        "symbols":int(df["symbol"].nunique()),
        "active_dates":int(active),
        "events_per_active_date":float(len(df)/active) if active else None,
        "am_share":float((df["bin_name"]=="AM_09_13").mean()) if len(df) else None,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--raw-glob",required=True)
    p.add_argument("--daily",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()

    daily_path=Path(a.daily)
    actual=base.sha256_file(daily_path)
    if actual!=base.EXPECTED_DAILY_SHA:
        raise RuntimeError(f"daily SHA mismatch {actual}")

    bins=base.build_bins_fast(a.raw_glob,"2025-12-31")
    bins=base.add_state_and_features(bins)
    daily=load_gate_daily(daily_path)
    ranked=gate_and_rank(bins,daily)

    events=ranked[ranked["signal"]].copy()
    events=events.loc[np.isfinite(events[FEATURES]).all(axis=1)].copy()

    h1=events[(events["date"]>="2025-03-01")&(events["date"]<="2025-06-30")].copy()
    h2=events[(events["date"]>="2025-07-01")&(events["date"]<="2025-12-31")].copy()

    out={
        "audit_id":"TENTEI-V17-H1-H2-SIGNALTIME-DRIFT-20260913-01",
        "strategy_returns_used":False,
        "2026_outcomes_opened":False,
        "daily_sha256":actual,
        "diagnostics":{"h1":diag(h1),"h2":diag(h2)},
        "features":{},
        "trigger_composition":{},
    }

    severe=0; moderate=0
    for col in FEATURES:
        av=h1[col].to_numpy(float); bv=h2[col].to_numpy(float)
        k=ks_stat(av,bv); pv=psi(av,bv)
        q25,q50,q75=np.quantile(av,[.25,.5,.75]); hm=float(np.median(bv))
        iqr=q75-q25; sh=float((hm-q50)/iqr) if iqr>0 else 0.0
        t=tier(k,pv,sh)
        severe+=t=="SEVERE"; moderate+=t=="MODERATE"
        out["features"][col]={
            "h1_median":float(q50),"h2_median":hm,
            "ks":k,"psi":pv,"median_shift_iqr":sh,"tier":t
        }

    trigger_severe=False
    for col in TRIGGERS:
        r1=float(h1[col].mean()); r2=float(h2[col].mean()); d=r2-r1; t=trigger_tier(d)
        trigger_severe=trigger_severe or t=="SEVERE"
        out["trigger_composition"][col]={
            "h1_rate":r1,"h2_rate":r2,"delta":d,"tier":t
        }

    if severe>=3 or trigger_severe:
        decision="MATERIAL_SIGNALTIME_SHIFT"
    elif severe in (1,2) or moderate>4:
        decision="PARTIAL_SIGNALTIME_SHIFT"
    else:
        decision="STABLE_SIGNALTIME_REPRESENTATION"

    out["summary"]={
        "severe_features":int(severe),
        "moderate_features":int(moderate),
        "any_severe_trigger":bool(trigger_severe),
        "decision":decision,
    }
    Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
