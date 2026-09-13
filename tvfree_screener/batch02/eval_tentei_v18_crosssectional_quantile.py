from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

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
TOP_NS = [1,2,3,5]
BINS = ["AM_09_13","PM_13_CLOSE"]
PARAMS = dict(
    learning_rate=0.05,max_iter=150,max_leaf_nodes=15,min_samples_leaf=100,
    l2_regularization=1.0,max_bins=63,early_stopping=False,random_state=0,
)


def load_daily(path: Path, min_date="2024-08-01", max_date="2025-07-10") -> pd.DataFrame:
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


def prepare(raw_glob: str, daily_path: str):
    daily_file=Path(daily_path)
    actual=base.sha256_file(daily_file)
    if actual != base.EXPECTED_DAILY_SHA:
        raise RuntimeError(f"daily SHA mismatch {actual}")

    bins=base.build_bins_fast(raw_glob,"2025-06-30")
    bins=base.add_state_and_features(bins)
    daily=load_daily(daily_file)

    sessions=sorted(daily["date"].dropna().unique().tolist())
    session_idx={d:i for i,d in enumerate(sessions)}
    prior={sessions[i]:sessions[i-1] for i in range(1,len(sessions))}
    entry={sessions[i]:sessions[i+1] for i in range(len(sessions)-5)}
    exit_map={sessions[i]:sessions[i+5] for i in range(len(sessions)-5)}

    x=bins.copy()
    x["date"]=x["date"].astype(str)
    x["prior_date"]=x["date"].map(prior)
    p=daily[["symbol","date","close","volume"]].rename(
        columns={"date":"prior_date","close":"prior_daily_close","volume":"prior_daily_volume"}
    )
    x=x.merge(p,on=["symbol","prior_date"],how="left")
    x=x[(x["prior_daily_close"]<=1000)&(x["prior_daily_volume"]>=10000)].copy()

    source=list(RANK_MAP.keys())
    x=x.loc[np.isfinite(x[source]).all(axis=1)].copy()
    for src,dst in RANK_MAP.items():
        x[dst]=x.groupby(["date","bin_name"],sort=False)[src].rank(
            method="average",pct=True,ascending=True
        )

    events=x[x["signal"]].copy()
    events=events.loc[np.isfinite(events[FEATURES]).all(axis=1)].copy()
    events["entry_date"]=events["date"].map(entry)
    events["exit_date"]=events["date"].map(exit_map)

    en=daily[["symbol","date","open"]].rename(columns={"date":"entry_date","open":"entry_open"})
    ex=daily[["symbol","date","close"]].rename(columns={"date":"exit_date","close":"exit_close"})
    events=events.merge(en,on=["symbol","entry_date"],how="left").merge(
        ex,on=["symbol","exit_date"],how="left"
    )
    ok=(
        np.isfinite(events["entry_open"])&(events["entry_open"]>0)
        &np.isfinite(events["exit_close"])&(events["exit_close"]>0)
    )
    events["endpoint_status"]=np.where(ok,"RESOLVED","UNRESOLVED_ENDPOINT")
    events["ret5bd_gross"]=np.where(ok,events["exit_close"]/events["entry_open"]-1.0,np.nan)
    return events,session_idx,actual


def fit_quantile(train: pd.DataFrame, valid: pd.DataFrame, q: float) -> np.ndarray:
    model=HistGradientBoostingRegressor(loss="quantile",quantile=q,**PARAMS)
    model.fit(train[FEATURES],train["ret5bd_gross"].to_numpy(float))
    return model.predict(valid[FEATURES])


def score(train: pd.DataFrame, valid: pd.DataFrame) -> pd.DataFrame:
    out=valid.copy()
    raw=np.column_stack([
        fit_quantile(train,valid,0.10),
        fit_quantile(train,valid,0.50),
        fit_quantile(train,valid,0.90),
    ])
    ordered=np.sort(raw,axis=1)
    out["q10"],out["q50"],out["q90"]=ordered[:,0],ordered[:,1],ordered[:,2]
    out["quantile_crossed_raw"]=(
        (raw[:,0]>raw[:,1]) | (raw[:,1]>raw[:,2])
    )
    return out


def pareto3(group: pd.DataFrame) -> pd.DataFrame:
    vals=group[["q90","q50","q10"]].to_numpy(float)
    keep=np.ones(len(group),dtype=bool)
    for i in range(len(group)):
        if not keep[i]:
            continue
        v=vals[i]
        dominates=(
            (vals[:,0]>=v[0])&(vals[:,1]>=v[1])&(vals[:,2]>=v[2])
            &((vals[:,0]>v[0])|(vals[:,1]>v[1])|(vals[:,2]>v[2]))
        )
        dominates[i]=False
        if dominates.any():
            keep[i]=False
    return group.iloc[np.flatnonzero(keep)].copy()


