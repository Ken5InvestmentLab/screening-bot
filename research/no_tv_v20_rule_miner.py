from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

CURRENT=["ema25","macdpos","stoch75","bb80","pre_down3","gap_up"]
# Explicit allow-list only. Never auto-admit columns from the teacher export: that file also
# contains outcome-derived fields such as win10 / lose10 / win_5bd / confirmed_5bd.
ALLOWED_BOOL=[
 "atr3","atr5","atr7","bb80","bb_lower","body1","body2","body_overheat15","body_pullback10",
 "cci_os","ema25","ema75","gap_up","hb20","ich_chikou","ich_cloud_above","ich_cloud_green",
 "ich_kumo_break","ich_price_kijun","ich_price_tenkan","ich_tk","lower_wick50","macdgc","macdpos",
 "pre_decline15","pre_down3","rci26_os","rci9_os","rci9_up","rsi4060","rsi5070","sbull",
 "smbull_seq2","smbull_seq3","stoch60","stoch75","vol12","vol15","vol20","vol30",
 "vp_near_poc","vp_no_overhead","vp_support"
]
FORBIDDEN={"win10","lose10","win_5bd","confirmed_5bd","teacher_win5","teacher_hit10","teacher_lose10"}
FOLDS=[
 {"id":"F1","train_start":"2026-03-05","train_end":"2026-04-30","valid_start":"2026-05-01","valid_end":"2026-05-31","test_start":"2026-06-01","test_end":"2026-06-30"},
 {"id":"F2","train_start":"2026-03-05","train_end":"2026-05-31","valid_start":"2026-06-01","valid_end":"2026-06-30","test_start":"2026-07-01","test_end":"2026-07-31"},
 {"id":"F3","train_start":"2026-03-05","train_end":"2026-06-30","valid_start":"2026-07-01","valid_end":"2026-07-31","test_start":"2026-08-01","test_end":"2026-08-31"},
]


def as_bool(s):
    if s.dtype==bool:return s.fillna(False)
    z=s.astype(str).str.strip().str.lower();return z.isin(["1","true","yes","y"])


def stats(df):
    x=pd.to_numeric(df.perf_5bd,errors="coerce").dropna().to_numpy(float)
    if not len(x):return {"n":0,"avg":0.,"median":0.,"robust_avg":0.,"wr":0.,"hit10":0.,"min":0.,"p10":0.}
    dec=x[x!=0];wr=float(np.mean(dec>0)) if len(dec) else 0.
    if len(x)>=10:
        lo,hi=np.quantile(x,[.05,.95]);rob=float(np.mean(np.clip(x,lo,hi)))
    else:rob=float(np.mean(x))
    return {"n":int(len(x)),"avg":float(np.mean(x)),"median":float(np.median(x)),"robust_avg":rob,"wr":wr,"hit10":float(np.mean(x>=.10)),"min":float(np.min(x)),"p10":float(np.quantile(x,.10))}


def mask_for(df,combo):
    m=pd.Series(True,index=df.index)
    for c in combo:m &= df[c]
    return m


def single_rank(train,cols):
    base_avg=stats(train)["avg"];rows=[]
    for c in cols:
        st=stats(train[train[c]])
        if st["n"]<20:continue
        score=st["robust_avg"]+.25*(st["avg"]-base_avg)+.01*(st["wr"]-.5)+.015*st["hit10"]
        rows.append((score,c,st))
    rows.sort(reverse=True,key=lambda x:x[0]);return rows


def objective(tr,va):
    if tr["n"]<18 or va["n"]<6:return -999.
    if tr["robust_avg"]<=0 or va["robust_avg"]<=0:return -999.
    core=min(tr["robust_avg"],va["robust_avg"]);tail=.08*min(0.,va["p10"])+.02*min(0.,va["min"])
    return core+.20*min(tr["avg"],va["avg"])+.012*(min(tr["wr"],va["wr"])-.5)+.015*min(tr["hit10"],va["hit10"])+tail+.0005*np.log1p(va["n"])


