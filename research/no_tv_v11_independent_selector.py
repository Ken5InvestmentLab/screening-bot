from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import average_precision_score, roc_auc_score

import no_tv_stage2_selector as s2
import no_tv_v10_standalone as base

RANK_BASE = [
    "session_ret", "session_range_pct", "session_body_pct", "session_close_loc",
    "session_vol_ratio20", "ret_1d", "ret_3d", "ret_5d", "ret_10d", "ret_20d",
    "gap_pct", "day_range_pct", "day_body_pct", "day_close_loc", "drawdown_high20",
    "recovery_low20", "rsi14", "atr14_pct", "bb_pct", "bb_width_pct",
    "ema25_gap_pct", "ema75_gap_pct", "macd_hist_pct", "stoch14",
    "day_vol_ratio5", "day_vol_ratio20", "stable_score",
]
REGIME_FEATURES = [
    "market_median_ret1d", "market_median_ret5d", "market_median_gap",
    "market_median_session_ret", "market_median_vol_ratio", "market_median_atr",
    "market_breadth_ema25", "market_breadth_macd", "market_breadth_stoch75",
    "market_breadth_bb80", "market_candidate_count",
]
WEIGHT_SETS = [
    (0.50, 0.30, 0.20),
    (0.40, 0.40, 0.20),
    (0.35, 0.25, 0.40),
    (0.30, 0.50, 0.20),
    (0.25, 0.30, 0.45),
]
TOPN = [1, 2, 3, 5, 8, 12]


def enrich_cross_sectional(data: pd.DataFrame) -> pd.DataFrame:
    d = data.copy()
    group = ["date", "session"]
    for c in RANK_BASE:
        d[f"rank_{c}"] = d.groupby(group)[c].rank(pct=True, method="average")
    g = d.groupby(group, sort=False)
    d["market_median_ret1d"] = g["ret_1d"].transform("median")
    d["market_median_ret5d"] = g["ret_5d"].transform("median")
    d["market_median_gap"] = g["gap_pct"].transform("median")
    d["market_median_session_ret"] = g["session_ret"].transform("median")
    d["market_median_vol_ratio"] = g["day_vol_ratio20"].transform("median")
    d["market_median_atr"] = g["atr14_pct"].transform("median")
    d["market_breadth_ema25"] = g["ema25_gap_pct"].transform(lambda x: float(np.mean(x > 0)))
    d["market_breadth_macd"] = g["macd_hist_pct"].transform(lambda x: float(np.mean(x > 0)))
    d["market_breadth_stoch75"] = g["stoch14"].transform(lambda x: float(np.mean(x >= 75)))
    d["market_breadth_bb80"] = g["bb_pct"].transform(lambda x: float(np.mean(x >= .80)))
    d["market_candidate_count"] = g["symbol"].transform("count").astype(float)
    return d


def features():
    return base.FEATURES + ["stable_score"] + [f"rank_{c}" for c in RANK_BASE] + REGIME_FEATURES


def balanced(y):
    return base.balanced_weights(np.asarray(y, int))


def fit_models(train, fcols):
    x = train[fcols].astype(float)
    r = train.perf_5bd.to_numpy(float)
    ywin = (r > 0).astype(int); yhit = (r >= .10).astype(int)
    win = HistGradientBoostingClassifier(learning_rate=.035, max_iter=220, max_leaf_nodes=15, min_samples_leaf=80, l2_regularization=3.0, random_state=111)
    hit = HistGradientBoostingClassifier(learning_rate=.035, max_iter=240, max_leaf_nodes=15, min_samples_leaf=60, l2_regularization=4.0, random_state=112)
    reg = HistGradientBoostingRegressor(learning_rate=.03, max_iter=220, max_leaf_nodes=15, min_samples_leaf=80, l2_regularization=4.0, random_state=113)
    win.fit(x, ywin, sample_weight=balanced(ywin)); hit.fit(x, yhit, sample_weight=balanced(yhit)); reg.fit(x, np.clip(r, -.20, .30))
    return win, hit, reg


def attach(df, models, fcols):
    win, hit, reg = models; o=df.copy(); x=o[fcols].astype(float)
    o["p_win"]=win.predict_proba(x)[:,1]; o["p_hit10"]=hit.predict_proba(x)[:,1]; o["pred_ret"]=reg.predict(x)
    o["ret_component"]=.5+.5*np.tanh(o.pred_ret.to_numpy(float)/.08)
    return o


