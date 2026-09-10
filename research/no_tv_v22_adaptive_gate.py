from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import no_tv_v10_standalone as base
import no_tv_v11_independent_selector as v11
import no_tv_v11_1_risk_guard as risk
import no_tv_v14_pine_outcome as v14
import no_tv_v17_unbiased_rolling as v17
import no_tv_v21_pine_gated_outcome as pg

FOLDS=v17.FOLDS
SAMPLE_CUTOFF=v17.SAMPLE_CUTOFF
GATES=("pine","stable4","stable5","pine_or_stable4","pine_or_stable5","pine_and_stable4")
VARIANTS=("v13","v14")


def gate_mask(df,g):
    p=df.pine_bottom>0;s4=df.stable_score>=4;s5=df.stable_score>=5
    if g=="pine":return p
    if g=="stable4":return s4
    if g=="stable5":return s5
    if g=="pine_or_stable4":return p|s4
    if g=="pine_or_stable5":return p|s5
    if g=="pine_and_stable4":return p&s4
    raise ValueError(g)


def verify_early(repo,codes):
    wl,_,_=base.load_exact_watchlists(repo,base.TRAIN_START,base.TEST_END);early=set()
    for d,syms in wl.items():
        if base.TRAIN_START<=d<=SAMPLE_CUTOFF:early.update(syms)
    bad=[c for c in codes if c not in early]
    if bad:raise RuntimeError(f"future-only symbols leaked: {bad[:10]}")


def train_score(data,fold,gate,variant):
    z=data[gate_mask(data,gate)].copy()
    train=z[z.date.between(fold["train_start"],fold["train_end"])&z.perf_5bd.notna()].copy();valid=z[z.date.between(fold["valid_start"],fold["valid_end"])&z.perf_5bd.notna()].copy();test=z[z.date.between(fold["test_start"],fold["test_end"])&z.perf_5bd.notna()].copy()
    if len(train)<80 or len(valid)<12:return None
    models=pg.fit_models(train,variant);va=pg.attach(valid,models,variant);te=pg.attach(test,models,variant);policy,trials=pg.choose(va);sel=pg.apply(te,policy)
    return {"gate":gate,"variant":variant,"sizes":{"train":len(train),"valid":len(valid),"test":len(test)},"policy":policy,"validation":policy["stats"],"validation_objective":float(policy["objective"]),"test":risk.risk_stats(sel),"selected":sel}


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--teacher",required=True);ap.add_argument("--watchlist-repo",required=True);ap.add_argument("--max-symbols",type=int,default=350);ap.add_argument("--max-workers",type=int,default=16);ap.add_argument("--output-dir",default="research_artifacts/v22_adaptive_gate");a=ap.parse_args()
    teacher,wstat,data,yahoo,codes=v17.build_dataset(a);verify_early(a.watchlist_repo,codes);data=v11.enrich_cross_sectional(data);fold_rows=[];selected=[]
    for f in FOLDS:
        candidates=[]
        for gate in GATES:
            for variant in VARIANTS:
                print(f"fit {f['id']} {gate} {variant}",flush=True);r=train_score(data,f,gate,variant)
                if r is not None:candidates.append(r)
        if not candidates:raise RuntimeError(f"no candidates {f['id']}")
        # Selection uses validation only. Test stats are not inspected by the selector.
        best=max(candidates,key=lambda r:(r["validation_objective"],r["validation"]["n"]))
        sel=best.pop("selected").assign(fold=f["id"],gate=best["gate"],variant=best["variant"]);selected.append(sel)
        diagnostics=[]
        for r in candidates:
            rr={k:v for k,v in r.items() if k!="selected"};diagnostics.append(rr)
        fold_rows.append({"fold":f["id"],"chosen":best,"validation_ranked":sorted(diagnostics,key=lambda r:(r["validation_objective"],r["validation"]["n"]),reverse=True)[:12]})
    allsel=pd.concat(selected,ignore_index=True);combined=risk.risk_stats(allsel)
    result={"scope":"Leakage-free intraday-causal adaptive trigger gate. Gate/model/policy selected only on prior validation month; TV labels evaluation-only.","sampling":{"cutoff":SAMPLE_CUTOFF,"symbols":codes},"teacher_rows":len(teacher),"watchlists":wstat,"yahoo":yahoo,"folds":fold_rows,"combined_test":combined,"current_champion":base.CHAMPION}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/"v22_adaptive_gate.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8");print(json.dumps({"folds":[{"fold":x["fold"],"chosen":x["chosen"]} for x in fold_rows],"combined_test":combined},ensure_ascii=False,indent=2,default=str))

if __name__=="__main__":main()
