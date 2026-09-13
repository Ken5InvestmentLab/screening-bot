from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tvfree_screener.batch02 import eval_tentei_inspired_4h_v14_fast_replay as base

EPS = 1e-9
RETAINED = [
    "bar_log_return","upper_wick_pct","close_location","prev4_log_return_mean",
    "bb_position","rsi12","rsi_delta","log_volume_rel20",
]
NORMALIZED = [
    "range_rel20_log","prev4_range_rel20_log","bb_width_rel20_log","atr_rel20_log",
    "lower_wick_rank20","dist_prior5_low_atr_rank20","prior5_rsi_min_rank20","prior5_band_min_rank20",
]
FEATURES = RETAINED + NORMALIZED


def prior20_rank(values: np.ndarray) -> np.ndarray:
    out=np.full(len(values),np.nan)
    for i in range(20,len(values)):
        hist=values[i-20:i]
        cur=values[i]
        if not np.isfinite(cur) or not np.isfinite(hist).all():
            continue
        out[i]=(np.sum(hist<cur)+0.5*np.sum(hist==cur))/20.0
    return out


def add_v15_features(bins: pd.DataFrame) -> pd.DataFrame:
    x=base.add_state_and_features(bins)
    group_cols=["symbol","bin_name"]
    med_sources={
        "range_pct":"range_rel20_log",
        "prev4_range_mean":"prev4_range_rel20_log",
        "bb_width_pct":"bb_width_rel20_log",
        "atr_pct":"atr_rel20_log",
    }
    for src,dst in med_sources.items():
        med=x.groupby(group_cols,sort=False)[src].transform(lambda s:s.shift(1).rolling(20,min_periods=20).median())
        x[dst]=np.log((x[src]+EPS)/(med+EPS))
    rank_sources={
        "lower_wick_pct":"lower_wick_rank20",
        "dist_prior5_low_atr":"dist_prior5_low_atr_rank20",
        "prior5_rsi_min":"prior5_rsi_min_rank20",
        "prior5_band_min":"prior5_band_min_rank20",
    }
    for src,dst in rank_sources.items():
        out=np.full(len(x),np.nan)
        for _,g in x.groupby(group_cols,sort=False):
            idx=g.index.to_numpy()
            out[idx]=prior20_rank(g[src].to_numpy(float))
        x[dst]=out
    return x


def load_gate_daily(path: Path, min_date="2024-08-01", max_date="2025-07-10") -> pd.DataFrame:
    parts=[]
    for c in pd.read_csv(path,dtype={"symbol":"string"},usecols=["date","close","volume","symbol"],chunksize=400000,low_memory=False):
        c["date"]=c["date"].astype(str).str[:10]
        c=c[(c["date"]>=min_date)&(c["date"]<=max_date)].copy()
        if len(c): parts.append(c)
    d=pd.concat(parts,ignore_index=True)
    d["symbol"]=d["symbol"].astype(str).str.replace(r"\.0$","",regex=True).str.upper()
    d["close"]=pd.to_numeric(d["close"],errors="coerce")
    d["volume"]=pd.to_numeric(d["volume"],errors="coerce")
    return d


def attach_prior_gate_and_maturity(events: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    sessions=sorted(daily["date"].dropna().unique().tolist())
    prior={sessions[i]:sessions[i-1] for i in range(1,len(sessions))}
    exitmap={sessions[i]:sessions[i+5] for i in range(len(sessions)-5)}
    x=events.copy()
    x["date"]=x["date"].astype(str)
    x["prior_date"]=x["date"].map(prior)
    p=daily[["symbol","date","close","volume"]].rename(columns={"date":"prior_date","close":"prior_daily_close","volume":"prior_daily_volume"})
    x=x.merge(p,on=["symbol","prior_date"],how="left")
    x=x[(x["prior_daily_close"]<=1000)&(x["prior_daily_volume"]>=10000)].copy()
    x["exit_date"]=x["date"].map(exitmap)
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
    if len(edges)<1: return None
    bins=np.concatenate(([-np.inf],edges,[np.inf]))
    tc,_=np.histogram(t,bins); hc,_=np.histogram(h,bins)
    tp=np.clip(tc/tc.sum(),eps,None); hp=np.clip(hc/hc.sum(),eps,None)
    return float(np.sum((hp-tp)*np.log(hp/tp)))


def tier(ks,p,shift):
    if ks>=.20 or (p is not None and p>=.25) or abs(shift)>=.50: return "SEVERE"
    if ks>=.10 or (p is not None and p>=.10) or abs(shift)>=.25: return "MODERATE"
    return "LOW"


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--raw-glob",required=True)
    ap.add_argument("--daily",required=True)
    ap.add_argument("--output",required=True)
    a=ap.parse_args()
    daily_path=Path(a.daily)
    actual=base.sha256_file(daily_path)
    if actual!=base.EXPECTED_DAILY_SHA:
        raise RuntimeError(f"daily SHA mismatch {actual}")

    bins=base.build_bins_fast(a.raw_glob,"2025-06-30")
    x=add_v15_features(bins)
    events=x[x["signal"]].copy()
    daily=load_gate_daily(daily_path)
    events=attach_prior_gate_and_maturity(events,daily)
    finite=np.isfinite(events[FEATURES]).all(axis=1)
    events=events.loc[finite].copy()
    train=events[(events["date"]<"2025-01-01")&(events["exit_date"]<"2025-01-01")].copy()
    h1=events[(events["date"]>="2025-03-01")&(events["date"]<="2025-06-30")].copy()

    out={
      "audit_id":"TENTEI-V15-REGIME-NORMALIZED-DRIFT-20260913-01",
      "strategy_returns_opened":False,
      "h2_returns_opened":False,
      "2026_outcomes_opened":False,
      "daily_sha256":actual,
      "cohorts":{
        "train_rows":int(len(train)),"train_symbols":int(train["symbol"].nunique()),
        "h1_rows":int(len(h1)),"h1_symbols":int(h1["symbol"].nunique())
      },
      "features":{}
    }
    severe=moderate=0
    for col in FEATURES:
        av=train[col].to_numpy(float); bv=h1[col].to_numpy(float)
        k=ks_stat(av,bv); p=psi(av,bv)
        q25,q50,q75=np.quantile(av,[.25,.5,.75]); hm=float(np.median(bv))
        iqr=q75-q25; shift=float((hm-q50)/iqr) if iqr>0 else 0.0
        p01,p99=np.quantile(av,[.01,.99]); outside=float(np.mean((bv<p01)|(bv>p99)))
        t=tier(k,p,shift)
        severe+=t=="SEVERE"; moderate+=t=="MODERATE"
        out["features"][col]={
          "train_median":float(q50),"h1_median":hm,"ks":k,"psi":p,
          "median_shift_iqr":shift,"h1_outside_train_p01_p99_rate":outside,"tier":t
        }
    passed=(severe==0 and moderate<=4)
    out["summary"]={
      "severe_features":severe,"moderate_features":moderate,
      "representation_gate_pass":passed,
      "decision":"PASS_TO_SUPERVISED_PREREGISTRATION" if passed else "FAIL_REDESIGN_OUTCOME_FREE"
    }
    Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
