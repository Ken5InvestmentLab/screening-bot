#!/usr/bin/env python3
"""Full-feature pure positive-tail relative-ranking research (TEST ONLY).

V5 absolute tail and V6 light-feature relative tail both failed 2024.
This V7 restores the historical V3 ingredients most directly:
- full 45 run.py signal-time features,
- monthly causal retraining,
- future same-day cross-sectional top 1% / top 0.25% labels,
- pure positive-tail ranking (no loss probability subtracted from Attack score),
- one-business-day same-symbol cooldown,
- next-session-open -> 5BD close.

Risk is enforced by blind-period acceptance gates, not by suppressing volatile
candidates inside the Attack score.

Protocol: 2024 only -> top2 -> 2025 only if qualified -> lock -> 2026 only after pass.
No production writes. No 2026 tuning.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

import run as base

OUT=Path("tvfree_screener/out")

DEV={
 "2024H1":("2024-01-01","2024-06-30"),
 "2024H2":("2024-07-01","2024-12-31"),
}
VAL={
 "2025H1":("2025-01-01","2025-06-30"),
 "2025H2":("2025-07-01","2025-12-31"),
}
VARIANTS={
 "full_top1_q999":{"w1":1.0,"w025":0.0,"gate":0.9990},
 "full_top025_q999":{"w1":0.0,"w025":1.0,"gate":0.9990},
 "full_blend_q999":{"w1":0.50,"w025":1.0,"gate":0.9990},
 "full_blend_q9995":{"w1":0.50,"w025":1.0,"gate":0.9995},
}


def model(y:pd.Series)->XGBClassifier:
 pos=max(int(y.sum()),1); neg=max(int(len(y)-pos),1)
 return XGBClassifier(
  n_estimators=160,max_depth=3,learning_rate=0.04,
  subsample=0.80,colsample_bytree=0.80,min_child_weight=18,
  reg_lambda=6,reg_alpha=0.3,objective="binary:logistic",
  eval_metric="logloss",scale_pos_weight=min(neg/pos,80.0),
  n_jobs=4,random_state=42,
 )


def cdf(ref:np.ndarray,v:np.ndarray)->np.ndarray:
 r=np.asarray(ref,dtype=float); r=r[np.isfinite(r)]; r.sort()
 if len(r)==0: raise RuntimeError("empty CDF reference")
 return np.searchsorted(r,np.asarray(v,dtype=float),side="right")/len(r)


def prepare(raw:pd.DataFrame)->pd.DataFrame:
 f=base.build_features(raw)
 q=base.eligible_rows(f,price_cap=1000.0).copy()
 q=q.dropna(subset=base.FEATURES+["target5_no","target_end_date"])
 q["date"]=pd.to_datetime(q["date"])
 q["target_end_date"]=pd.to_datetime(q["target_end_date"])
 q["future_rank"]=q.groupby("date")["target5_no"].rank(pct=True,method="average")
 q["y_top1"]=(q["future_rank"]>=0.99).astype(int)
 q["y_top025"]=(q["future_rank"]>=0.9975).astype(int)
 return q


def fit_month(train:pd.DataFrame,pred:pd.DataFrame)->pd.DataFrame:
 out=pred.copy()
 trcdf={}
 for target in ["y_top1","y_top025"]:
  y=train[target].astype(int)
  if y.nunique()<2: raise RuntimeError(f"degenerate {target}")
  m=model(y); m.fit(train[base.FEATURES],y,verbose=False)
  tr=m.predict_proba(train[base.FEATURES])[:,1]
  pr=m.predict_proba(pred[base.FEATURES])[:,1]
  trcdf[target]=cdf(tr,tr)
  out[f"p_{target}"]=pr
  out[f"cdf_{target}"]=cdf(tr,pr)
 for name,s in VARIANTS.items():
  trraw=s["w1"]*trcdf["y_top1"]+s["w025"]*trcdf["y_top025"]
  prraw=s["w1"]*out["cdf_y_top1"].to_numpy()+s["w025"]*out["cdf_y_top025"].to_numpy()
  out[f"raw__{name}"]=prraw
  out[f"q__{name}"]=cdf(trraw,prraw)
 return out


def scores(q:pd.DataFrame,start:str,end:str)->pd.DataFrame:
 parts=[]
 for p in pd.period_range(pd.Timestamp(start).to_period("M"),pd.Timestamp(end).to_period("M"),freq="M"):
  a=p.start_time;b=p.end_time.normalize()
  train=q[q["target_end_date"]<a].copy()
  pred=q[(q["date"]>=a)&(q["date"]<=b)].copy()
  if len(train)<30000 or pred.empty: continue
  print(f"fit {p}: train={len(train)} pred={len(pred)}")
  z=fit_month(train,pred);z["model_period"]=str(p);parts.append(z)
 if not parts: raise RuntimeError("no V7 scores")
 return pd.concat(parts,ignore_index=True)


def select(scored:pd.DataFrame,name:str,trading_dates:pd.Index)->pd.DataFrame:
 gate=VARIANTS[name]["gate"]
 z=scored.copy();z["tail_raw"]=z[f"raw__{name}"];z["tail_q"]=z[f"q__{name}"]
 z=z[z["tail_q"]>=gate]
 if z.empty:return z
 date_idx={pd.Timestamp(d):i for i,d in enumerate(pd.Index(trading_dates).sort_values())}
 rows=[];last_sym=None;last_idx=None
 for date,day in z.sort_values(["date","tail_q","tail_raw"],ascending=[True,False,False]).groupby("date",sort=True):
  idx=date_idx[pd.Timestamp(date)];chosen=None
  for _,row in day.sort_values(["tail_q","tail_raw"],ascending=False).iterrows():
   if last_idx is not None and idx==last_idx+1 and str(row["symbol"])==last_sym:continue
   chosen=row;break
  if chosen is not None:
   rows.append(chosen);last_sym=str(chosen["symbol"]);last_idx=idx
 return pd.DataFrame(rows).reset_index(drop=True)


def summary(s:pd.Series)->dict:
 x=pd.to_numeric(s,errors="coerce").dropna()
 if x.empty:return {"n":0}
 return {
  "n":int(len(x)),"mean":float(x.mean()),"median":float(x.median()),
  "win_rate":float((x>0).mean()),"hit10_rate":float((x>=.10).mean()),
  "hit20_rate":float((x>=.20).mean()),"hit50_rate":float((x>=.50).mean()),
  "hit100_rate":float((x>=1).mean()),"loss10_rate":float((x<=-.10).mean()),
  "max":float(x.max()),"min":float(x.min()),
 }


def pstats(p:pd.DataFrame,periods:dict)->dict:
 return {n:summary(p[(p.date>=a)&(p.date<=b)].target5_no) for n,(a,b) in periods.items()}


def devutil(ps:dict,pool:dict)->float|None:
 h1,h2=ps["2024H1"],ps["2024H2"]
 if h1.get("n",0)<8 or h2.get("n",0)<8:return None
 if h1["mean"]<=0 or h2["mean"]<=0:return None
 if pool["mean"]<.02:return None
 if max(h1["loss10_rate"],h2["loss10_rate"])>.25:return None
 return float(min(h1["mean"],h2["mean"])+.5*pool["mean"]+.10*pool["hit20_rate"]+.15*pool["hit50_rate"]-.05*max(h1["loss10_rate"],h2["loss10_rate"]))


def valpass(ps:dict,pool:dict)->bool:
 h1,h2=ps["2025H1"],ps["2025H2"]
 return bool(h1.get("n",0)>=8 and h2.get("n",0)>=8 and h1["mean"]>0 and h2["mean"]>0 and pool["mean"]>=.02 and pool["hit20_rate"]>=.05 and max(h1["loss10_rate"],h2["loss10_rate"])<=.25)


def main()->None:
 ap=argparse.ArgumentParser();ap.add_argument("--cache",default=str(OUT/"tse_daily.csv"));args=ap.parse_args()
 raw=pd.read_csv(args.cache,parse_dates=["date"],dtype={"symbol":str})
 for c in ["open","high","low","close","volume"]:raw[c]=pd.to_numeric(raw[c],errors="coerce")
 raw=raw.dropna(subset=["date","symbol","open","high","low","close","volume"]).sort_values(["symbol","date"]).reset_index(drop=True)
 trading_dates=pd.Index(pd.to_datetime(raw.date.unique())).sort_values()
 q=prepare(raw)

 devs=scores(q,"2024-01-01","2024-12-31")
 cand={}
 for name in VARIANTS:
  p=select(devs,name,trading_dates);ps=pstats(p,DEV);pool=summary(p[(p.date>="2024-01-01")&(p.date<="2024-12-31")].target5_no)
  cand[name]={"spec":VARIANTS[name],"development_2024":ps,"development_2024_pooled":pool,"development_utility":devutil(ps,pool)}
 ranked=sorted([(v["development_utility"],n) for n,v in cand.items() if v["development_utility"] is not None],reverse=True)
 opened=[n for _,n in ranked[:2]];accepted=[];pre=None
 if opened:
  vals=scores(q,"2025-01-01","2025-12-31");pre=pd.concat([devs,vals],ignore_index=True)
  for name in opened:
   p=select(pre,name,trading_dates);ps=pstats(p,VAL);pool=summary(p[(p.date>="2025-01-01")&(p.date<="2025-12-31")].target5_no)
   cand[name]["validation_2025"]=ps;cand[name]["validation_2025_pooled"]=pool;cand[name]["validation_pass"]=valpass(ps,pool)
   if cand[name]["validation_pass"]:accepted.append((min(ps["2025H1"]["mean"],ps["2025H2"]["mean"]),pool["mean"],name))
 locked=sorted(accepted,reverse=True)[0][2] if accepted else None
 fixed=None;monthly=None
 if locked:
  fut=scores(q,"2026-01-01","2026-08-31");allsc=pd.concat([pre,fut],ignore_index=True);p=select(allsc,locked,trading_dates)
  z=p[(p.date>="2026-03-01")&(p.date<="2026-08-31")].copy();fixed=summary(z.target5_no);monthly={str(m):summary(g.target5_no) for m,g in z.groupby(z.date.dt.to_period("M"))};z.to_csv(OUT/"v7_full_tail_locked_2026.csv",index=False)
 report={
  "status":"research_only_no_production_writes","hypothesis":"full 45-feature monthly pure positive relative tail","entry":"next_session_open_to_5BD_close",
  "protocol":"2024 -> top2 -> 2025 -> lock -> 2026 only after pass","eligible_rows":int(len(q)),
  "label_counts_audit":{"top1":int(q.y_top1.sum()),"top025":int(q.y_top025.sum())},
  "development_ranked":[{"name":n,"utility":float(u)} for u,n in ranked],"validation_opened":opened,"locked_candidate":locked,"candidates":{}
 }
 for n,v in cand.items():
  x={"spec":v["spec"],"development_2024":v["development_2024"],"development_2024_pooled":v["development_2024_pooled"],"development_utility":v["development_utility"]}
  if n in opened:x.update({"validation_2025":v["validation_2025"],"validation_2025_pooled":v["validation_2025_pooled"],"validation_pass":v["validation_pass"]})
  if n==locked:x.update({"fixed_2026_MarAug":fixed,"fixed_2026_monthly":monthly})
  report["candidates"][n]=x
 OUT.mkdir(parents=True,exist_ok=True)
 with open(OUT/"v7_full_tail_report.json","w",encoding="utf-8") as f:json.dump(report,f,ensure_ascii=False,indent=2)
 print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
