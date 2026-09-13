from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tvfree_screener.batch02 import eval_tentei_inspired_4h_v14_fast_replay as base

BINS=["AM_09_13","PM_13_CLOSE"]


def load_daily(path: Path, min_date="2024-09-01", max_date="2025-01-15") -> pd.DataFrame:
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
    if actual!=base.EXPECTED_DAILY_SHA:
        raise RuntimeError(f"daily SHA mismatch {actual}")

    bins=base.build_bins_fast(raw_glob,"2024-12-30")
    bins=base.add_state_features(bins)
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

    required=["bb_width_pct","range_pct","bar_log_return","close_location","log_volume_rel20","high","close"]
    x=x.loc[np.isfinite(x[required]).all(axis=1)].copy()

    x["xrank_bb_width_pct"]=x.groupby(["date","bin_name"],sort=False)["bb_width_pct"].rank(
        method="average",pct=True,ascending=True
    )
    x["xrank_range_pct"]=x.groupby(["date","bin_name"],sort=False)["range_pct"].rank(
        method="average",pct=True,ascending=True
    )
    x["prior4_min_xrank_bb_width"]=x.groupby("symbol",sort=False)["xrank_bb_width_pct"].transform(
        lambda s:s.shift(1).rolling(4,min_periods=4).min()
    )
    x["prior4_high"]=x.groupby("symbol",sort=False)["high"].transform(
        lambda s:s.shift(1).rolling(4,min_periods=4).max()
    )

    x["signal"]=(
        (x["prior4_min_xrank_bb_width"]<=0.30)
        &(x["close"]>x["prior4_high"])
        &(x["bar_log_return"]>0)
        &(x["close_location"]>=0.75)
        &(x["xrank_range_pct"]>=0.80)
        &(x["log_volume_rel20"]>=np.log(2.0))
    )

    sig=x[x["signal"]].copy()
    sig["entry_date"]=sig["date"].map(entry)
    sig["exit_date"]=sig["date"].map(exit_map)
    en=daily[["symbol","date","open"]].rename(columns={"date":"entry_date","open":"entry_open"})
    ex=daily[["symbol","date","close"]].rename(columns={"date":"exit_date","close":"exit_close"})
    sig=sig.merge(en,on=["symbol","entry_date"],how="left").merge(
        ex,on=["symbol","exit_date"],how="left"
    )
    ok=(
        np.isfinite(sig["entry_open"])&(sig["entry_open"]>0)
        &np.isfinite(sig["exit_close"])&(sig["exit_close"]>0)
    )
    sig["endpoint_status"]=np.where(ok,"RESOLVED","UNRESOLVED_ENDPOINT")
    sig["ret5bd_gross"]=np.where(ok,sig["exit_close"]/sig["entry_open"]-1.0,np.nan)
    return sig,session_idx,actual


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
    active=r["date"].nunique()
    out.update(
        net_mean=float(net.mean()),
        net_median=float(np.median(net)),
        net_win_rate=float((net>0).mean()),
        gross_ge10_rate=float((v>=0.10).mean()),
        gross_ge20_rate=float((v>=0.20).mean()),
        gross_ge50_rate=float((v>=0.50).mean()),
        gross_le10_rate=float((v<=-0.10).mean()),
        top1_removed_net_mean=float(desc[1:].mean()) if len(desc)>1 else None,
        top3_removed_net_mean=float(desc[3:].mean()) if len(desc)>3 else None,
        monthly_positive_mean_fraction=float((mm>0).mean()),
        active_dates=int(active),
        signals_per_active_date=float(len(r)/active) if active else None,
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
    p.add_argument("--output",required=True)
    a=p.parse_args()

    signals,session_idx,daily_sha=prepare(a.raw_glob,a.daily)
    discovery=signals[
        (signals["date"]>="2024-10-01")
        &(signals["date"]<="2024-12-20")
        &(signals["exit_date"]<="2024-12-30")
    ].copy()
    selected=cooldown(discovery,session_idx)
    m=metrics(selected,.005)
    m["passes_core_gate"]=passes_core(m)
    m["passes_monster_gate"]=passes_monster(m)
    m["passes_density_gate"]=(
        m.get("resolved",0)>=30 and m.get("active_dates",0)>=15
    )
    m["cost0"]=metrics(selected,0)
    m["cost1pct"]=metrics(selected,.01)

    if not m["passes_density_gate"]:
        decision="REJECT_TOO_SPARSE"
    elif m["passes_core_gate"] and m["passes_monster_gate"]:
        decision="PASS_DISCOVERY_BOTH_ROLES"
    elif m["passes_core_gate"]:
        decision="PASS_DISCOVERY_CORE_ONLY"
    elif m["passes_monster_gate"]:
        decision="PASS_DISCOVERY_MONSTER_ONLY"
    else:
        decision="REJECT_DISCOVERY"

    out={
        "experiment_id":"EVENT-4H-V20-COMPRESSION-BREAKOUT-20260913",
        "period":"2024Q4_DISCOVERY",
        "daily_sha256":daily_sha,
        "raw_signal_rows_before_cooldown":int(len(discovery)),
        "selected_rows_after_cooldown":int(len(selected)),
        "decision":decision,
        "2025_outcomes_opened":False,
        "2026_outcomes_opened":False,
        "production_modified":False,
        "metrics":m,
    }
    Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
