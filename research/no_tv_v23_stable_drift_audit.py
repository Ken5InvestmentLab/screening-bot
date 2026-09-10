from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

CURRENT=["ema25","macdpos","stoch75","bb80","pre_down3","gap_up"]


def as_bool(s):
    if s.dtype==bool:return s.fillna(False)
    return s.astype(str).str.strip().str.lower().isin(["1","true","yes","y"])


def stats(df):
    x=pd.to_numeric(df.perf_5bd,errors="coerce").dropna().to_numpy(float)
    if not len(x):return {"n":0,"avg":0.,"median":0.,"robust_avg":0.,"wr":0.,"hit10":0.,"min":0.,"p10":0.}
    d=x[x!=0];wr=float(np.mean(d>0)) if len(d) else 0.
    if len(x)>=10:
        lo,hi=np.quantile(x,[.05,.95]);rob=float(np.mean(np.clip(x,lo,hi)))
    else:rob=float(np.mean(x))
    return {"n":int(len(x)),"avg":float(np.mean(x)),"median":float(np.median(x)),"robust_avg":rob,"wr":wr,"hit10":float(np.mean(x>=.10)),"min":float(np.min(x)),"p10":float(np.quantile(x,.10))}


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--teacher",required=True);ap.add_argument("--output-dir",default="research_artifacts/v23_stable_drift");a=ap.parse_args()
    d=pd.read_csv(a.teacher,low_memory=False);d["date_norm"]=pd.to_datetime(d.date,errors="coerce");d["month"]=d.date_norm.dt.strftime("%Y-%m");d["perf_5bd"]=pd.to_numeric(d.perf_5bd,errors="coerce")
    for c in CURRENT:
        if c not in d.columns:raise RuntimeError(f"missing {c}")
        d[c]=as_bool(d[c])
    d["stable6"]=d[CURRENT].all(axis=1)
    if "session" not in d.columns:
        rec=pd.to_datetime(d.get("received_at"),errors="coerce");d["session"]=np.where(rec.dt.hour<14,9,13)
    d["session"]=pd.to_numeric(d.session,errors="coerce")
    months=sorted(x for x in d.month.dropna().unique() if x<="2026-08")
    monthly={}
    for m in months:
        x=d[d.month==m];monthly[m]={"all_bottom":stats(x),"stable6":stats(x[x.stable6]),"stable6_count_raw":int(x.stable6.sum())}
    by_session={}
    for s in (9,13):
        x=d[d.session==s];by_session[str(s)]={"all_bottom":stats(x),"stable6":stats(x[x.stable6])}
    conditions={}
    for c in CURRENT:
        x=d[d[c]];conditions[c]={"true_rows":int(d[c].sum()),"stats":stats(x)}
    windows={
      "mar_may":{"all_bottom":stats(d[d.date_norm.between("2026-03-05","2026-05-31")]),"stable6":stats(d[d.date_norm.between("2026-03-05","2026-05-31")&d.stable6])},
      "jun_aug":{"all_bottom":stats(d[d.date_norm.between("2026-06-01","2026-08-31")]),"stable6":stats(d[d.date_norm.between("2026-06-01","2026-08-31")&d.stable6])},
      "mar_aug":{"all_bottom":stats(d[d.date_norm.between("2026-03-05","2026-08-31")]),"stable6":stats(d[d.date_norm.between("2026-03-05","2026-08-31")&d.stable6])},
    }
    result={"scope":"Descriptive audit only; no optimization. Actual Tenchi BOTTOM production signal-time snapshots.","rows":len(d),"current_conditions":CURRENT,"monthly":monthly,"by_session":by_session,"windows":windows,"condition_univariate":conditions}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/"v23_stable_drift.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8");print(json.dumps({"monthly":monthly,"by_session":by_session,"windows":windows},ensure_ascii=False,indent=2,default=str))

if __name__=="__main__":main()