def daily_top(df, score, n):
    return df.sort_values(["date",score],ascending=[True,False]).groupby("date",sort=False).head(n).copy()


def objective(st):
    if st["n"] < 20: return -999.
    # Robust + median are emphasized to avoid a V3-style outlier-only win.
    return .45*st["robust_avg"] + .25*st["avg"] + .15*st["median"] + .01*(st["wr"]-.5) + .015*st["target_rate"]


def choose_policy(valid):
    best=None; trials=[]
    for w in WEIGHT_SETS:
        score=w[0]*valid.p_win+w[1]*valid.p_hit10+w[2]*valid.ret_component
        v=valid.copy(); v["joint_score"]=score
        for n in TOPN:
            sel=daily_top(v,"joint_score",n); st=base.trade_stats(sel); obj=objective(st)
            rec={"weights":list(w),"topn":n,"objective":obj,"stats":st}; trials.append(rec)
            if best is None or obj>best["objective"]: best=rec
    return best,sorted(trials,key=lambda x:x["objective"],reverse=True)


def apply_policy(df,p):
    w=p["weights"]; o=df.copy(); o["joint_score"]=w[0]*o.p_win+w[1]*o.p_hit10+w[2]*o.ret_component
    return daily_top(o,"joint_score",int(p["topn"]))


def safe_auc(y,p):
    return float(roc_auc_score(y,p)) if len(np.unique(y))>1 else None


def safe_ap(y,p):
    return float(average_precision_score(y,p)) if np.sum(y)>0 else None


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--teacher",required=True); ap.add_argument("--watchlist-repo",required=True); ap.add_argument("--max-symbols",type=int); ap.add_argument("--max-workers",type=int,default=20); ap.add_argument("--output-dir",default="research_artifacts/v11_independent")
    a=ap.parse_args()
    _,wl_stats,data,_,_,_,yahoo=s2.build_dataset(a)
    data=enrich_cross_sectional(data)
    train=data[(data.date>=base.TRAIN_START)&(data.date<=base.TRAIN_END)&data.perf_5bd.notna()].copy()
    valid=data[(data.date>=base.VALID_START)&(data.date<=base.VALID_END)&data.perf_5bd.notna()].copy()
    test=data[(data.date>=base.TEST_START)&(data.date<=base.TEST_END)&data.perf_5bd.notna()].copy()
    fcols=features(); models=fit_models(train,fcols); v=attach(valid,models,fcols); t=attach(test,models,fcols); policy,trials=choose_policy(v); selected=apply_policy(t,policy)
    yw=(t.perf_5bd.to_numpy(float)>0).astype(int); yh=(t.perf_5bd.to_numpy(float)>=.10).astype(int)
    result={
      "scope":"fully independent Yahoo-only candidate scoring; no TV signal required at runtime",
      "watchlists":wl_stats,"yahoo":yahoo,"features":fcols,
      "split":{"train":{"n":len(train)},"valid":{"n":len(valid)},"test":{"n":len(test)}},
      "models":{"win_auc":safe_auc(yw,t.p_win),"win_pr_auc":safe_ap(yw,t.p_win),"hit10_auc":safe_auc(yh,t.p_hit10),"hit10_pr_auc":safe_ap(yh,t.p_hit10),"ret_corr":float(np.corrcoef(t.perf_5bd,t.pred_ret)[0,1])},
      "policy":policy,"validation_trials":trials[:15],"current_champion":base.CHAMPION,
      "trading_test":{"all_monitored_sessions":base.trade_stats(t),"v11_selected":base.trade_stats(selected),"test_actual_bottom":base.trade_stats(t[t.label==1]),"test_reconstructed_stable6":base.trade_stats(t[t.stable_score==6])},
      "selected":selected.sort_values(["date","joint_score"],ascending=[True,False])[["date","session","symbol","joint_score","p_win","p_hit10","pred_ret","stable_score","label","perf_5bd"]].to_dict("records")}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/"v11_result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    print(json.dumps({k:result[k] for k in ["split","models","policy","trading_test"]},ensure_ascii=False,indent=2))

if __name__=="__main__": main()
