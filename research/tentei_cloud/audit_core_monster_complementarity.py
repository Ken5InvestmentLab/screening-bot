#!/usr/bin/env python3
"""Complementarity audit for fixed reconstructed Core and fixed walk-forward Monster tiers.

Research-only. No production writes and no signal-rule changes.

Purpose:
Determine whether Core and Monster Watch/Prime are genuinely distinct lanes or
mostly duplicate the same candidates.

Fixed ingredients:
- Core = existing reconstructed SAFE/Core rule.
- Monster Watch/Prime = existing fixed expanding walk-forward 4H ensemble
  (q65 Watch, q90 Prime), fit exactly as walkforward_4h_ensemble.py.

Descriptive outputs:
- exact overlap (symbol + date + session);
- same-symbol same-date overlap ignoring session;
- unique-to-lane and overlap return metrics;
- exact-deduplicated union metrics;
- daily lane-count and daily-mean-return correlations.

No weighting or allocation rule is optimized. Union metrics are descriptive only
and are not a portfolio backtest.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from reconstruct_4h_from_1h import load, aggregate, enrich_session, add_daily_context, cooldown
from mtf_monster_model import make_candidate_pool, metrics
from walkforward_4h_ensemble import (
    FOLDS, TARGET, MIN_TRAIN, MIN_POS, fit_ensemble, score_ensemble
)

KEY_EXACT=["symbol","date","session"]
KEY_DAY=["symbol","date"]


def make_core_pool(raw: pd.DataFrame) -> pd.DataFrame:
    s=aggregate(raw,780)
    s=enrich_session(s)
    s,dates=add_daily_context(s,raw)
    eligible=s[
        (s["prev_daily_close"]<=1000)
        & (s["prev_daily_volume"]>=10000)
        & (s["volume"]>=5000)
    ].copy()
    gate=(
        (eligible["rsi12"]<45)
        & eligible["pre_down3"].fillna(False)
        & (eligible["close"]>eligible["bb_mid"])
        & (eligible["atr14_pct"]<0.05)
    )
    q=cooldown(eligible[gate].copy(),dates,5)
    q=q[q["ret5bd"].notna()].copy()
    q["date_dt"]=pd.to_datetime(q["date"],errors="coerce")
    return q


def keyed_set(x: pd.DataFrame, cols: list[str]) -> set[tuple]:
    if x.empty:
        return set()
    return set(map(tuple,x[cols].astype(str).itertuples(index=False,name=None)))


def simple_metrics(name: str, period: str, x: pd.DataFrame) -> dict:
    m=metrics("CORE_MONSTER_COMPLEMENT",name,period,x,TARGET)
    return m


def union_exact(a: pd.DataFrame,b: pd.DataFrame) -> pd.DataFrame:
    if a.empty:
        return b.copy()
    if b.empty:
        return a.copy()
    z=pd.concat([a,b],ignore_index=True,sort=False)
    # Same exact signal has the same return label by construction. Keep one.
    return z.drop_duplicates(KEY_EXACT,keep="first").copy()


def subset_by_keys(x: pd.DataFrame, keys: set[tuple], cols: list[str]) -> pd.DataFrame:
    if not keys or x.empty:
        return x.iloc[0:0].copy()
    k=x[cols].astype(str).apply(tuple,axis=1)
    return x[k.isin(keys)].copy()


def daily_stats(a: pd.DataFrame,b: pd.DataFrame,period: str,lane_a: str,lane_b: str) -> dict:
    da=(a.groupby("date")
        .agg(a_count=("symbol","size"),a_mean=("ret5bd","mean"))
        .reset_index()) if not a.empty else pd.DataFrame(columns=["date","a_count","a_mean"])
    db=(b.groupby("date")
        .agg(b_count=("symbol","size"),b_mean=("ret5bd","mean"))
        .reset_index()) if not b.empty else pd.DataFrame(columns=["date","b_count","b_mean"])

    all_dates=sorted(set(da["date"]).union(set(db["date"])))
    z=pd.DataFrame({"date":all_dates}).merge(da,on="date",how="left").merge(db,on="date",how="left")
    z["a_count"]=z["a_count"].fillna(0)
    z["b_count"]=z["b_count"].fillna(0)

    both=z[z["a_mean"].notna()&z["b_mean"].notna()]
    count_corr=float(z["a_count"].corr(z["b_count"])) if len(z)>=2 else np.nan
    mean_corr=float(both["a_mean"].corr(both["b_mean"])) if len(both)>=3 else np.nan

    return {
        "period":period,
        "lane_a":lane_a,
        "lane_b":lane_b,
        "calendar_union_days":int(len(z)),
        "both_active_days":int(len(both)),
        "count_corr_all_union_days":count_corr,
        "daily_mean_ret_corr_both_active":mean_corr,
        "a_active_days":int((z["a_count"]>0).sum()),
        "b_active_days":int((z["b_count"]>0).sum()),
        "a_mean_signals_per_active_day":float(z.loc[z["a_count"]>0,"a_count"].mean()) if (z["a_count"]>0).any() else None,
        "b_mean_signals_per_active_day":float(z.loc[z["b_count"]>0,"b_count"].mean()) if (z["b_count"]>0).any() else None,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--inputs",action="append",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()

    out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)
    raw=load(a.inputs)
    core=make_core_pool(raw)

    cand=make_candidate_pool(raw)
    cand=cand[cand["ret5bd"].notna()].copy()
    cand["target_date_dt"]=pd.to_datetime(cand["target_date"],errors="coerce")
    cand["date_dt"]=pd.to_datetime(cand["date"],errors="coerce")

    overlap_rows=[]
    metric_rows=[]
    daily_rows=[]
    selected_exports=[]
    fold_meta=[]

    for fold,test_start,test_end in FOLDS:
        ts=pd.Timestamp(test_start)
        te=pd.Timestamp(test_end)
        train=cand[
            (cand["date_dt"]>=pd.Timestamp("2024-11-01"))
            & (cand["target_date_dt"]<ts)
        ].copy()
        test=cand[(cand["date_dt"]>=ts)&(cand["date_dt"]<=te)].copy()
        ctest=core[(core["date_dt"]>=ts)&(core["date_dt"]<=te)].copy()

        pos=int((train["ret5bd"]>=TARGET).sum())
        neg=int(len(train)-pos)
        fm={
            "fold":fold,"train_n":int(len(train)),"train_pos":pos,
            "train_neg":neg,"monster_test_n":int(len(test)),"core_n":int(len(ctest))
        }
        if len(train)<MIN_TRAIN or pos<MIN_POS or neg<MIN_POS or test.empty:
            fm["status"]="SKIP"
            fold_meta.append(fm)
            continue

        models,watch_thr,prime_thr=fit_ensemble(train)
        test=test.copy()
        test["ensemble_score"],test["score_std"]=score_ensemble(models,test)
        watch=test[test["ensemble_score"]>=watch_thr].copy()
        prime=test[test["ensemble_score"]>=prime_thr].copy()

        fm.update({
            "status":"OK","watch_n":int(len(watch)),"prime_n":int(len(prime)),
            "watch_threshold":float(watch_thr),"prime_threshold":float(prime_thr)
        })
        fold_meta.append(fm)

        for tier_name,lane in [("Watch",watch),("Prime",prime)]:
            c_exact=keyed_set(ctest,KEY_EXACT)
            l_exact=keyed_set(lane,KEY_EXACT)
            c_day=keyed_set(ctest,KEY_DAY)
            l_day=keyed_set(lane,KEY_DAY)

            exact_i=c_exact & l_exact
            exact_u=c_exact | l_exact
            day_i=c_day & l_day
            day_u=c_day | l_day

            overlap_rows.append({
                "period":fold,
                "monster_tier":tier_name,
                "core_n":int(len(ctest)),
                "monster_n":int(len(lane)),
                "exact_overlap_n":int(len(exact_i)),
                "exact_overlap_pct_core":float(len(exact_i)/len(c_exact)) if c_exact else None,
                "exact_overlap_pct_monster":float(len(exact_i)/len(l_exact)) if l_exact else None,
                "exact_jaccard":float(len(exact_i)/len(exact_u)) if exact_u else None,
                "symbol_date_overlap_n":int(len(day_i)),
                "symbol_date_jaccard":float(len(day_i)/len(day_u)) if day_u else None,
            })

            core_overlap=subset_by_keys(ctest,exact_i,KEY_EXACT)
            core_only=ctest[~ctest[KEY_EXACT].astype(str).apply(tuple,axis=1).isin(l_exact)].copy()
            monster_only=lane[~lane[KEY_EXACT].astype(str).apply(tuple,axis=1).isin(c_exact)].copy()
            union=union_exact(ctest,lane)

            for label,frame in [
                ("Core",ctest),
                (tier_name,lane),
                (f"Core_only_vs_{tier_name}",core_only),
                (f"{tier_name}_only_vs_Core",monster_only),
                (f"Exact_overlap_Core_{tier_name}",core_overlap),
                (f"Union_Core_{tier_name}",union),
            ]:
                metric_rows.append(simple_metrics(label,fold,frame))

            daily_rows.append(daily_stats(ctest,lane,fold,"Core",tier_name))

            ex=lane.copy()
            ex["fold"]=fold
            ex["monster_tier"]=tier_name
            ex["in_core_exact"]=ex[KEY_EXACT].astype(str).apply(tuple,axis=1).isin(c_exact)
            ex["in_core_symbol_date"]=ex[KEY_DAY].astype(str).apply(tuple,axis=1).isin(c_day)
            selected_exports.append(ex)

    pd.DataFrame(fold_meta).to_csv(out/"core_monster_fold_meta.csv",index=False)
    pd.DataFrame(overlap_rows).to_csv(out/"core_monster_overlap.csv",index=False)
    pd.DataFrame(metric_rows).to_csv(out/"core_monster_metrics.csv",index=False)
    pd.DataFrame(daily_rows).to_csv(out/"core_monster_daily_correlation.csv",index=False)

    if selected_exports:
        z=pd.concat(selected_exports,ignore_index=True,sort=False)
        keep=[
            "fold","monster_tier","date","session","symbol","close","ret5bd",
            "ensemble_score","score_std","in_core_exact","in_core_symbol_date"
        ]
        z[[k for k in keep if k in z.columns]].to_csv(out/"core_monster_monster_rows.csv",index=False)

    meta={
        "raw_start":str(raw["date"].min()),
        "raw_end":str(raw["date"].max()),
        "core_rule":"fixed reconstructed Core/SAFE",
        "monster_rule":"fixed expanding walk-forward 4H ensemble Watch q65 / Prime q90",
        "overlap_keys":{"exact":KEY_EXACT,"same_symbol_date":KEY_DAY},
        "union":"exact-signal deduplicated descriptive union; not a capital-weighted portfolio",
        "optimization":False,
        "production_writes":False,
        "status":"RETROSPECTIVE_ARCHITECTURE_COMPLEMENTARITY_AUDIT",
    }
    (out/"core_monster_meta.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")

    print(json.dumps(meta,ensure_ascii=False,indent=2))
    print("\nOVERLAP")
    print(pd.DataFrame(overlap_rows).to_string(index=False))
    print("\nMETRICS")
    print(pd.DataFrame(metric_rows).to_string(index=False))
    print("\nDAILY CORRELATION")
    print(pd.DataFrame(daily_rows).to_string(index=False))


if __name__=="__main__":
    main()