def select_core(scored: pd.DataFrame, session_idx: dict[str,int], n: int) -> pd.DataFrame:
    x=scored.sort_values(
        ["date","bin_name","q50","symbol"],
        ascending=[True,True,False,True],kind="stable"
    )
    return _cooldown_select(x,session_idx,n)


def select_monster(scored: pd.DataFrame, session_idx: dict[str,int], n: int) -> pd.DataFrame:
    fronts=[pareto3(g) for _,g in scored.groupby(["date","bin_name"],sort=False)]
    x=pd.concat(fronts,ignore_index=True) if fronts else scored.iloc[0:0].copy()
    x=x.sort_values(
        ["date","bin_name","q90","q50","q10","symbol"],
        ascending=[True,True,False,False,False,True],kind="stable"
    )
    return _cooldown_select(x,session_idx,n)


def _cooldown_select(ranked: pd.DataFrame, session_idx: dict[str,int], n: int) -> pd.DataFrame:
    groups={(d,b):g.to_dict("records") for (d,b),g in ranked.groupby(["date","bin_name"],sort=False)}
    blocked={}
    rows=[]
    for day in sorted(ranked["date"].unique()):
        di=session_idx[day]
        for bn in BINS:
            picked=0
            for row in groups.get((day,bn),()):
                sym=str(row["symbol"])
                if blocked.get(sym,-999999)>di:
                    continue
                rows.append(row)
                blocked[sym]=di+5
                picked+=1
                if picked>=n:
                    break
    return pd.DataFrame(rows)


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
    out.update(
        net_mean=float(net.mean()),
        net_median=float(np.median(net)),
        net_win_rate=float((net>0).mean()),
        gross_ge20_rate=float((v>=0.20).mean()),
        gross_le10_rate=float((v<=-0.10).mean()),
        top1_removed_net_mean=float(desc[1:].mean()) if len(desc)>1 else None,
        top3_removed_net_mean=float(desc[3:].mean()) if len(desc)>3 else None,
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


def passes_monster(m: dict) -> bool:
    return (
        m.get("resolved",0)>=30
        and m.get("net_mean",-999.0)>0
        and m.get("gross_ge20_rate",-1.0)>=0.10
        and m.get("top1_removed_net_mean",-999.0)>0
        and m.get("gross_le10_rate",999.0)<=0.40
    )


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--raw-glob",required=True)
    p.add_argument("--daily",required=True)
    p.add_argument("--period",choices=["h1","h2"],required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()

    events,session_idx,daily_sha=prepare(a.raw_glob,a.daily)
    train=events[
        (events["date"]<"2025-01-01")
        &(events["exit_date"]<"2025-01-01")
        &(events["endpoint_status"]=="RESOLVED")
    ].copy()
    if len(train)!=4924 or train["symbol"].nunique()!=966:
        raise RuntimeError(
            f"train receipt mismatch rows={len(train)} symbols={train['symbol'].nunique()}"
        )

    if a.period=="h1":
        start,end="2025-03-01","2025-06-30"
    else:
        start,end="2025-07-01","2025-12-31"
    valid=events[(events["date"]>=start)&(events["date"]<=end)].copy()
    if a.period=="h1" and len(valid)!=8227:
        raise RuntimeError(f"H1 receipt mismatch rows={len(valid)}")

    scored=score(train,valid)

    out={
        "experiment_id":"TENTEI-INSPIRED-4H-V18-CROSSSECTIONAL-QUANTILE-20260913",
        "period":a.period,
        "daily_sha256":daily_sha,
        "train_rows":int(len(train)),
        "train_symbols":int(train["symbol"].nunique()),
        "valid_rows":int(len(valid)),
        "quantile_crossing_raw_rate":float(scored["quantile_crossed_raw"].mean()),
        "2025_labels_used_for_fit":False,
        "2026_outcomes_opened":False,
        "production_modified":False,
        "results":{"core":{},"monster":{}},
    }

    for n in TOP_NS:
        c=select_core(scored,session_idx,n)
        cm=metrics(c,.005)
        cm["passes_core_gate"]=passes_core(cm)
        cm["cost0"]=metrics(c,0)
        cm["cost1pct"]=metrics(c,.01)
        out["results"]["core"][str(n)]=cm

        m=select_monster(scored,session_idx,n)
        mm=metrics(m,.005)
        mm["passes_monster_gate"]=passes_monster(mm)
        mm["cost0"]=metrics(m,0)
        mm["cost1pct"]=metrics(m,.01)
        out["results"]["monster"][str(n)]=mm

    Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
