from __future__ import annotations

import argparse, glob, json, math
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from tvfree_screener.batch02 import eval_causal_4h_scoring_v3 as v3
from tvfree_screener.batch02 import eval_causal_4h_scoring_v4 as v4
from tvfree_screener.batch02.eval_causal_4h_monster_v8 import pareto_front

FEATURES = list(v4.FEATURES) + ["log_volume_rel20", "xrank_log_volume_rel20"]
BINS = ["AM_09_13", "PM_13_CLOSE"]
TOP_NS = [1, 2, 3, 5]
REG_PARAMS = dict(learning_rate=0.05, max_iter=150, max_leaf_nodes=15, min_samples_leaf=200, l2_regularization=1.0, max_bins=63, early_stopping=False, random_state=0)

def prepare(candidates_pattern: str, relative_volume_csv: str, daily_path: str):
    cand = v4.load_candidates(candidates_pattern)
    rv = pd.read_csv(relative_volume_csv, dtype={"symbol": "string"})
    rv["symbol"] = rv["symbol"].astype(str).str.replace(r"\.0$", "", regex=True).str.upper()
    rv["date"] = rv["date"].astype(str).str[:10]
    rv["log_volume_rel20"] = pd.to_numeric(rv["log_volume_rel20"], errors="coerce")
    cand = cand.merge(rv, on=["symbol", "date", "bin_name"], how="left")
    cand["xrank_log_volume_rel20"] = cand.groupby(["date", "bin_name"], sort=False)["log_volume_rel20"].rank(method="average", pct=True, ascending=True)
    cand = cand[np.isfinite(cand[FEATURES]).all(axis=1)].copy()
    daily = v3.load_daily(Path(daily_path))
    cand, session_idx = v3.attach_endpoint_labels(cand, daily)
    gate = (
        (cand["xctx_breadth_positive"] <= 0.50)
        & (cand["prev4_log_return_mean"] <= 0)
        & (cand["bar_log_return"] > 0)
        & (cand["range_pct"] >= cand["prev4_range_mean"])
        & (cand["log_volume_rel20"] >= math.log(2.0))
    )
    return cand.loc[gate].copy(), daily, session_idx

def fit_q(train, valid, q):
    model = HistGradientBoostingRegressor(loss="quantile", quantile=q, **REG_PARAMS)
    model.fit(train[FEATURES], train["ret5bd_gross"].to_numpy(float))
    return model.predict(valid[FEATURES])

def score_month(events: pd.DataFrame, month: str):
    p = pd.Period(month, freq="M"); start = p.start_time.date().isoformat(); end = p.end_time.date().isoformat()
    train = events[(events["date"] >= "2025-01-01") & (events["date"] < start) & (events["exit_date"] < start) & (events["endpoint_status"] == "RESOLVED")].copy()
    valid = events[(events["date"] >= start) & (events["date"] <= end)].copy()
    out = valid[["symbol", "date", "bin_name", "endpoint_status", "ret5bd_gross"]].copy()
    raw = np.full((len(valid), 3), np.nan)
    for bn in BINS:
        tr = train[train["bin_name"] == bn]; mask = (valid["bin_name"] == bn).to_numpy()
        if tr.empty or not mask.any(): continue
        va = valid.loc[mask]
        for j, q in enumerate((0.10, 0.50, 0.90)): raw[mask, j] = fit_q(tr, va, q)
    ordered = np.sort(raw, axis=1)
    out["q10"], out["q50"], out["q90"] = ordered[:,0], ordered[:,1], ordered[:,2]
    meta = {"month": month, "train_rows": int(len(train)), "eval_rows": int(len(valid)), "train_max_exit": str(train["exit_date"].max())}
    return out, meta

def select(scored: pd.DataFrame, session_idx: dict[str, int], n: int):
    fronts = [pareto_front(g) for _, g in scored.groupby(["date", "bin_name"], sort=False)]
    x = pd.concat(fronts, ignore_index=True) if fronts else scored.iloc[0:0].copy()
    x = x.sort_values(["date", "bin_name", "q90", "q10", "symbol"], ascending=[True, True, False, False, True], kind="stable")
    groups = {(d,b): g.to_dict("records") for (d,b), g in x.groupby(["date", "bin_name"], sort=False)}
    blocked = {}; rows = []
    for day in sorted(scored["date"].astype(str).unique()):
        di = session_idx[day]
        for bn in BINS:
            picked = 0
            for row in groups.get((day,bn), ()):
                sym = str(row["symbol"])
                if blocked.get(sym, -999999) > di: continue
                rows.append(row); blocked[sym] = di + 5; picked += 1
                if picked >= n: break
    return pd.DataFrame(rows)

def passes(m):
    return (m.get("resolved",0) >= 30 and m.get("net_mean",-999.0) > 0 and m.get("gross_ge20_rate",-1.0) >= 0.10 and m.get("top1_removed_net_mean",-999.0) > 0 and m.get("gross_le10_rate",999.0) <= 0.40)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--mode", choices=["month","aggregate"], required=True); ap.add_argument("--candidates"); ap.add_argument("--relative-volume"); ap.add_argument("--daily", required=True); ap.add_argument("--month"); ap.add_argument("--scored-output"); ap.add_argument("--meta-output"); ap.add_argument("--scored-glob"); ap.add_argument("--period"); ap.add_argument("--output"); a = ap.parse_args()
    if a.mode == "month":
        events, _, _ = prepare(a.candidates, a.relative_volume, a.daily); scored, meta = score_month(events, a.month)
        Path(a.scored_output).parent.mkdir(parents=True, exist_ok=True); scored.to_csv(a.scored_output, index=False, compression="gzip" if str(a.scored_output).endswith(".gz") else None); Path(a.meta_output).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"); print(json.dumps(meta, ensure_ascii=False, indent=2)); return
    files = sorted(glob.glob(a.scored_glob)); scored = pd.concat([pd.read_csv(f, dtype={"symbol":"string"}) for f in files], ignore_index=True)
    daily = v3.load_daily(Path(a.daily)); sessions = sorted(daily["date"].dropna().unique().tolist()); idx = {d:i for i,d in enumerate(sessions)}
    out = {"experiment_id":"CAUSAL-4H-MONSTER-V11-WEAK-REVERSAL-IGNITION-20260913", "period":a.period, "rows":int(len(scored)), "2026_outcomes_opened":False, "results":{}}
    for n in TOP_NS:
        chosen = select(scored, idx, n); m = v3.metrics(chosen, 0.005); m["passes_v11_gates"] = passes(m); m["cost0"] = v3.metrics(chosen,0); m["cost1pct"] = v3.metrics(chosen,0.01); out["results"][str(n)] = m
    Path(a.output).write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"); print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__": main()
