from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

import no_tv_v10_standalone as base
import no_tv_v11_independent_selector as v11
import no_tv_v11_1_risk_guard as risk
import no_tv_v17_unbiased_rolling as v17
import no_tv_v18_rank_rolling as v18
import no_tv_v25_consensus_expansion as v25

FOLDS = v17.FOLDS
SAMPLE_CUTOFF = v17.SAMPLE_CUTOFF
GUARDS = v25.GUARDS
SESSIONS = v25.SESSIONS
COOLDOWNS = v25.COOLDOWNS
THRESHOLDS = [.85, .90, .93, .95, .97, .98]
TOPK = [1, 2]


def add_training_targets(train):
    x = train.copy()
    grp = ["date", "session"]
    x["future_rank"] = x.groupby(grp).perf_5bd.rank(pct=True, method="average")
    x["future_top20"] = (x.future_rank >= .80).astype(int)
    x["future_top10"] = (x.future_rank >= .90).astype(int)
    return x


def fit_attach(train, valid, test):
    cols = v11.features()
    tr = add_training_targets(train)
    xx = tr[cols].astype(float)
    y20 = tr.future_top20.to_numpy(int)
    y10 = tr.future_top10.to_numpy(int)
    yr = tr.future_rank.to_numpy(float)

    m20 = HistGradientBoostingClassifier(
        learning_rate=.035, max_iter=240, max_leaf_nodes=15,
        min_samples_leaf=70, l2_regularization=4.0, random_state=271,
    )
    m10 = HistGradientBoostingClassifier(
        learning_rate=.035, max_iter=260, max_leaf_nodes=15,
        min_samples_leaf=55, l2_regularization=5.0, random_state=272,
    )
    mr = HistGradientBoostingRegressor(
        learning_rate=.03, max_iter=240, max_leaf_nodes=15,
        min_samples_leaf=75, l2_regularization=4.0, random_state=273,
    )
    m20.fit(xx, y20, sample_weight=base.balanced_weights(y20))
    m10.fit(xx, y10, sample_weight=base.balanced_weights(y10))
    mr.fit(xx, yr)

    def attach(df):
        o = df.copy()
        z = o[cols].astype(float)
        o["p_top20"] = m20.predict_proba(z)[:, 1]
        o["p_top10"] = m10.predict_proba(z)[:, 1]
        o["pred_rank"] = mr.predict(z)
        return o
    return attach(valid), attach(test)


def add_relative_consensus(df, guard):
    x = risk.apply_guard(df, guard).copy()
    if x.empty:
        return x
    grp = ["date", "session"]
    x["r20"] = x.groupby(grp).p_top20.rank(pct=True, method="average")
    x["r10"] = x.groupby(grp).p_top10.rank(pct=True, method="average")
    x["rrank"] = x.groupby(grp).pred_rank.rank(pct=True, method="average")
    heads = x[["r20", "r10", "rrank"]]
    x["rel_min"] = heads.min(axis=1)
    x["rel_geo"] = (x.r20 * x.r10 * x.rrank).pow(1 / 3)
    x["rel_harm"] = 3.0 / (1.0 / x.r20.clip(lower=1e-6) + 1.0 / x.r10.clip(lower=1e-6) + 1.0 / x.rrank.clip(lower=1e-6))
    x["rel_spread"] = heads.mean(axis=1) - .5 * (heads.max(axis=1) - heads.min(axis=1))
    return x


def apply_policy(df, p):
    x = add_relative_consensus(df, p["guard"])
    if x.empty:
        return x
    col = p["score_col"]
    x = x[x[col] >= float(p["threshold"])].copy()
    x = v18.session_filter(x, p["sessions"])
    return v25.causal_topk(x, col, int(p["topk"]), int(p["cooldown_days"]))


def choose_policy(valid):
    trials = []
    for guard in GUARDS:
        scored = add_relative_consensus(valid, guard)
        for col in ("rel_min", "rel_geo", "rel_harm", "rel_spread"):
            for th in THRESHOLDS:
                q = scored[scored[col] >= th].copy()
                for sm in SESSIONS:
                    sf = v18.session_filter(q, sm)
                    for topk in TOPK:
                        for cd in COOLDOWNS:
                            sel = v25.causal_topk(sf, col, topk, cd)
                            st = risk.risk_stats(sel)
                            h1, h2 = v25.split_half_stats(sel)
                            o = v25.objective(st, h1, h2)
                            trials.append({
                                "score_col": col, "threshold": th, "guard": guard,
                                "sessions": sm, "topk": topk, "cooldown_days": cd,
                                "objective": float(o), "stats": st,
                                "half1": h1, "half2": h2,
                            })
    trials.sort(key=lambda r: (r["objective"], r["stats"]["n"]), reverse=True)
    return trials[0], trials


def evaluate(data, fold):
    train = data[data.date.between(fold["train_start"], fold["train_end"]) & data.perf_5bd.notna()].copy()
    valid = data[data.date.between(fold["valid_start"], fold["valid_end"]) & data.perf_5bd.notna()].copy()
    test = data[data.date.between(fold["test_start"], fold["test_end"]) & data.perf_5bd.notna()].copy()
    va, te = fit_attach(train, valid, test)
    best, trials = choose_policy(va)
    selected = apply_policy(te, best)
    return {
        "fold": fold["id"],
        "sizes": {"train": len(train), "valid": len(valid), "test": len(test)},
        "policy": best,
        "test": risk.risk_stats(selected),
        "selected": selected.assign(fold=fold["id"]),
        "validation_top": trials[:15],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", required=True)
    ap.add_argument("--watchlist-repo", required=True)
    ap.add_argument("--max-symbols", type=int, default=350)
    ap.add_argument("--max-workers", type=int, default=16)
    ap.add_argument("--output-dir", default="research_artifacts/v27_relative_target")
    a = ap.parse_args()

    teacher, wstat, data, yahoo, codes = v17.build_dataset(a)
    v18.verify_early_sample(a.watchlist_repo, codes)
    data = v11.enrich_cross_sectional(data)

    rows, parts = [], []
    for fold in FOLDS:
        print(f"evaluate V27 {fold['id']}", flush=True)
        r = evaluate(data, fold)
        parts.append(r.pop("selected"))
        rows.append(r)

    combined = risk.risk_stats(pd.concat(parts, ignore_index=True))
    result = {
        "scope": "V27 development rolling OOS. Leakage-free universe and intraday-causal 09/13 decisions. Targets are future 5BD cross-sectional ranks within the same date/session, trained on prior data only. Jun-Aug is reused development OOS, not pristine final holdout.",
        "sampling": {"cutoff": SAMPLE_CUTOFF, "max_symbols": a.max_symbols, "symbols": codes},
        "teacher_rows": len(teacher), "watchlists": wstat, "yahoo": yahoo,
        "folds": rows, "combined_test": combined, "current_champion": base.CHAMPION,
    }
    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "v27_relative_target.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"combined_test": combined, "folds": rows}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
