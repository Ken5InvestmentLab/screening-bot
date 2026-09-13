#!/usr/bin/env python3
"""Causal correlation-peer lag audit for the fixed reconstructed Core.

Research-only. No production writes.

Goal:
Test a sector-lag-like hypothesis without relying on a current-only industry map
(which would introduce survivorship issues for delisted names). For each fixed
Core candidate, identify its top correlated peers using ONLY prior daily returns,
then attach peers' already-known prior-session momentum.

Peer construction:
- daily close-to-close returns reconstructed from genuine Yahoo 1H data
- trailing 60 official observed dates ending BEFORE candidate date
- minimum 40 overlapping return observations
- top 5 positively correlated peers by Pearson correlation; symbol tie-break
- require at least 3 peers

Fixed peer-lag hypotheses (no threshold sweep):
- PEER1_POS: median prior-session 1D return of peers > 0
- PEER5_POS: median prior-session 5D return of peers > 0
- PEER1_AND_5_POS: both > 0

Qualification:
A gate may freeze only if in BOTH DEV_A and DEV_B it has n>=15 and improves
mean and median 5BD return while not worsening <=-10% rate versus BASE.
If more than one qualifies, choose the largest worst-half mean advantage,
then fixed gate name.

2025H2/2026 have been inspected at aggregate level in prior research, so later
reporting is retrospective causal evidence, not pristine OOS.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from reconstruct_4h_from_1h import load, aggregate, enrich_session, add_daily_context, cooldown
from mtf_monster_model import metrics

TARGET = 0.075
LOOKBACK = 60
MIN_OVERLAP = 40
TOP_PEERS = 5
MIN_PEERS = 3

DEV_A = ("DEV_A", "2024-11-01", "2025-02-28")
DEV_B = ("DEV_B", "2025-03-01", "2025-06-30")
REPORT_PERIODS = [
    ("DEV", "2024-11-01", "2025-06-30"),
    ("2025H2", "2025-07-01", "2025-12-31"),
    ("2026_YTD", "2026-01-01", "2026-08-31"),
    ("2026_01_02", "2026-01-01", "2026-02-28"),
    ("2026_03_04", "2026-03-01", "2026-04-30"),
    ("2026_05_06", "2026-05-01", "2026-06-30"),
    ("2026_07_08", "2026-07-01", "2026-08-31"),
]

GATES = ["PEER1_POS", "PEER5_POS", "PEER1_AND_5_POS"]


def make_core_pool(raw: pd.DataFrame) -> pd.DataFrame:
    s = aggregate(raw, 780)
    s = enrich_session(s)
    s, dates = add_daily_context(s, raw)
    eligible = s[
        (s["prev_daily_close"] <= 1000)
        & (s["prev_daily_volume"] >= 10000)
        & (s["volume"] >= 5000)
    ].copy()
    gate = (
        (eligible["rsi12"] < 45)
        & eligible["pre_down3"].fillna(False)
        & (eligible["close"] > eligible["bb_mid"])
        & (eligible["atr14_pct"] < 0.05)
    )
    q = cooldown(eligible[gate].copy(), dates, 5)
    q = q[q["ret5bd"].notna()].copy()
    q["date_dt"] = pd.to_datetime(q["date"], errors="coerce")
    return q


def make_daily_panels(raw: pd.DataFrame):
    daily = (
        raw.sort_values("timestamp")
        .groupby(["symbol", "date"], as_index=False)
        .agg(close=("close", "last"))
    )
    px = daily.pivot(index="date", columns="symbol", values="close").sort_index()
    ret1 = px.pct_change(fill_method=None)
    ret5 = px.pct_change(5, fill_method=None)
    dates = px.index.astype(str).tolist()
    pos = {d:i for i,d in enumerate(dates)}
    return px, ret1, ret5, dates, pos


def peer_features_for_row(symbol: str, date: str, ret1: pd.DataFrame, ret5: pd.DataFrame, pos: dict) -> dict:
    i = pos.get(str(date))
    if i is None or i < MIN_OVERLAP + 1 or symbol not in ret1.columns:
        return {
            "peer_count": 0,
            "peer_corr_median": np.nan,
            "peer_ret1_prev_median": np.nan,
            "peer_ret5_prev_median": np.nan,
            "peer_symbols": "",
        }

    start = max(0, i - LOOKBACK)
    hist = ret1.iloc[start:i]
    target = hist[symbol]
    overlap = hist.notna().mul(target.notna(), axis=0).sum()
    corr = hist.corrwith(target)
    corr = corr.drop(labels=[symbol], errors="ignore")
    corr = corr[(overlap.drop(labels=[symbol], errors="ignore") >= MIN_OVERLAP) & corr.notna() & (corr > 0)]
    if corr.empty:
        return {
            "peer_count": 0,
            "peer_corr_median": np.nan,
            "peer_ret1_prev_median": np.nan,
            "peer_ret5_prev_median": np.nan,
            "peer_symbols": "",
        }

    ranked = sorted(corr.items(), key=lambda kv: (-float(kv[1]), str(kv[0])))[:TOP_PEERS]
    peers = [str(s) for s,_ in ranked]
    vals1 = ret1.iloc[i-1][peers].dropna().astype(float)
    vals5 = ret5.iloc[i-1][peers].dropna().astype(float)
    return {
        "peer_count": len(peers),
        "peer_corr_median": float(np.median([v for _,v in ranked])) if ranked else np.nan,
        "peer_ret1_prev_median": float(vals1.median()) if len(vals1) >= MIN_PEERS else np.nan,
        "peer_ret5_prev_median": float(vals5.median()) if len(vals5) >= MIN_PEERS else np.nan,
        "peer_symbols": ",".join(peers),
    }


def attach_peer_features(core: pd.DataFrame, ret1: pd.DataFrame, ret5: pd.DataFrame, pos: dict) -> pd.DataFrame:
    rows=[]
    for _,r in core.iterrows():
        pf=peer_features_for_row(str(r["symbol"]), str(r["date"]), ret1, ret5, pos)
        rows.append(pf)
    return pd.concat([core.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


def masks(x: pd.DataFrame) -> dict[str,pd.Series]:
    p1 = x["peer_ret1_prev_median"].notna() & (x["peer_ret1_prev_median"] > 0)
    p5 = x["peer_ret5_prev_median"].notna() & (x["peer_ret5_prev_median"] > 0)
    return {
        "BASE": pd.Series(True, index=x.index),
        "PEER1_POS": p1,
        "PEER5_POS": p5,
        "PEER1_AND_5_POS": p1 & p5,
    }


def simple(q: pd.DataFrame) -> dict:
    r=q["ret5bd"].dropna().astype(float)
    if r.empty:
        return {"n":0,"mean":None,"median":None,"le10":None}
    return {
        "n":int(len(r)),
        "mean":float(r.mean()),
        "median":float(r.median()),
        "le10":float((r<=-0.10).mean()),
    }


def p_mask(x,start,end):
    return (x["date_dt"]>=pd.Timestamp(start)) & (x["date_dt"]<=pd.Timestamp(end))


def discovery_table(x: pd.DataFrame):
    ms=masks(x)
    rows=[]
    for pname,start,end in [DEV_A,DEV_B]:
        pm=p_mask(x,start,end)
        for name,m in ms.items():
            q=x[pm & m.fillna(False)].copy()
            rows.append({"period":pname,"gate":name,**simple(q)})
    return pd.DataFrame(rows)


def qualify(discovery: pd.DataFrame):
    candidates=[]
    for gate in GATES:
        detail={}
        good=True
        adv=[]
        for period in [DEV_A[0],DEV_B[0]]:
            b=discovery[(discovery["period"]==period)&(discovery["gate"]=="BASE")].iloc[0]
            g=discovery[(discovery["period"]==period)&(discovery["gate"]==gate)].iloc[0]
            checks={
                "n": int(g["n"])>=15,
                "mean": pd.notna(g["mean"]) and pd.notna(b["mean"]) and float(g["mean"])>float(b["mean"]),
                "median": pd.notna(g["median"]) and pd.notna(b["median"]) and float(g["median"])>=float(b["median"]),
                "le10": pd.notna(g["le10"]) and pd.notna(b["le10"]) and float(g["le10"])<=float(b["le10"]),
            }
            detail[period]={"checks":checks,"mean_advantage":float(g["mean"]-b["mean"]) if pd.notna(g["mean"]) else None}
            if not all(checks.values()):
                good=False
            if pd.notna(g["mean"]) and pd.notna(b["mean"]):
                adv.append(float(g["mean"]-b["mean"]))
        candidates.append({
            "gate":gate,
            "qualifies":bool(good),
            "worst_half_mean_advantage":min(adv) if len(adv)==2 else None,
            "detail":detail,
        })
    eligible=[z for z in candidates if z["qualifies"]]
    eligible=sorted(eligible,key=lambda z:(-z["worst_half_mean_advantage"],z["gate"]))
    freeze=eligible[0]["gate"] if eligible else None
    return candidates,freeze


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--inputs",action="append",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()

    out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)
    raw=load(a.inputs)
    core=make_core_pool(raw)
    _,ret1,ret5,_,pos=make_daily_panels(raw)
    x=attach_peer_features(core,ret1,ret5,pos)

    discovery=discovery_table(x)
    candidates,freeze=qualify(discovery)
    discovery.to_csv(out/"core_peer_lag_discovery.csv",index=False)
    (out/"core_peer_lag_candidates.json").write_text(json.dumps(candidates,ensure_ascii=False,indent=2),encoding="utf-8")

    ms=masks(x)
    rows=[]
    for pname,start,end in REPORT_PERIODS:
        pm=p_mask(x,start,end)
        for name in ["BASE"] + ([freeze] if freeze else []):
            q=x[pm & ms[name].fillna(False)].copy()
            m=metrics("CORE_PEER_LAG",name,pname,q,TARGET)
            rows.append(m)
    report=pd.DataFrame(rows)
    report.to_csv(out/"core_peer_lag_report.csv",index=False)

    keep=[
        "date","session","session_time","symbol","close","ret5bd",
        "peer_count","peer_corr_median","peer_ret1_prev_median","peer_ret5_prev_median","peer_symbols",
    ]
    x[[k for k in keep if k in x.columns]].to_csv(out/"core_peer_lag_context.csv",index=False)

    meta={
        "raw_start":str(raw["date"].min()),
        "raw_end":str(raw["date"].max()),
        "core_pool_n":int(len(x)),
        "lookback_sessions":LOOKBACK,
        "min_overlap":MIN_OVERLAP,
        "top_peers":TOP_PEERS,
        "min_peers_for_median":MIN_PEERS,
        "peer_selection_timing":"trailing daily returns strictly before candidate date",
        "fixed_gates":GATES,
        "qualification":"both DEV halves: n>=15, mean>BASE, median>=BASE, le10<=BASE",
        "freeze":freeze,
        "reporting_status":"RETROSPECTIVE_CAUSAL_EVIDENCE; later aggregate outcomes already inspected",
        "industry_map_used":False,
        "reason_for_no_industry_map":"avoid current-only sector membership survivorship for delisted historical symbols",
        "production_writes":False,
    }
    (out/"core_peer_lag_meta.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")

    print(json.dumps(meta,ensure_ascii=False,indent=2))
    print("\nDISCOVERY")
    print(discovery.to_string(index=False))
    print("\nCANDIDATES")
    print(json.dumps(candidates,ensure_ascii=False,indent=2))
    print("\nREPORT")
    print(report.to_string(index=False))


if __name__=="__main__":
    main()
