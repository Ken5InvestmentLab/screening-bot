from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.utils.class_weight import compute_sample_weight

from tvfree_screener.batch02 import eval_causal_4h_scoring_v3 as v3
from tvfree_screener.batch02 import eval_tentei_inspired_4h_v12 as v12

FEATURES = [
    "bar_log_return","range_pct","upper_wick_pct","lower_wick_pct","close_location",
    "prev4_log_return_mean","prev4_range_mean","bb_position","bb_width_pct","rsi12",
    "rsi_delta","atr_pct","dist_prior5_low_atr","prior5_rsi_min","prior5_band_min",
    "log_volume_rel20","trigger_rsi_recovery","trigger_trend_flip","trigger_emergency_reversal",
]
TOP_NS = [1,2,3,5]
BINS = ["AM_09_13","PM_13_CLOSE"]
PARAMS = dict(
    learning_rate=0.05,max_iter=150,max_leaf_nodes=15,min_samples_leaf=100,
    l2_regularization=1.0,max_bins=63,early_stopping=False,random_state=0,
)


def add_features(bins: pd.DataFrame) -> pd.DataFrame:
    x = bins.copy()
    base = x["open"].where(x["open"] > 0)
    x["bar_log_return"] = np.log(x["close"] / base)
    x["range_pct"] = (x["high"] - x["low"]) / base
    x["upper_wick_pct"] = (x["high"] - np.maximum(x["open"],x["close"])) / base
    x["lower_wick_pct"] = (np.minimum(x["open"],x["close"]) - x["low"]) / base
    span = x["high"] - x["low"]
    x["close_location"] = np.where(span > 0,(x["close"]-x["low"])/span,0.5)
    x["prev4_log_return_mean"] = x.groupby("symbol",sort=False)["bar_log_return"].transform(lambda s:s.shift(1).rolling(4,min_periods=4).mean())
    x["prev4_range_mean"] = x.groupby("symbol",sort=False)["range_pct"].transform(lambda s:s.shift(1).rolling(4,min_periods=4).mean())
    width = 4.0 * x["bb_std"]
    lower = x["bb_mid"] - 2.0 * x["bb_std"]
    x["bb_position"] = np.where(width > 0,(x["close"]-lower)/width,np.nan)
    x["bb_width_pct"] = np.where(x["bb_mid"] > 0,width/x["bb_mid"],np.nan)
    x["rsi_delta"] = x["rsi12"] - x["prev_rsi12"]
    x["atr_pct"] = np.where(x["close"] > 0,x["atr14"]/x["close"],np.nan)
    x["dist_prior5_low_atr"] = np.where(x["atr14"] > 0,(x["close"]-x["prior5_low"])/x["atr14"],np.nan)
    med = x.groupby(["symbol","bin_name"],sort=False)["volume"].transform(lambda s:s.shift(1).rolling(20,min_periods=20).median())
    x["log_volume_rel20"] = np.where(med > 0,np.log1p(x["volume"]/med),np.nan)
    x["trigger_rsi_recovery"] = x["rsi_recovery"].astype(float)
    x["trigger_trend_flip"] = x["trend_flip"].astype(float)
    x["trigger_emergency_reversal"] = x["emergency_reversal"].astype(float)
    return x


def prepare(raw_glob: str,daily_path: str):
    bins = add_features(v12.add_v12_state(v12.build_bins(raw_glob)))
    events = bins[bins["signal"]].copy()
    events, session_idx = v12.attach_gates_and_labels(events,daily_path)
    finite = np.isfinite(events[FEATURES]).all(axis=1)
    return events.loc[finite].copy(), session_idx


def fit_probability(train: pd.DataFrame, valid: pd.DataFrame, target: str) -> np.ndarray:
    y = train[target].to_numpy(int)
    if len(np.unique(y)) < 2:
        return np.full(len(valid),float(y[0]) if len(y) else 0.0)
    w = compute_sample_weight(class_weight="balanced",y=y)
    model = HistGradientBoostingClassifier(**PARAMS)
    model.fit(train[FEATURES],y,sample_weight=w)
    return model.predict_proba(valid[FEATURES])[:,1]


