from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import no_tv_v11_independent_selector as v11
import no_tv_v18_rank_rolling as v18
import select_consensus_v47_price_policy as price_policy
import no_tv_v47_dev_price_policy as devmod

VALID_START="2025-07-01"
VALID_END="2025-12-30"
COST=0.005
POLICY=devmod.POLICY


def load_label_map(frozen: Path, restored: Path) -> pd.DataFrame:
    cols=["date","open","close","symbol"]
    a=pd.read_csv(frozen,usecols=cols,dtype={"symbol":str},low_memory=False)
    b=pd.read_csv(restored,usecols=cols,dtype={"symbol":str},low_memory=False)
    d=pd.concat([a,b],ignore_index=True,sort=False)
    d["symbol"]=d["symbol"].astype(str).str.replace(r"\.0$","",regex=True).str.strip()
    d["date"]=pd.to_datetime(d["date"],errors="coerce").dt.strftime("%Y-%m-%d")
    d["open"]=pd.to_numeric(d["open"],errors="coerce")
    d["close"]=pd.to_numeric(d["close"],errors="coerce")
    d=(d.dropna(subset=["date","symbol","open","close"])
       .sort_values(["symbol","date"])
       .drop_duplicates(["symbol","date"],keep="last"))
    g=d.groupby("symbol",sort=False)
    d["next_open"]=g["open"].shift(-1)
    d["d5_close"]=g["close"].shift(-5)
    d["exit_date_calc"]=g["date"].shift(-5)
    d["canonical_ret_5bd"]=d["d5_close"]/d["next_open"]-1
    return d[["symbol","date","canonical_ret_5bd","exit_date_calc"]]


def attach_h2_labels(blind: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    x=blind.copy()
    x["symbol"]=x["symbol"].astype(str).str.replace(r"\.0$","",regex=True).str.strip()
    x["date"]=x["date"].astype(str).str[:10]
    if pd.to_datetime(x["date"]).min() < pd.Timestamp(VALID_START):
        raise RuntimeError("non-H2 rows in validation-blind input")
    x=x.merge(labels,on=["symbol","date"],how="left",validate="many_to_one")
    if x["canonical_ret_5bd"].isna().any():
        n=int(x["canonical_ret_5bd"].isna().sum())
        raise RuntimeError(f"missing canonical H2 labels: {n}")
    calc=x["exit_date_calc"].astype(str).str[:10]
    stored=x["exit_date_5bd"].astype(str).str[:10]
    mismatch=(calc!=stored)
    if mismatch.any():
        raise RuntimeError(f"exit-date mismatch: {int(mismatch.sum())}")
    x=x.drop(columns=["exit_date_calc"])
    return x


def prequential_h2(history: pd.DataFrame) -> pd.DataFrame:
    d=history.copy()
    d["date"]=d["date"].astype(str).str[:10]
    d["exit_date_5bd"]=d["exit_date_5bd"].astype(str).str[:10]
    d["perf_5bd"]=pd.to_numeric(d["canonical_ret_5bd"],errors="coerce")
    dates=sorted(
        d.loc[d["date"].between(VALID_START,VALID_END),"date"].unique()
    )
    blocks=[dates[i:i+5] for i in range(0,len(dates),5) if dates[i:i+5]]
    parts=[]
    for dates5 in blocks:
        start=dates5[0]
        train=devmod.available_before(d,start)
        test=d[d["date"].isin(dates5)&d["perf_5bd"].notna()].copy()
        if train.empty or test.empty:
            continue
        if len(train)<1000:
            raise RuntimeError(f"too little training before {start}: {len(train)}")
        models=v11.fit_models(train,v11.features())
        scored=v11.attach(test,models,v11.features())
        sel=v18.apply_consensus(scored,POLICY).copy()
        if len(sel):
            sel["block_start"]=start
            parts.append(sel)
        print(
            f"H2 {start}..{dates5[-1]} train={len(train)} "
            f"test={len(test)} selected={len(sel)}",
            flush=True,
        )
    return pd.concat(parts,ignore_index=True) if parts else d.iloc[0:0].copy()


def strict5_with_carry(
    h2_selected: pd.DataFrame,
    dev_selected: pd.DataFrame,
    day_ix: dict[str,int],
) -> pd.DataFrame:
    last={}
    if not dev_selected.empty:
        z=dev_selected.sort_values(["date","session"])
        for row in z.itertuples(index=False):
            dt=str(row.date)[:10]
            if dt in day_ix:
                last[str(row.symbol)]=day_ix[dt]

    keep=[]
    x=h2_selected.sort_values(
        ["date","session","cons_min","symbol"],
        ascending=[True,True,False,True],
    )
    for idx,row in x.iterrows():
        dt=str(row["date"])[:10]
        sym=str(row["symbol"])
        di=day_ix[dt]
        prior=last.get(sym)
        if prior is not None and di-prior<5:
            continue
        keep.append(idx)
        last[sym]=di
    return x.loc[keep].copy()


def main()->None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--dev-json",required=True,type=Path)
    ap.add_argument("--arm",required=True,choices=["NOCAP","CAP1000_PIT"])
    ap.add_argument("--dev-features",required=True,type=Path)
    ap.add_argument("--validation-blind",required=True,type=Path)
    ap.add_argument("--dev-selected",required=True,type=Path)
    ap.add_argument("--frozen-daily",required=True,type=Path)
    ap.add_argument("--restored-daily",required=True,type=Path)
    ap.add_argument("--output-dir",required=True,type=Path)
    a=ap.parse_args()

    decision=json.loads(a.dev_json.read_text(encoding="utf-8"))
    winner=decision["decision"]["winner"]
    if a.arm!=winner:
        raise RuntimeError(
            f"validation input arm {a.arm} != development winner {winner}"
        )

    dev=pd.read_parquet(a.dev_features)
    blind=pd.read_parquet(a.validation_blind)
    if "canonical_ret_5bd" in blind.columns or "legacy_ret_5bd" in blind.columns:
        raise RuntimeError("validation-blind artifact already contains target returns")

    labels=load_label_map(a.frozen_daily,a.restored_daily)
    h2=attach_h2_labels(blind,labels)
    history=pd.concat([dev,h2],ignore_index=True,sort=False)

    raw_sel=prequential_h2(history)
    dev_sel=pd.read_csv(a.dev_selected,dtype={"symbol":str})
    day_ix=devmod.trading_day_index(a.frozen_daily)
    strict= strict5_with_carry(raw_sel,dev_sel,day_ix)

    st=devmod.stats(strict)
    validation_payload={"arm":winner,**st}
    gate=price_policy.validate_winner(winner,validation_payload)

    out=a.output_dir
    out.mkdir(parents=True,exist_ok=True)
    strict.to_csv(out/"v47_h2_selected_winner.csv",index=False)
    payload={
        "scope":"locked clean PIT V47B H2 winner-only validation",
        "winner":winner,
        "validation_period":[VALID_START,VALID_END],
        "target":"next official XTKS open -> D+5 close",
        "cost_round_trip":COST,
        "strict_same_symbol_cooldown_sessions":5,
        "cooldown_state_carried_from_development":True,
        "validation":gate,
        "losing_arm_h2_opened":False,
        "2026_opened":False,
        "production_writes":False,
    }
    (out/"v47_h2_winner_validation.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
