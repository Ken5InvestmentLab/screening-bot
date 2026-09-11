#!/usr/bin/env python3
"""7-seed ensemble audit for the fixed 4H-only Monster rank.

Exploratory pre-2026 research only.
- Same reconstructed 4H candidate pool and TRAIN/VALIDATION split.
- Same TRAIN-only feasible target.
- Average 7 RandomForest probabilities to reduce seed noise.
- Tier thresholds are percentiles of the ensemble TRAIN OOB score only.
- q60..q90 sweep is diagnostic; do not call the best validation row final.
- 2026 is not scored.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from reconstruct_4h_from_1h import load
from mtf_monster_model import (
    TRAIN_START, TRAIN_END, VAL_START, VAL_END,
    FOUR_H_FEATURES, make_candidate_pool, choose_target,
    fit_rf, score, metrics,
)

SEEDS = [11, 23, 42, 71, 97, 131, 211]
QUANTILES = [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", action="append", required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)

    raw = load(a.inputs)
    c = make_candidate_pool(raw)
    c = c[c["ret5bd"].notna()].copy()
    train = c[(c["date"] >= TRAIN_START) & (c["date"] <= TRAIN_END)].copy()
    val = c[(c["date"] >= VAL_START) & (c["date"] <= VAL_END)].copy()
    target, counts = choose_target(train)

    train_oob = []
    val_scores = []
    feature_importance = []

    for seed in SEEDS:
        model, med, _, _, _, _ = fit_rf(train, FOUR_H_FEATURES, target, seed)

        X = train[FOUR_H_FEATURES].replace([np.inf, -np.inf], np.nan).copy()
        X = X.fillna(med).fillna(0.0)
        oob = model.oob_decision_function_[:, 1]
        train_oob.append(oob)

        val_scores.append(score(model, med, val, FOUR_H_FEATURES))
        for feat, imp in zip(FOUR_H_FEATURES, model.feature_importances_):
            feature_importance.append({"seed": seed, "feature": feat, "importance": float(imp)})

    train_mat = np.column_stack(train_oob)
    val_mat = np.column_stack(val_scores)
    train["ensemble_oob"] = np.nanmean(train_mat, axis=1)
    val["ensemble_score"] = np.mean(val_mat, axis=1)
    val["score_std"] = np.std(val_mat, axis=1)
    val["score_min"] = np.min(val_mat, axis=1)
    val["score_max"] = np.max(val_mat, axis=1)

    rows = [metrics("BASE", "TAIL_POOL", "VALIDATION", val, target)]
    thresholds = {}
    for q in QUANTILES:
        thr = float(train["ensemble_oob"].quantile(q))
        thresholds[f"q{int(q*100)}"] = thr
        z = val[val["ensemble_score"] >= thr].copy()
        m = metrics("4H_ENSEMBLE", f"q{int(q*100)}", "VALIDATION", z, target)
        m["threshold"] = thr
        m["avg_score_std"] = float(z["score_std"].mean()) if len(z) else None
        rows.append(m)

    summary = pd.DataFrame(rows)
    summary.to_csv(out / "ensemble_quantile_sweep.csv", index=False)

    monthly = []
    for q in QUANTILES:
        tier = f"q{int(q*100)}"
        thr = thresholds[tier]
        z = val[val["ensemble_score"] >= thr].copy()
        md = pd.to_datetime(z["date"], errors="coerce")
        for month in sorted(md.dropna().dt.to_period("M").astype(str).unique()):
            zz = z[md.dt.to_period("M").astype(str) == month]
            mm = metrics("4H_ENSEMBLE", tier, month, zz, target)
            mm["threshold"] = thr
            monthly.append(mm)
    pd.DataFrame(monthly).to_csv(out / "ensemble_monthly.csv", index=False)

    # Save validation candidates so later research can inspect score separation without rerunning.
    keep = [
        "date","session","session_time","last_ts","symbol","open","high","low","close","volume",
        "range_pct","rsi12","atr14_pct","macd_hist","ema75","bb_mid","target_date","target_close","ret5bd",
        "ensemble_score","score_std","score_min","score_max"
    ]
    val[[x for x in keep if x in val.columns]].sort_values("ensemble_score", ascending=False).to_csv(
        out / "ensemble_validation_candidates.csv", index=False
    )

    imp = pd.DataFrame(feature_importance)
    imp_summary = (
        imp.groupby("feature")["importance"]
        .agg(["mean","std","min","max"])
        .sort_values("mean", ascending=False)
        .reset_index()
    )
    imp_summary.to_csv(out / "ensemble_feature_importance.csv", index=False)

    meta = {
        "raw_start": str(raw["date"].min()),
        "raw_end": str(raw["date"].max()),
        "train_n": int(len(train)),
        "validation_n": int(len(val)),
        "target_threshold": target,
        "train_target_counts": counts,
        "seeds": SEEDS,
        "quantiles": QUANTILES,
        "thresholds": thresholds,
        "2026_scored": False,
        "production_writes": False,
        "warning": "Validation has already been inspected. Quantile sweep is exploratory, not a fresh holdout.",
    }
    (out / "ensemble_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print("\nENSEMBLE QUANTILE SWEEP")
    print(summary.to_string(index=False))
    print("\nFEATURE IMPORTANCE")
    print(imp_summary.to_string(index=False))


if __name__ == "__main__":
    main()