def pareto_front(group: pd.DataFrame) -> pd.DataFrame:
    g = group.sort_values(["p_tail20","p_loss10","symbol"],ascending=[False,True,True],kind="stable").copy()
    tail = g["p_tail20"].to_numpy(float)
    loss = g["p_loss10"].to_numpy(float)
    keep = np.zeros(len(g),dtype=bool)
    best_loss = np.inf
    last_pair = None
    for i,pair in enumerate(zip(tail,loss)):
        t,l = pair
        if l < best_loss:
            keep[i] = True
            best_loss = l
        elif last_pair is not None and pair == last_pair:
            keep[i] = True
        last_pair = pair
    return g.loc[keep]


def select(scored: pd.DataFrame,session_idx: dict[str,int],n: int) -> pd.DataFrame:
    fronts = [pareto_front(g) for _,g in scored.groupby(["date","bin_name"],sort=False)]
    x = pd.concat(fronts,ignore_index=True) if fronts else scored.iloc[0:0].copy()
    x = x.sort_values(["date","bin_name","p_tail20","p_loss10","symbol"],ascending=[True,True,False,True,True],kind="stable")
    groups = {(d,b):g.to_dict("records") for (d,b),g in x.groupby(["date","bin_name"],sort=False)}
    blocked = {}; rows = []
    for day in sorted(scored["date"].astype(str).unique()):
        di = session_idx[day]
        for bn in BINS:
            picked = 0
            for row in groups.get((day,bn),()):
                sym = str(row["symbol"])
                if blocked.get(sym,-999999) > di:
                    continue
                rows.append(row); blocked[sym] = di + 5; picked += 1
                if picked >= n: break
    return pd.DataFrame(rows)


def passes(m: dict[str,object]) -> bool:
    return (
        m.get("resolved",0) >= 30 and m.get("net_mean",-999.0) > 0
        and m.get("gross_ge20_rate",-1.0) >= 0.10
        and m.get("top1_removed_net_mean",-999.0) > 0
        and m.get("gross_le10_rate",999.0) <= 0.40
    )


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--raw-glob",required=True); p.add_argument("--daily",required=True)
    p.add_argument("--period",choices=["h1","h2"],required=True); p.add_argument("--output",required=True)
    a=p.parse_args()
    events,session_idx=prepare(a.raw_glob,a.daily)
    train=events[(events["date"] < "2025-01-01") & (events["exit_date"] < "2025-01-01") & (events["endpoint_status"]=="RESOLVED")].copy()
    train["target_tail20"]=(train["ret5bd_gross"]>=0.20).astype(int)
    train["target_loss10"]=(train["ret5bd_gross"]<=-0.10).astype(int)
    if a.period=="h1": start,end="2025-03-01","2025-06-30"
    else: start,end="2025-07-01","2025-12-31"
    valid=events[(events["date"]>=start)&(events["date"]<=end)].copy()
    valid["p_tail20"]=fit_probability(train,valid,"target_tail20")
    valid["p_loss10"]=fit_probability(train,valid,"target_loss10")
    out={
        "experiment_id":"TENTEI-INSPIRED-4H-V14-PRE2025-DUAL-CLASSIFIER-20260913",
        "period":a.period,
        "train_rows":int(len(train)),
        "train_symbols":int(train["symbol"].nunique()),
        "train_tail20_rate":float(train["target_tail20"].mean()),
        "train_loss10_rate":float(train["target_loss10"].mean()),
        "valid_rows":int(len(valid)),
        "2025_labels_used_for_fit":False,
        "2026_outcomes_opened":False,
        "production_modified":False,
        "results":{},
    }
    for n in TOP_NS:
        chosen=select(valid,session_idx,n)
        m=v3.metrics(chosen,0.005); m["passes_v14_gate"]=passes(m)
        m["cost0"]=v3.metrics(chosen,0.0); m["cost1pct"]=v3.metrics(chosen,0.01)
        out["results"][str(n)]=m
    Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
