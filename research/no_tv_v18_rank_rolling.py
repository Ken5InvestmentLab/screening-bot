from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import no_tv_v10_standalone as base
import no_tv_v11_independent_selector as v11
import no_tv_v11_1_risk_guard as risk
import no_tv_v14_pine_outcome as v14
import no_tv_v17_unbiased_rolling as v17

FOLDS=v17.FOLDS
SAMPLE_CUTOFF=v17.SAMPLE_CUTOFF


def verify_early_sample(watchlist_repo,codes):
    wl,_,_=base.load_exact_watchlists(watchlist_repo,base.TRAIN_START,base.TEST_END)
    early=set()
    for d,syms in wl.items():
        if base.TRAIN_START<=d<=SAMPLE_CUTOFF:
            early.update(syms)
    missing=[c for c in codes if c not in early]
    if missing:
        raise RuntimeError(f"future-only symbols leaked into sample: {missing[:10]}")


def fit_attach(train,valid,test,variant):
    cols=v11.features() if variant=="v13" else v14.feature_cols()
    models=v11.fit_models(train,cols) if variant=="v13" else v14.fit(train,cols)
    va=v11.attach(valid,models,cols) if variant=="v13" else v14.attach(valid,models,cols)
    te=v11.attach(test,models,cols) if variant=="v13" else v14.attach(test,models,cols)
    return va,te


def evaluate(data,fold,variant):
    train=data[data.date.between(fold["train_start"],fold["train_end"]) & data.perf_5bd.notna()].copy()
    valid=data[data.date.between(fold["valid_start"],fold["valid_end"]) & data.perf_5bd.notna()].copy()
    test=data[data.date.between(fold["test_start"],fold["test_end"]) & data.perf_5bd.notna()].copy()
    va,te=fit_attach(train,valid,test,variant)
    # Rank-only policy: no absolute probability threshold. This prevents month-to-month
    # probability-scale drift from producing zero or tiny test samples.
    policy,trials=risk.choose(va)
    selected=risk.apply_policy(te,policy)
    return {
        "fold":fold["id"],"variant":variant,
        "sizes":{"train":len(train),"valid":len(valid),"test":len(test)},
        "policy":policy,"validation":policy["stats"],"test":risk.risk_stats(selected),
        "selected":selected.assign(fold=fold["id"],variant=variant),
    }


def fixed_baselines(data):
    tests=[]
    for fold in FOLDS:
        x=data[data.date.between(fold["test_start"],fold["test_end"]) & data.perf_5bd.notna()].copy()
        x["fold"]=fold["id"]; tests.append(x)
    t=pd.concat(tests,ignore_index=True)
    rules={
        "pine_bottom_all":t.pine_bottom>0,
        "pine_stable_ge4":(t.pine_bottom>0)&(t.stable_score>=4),
        "pine_stable_ge5":(t.pine_bottom>0)&(t.stable_score>=5),
        "pine_stable_6":(t.pine_bottom>0)&(t.stable_score==6),
        "actual_bottom_stable6_eval_only":(t.label==1)&(t.stable_score==6),
    }
    return {k:risk.risk_stats(t[m].copy()) for k,m in rules.items()}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--teacher",required=True)
    ap.add_argument("--watchlist-repo",required=True)
    ap.add_argument("--max-symbols",type=int,default=350)
    ap.add_argument("--max-workers",type=int,default=16)
    ap.add_argument("--output-dir",default="research_artifacts/v18_rank_rolling")
    a=ap.parse_args()

    teacher,wstat,data,yahoo,codes=v17.build_dataset(a)
    verify_early_sample(a.watchlist_repo,codes)
    data=v11.enrich_cross_sectional(data)
    rows=[]; parts={"v13":[],"v14":[]}
    for fold in FOLDS:
        for variant in ("v13","v14"):
            print(f"evaluate {fold['id']} {variant}",flush=True)
            r=evaluate(data,fold,variant)
            parts[variant].append(r.pop("selected")); rows.append(r)
    combined={k:risk.risk_stats(pd.concat(v,ignore_index=True)) for k,v in parts.items()}
    baselines=fixed_baselines(data)
    result={
        "scope":"Leakage-free rank-only rolling smoke; no absolute score threshold; 350 symbols selected only from Mar05-Apr30 watchlist frequency",
        "sampling":{"cutoff":SAMPLE_CUTOFF,"max_symbols":a.max_symbols,"symbols":codes},
        "teacher_rows":len(teacher),"watchlists":wstat,"yahoo":yahoo,
        "folds":rows,"combined_test":combined,"fixed_baselines":baselines,"current_champion":base.CHAMPION,
    }
    out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True)
    (out/"v18_rank_rolling.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    print(json.dumps({"folds":rows,"combined_test":combined,"fixed_baselines":baselines},ensure_ascii=False,indent=2,default=str))

if __name__=="__main__":main()
