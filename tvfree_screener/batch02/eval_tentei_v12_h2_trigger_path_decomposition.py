from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tvfree_screener.batch02 import eval_tentei_inspired_4h_v14_fast_replay as base

PATHS = {
    "RSI_RECOVERY": lambda x: x["setup"] & x["rsi_recovery"],
    "TREND_FLIP": lambda x: x["setup"] & x["trend_flip"],
    "EMERGENCY_REVERSAL": lambda x: x["setup"] & x["emergency_reversal"],
}


def load_daily(path: Path, min_date="2025-06-01", max_date="2026-01-20") -> pd.DataFrame:
    parts=[]
    for c in pd.read_csv(
        path,dtype={"symbol":"string"},
        usecols=["date","open","close","volume","symbol"],
        chunksize=400000,low_memory=False,
    ):
        c["date"]=c["date"].astype(str).str[:10]
        c=c[(c["date"]>=min_date)&(c["date"]<=max_date)].copy()
        if len(c):
            parts.append(c)
    d=pd.concat(parts,ignore_index=True)
    d["symbol"]=d["symbol"].astype(str).str.replace(r"\.0$","",regex=True).str.upper()
    for col in ["open","close","volume"]:
        d[col]=pd.to_numeric(d[col],errors="coerce")
    return d


def attach(events: pd.DataFrame, daily: pd.DataFrame):
    sessions=sorted(daily["date"].dropna().unique().tolist())
    idx={d:i for i,d in enumerate(sessions)}
    prior={sessions[i]:sessions[i-1] for i in range(1,len(sessions))}
    entry={sessions[i]:sessions[i+1] for i in range(len(sessions)-5)}
    exit_map={sessions[i]:sessions[i+5] for i in range(len(sessions)-5)}

    x=events.copy()
    x["date"]=x["date"].astype(str)
    x["prior_date"]=x["date"].map(prior)
    p=daily[["symbol","date","close","volume"]].rename(
        columns={"date":"prior_date","close":"prior_daily_close","volume":"prior_daily_volume"}
    )
    x=x.merge(p,on=["symbol","prior_date"],how="left")
    x=x[(x["prior_daily_close"]<=1000)&(x["prior_daily_volume"]>=10000)].copy()
    x["entry_date"]=x["date"].map(entry)
    x["exit_date"]=x["date"].map(exit_map)
    en=daily[["symbol","date","open"]].rename(columns={"date":"entry_date","open":"entry_open"})
    ex=daily[["symbol","date","close"]].rename(columns={"date":"exit_date","close":"exit_close"})
    x=x.merge(en,on=["symbol","entry_date"],how="left").merge(ex,on=["symbol","exit_date"],how="left")
    ok=(
        np.isfinite(x["entry_open"])&(x["entry_open"]>0)
        &np.isfinite(x["exit_close"])&(x["exit_close"]>0)
    )
    x["endpoint_status"]=np.where(ok,"RESOLVED","UNRESOLVED_ENDPOINT")
    x["ret5bd_gross"]=np.where(ok,x["exit_close"]/x["entry_open"]-1.0,np.nan)
    return x,idx


def cooldown(rows: pd.DataFrame, session_idx: dict[str,int]) -> pd.DataFrame:
    x=rows.sort_values(["date","bin_ord","symbol"],kind="stable")
    blocked={}
    keep=[]
    for i,row in x.iterrows():
        di=session_idx.get(row["date"])
        if di is None:
            continue
        sym=str(row["symbol"])
        if blocked.get(sym,-999999)>di:
            continue
        keep.append(i)
        blocked[sym]=di+5
    return x.loc[keep].copy()


def metrics(sel: pd.DataFrame, cost: float=.005) -> dict:
    if sel.empty:
        return {"requested":0,"resolved":0,"unresolved":0}
    r=sel[sel["endpoint_status"]=="RESOLVED"].copy()
    out={"requested":int(len(sel)),"resolved":int(len(r)),"unresolved":int(len(sel)-len(r))}
    if r.empty:
        return out
    v=r["ret5bd_gross"].to_numpy(float)
    net=v-cost
    desc=np.sort(net)[::-1]
    rr=r.assign(net=net,month=r["date"].str[:7])
    mm=rr.groupby("month")["net"].mean()
    out.update(
        net_mean=float(net.mean()),
        net_median=float(np.median(net)),
        net_win_rate=float((net>0).mean()),
        gross_ge10_rate=float((v>=0.10).mean()),
        gross_ge20_rate=float((v>=0.20).mean()),
        gross_le10_rate=float((v<=-0.10).mean()),
        top1_removed_net_mean=float(desc[1:].mean()) if len(desc)>1 else None,
        top3_removed_net_mean=float(desc[3:].mean()) if len(desc)>3 else None,
        monthly_positive_mean_fraction=float((mm>0).mean()),
    )
    return out


def passes_core(m: dict) -> bool:
    return (
        m.get("resolved",0)>=50
        and m.get("net_mean",-999.0)>0
        and m.get("net_median",-999.0)>=0
        and m.get("net_win_rate",-999.0)>0.50
        and m.get("top3_removed_net_mean",-999.0)>0
        and m.get("gross_le10_rate",999.0)<=0.20
    )


def main() -> None:
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
    bins=base.add_state_features(bins)
    daily=load_daily(daily_path)
    gated,session_idx=attach(bins,daily)
    h2=gated[(gated["date"]>="2025-07-01")&(gated["date"]<="2025-12-31")].copy()

    out={
        "audit_id":"TENTEI-V12-H2-TRIGGER-PATH-DECOMPOSITION-20260913-01",
        "period":"2025H2",
        "daily_sha256":actual,
        "2026_outcomes_opened":False,
        "production_modified":False,
        "paths":{},
    }

    for name,fn in PATHS.items():
        selected=cooldown(h2[fn(h2)].copy(),session_idx)
        m=metrics(selected,.005)
        m["passes_core_gate"]=passes_core(m)
        m["cost0"]=metrics(selected,0)
        m["cost1pct"]=metrics(selected,.01)
        out["paths"][name]=m

    rsi_pass=out["paths"]["RSI_RECOVERY"]["passes_core_gate"]
    emerg_pass=out["paths"]["EMERGENCY_REVERSAL"]["passes_core_gate"]
    if rsi_pass and emerg_pass:
        decision="MIXTURE_DRIFT_SUPPORTED"
    else:
        decision="WITHIN_PATH_DEGRADATION_SUPPORTED"
    out["diagnostic_decision"]=decision

    Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
