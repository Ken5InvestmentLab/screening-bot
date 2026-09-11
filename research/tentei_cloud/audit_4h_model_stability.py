#!/usr/bin/env python3
"""Seed-stability audit for the fixed 4H-only Monster rank.

No model/hyperparameter/threshold tuning. Uses the same TRAIN/VALIDATION split
and TRAIN-only feasible target selection as mtf_monster_model.py.
2026 is not scored.
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from reconstruct_4h_from_1h import load
from mtf_monster_model import (
    TRAIN_START, TRAIN_END, VAL_START, VAL_END,
    FOUR_H_FEATURES, make_candidate_pool, choose_target,
    fit_rf, score, select, metrics,
)

SEEDS = [11, 23, 42, 71, 97, 131, 211]


def ids(q: pd.DataFrame) -> set[str]:
    return set(
        q["date"].astype(str) + "|" +
        q["session"].astype(str) + "|" +
        q["symbol"].astype(str)
    )


def jaccard(a: set[str], b: set[str]) -> float:
    u = a | b
    return len(a & b) / len(u) if u else 1.0


def bootstrap_ci(values: pd.Series, reps: int = 10000, seed: int = 20260911):
    x = values.dropna().to_numpy(dtype=float)
    if len(x) == 0:
        return {"mean": None, "lo": None, "hi": None}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(reps, len(x)))
    means = x[idx].mean(axis=1)
    return {
        "mean": float(x.mean()),
        "lo": float(np.quantile(means, 0.025)),
        "hi": float(np.quantile(means, 0.975)),
    }


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

    rows = []
    sel = {"Watch": {}, "Prime": {}}
    importance = []
    monthly = []

    base = metrics("BASE", "TAIL_POOL", "VALIDATION", val, target)
    rows.append({"seed": -1, **base})

    for seed in SEEDS:
        model, med, q70, q90, pos, ntrain = fit_rf(train, FOUR_H_FEATURES, target, seed)
        v = val.copy()
        v["score"] = score(model, med, v, FOUR_H_FEATURES)
        for tier, thr in [("Watch", q70), ("Prime", q90)]:
            q = select(v, "score", thr)
            m = metrics("4H_ONLY", tier, "VALIDATION", q, target)
            rows.append({"seed": seed, "threshold": thr, **m})
            sel[tier][seed] = ids(q)
            md = pd.to_datetime(q["date"], errors="coerce")
            for month in sorted(md.dropna().dt.to_period("M").astype(str).unique()):
                z = q[md.dt.to_period("M").astype(str) == month]
                mm = metrics("4H_ONLY", tier, month, z, target)
                monthly.append({"seed": seed, **mm})

        for feat, imp in zip(FOUR_H_FEATURES, model.feature_importances_):
            importance.append({"seed": seed, "feature": feat, "importance": float(imp)})

    result = pd.DataFrame(rows)
    result.to_csv(out / "seed_metrics.csv", index=False)
    pd.DataFrame(monthly).to_csv(out / "seed_monthly_metrics.csv", index=False)

    pairs = []
    for tier in ["Watch", "Prime"]:
        for aseed, bseed in itertools.combinations(SEEDS, 2):
            pairs.append({
                "tier": tier,
                "seed_a": aseed,
                "seed_b": bseed,
                "jaccard": jaccard(sel[tier][aseed], sel[tier][bseed]),
            })
    pairdf = pd.DataFrame(pairs)
    pairdf.to_csv(out / "seed_selection_jaccard.csv", index=False)

    imp = pd.DataFrame(importance)
    imp_summary = (
        imp.groupby("feature")["importance"]
        .agg(["mean", "std", "min", "max"])
        .sort_values("mean", ascending=False)
        .reset_index()
    )
    imp.to_csv(out / "seed_feature_importance.csv", index=False)
    imp_summary.to_csv(out / "seed_feature_importance_summary.csv", index=False)

    stability = []
    for tier in ["Watch", "Prime"]:
        z = result[(result["model"] == "4H_ONLY") & (result["tier"] == tier)]
        stability.append({
            "tier": tier,
            "seeds": len(z),
            "n_min": int(z["n"].min()),
            "n_max": int(z["n"].max()),
            "mean_return_avg": float(z["mean"].mean()),
            "mean_return_min": float(z["mean"].min()),
            "mean_return_max": float(z["mean"].max()),
            "median_return_avg": float(z["median"].mean()),
            "win_avg": float(z["win"].mean()),
            "ge10_avg": float(z["ge10"].mean()),
            "ge20_avg": float(z["ge20"].mean()),
            "le10_avg": float(z["le10"].mean()),
            "pairwise_jaccard_mean": float(pairdf[pairdf["tier"] == tier]["jaccard"].mean()),
            "pairwise_jaccard_min": float(pairdf[pairdf["tier"] == tier]["jaccard"].min()),
        })
    stab = pd.DataFrame(stability)
    stab.to_csv(out / "seed_stability_summary.csv", index=False)

    # Bootstrap only the fixed seed=42 selections; diagnostic only, no tuning.
    seed42 = {}
    model, med, q70, q90, _, _ = fit_rf(train, FOUR_H_FEATURES, target, 42)
    v = val.copy()
    v["score"] = score(model, med, v, FOUR_H_FEATURES)
    for tier, thr in [("Watch", q70), ("Prime", q90)]:
        q = select(v, "score", thr)
        seed42[tier] = {
            "n": int(len(q)),
            "bootstrap_mean_95ci": bootstrap_ci(q["ret5bd"], seed=20260911 + (0 if tier=="Watch" else 1)),
        }

    meta = {
        "raw_start": str(raw["date"].min()),
        "raw_end": str(raw["date"].max()),
        "train_n": int(len(train)),
        "validation_n": int(len(val)),
        "target_threshold": target,
        "train_target_counts": counts,
        "seeds": SEEDS,
        "seed42_bootstrap": seed42,
        "production_writes": False,
        "2026_scored": False,
    }
    (out / "seed_stability_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print("\nSEED METRICS")
    print(result.to_string(index=False))
    print("\nSTABILITY SUMMARY")
    print(stab.to_string(index=False))
    print("\nFEATURE IMPORTANCE")
    print(imp_summary.to_string(index=False))


if __name__ == "__main__":
    main()
