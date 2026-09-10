from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

BOOL_FEATURES=[
 "atr3","atr5","atr7","bb80","bb_lower","body1","body2","body_overheat15","body_pullback10",
 "cci_os","ema25","ema75","gap_up","hb20","ich_chikou","ich_cloud_above","ich_cloud_green",
 "ich_kumo_break","ich_price_kijun","ich_price_tenkan","ich_tk","lower_wick50","macdgc","macdpos",
 "pre_decline15","pre_down3","rci26_os","rci9_os","rci9_up","rsi4060","rsi5070","sbull",
 "smbull_seq2","smbull_seq3","stoch60","stoch75","vol12","vol15","vol20","vol30",
 "vp_near_poc","vp_no_overhead","vp_support"
]
NUM_FEATURES=["_vsurge","_atr","_body","_rsi","_stoch","_bbpct","_rci9","_rci26","_cci","_vp_support","_vp_overhead","_vp_poc_abs"]
CURRENT=["ema25","macdpos","stoch75","bb80","pre_down3","gap_up"]
FORBIDDEN={"win10","lose10","win_5bd","confirmed_5bd","perf_5bd","teacher_win5","teacher_hit10","teacher_lose10"}
FOLDS=[
 {"id":"F1","train_start":"2026-03-05","train_end":"2026-04-30","valid_start":"2026-05-01","valid_end":"2026-05-31","test_start":"2026-06-01","test_end":"2026-06-30"},
 {"id":"F2","train_start":"2026-03-05","train_end":"2026-05-31","valid_start":"2026-06-01","valid_end":"2026-06-30","test_start":"2026-07-01","test_end":"2026-07-31"},
 {"id":"F3","train_start":"2026-03-05","train_end":"2026-06-30","valid_start":"2026-07-01","valid_end":"2026-07-31","test_start":"2026-08-01","test_end":"2026-08-31"},
]
WEIGHTS=[(.4,.3,.2,.1),(.35,.35,.2,.1),(.3,.3,.25,.15),(.3,.25,.2,.25)] # win, hit, ret, safety
Q=[0,.5,.67,.8,.9]


def to_bool(s):
    if s.dtype==bool:return s.fillna(False)
    return s.astype(str).str.strip().str.lower().isin(["1","true","yes","y"])


def trade_stats(df):
    x=pd.to_numeric(df.perf_5bd,errors="coerce").dropna().to_numpy(float)
    if not len(x):return {"n":0,"avg":0.,"median":0.,"robust_avg":0.,"wr":0.,"hit10":0.,"min":0.,"p10":0.,"loss10":0.}
    d=x[x!=0];wr=float(np.mean(d>0)) if len(d) else 0.;lo,hi=(np.quantile(x,[.05,.95]) if len(x)>=10 else (x.min(),x.max()))
    return {"n":int(len(x)),"avg":float(x.mean()),"median":float(np.median(x)),"robust_avg":float(np.mean(np.clip(x,lo,hi))),"wr":wr,"hit10":float(np.mean(x>=.10)),"min":float(x.min()),"p10":float(np.quantile(x,.1)),"loss10":float(np.mean(x<=-.10))}


def balanced(y):
    y=np.asarray(y,int);n=len(y);p=max(1,int(y.sum()));q=max(1,n-p);return np.where(y==1,n/(2*p),n/(2*q))


def fit_models(train,features):
    x=train[features].astype(float);r=train.perf_5bd.to_numpy(float);yw=(r>0).astype(int);yh=(r>=.10).astype(int);yl=(r<=-.10).astype(int)
    def clf(seed):return HistGradientBoostingClassifier(learning_rate=.04,max_iter=220,max_leaf_nodes=11,min_samples_leaf=18,l2_regularization=4.0,random_state=seed)
    win,hit,loss=clf(241),clf(242),clf(243);reg=HistGradientBoostingRegressor(learning_rate=.035,max_iter=220,max_leaf_nodes=11,min_samples_leaf=18,l2_regularization=4.0,random_state=244)
    win.fit(x,yw,sample_weight=balanced(yw));hit.fit(x,yh,sample_weight=balanced(yh));loss.fit(x,yl,sample_weight=balanced(yl));reg.fit(x,np.clip(r,-.20,.30));return win,hit,loss,reg


def score(df,models,features):
    if df.empty:return df.copy()
    win,hit,loss,reg=models;x=df[features].astype(float);o=df.copy();o["p_win"]=win.predict_proba(x)[:,1];o["p_hit10"]=hit.predict_proba(x)[:,1];o["p_loss10"]=loss.predict_proba(x)[:,1];o["pred_ret"]=reg.predict(x)
    g=["date_norm","session"];o["r_win"]=o.groupby(g).p_win.rank(pct=True);o["r_hit"]=o.groupby(g).p_hit10.rank(pct=True);o["r_ret"]=o.groupby(g).pred_ret.rank(pct=True);o["r_safe"]=(-o.p_loss10).groupby([o.date_norm,o.session]).rank(pct=True);o["cons_min"]=o[["r_win","r_hit","r_ret","r_safe"]].min(axis=1);return o


