#!/usr/bin/env python3
"""Causal cross-sectional extreme-winner ranking research (TEST ONLY).

Motivation:
The direct absolute +20%/+50% V5 classifier failed 2024. The historical +5.42%
Short architecture was explicitly a monthly relative-ranking model, so this
runner tests a materially different hypothesis: predict future cross-sectional
extreme winners rather than absolute return thresholds.

Blind protocol:
  2024 scored first -> top2 variants only may expose 2025 -> at most one lock ->
  2026 Mar-Aug is scored only after 2025 validation passes.

Entry: next-session open -> 5BD close.
No production writes. No 2026 tuning.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

import short_event_experiment as ev

OUT = Path("tvfree_screener/out")

FEATURES = [
    "ret1","ret3","ret5","ret10","ret20","ret40","prev_ret5",
    "volr5","volr10","volr20","rv10","rv40","range_pct","avg_range10",
    "close_loc","gap","pos20","pos60","break20","break60",
    "rv_ratio","range_expansion","ret5_pct","ret20_pct","volr20_pct","pos60_pct",
]

DEV_PERIODS = {
    "2024H1": ("2024-01-01","2024-06-30"),
    "2024H2": ("2024-07-01","2024-12-31"),
}
VAL_PERIODS = {
    "2025H1": ("2025-01-01","2025-06-30"),
    "2025H2": ("2025-07-01","2025-12-31"),
}

VARIANTS = {
    "rel1_q999":    {"w1":1.00,"w025":0.00,"wloss":1.00,"gate":0.9990},
    "rel025_q999":  {"w1":0.25,"w025":1.00,"wloss":0.75,"gate":0.9990},
    "relblend_q999":{"w1":0.75,"w025":1.00,"wloss":1.00,"gate":0.9990},
    "relblend_q9995":{"w1":0.75,"w025":1.00,"wloss":1.00,"gate":0.9995},
}


def clf(y: pd.Series) -> XGBClassifier:
    pos=max(int(y.sum()),1)
    neg=max(int(len(y)-pos),1)
    return XGBClassifier(
        n_estimators=120,
        max_depth=3,
        learning_rate=0.04,
        subsample=0.80,
        colsample_bytree=0.80,
        min_child_weight=20,
        reg_lambda=6,
        reg_alpha=0.3,
        objective="binary:logistic",
        eval_metric="logloss",
        scale_pos_weight=min(neg/pos,25.0),
        n_jobs=4,
        random_state=42,
    )


def empirical_cdf(ref: np.ndarray, values: np.ndarray) -> np.ndarray:
    r=np.asarray(ref,dtype=float)
    r=r[np.isfinite(r)]
    r.sort()
    if len(r)==0:
        raise RuntimeError("empty training CDF")
    return np.searchsorted(r,np.asarray(values,dtype=float),side="right")/len(r)


def attach_target_end(q: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    z=raw[["date","symbol"]].sort_values(["symbol","date"]).copy()
    z["target_end_date"]=z.groupby("symbol",sort=False)["date"].shift(-5)
    return q.merge(z,on=["date","symbol"],how="left",validate="many_to_one")


def prepare(q: pd.DataFrame) -> pd.DataFrame:
    z=q.copy()
    z["rv_ratio"]=z["rv10"]/z["rv40"].replace(0,np.nan)
    z["range_expansion"]=z["range_pct"]/z["avg_range10"].replace(0,np.nan)
    for c in ["ret5","ret20","volr20","pos60"]:
        z[f"{c}_pct"]=z.groupby("date")[c].rank(pct=True,method="average")

    z=z.dropna(subset=FEATURES+["target5_no","target_end_date"]).copy()
    z["future_rank"]=z.groupby("date")["target5_no"].rank(pct=True,method="average")
    z["y_top1"]=(z["future_rank"]>=0.99).astype(int)
    z["y_top025"]=(z["future_rank"]>=0.9975).astype(int)
    z["y_loss10"]=(z["target5_no"]<=-0.10).astype(int)
    return z


def fit_month(train: pd.DataFrame,pred: pd.DataFrame) -> pd.DataFrame:
    train=train.dropna(subset=FEATURES).copy()
    pred=pred.dropna(subset=FEATURES).copy()
    out=pred.copy()
    train_cdfs={}
    for target in ["y_top1","y_top025","y_loss10"]:
        y=train[target].astype(int)
        if y.nunique()<2:
            raise RuntimeError(f"degenerate {target}")
        m=clf(y)
        m.fit(train[FEATURES],y,verbose=False)
        tr=m.predict_proba(train[FEATURES])[:,1]
        pr=m.predict_proba(pred[FEATURES])[:,1]
        train_cdfs[target]=empirical_cdf(tr,tr)
        out[f"p_{target}"]=pr
        out[f"cdf_{target}"]=empirical_cdf(tr,pr)

    for name,spec in VARIANTS.items():
        tr_raw=(
            spec["w1"]*train_cdfs["y_top1"]
            +spec["w025"]*train_cdfs["y_top025"]
            -spec["wloss"]*train_cdfs["y_loss10"]
        )
        pr_raw=(
            spec["w1"]*out["cdf_y_top1"].to_numpy()
            +spec["w025"]*out["cdf_y_top025"].to_numpy()
            -spec["wloss"]*out["cdf_y_loss10"].to_numpy()
        )
        out[f"rel_raw__{name}"]=pr_raw
        out[f"rel_q__{name}"]=empirical_cdf(tr_raw,pr_raw)
    return out


def monthly_scores(q: pd.DataFrame,start: str,end: str) -> pd.DataFrame:
    parts=[]
    for p in pd.period_range(pd.Timestamp(start).to_period("M"),pd.Timestamp(end).to_period("M"),freq="M"):
        a=p.start_time
        b=p.end_time.normalize()
        train=q[q["target_end_date"]<a].copy()
        pred=q[(q["date"]>=a)&(q["date"]<=b)].copy()
        if len(train)<30000 or pred.empty:
            continue
        print(f"fit {p}: train={len(train)} pred={len(pred)}")
        s=fit_month(train,pred)
        s["model_period"]=str(p)
        parts.append(s)
    if not parts:
        raise RuntimeError("no monthly relative-tail scores")
    return pd.concat(parts,ignore_index=True)


def select_sparse(scored: pd.DataFrame,name: str,gate: float,trading_dates: pd.Index) -> pd.DataFrame:
    z=scored.copy()
    z["rel_raw"]=z[f"rel_raw__{name}"]
    z["rel_q"]=z[f"rel_q__{name}"]
    z=z[z["rel_q"]>=gate]
    if z.empty:
        return z
    date_idx={pd.Timestamp(d):i for i,d in enumerate(pd.Index(trading_dates).sort_values())}
    rows=[]
    last_symbol=None
    last_idx=None
    for date,day in z.sort_values(["date","rel_q","rel_raw"],ascending=[True,False,False]).groupby("date",sort=True):
        idx=date_idx[pd.Timestamp(date)]
        chosen=None
        for _,row in day.sort_values(["rel_q","rel_raw"],ascending=False).iterrows():
            if last_idx is not None and idx==last_idx+1 and str(row["symbol"])==last_symbol:
                continue
            chosen=row
            break
        if chosen is not None:
            rows.append(chosen)
            last_symbol=str(chosen["symbol"])
            last_idx=idx
    return pd.DataFrame(rows).reset_index(drop=True)


def summarize(s: pd.Series) -> dict:
    x=pd.to_numeric(s,errors="coerce").dropna()
    if x.empty:
        return {"n":0}
    return {
        "n":int(len(x)),
        "mean":float(x.mean()),
        "median":float(x.median()),
        "win_rate":float((x>0).mean()),
        "hit10_rate":float((x>=0.10).mean()),
        "hit20_rate":float((x>=0.20).mean()),
        "hit50_rate":float((x>=0.50).mean()),
        "hit100_rate":float((x>=1.00).mean()),
        "loss10_rate":float((x<=-0.10).mean()),
        "max":float(x.max()),
        "min":float(x.min()),
    }


def period_stats(picks: pd.DataFrame,periods: dict[str,tuple[str,str]]) -> dict:
    return {
        name:summarize(picks[(picks["date"]>=a)&(picks["date"]<=b)]["target5_no"])
        for name,(a,b) in periods.items()
    }


def dev_utility(ps: dict,pool: dict) -> float|None:
    h1,h2=ps["2024H1"],ps["2024H2"]
    if h1.get("n",0)<8 or h2.get("n",0)<8:
        return None
    if h1["mean"]<=0 or h2["mean"]<=0:
        return None
    if pool["mean"]<0.02:
        return None
    if max(h1["loss10_rate"],h2["loss10_rate"])>0.20:
        return None
    return float(
        min(h1["mean"],h2["mean"])
        +0.50*pool["mean"]
        +0.08*pool["hit20_rate"]
        +0.12*pool["hit50_rate"]
        -0.08*max(h1["loss10_rate"],h2["loss10_rate"])
    )


def val_pass(ps: dict,pool: dict) -> bool:
    h1,h2=ps["2025H1"],ps["2025H2"]
    return bool(
        h1.get("n",0)>=8 and h2.get("n",0)>=8
        and h1["mean"]>0 and h2["mean"]>0
        and pool["mean"]>=0.02
        and pool["hit20_rate"]>=0.05
        and max(h1["loss10_rate"],h2["loss10_rate"])<=0.20
    )


def variant_picks(scored: pd.DataFrame,name: str,trading_dates: pd.Index) -> pd.DataFrame:
    return select_sparse(scored,name,VARIANTS[name]["gate"],trading_dates)


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--cache",default=str(OUT/"tse_daily.csv"))
    ap.add_argument("--symbol-batch",type=int,default=200)
    args=ap.parse_args()

    raw=pd.read_csv(args.cache,parse_dates=["date"],dtype={"symbol":str})
    for c in ["open","high","low","close","volume"]:
        raw[c]=pd.to_numeric(raw[c],errors="coerce")
    raw=raw.dropna(subset=["date","symbol","open","high","low","close","volume"])
    raw=raw.sort_values(["symbol","date"]).reset_index(drop=True)
    trading_dates=pd.Index(pd.to_datetime(raw["date"].unique())).sort_values()

    q=ev.build_candidates(raw,args.symbol_batch)
    q=attach_target_end(q,raw)
    q=prepare(q)

    dev_scored=monthly_scores(q,"2024-01-01","2024-12-31")
    candidates={}
    for name in VARIANTS:
        picks=variant_picks(dev_scored,name,trading_dates)
        dev=period_stats(picks,DEV_PERIODS)
        pool=summarize(picks[(picks["date"]>="2024-01-01")&(picks["date"]<="2024-12-31")]["target5_no"])
        candidates[name]={
            "spec":VARIANTS[name],
            "development_2024":dev,
            "development_2024_pooled":pool,
            "development_utility":dev_utility(dev,pool),
        }

    ranked=sorted(
        [(c["development_utility"],name) for name,c in candidates.items() if c["development_utility"] is not None],
        reverse=True,
    )
    opened=[name for _,name in ranked[:2]]
    accepted=[]
    combined_pre2026=None
    if opened:
        val_scored=monthly_scores(q,"2025-01-01","2025-12-31")
        combined_pre2026=pd.concat([dev_scored,val_scored],ignore_index=True)
        for name in opened:
            picks=variant_picks(combined_pre2026,name,trading_dates)
            val=period_stats(picks,VAL_PERIODS)
            pool=summarize(picks[(picks["date"]>="2025-01-01")&(picks["date"]<="2025-12-31")]["target5_no"])
            candidates[name]["validation_2025"]=val
            candidates[name]["validation_2025_pooled"]=pool
            candidates[name]["validation_pass"]=val_pass(val,pool)
            if candidates[name]["validation_pass"]:
                accepted.append((min(val["2025H1"]["mean"],val["2025H2"]["mean"]),pool["mean"],name))

    locked=sorted(accepted,reverse=True)[0][2] if accepted else None
    fixed=None
    monthly=None
    if locked is not None:
        future_scored=monthly_scores(q,"2026-01-01","2026-08-31")
        all_scored=pd.concat([combined_pre2026,future_scored],ignore_index=True)
        picks=variant_picks(all_scored,locked,trading_dates)
        f=picks[(picks["date"]>="2026-03-01")&(picks["date"]<="2026-08-31")].copy()
        fixed=summarize(f["target5_no"])
        monthly={str(m):summarize(g["target5_no"]) for m,g in f.groupby(f["date"].dt.to_period("M"))}
        f.to_csv(OUT/"v6_relative_tail_locked_2026.csv",index=False)

    report={
        "status":"research_only_no_production_writes",
        "hypothesis":"monthly causal cross-sectional top1/top0.25 future-return ranking",
        "entry":"next_session_open_to_5BD_close",
        "protocol":"2024 only -> top2 -> 2025 only if qualified -> lock -> 2026 only after pass",
        "eligible_rows":int(len(q)),
        "label_counts_audit":{
            "top1":int(q["y_top1"].sum()),
            "top025":int(q["y_top025"].sum()),
            "loss10":int(q["y_loss10"].sum()),
        },
        "development_ranked":[{"name":n,"utility":float(u)} for u,n in ranked],
        "validation_opened":opened,
        "locked_candidate":locked,
        "candidates":{},
    }
    for name,c in candidates.items():
        item={
            "spec":c["spec"],
            "development_2024":c["development_2024"],
            "development_2024_pooled":c["development_2024_pooled"],
            "development_utility":c["development_utility"],
        }
        if name in opened:
            item["validation_2025"]=c["validation_2025"]
            item["validation_2025_pooled"]=c["validation_2025_pooled"]
            item["validation_pass"]=c["validation_pass"]
        if name==locked:
            item["fixed_2026_MarAug"]=fixed
            item["fixed_2026_monthly"]=monthly
        report["candidates"][name]=item

    OUT.mkdir(parents=True,exist_ok=True)
    with open(OUT/"v6_relative_tail_report.json","w",encoding="utf-8") as fh:
        json.dump(report,fh,ensure_ascii=False,indent=2)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
