from __future__ import annotations

import argparse, glob, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.utils.class_weight import compute_sample_weight
from tvfree_screener.batch02 import eval_causal_4h_scoring_v3 as v3

RAW = list(v3.FEATURES)
RANK_SRC = RAW + ["bin_volume"]
RANK = [f"xrank_{x}" for x in RANK_SRC]
CTX = ["xctx_breadth_positive","xctx_median_bar_log_return","xctx_median_range_pct","xctx_median_log_range_vs_prior20"]
FEATURES = RAW + RANK + CTX


def add_cross_sectional_features(df: pd.DataFrame) -> pd.DataFrame:
    out=df.copy(); g=out.groupby(["date","bin_name"],sort=False)
    for c in RANK_SRC: out[f"xrank_{c}"]=g[c].rank(method="average",pct=True,ascending=True)
    out["xctx_breadth_positive"]=g["bar_log_return"].transform(lambda s: float((s>0).mean()))
    out["xctx_median_bar_log_return"]=g["bar_log_return"].transform("median")
    out["xctx_median_range_pct"]=g["range_pct"].transform("median")
    out["xctx_median_log_range_vs_prior20"]=g["log_range_vs_prior20"].transform("median")
    return out


def load_candidates(pattern: str) -> pd.DataFrame:
    files=sorted(glob.glob(pattern))
    if not files: raise FileNotFoundError(pattern)
    df=pd.concat([pd.read_csv(f,dtype={"symbol":"string"}) for f in files],ignore_index=True)
    df["symbol"]=df.symbol.astype(str).str.replace(r"\.0$","",regex=True).str.upper(); df["date"]=df.date.astype(str).str[:10]
    for c in RAW+["bin_volume","prior_daily_close","prior_daily_volume"]: df[c]=pd.to_numeric(df[c],errors="coerce")
    gate=(np.isfinite(df[RAW]).all(axis=1)&np.isfinite(df.prior_daily_close)&(df.prior_daily_close<=1000)&np.isfinite(df.prior_daily_volume)&(df.prior_daily_volume>=10000)&np.isfinite(df.bin_volume)&(df.bin_volume>=0))
    return add_cross_sectional_features(df.loc[gate].copy())


def _fit(train, valid, target):
    y=train[target].to_numpy(int)
    if len(np.unique(y))<2: return np.full(len(valid),float(y[0]) if len(y) else 0.0)
    m=HistGradientBoostingClassifier(**v3.MODEL_PARAMS); m.fit(train[FEATURES],y,sample_weight=compute_sample_weight("balanced",y)); return m.predict_proba(valid[FEATURES])[:,1]


def score_period(train, valid):
    s=valid.copy()
    for c in ["p_positive","p_plus20","p_loss10"]: s[c]=np.nan
    for bn in v3.BINS:
        tr=train[train.bin_name==bn].copy(); idx=s.index[s.bin_name==bn]
        if tr.empty or not len(idx): continue
        va=s.loc[idx]; tr["y_pos"]=(tr.ret5bd_gross>0).astype(int); tr["y_20"]=(tr.ret5bd_gross>=.2).astype(int); tr["y_loss"]=(tr.ret5bd_gross<=-.1).astype(int)
        s.loc[idx,"p_positive"]=_fit(tr,va,"y_pos"); s.loc[idx,"p_plus20"]=_fit(tr,va,"y_20"); s.loc[idx,"p_loss10"]=_fit(tr,va,"y_loss")
    for c in ["p_positive","p_plus20","p_loss10"]: s[c]=s[c].clip(v3.EPS,1-v3.EPS)
    s["score_core"]=np.log(s.p_positive/(1-s.p_positive))-np.log(s.p_loss10/(1-s.p_loss10)); s["score_monster"]=s.p_plus20
    return s


def select_policy(scored, session_idx, head, top_n):
    if head=="core": cols=["date","bin_name","score_core","symbol"]; asc=[True,True,False,True]
    else: cols=["date","bin_name","score_monster","p_loss10","symbol"]; asc=[True,True,False,True,True]
    w=scored.sort_values(cols,ascending=asc,kind="stable"); groups={(d,b):g.to_dict("records") for (d,b),g in w.groupby(["date","bin_name"],sort=False)}; blocked={}; rows=[]
    for day in sorted(scored.date.unique()):
        di=session_idx[day]
        for bn in v3.BINS:
            n=0
            for r in groups.get((day,bn),()):
                sym=r["symbol"]
                if blocked.get(sym,-999999)>di: continue
                rows.append(r); blocked[sym]=di+5; n+=1
                if n>=top_n: break
    return pd.DataFrame(rows)


def evaluate_window(cand, session_idx, **kw):
    tr=cand[(cand.date>=kw["train_start"])&(cand.date<=kw["train_end"])&(cand.exit_date<kw["maturity_cutoff"])&(cand.endpoint_status=="RESOLVED")].copy(); va=cand[(cand.date>=kw["eval_start"])&(cand.date<=kw["eval_end"])].copy(); scored=score_period(tr,va); results={}
    for head in ["core","monster"]:
        results[head]={}
        for n in v3.TOP_NS:
            sel=select_policy(scored,session_idx,head,n); m=v3.metrics(sel,.005); m["passes_comparability_gates"]=v3.passes(head,m); m["cost0"]=v3.metrics(sel,0); m["cost1pct"]=v3.metrics(sel,.01); results[head][str(n)]=m
    return {"train_rows":len(tr),"eval_rows":len(va),"train_targets":{"positive":int((tr.ret5bd_gross>0).sum()),"plus20":int((tr.ret5bd_gross>=.2).sum()),"loss10":int((tr.ret5bd_gross<=-.1).sum())},"results":results}


def main():
    p=argparse.ArgumentParser(); p.add_argument("--candidates",required=True); p.add_argument("--daily",required=True); p.add_argument("--output",required=True); a=p.parse_args(); daily=Path(a.daily)
    expected="6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0"; actual=v3.sha256_file(daily)
    if actual!=expected: raise RuntimeError("daily SHA mismatch")
    c=load_candidates(a.candidates); d=v3.load_daily(daily); c,idx=v3.attach_endpoint_labels(c,d)
    windows={"h1_fold1":dict(train_start="2025-01-01",train_end="2025-02-28",maturity_cutoff="2025-03-01",eval_start="2025-03-01",eval_end="2025-04-30"),"h1_fold2":dict(train_start="2025-01-01",train_end="2025-04-30",maturity_cutoff="2025-05-01",eval_start="2025-05-01",eval_end="2025-06-30"),"h2_retrospective":dict(train_start="2025-01-01",train_end="2025-06-30",maturity_cutoff="2025-07-01",eval_start="2025-07-01",eval_end="2025-12-31")}
    out={"experiment_id":"CAUSAL-4H-SCORING-V4-CROSSSECTIONAL-REGIME-20260913","features":FEATURES,"h2_role":"RETROSPECTIVE_REFUTATION_ONLY_NOT_PROMOTABLE","2026_outcomes_opened":False,"windows":{}}
    for name,kw in windows.items(): print("RUN",name,flush=True); out["windows"][name]=evaluate_window(c,idx,**kw)
    Path(a.output).parent.mkdir(parents=True,exist_ok=True); Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")

if __name__=="__main__": main()
