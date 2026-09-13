from __future__ import annotations

import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from tvfree_screener.batch02 import eval_causal_4h_scoring_v3 as v3
from tvfree_screener.batch02 import eval_causal_4h_scoring_v4 as v4

FEATURES = list(v4.FEATURES)
QUANTILES = (0.10, 0.50, 0.90)
REG_PARAMS = dict(
    learning_rate=0.05,
    max_iter=150,
    max_leaf_nodes=15,
    min_samples_leaf=200,
    l2_regularization=1.0,
    max_bins=63,
    early_stopping=False,
    random_state=0,
)


def fit_quantile(train: pd.DataFrame, valid: pd.DataFrame, q: float) -> np.ndarray:
    model = HistGradientBoostingRegressor(loss="quantile", quantile=q, **REG_PARAMS)
    model.fit(train[FEATURES], train["ret5bd_gross"].to_numpy(float))
    return model.predict(valid[FEATURES])


def score_period(train: pd.DataFrame, valid: pd.DataFrame) -> pd.DataFrame:
    out = valid.copy()
    for c in ["q10_raw", "q50_raw", "q90_raw"]:
        out[c] = np.nan
    for bn in v3.BINS:
        tr = train[train["bin_name"] == bn]
        idx = out.index[out["bin_name"] == bn]
        if tr.empty or not len(idx):
            continue
        va = out.loc[idx]
        for q, c in zip(QUANTILES, ["q10_raw", "q50_raw", "q90_raw"]):
            out.loc[idx, c] = fit_quantile(tr, va, q)
    raw = out[["q10_raw", "q50_raw", "q90_raw"]].to_numpy(float)
    out["quantile_crossed_raw"] = (raw[:, 0] > raw[:, 1]) | (raw[:, 1] > raw[:, 2])
    ordered = np.sort(raw, axis=1)
    out["q10"], out["q50"], out["q90"] = ordered[:, 0], ordered[:, 1], ordered[:, 2]
    out["score_core"] = out["q50"]
    out["score_monster"] = out["q90"] + np.minimum(out["q10"], 0.0)
    return out


def select_policy(scored: pd.DataFrame, session_idx: dict[str, int], head: str, top_n: int) -> pd.DataFrame:
    if head == "core":
        cols, asc = ["date", "bin_name", "score_core", "symbol"], [True, True, False, True]
    else:
        cols, asc = ["date", "bin_name", "score_monster", "q90", "q50", "symbol"], [True, True, False, False, False, True]
    ranked = scored.sort_values(cols, ascending=asc, kind="stable")
    groups = {(d, b): g.to_dict("records") for (d, b), g in ranked.groupby(["date", "bin_name"], sort=False)}
    blocked, rows = {}, []
    for day in sorted(scored["date"].unique()):
        di = session_idx[day]
        for bn in v3.BINS:
            picked = 0
            for r in groups.get((day, bn), ()):
                sym = r["symbol"]
                if blocked.get(sym, -999999) > di:
                    continue
                rows.append(r); blocked[sym] = di + 5; picked += 1
                if picked >= top_n:
                    break
    return pd.DataFrame(rows)


def evaluate_window(cand: pd.DataFrame, session_idx: dict[str, int], **kw) -> dict:
    train = cand[(cand.date >= kw["train_start"]) & (cand.date <= kw["train_end"]) & (cand.exit_date < kw["maturity_cutoff"]) & (cand.endpoint_status == "RESOLVED")].copy()
    valid = cand[(cand.date >= kw["eval_start"]) & (cand.date <= kw["eval_end"])].copy()
    scored = score_period(train, valid)
    results = {}
    for head in ["core", "monster"]:
        results[head] = {}
        for n in v3.TOP_NS:
            sel = select_policy(scored, session_idx, head, n)
            m = v3.metrics(sel, .005); m["passes_comparability_gates"] = v3.passes(head, m); m["cost0"] = v3.metrics(sel, 0); m["cost1pct"] = v3.metrics(sel, .01)
            results[head][str(n)] = m
    return {
        "train_rows": int(len(train)), "eval_rows": int(len(valid)),
        "quantile_crossing_raw_rate": float(scored["quantile_crossed_raw"].mean()),
        "results": results,
    }


def main():
    p=argparse.ArgumentParser(); p.add_argument("--candidates",required=True); p.add_argument("--daily",required=True); p.add_argument("--output",required=True); a=p.parse_args(); daily=Path(a.daily)
    expected="6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0"
    if v3.sha256_file(daily) != expected: raise RuntimeError("daily SHA mismatch")
    cand=v4.load_candidates(a.candidates); d=v3.load_daily(daily); cand,idx=v3.attach_endpoint_labels(cand,d)
    windows={"h1_fold1":dict(train_start="2025-01-01",train_end="2025-02-28",maturity_cutoff="2025-03-01",eval_start="2025-03-01",eval_end="2025-04-30"),"h1_fold2":dict(train_start="2025-01-01",train_end="2025-04-30",maturity_cutoff="2025-05-01",eval_start="2025-05-01",eval_end="2025-06-30"),"h2_retrospective":dict(train_start="2025-01-01",train_end="2025-06-30",maturity_cutoff="2025-07-01",eval_start="2025-07-01",eval_end="2025-12-31")}
    out={"experiment_id":"CAUSAL-4H-SCORING-V5-QUANTILE-DISTRIBUTION-20260913","features":FEATURES,"2026_outcomes_opened":False,"h2_role":"RETROSPECTIVE_REFUTATION_ONLY_NOT_PROMOTABLE","windows":{}}
    for name,kw in windows.items(): print("RUN",name,flush=True); out["windows"][name]=evaluate_window(cand,idx,**kw)
    Path(a.output).parent.mkdir(parents=True,exist_ok=True); Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")

if __name__=="__main__": main()
