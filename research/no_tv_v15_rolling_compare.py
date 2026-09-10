from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import no_tv_v10_standalone as base
import no_tv_v11_independent_selector as v11
import no_tv_v11_1_risk_guard as risk
import no_tv_v14_pine_outcome as v14

FOLDS=[
 {"id":"F1","train_start":"2026-03-05","train_end":"2026-04-30","valid_start":"2026-05-01","valid_end":"2026-05-31","test_start":"2026-06-01","test_end":"2026-06-30"},
 {"id":"F2","train_start":"2026-03-05","train_end":"2026-05-31","valid_start":"2026-06-01","valid_end":"2026-06-30","test_start":"2026-07-01","test_end":"2026-07-31"},
 {"id":"F3","train_start":"2026-03-05","train_end":"2026-06-30","valid_start":"2026-07-01","valid_end":"2026-07-31","test_start":"2026-08-01","test_end":"2026-08-31"},
]


def run_variant(data,fold,variant):
    train=data[data.date.between(fold["train_start"],fold["train_end"])&data.perf_5bd.notna()].copy()
    valid=data[data.date.between(fold["valid_start"],fold["valid_end"])&data.perf_5bd.notna()].copy()
    test=data[data.date.between(fold["test_start"],fold["test_end"])&data.perf_5bd.notna()].copy()
    cols=v11.features() if variant=="v13" else v14.feature_cols()
    models=v11.fit_models(train,cols) if variant=="v13" else v14.fit(train,cols)
    v=v11.attach(valid,models,cols) if variant=="v13" else v14.attach(valid,models,cols)
    t=v11.attach(test,models,cols) if variant=="v13" else v14.attach(test,models,cols)
    policy,trials=risk.choose(v);sel=risk.apply_policy(t,policy)
    return {"fold":fold,"variant":variant,"sizes":{"train":len(train),"valid":len(valid),"test":len(test)},"policy":policy,"validation":policy["stats"],"test":risk.risk_stats(sel),"selected":sel.assign(fold=fold["id"],variant=variant)}


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--teacher",required=True);ap.add_argument("--watchlist-repo",required=True);ap.add_argument("--max-symbols",type=int,default=350);ap.add_argument("--max-workers",type=int,default=16);ap.add_argument("--output-dir",default="research_artifacts/v15_rolling")
    a=ap.parse_args();teacher,wstat,data,yahoo=v14.build_dataset(a);data=v11.enrich_cross_sectional(data)
    rows=[];selected={"v13":[],"v14":[]}
    for fold in FOLDS:
        for variant in ("v13","v14"):
            print(f"running {fold['id']} {variant}",flush=True);r=run_variant(data,fold,variant);selected[variant].append(r.pop("selected"));rows.append(r)
    combined={}
    for variant,parts in selected.items():
        x=pd.concat(parts,ignore_index=True) if parts else pd.DataFrame();combined[variant]=risk.risk_stats(x)
    result={"scope":"Expanding rolling OOS: each fold selects policy only on prior validation month","teacher_rows":len(teacher),"watchlists":wstat,"yahoo":yahoo,"folds":rows,"combined_test":combined,"current_champion":base.CHAMPION}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/"v15_rolling_result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8");print(json.dumps({"folds":rows,"combined_test":combined},ensure_ascii=False,indent=2,default=str))

if __name__=="__main__":main()
