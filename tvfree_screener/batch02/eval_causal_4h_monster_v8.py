from __future__ import annotations

import argparse, glob, json
from pathlib import Path
import numpy as np
import pandas as pd
from tvfree_screener.batch02 import eval_causal_4h_scoring_v3 as v3

TOP_NS=[1,2,3,5]
BINS=["AM_09_13","PM_13_CLOSE"]

def pareto_front(group: pd.DataFrame) -> pd.DataFrame:
    g=group.sort_values(["q90","q10","symbol"],ascending=[False,False,True],kind="stable").copy()
    q10=g["q10"].to_numpy(float); q90=g["q90"].to_numpy(float)
    keep=np.zeros(len(g),dtype=bool); max_q10=-np.inf; last_pair=None
    for i,(hi,lo) in enumerate(zip(q90,q10)):
        pair=(hi,lo)
        if lo>max_q10:
            keep[i]=True; max_q10=lo; last_pair=pair
        elif last_pair is not None and pair==last_pair:
            keep[i]=True
        last_pair=pair
    return g.loc[keep]

def select(scored: pd.DataFrame, session_idx: dict[str,int], n:int) -> pd.DataFrame:
    fronts=[]
    for (_, _),g in scored.groupby(["date","bin_name"],sort=False):
        fronts.append(pareto_front(g))
    x=pd.concat(fronts,ignore_index=True) if fronts else scored.iloc[0:0].copy()
    x=x.sort_values(["date","bin_name","q90","q10","symbol"],ascending=[True,True,False,False,True],kind="stable")
    groups={(d,b):g.to_dict("records") for (d,b),g in x.groupby(["date","bin_name"],sort=False)}
    blocked={}; rows=[]
    for day in sorted(scored["date"].astype(str).unique()):
        di=session_idx[day]
        for bn in BINS:
            picked=0
            for r in groups.get((day,bn),()):
                sym=str(r["symbol"])
                if blocked.get(sym,-999999)>di: continue
                rows.append(r); blocked[sym]=di+5; picked+=1
                if picked>=n: break
    return pd.DataFrame(rows)

def passes(m):
    return (m.get("resolved",0)>=30 and m.get("net_mean",-999.0)>0 and
            m.get("gross_ge20_rate",-1.0)>=0.10 and m.get("top1_removed_net_mean",-999.0)>0 and
            m.get("gross_le10_rate",999.0)<=0.40)

def main():
    p=argparse.ArgumentParser(); p.add_argument("--scored-glob",required=True); p.add_argument("--daily",required=True); p.add_argument("--period",required=True); p.add_argument("--output",required=True); a=p.parse_args()
    files=sorted(glob.glob(a.scored_glob))
    if not files: raise FileNotFoundError(a.scored_glob)
    scored=pd.concat([pd.read_csv(f,dtype={"symbol":"string"}) for f in files],ignore_index=True)
    scored["symbol"]=scored["symbol"].astype(str); scored["date"]=scored["date"].astype(str).str[:10]
    front_rows=sum(len(pareto_front(g)) for _,g in scored.groupby(["date","bin_name"],sort=False))
    daily=v3.load_daily(Path(a.daily)); sessions=sorted(daily["date"].dropna().unique().tolist()); idx={d:i for i,d in enumerate(sessions)}
    out={"experiment_id":"CAUSAL-4H-MONSTER-V8-PARETO-FRONT-20260913","period":a.period,"input_rows":int(len(scored)),"pareto_front_rows":int(front_rows),"pareto_front_rate":float(front_rows/len(scored)),"2026_outcomes_opened":False,"results":{}}
    for n in TOP_NS:
        sel=select(scored,idx,n); m=v3.metrics(sel,.005); m["passes_v8_gates"]=passes(m); m["cost0"]=v3.metrics(sel,0); m["cost1pct"]=v3.metrics(sel,.01); out["results"][str(n)]=m
    Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