def select(df,policy):
    if df.empty:return df
    o=df.copy();w=policy["weights"];o["utility"]=w[0]*o.r_win+w[1]*o.r_hit+w[2]*o.r_ret+w[3]*o.r_safe
    if policy["mode"]=="cons":o=o[o.cons_min>=policy["q"]].copy();col="cons_min"
    else:o=o[o.utility>=policy["q"]].copy();col="utility"
    if policy["sessions"]!="both":o=o[o.session.astype(int)==int(policy["sessions"])].copy()
    return o.sort_values(["date_norm","session",col],ascending=[True,True,False]).groupby(["date_norm","session"],sort=False).head(1)


def objective(st):
    if st["n"]<6:return -999.
    return .45*st["robust_avg"]+.25*st["avg"]+.15*st["median"]+.015*(st["wr"]-.5)+.02*st["hit10"]+.18*min(0.,st["p10"])+.04*min(0.,st["min"])-.03*st["loss10"]


def choose(valid):
    best=None;tr=[]
    for w in WEIGHTS:
        for mode in ("utility","cons"):
            for q in Q:
                for sess in ("both","9","13"):
                    p={"weights":list(w),"mode":mode,"q":q,"sessions":sess};st=trade_stats(select(valid,p));obj=objective(st);r={"policy":p,"stats":st,"objective":float(obj)};tr.append(r)
                    if best is None or (obj,st["n"])>(best["objective"],best["stats"]["n"]):best=r
    return best,sorted(tr,key=lambda x:(x["objective"],x["stats"]["n"]),reverse=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--teacher",required=True);ap.add_argument("--output-dir",default="research_artifacts/v24_snapshot_ml");a=ap.parse_args();d=pd.read_csv(a.teacher,low_memory=False)
    d["date_norm"]=pd.to_datetime(d.date,errors="coerce").dt.strftime("%Y-%m-%d");d["perf_5bd"]=pd.to_numeric(d.perf_5bd,errors="coerce")
    if "session" not in d.columns:
        rec=pd.to_datetime(d.received_at,errors="coerce");d["session"]=np.where(rec.dt.hour<14,9,13)
    d["session"]=pd.to_numeric(d.session,errors="coerce")
    bools=[c for c in BOOL_FEATURES if c in d.columns];nums=[c for c in NUM_FEATURES if c in d.columns];features=bools+nums+["session"]
    if set(features)&FORBIDDEN:raise RuntimeError("outcome leakage in features")
    if len(nums)<5 or len(bools)<20:raise RuntimeError(f"insufficient signal-time features bool={len(bools)} num={len(nums)}")
    for c in bools:d[c]=to_bool(d[c]).astype(int)
    for c in nums:d[c]=pd.to_numeric(d[c],errors="coerce")
    current_mask=d[[c for c in CURRENT]].apply(to_bool).all(axis=1)
    rows=[];parts=[];curparts=[]
    for f in FOLDS:
        train=d[d.date_norm.between(f["train_start"],f["train_end"])&d.perf_5bd.notna()].copy();valid=d[d.date_norm.between(f["valid_start"],f["valid_end"])&d.perf_5bd.notna()].copy();test=d[d.date_norm.between(f["test_start"],f["test_end"])&d.perf_5bd.notna()].copy();models=fit_models(train,features);va=score(valid,models,features);te=score(test,models,features);best,tr=choose(va);sel=select(te,best["policy"]);cm=current_mask.loc[test.index]
        tst=trade_stats(sel);cur=trade_stats(test[cm]);parts.append(sel.assign(fold=f["id"]));curparts.append(test[cm].assign(fold=f["id"]));rows.append({"fold":f["id"],"sizes":{"train":len(train),"valid":len(valid),"test":len(test)},"chosen":best,"test":tst,"current_stable6_test":cur,"validation_top":tr[:10]});print(f"{f['id']} test={tst} current={cur}",flush=True)
    result={"scope":"Scoring-only ML on actual Tenchi BOTTOM signal-time snapshots. Explicit feature whitelist; no outcome columns. Selection is session-causal and rolling.","features":features,"folds":rows,"combined_test":{"candidate":trade_stats(pd.concat(parts,ignore_index=True)),"current_stable6_same_window":trade_stats(pd.concat(curparts,ignore_index=True))}}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/"v24_snapshot_ml.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8");print(json.dumps(result["combined_test"],ensure_ascii=False,indent=2))

if __name__=="__main__":main()