def mine(train,valid,all_cols,pool_n=16):
    ranked=single_rank(train,all_cols);pool=[c for _,c,_ in ranked[:pool_n]]
    for c in CURRENT:
        if c in all_cols and c not in pool:pool.append(c)
    best=None;checked=0
    for k in (3,4,5,6):
        for combo in itertools.combinations(pool,k):
            checked+=1;tr=stats(train[mask_for(train,combo)]);va=stats(valid[mask_for(valid,combo)]);o=objective(tr,va)
            rec={"conditions":list(combo),"objective":float(o),"train":tr,"validation":va}
            if best is None or (o,va["n"])>(best["objective"],best["validation"]["n"]):best=rec
    return best,{"pool":pool,"checked":checked,"top_singles":[{"condition":c,"score":float(s),"stats":st} for s,c,st in ranked[:20]]}


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--teacher",required=True);ap.add_argument("--output-dir",default="research_artifacts/v20_rule_miner");a=ap.parse_args()
    df=pd.read_csv(a.teacher,low_memory=False)
    if "date" not in df.columns or "perf_5bd" not in df.columns:raise RuntimeError("teacher missing date/perf_5bd")
    # Fail closed if any known outcome field accidentally enters the allow-list.
    leaked=sorted(set(ALLOWED_BOOL)&FORBIDDEN)
    if leaked:raise RuntimeError(f"target leakage in allow-list: {leaked}")
    cols=[c for c in ALLOWED_BOOL if c in df.columns]
    missing=[c for c in CURRENT if c not in cols]
    if missing:raise RuntimeError(f"current Stable columns missing: {missing}")
    if len(cols)<20:raise RuntimeError(f"too few approved signal-time columns: {len(cols)}")
    df["date_norm"]=pd.to_datetime(df.date,errors="coerce").dt.strftime("%Y-%m-%d");df["perf_5bd"]=pd.to_numeric(df.perf_5bd,errors="coerce")
    for c in cols:df[c]=as_bool(df[c])
    folds=[];selected_parts=[];current_parts=[]
    for f in FOLDS:
        train=df[df.date_norm.between(f["train_start"],f["train_end"])&df.perf_5bd.notna()].copy();valid=df[df.date_norm.between(f["valid_start"],f["valid_end"])&df.perf_5bd.notna()].copy();test=df[df.date_norm.between(f["test_start"],f["test_end"])&df.perf_5bd.notna()].copy()
        best,meta=mine(train,valid,cols);tm=mask_for(test,best["conditions"]);cm=mask_for(test,CURRENT);tst=stats(test[tm]);cur=stats(test[cm])
        selected_parts.append(test[tm].assign(fold=f["id"]));current_parts.append(test[cm].assign(fold=f["id"]));folds.append({"fold":f["id"],"sizes":{"train":len(train),"valid":len(valid),"test":len(test)},"selected":best,"test":tst,"current_stable6_test":cur,"search":meta});print(f"{f['id']} best={best['conditions']} test={tst}",flush=True)
    sel=pd.concat(selected_parts,ignore_index=True) if selected_parts else df.iloc[0:0];cur=pd.concat(current_parts,ignore_index=True) if current_parts else df.iloc[0:0]
    result={"scope":"Actual Tenchi BOTTOM scoring-only rule mining. EXPLICIT signal-time feature allow-list; outcome-derived columns forbidden. Each fold mines train+prior validation only.","teacher_rows":len(df),"approved_boolean_columns":cols,"forbidden_columns":sorted(FORBIDDEN),"folds":folds,"combined_test":{"candidate":stats(sel),"current_stable6_same_window":stats(cur)},"current_conditions":CURRENT}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/"v20_rule_miner.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8");print(json.dumps(result["combined_test"],ensure_ascii=False,indent=2))

if __name__=="__main__":main()
