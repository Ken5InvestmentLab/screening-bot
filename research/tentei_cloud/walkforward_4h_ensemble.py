#!/usr/bin/env python3
"""Expanding walk-forward audit for fixed 4H ensemble tiers.

Research-only, no production writes.

Fixed after pre-2026 research:
- Candidate pool: reconstructed 4H TAIL gate.
- 4H-only features.
- 7 RF seeds.
- Classification target fixed at 5BD >= +7.5%.
- Watch = q65 of ensemble TRAIN OOB probability.
- Prime = q90 of ensemble TRAIN OOB probability.

Each fold trains only on candidates whose target_date is strictly before the
test period, so 5BD outcome labels do not leak across the boundary.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from reconstruct_4h_from_1h import load
from mtf_monster_model import FOUR_H_FEATURES, make_candidate_pool, fit_rf, score, metrics

SEEDS = [11, 23, 42, 71, 97, 131, 211]
TARGET = 0.075
WATCH_Q = 0.65
PRIME_Q = 0.90
MIN_TRAIN = 80
MIN_POS = 8

FOLDS = [
    ("2025H2", "2025-07-01", "2025-12-31"),
    ("2026_01_02", "2026-01-01", "2026-02-28"),
    ("2026_03_04", "2026-03-01", "2026-04-30"),
    ("2026_05_06", "2026-05-01", "2026-06-30"),
    ("2026_07_08", "2026-07-01", "2026-08-31"),
]


def fit_ensemble(train: pd.DataFrame):
    train_oob = []
    models = []
    for seed in SEEDS:
        # fit_rf accepts a target threshold and returns OOB probabilities.
        model, med, _, _, pos, ntrain = fit_rf(train, FOUR_H_FEATURES, TARGET, seed)
        oob = model.oob_decision_function_[:, 1]
        train_oob.append(oob)
        models.append((model, med))
    ensemble_oob = np.nanmean(np.column_stack(train_oob), axis=1)
    watch_thr = float(np.nanquantile(ensemble_oob, WATCH_Q))
    prime_thr = float(np.nanquantile(ensemble_oob, PRIME_Q))
    return models, watch_thr, prime_thr


def score_ensemble(models, frame: pd.DataFrame):
    ps = [score(model, med, frame, FOUR_H_FEATURES) for model, med in models]
    mat = np.column_stack(ps)
    return np.mean(mat, axis=1), np.std(mat, axis=1)


def summarize_selected(model_name, tier, period, frame):
    return metrics(model_name, tier, period, frame, TARGET)


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
    c["target_date_dt"] = pd.to_datetime(c["target_date"], errors="coerce")
    c["date_dt"] = pd.to_datetime(c["date"], errors="coerce")

    rows = []
    selected_rows = []
    fold_meta = []

    for fold, test_start, test_end in FOLDS:
        ts = pd.Timestamp(test_start)
        # Outcome label must have been known before the test begins.
        train = c[
            (c["date_dt"] >= pd.Timestamp("2024-11-01"))
            & (c["target_date_dt"] < ts)
        ].copy()
        test = c[
            (c["date_dt"] >= pd.Timestamp(test_start))
            & (c["date_dt"] <= pd.Timestamp(test_end))
        ].copy()

        pos = int((train["ret5bd"] >= TARGET).sum())
        neg = int(len(train) - pos)
        fm = {
            "fold": fold,
            "test_start": test_start,
            "test_end": test_end,
            "train_n": int(len(train)),
            "train_pos": pos,
            "train_neg": neg,
            "test_n": int(len(test)),
        }

        if len(train) < MIN_TRAIN or pos < MIN_POS or neg < MIN_POS or test.empty:
            fm["status"] = "SKIP"
            fm["reason"] = "insufficient_train_classes_or_test"
            fold_meta.append(fm)
            continue

        models, watch_thr, prime_thr = fit_ensemble(train)
        test = test.copy()
        test["ensemble_score"], test["score_std"] = score_ensemble(models, test)
        test["fold"] = fold
        test["watch_threshold"] = watch_thr
        test["prime_threshold"] = prime_thr

        fm.update({
            "status": "OK",
            "watch_threshold": watch_thr,
            "prime_threshold": prime_thr,
        })
        fold_meta.append(fm)

        rows.append(summarize_selected("BASE", "TAIL_POOL", fold, test))

        watch = test[test["ensemble_score"] >= watch_thr].copy()
        watch["tier"] = "Watch"
        prime = test[test["ensemble_score"] >= prime_thr].copy()
        prime["tier"] = "Prime"

        rows.append(summarize_selected("4H_WALKFORWARD", "Watch", fold, watch))
        rows.append(summarize_selected("4H_WALKFORWARD", "Prime", fold, prime))
        selected_rows.extend([watch, prime])

    fold_df = pd.DataFrame(fold_meta)
    fold_df.to_csv(out / "walkforward_folds.csv", index=False)

    per_fold = pd.DataFrame(rows)
    per_fold.to_csv(out / "walkforward_metrics_by_fold.csv", index=False)

    if selected_rows:
        sels = pd.concat(selected_rows, ignore_index=True, sort=False)
    else:
        sels = pd.DataFrame()

    # Aggregate out-of-sample rows; Prime is intentionally a subset of Watch.
    agg_rows = []
    base_parts = []
    for fold, test_start, test_end in FOLDS:
        ts = pd.Timestamp(test_start)
        te = pd.Timestamp(test_end)
        base_parts.append(c[(c["date_dt"] >= ts) & (c["date_dt"] <= te)].copy())
    base_all = pd.concat(base_parts, ignore_index=True).drop_duplicates(["symbol","date","session"])
    agg_rows.append(metrics("BASE", "TAIL_POOL", "ALL_OOS", base_all, TARGET))

    if not sels.empty:
        for tier in ["Watch", "Prime"]:
            z = sels[sels["tier"] == tier].copy()
            z = z.drop_duplicates(["symbol","date","session","fold"])
            agg_rows.append(metrics("4H_WALKFORWARD", tier, "ALL_OOS", z, TARGET))

    aggregate = pd.DataFrame(agg_rows)
    aggregate.to_csv(out / "walkforward_aggregate.csv", index=False)

    if not sels.empty:
        keep = [
            "fold","tier","date","session","session_time","last_ts","symbol",
            "open","high","low","close","volume","range_pct","rsi12","atr14_pct",
            "macd_hist","ema75","bb_mid","target_date","target_close","ret5bd",
            "ensemble_score","score_std","watch_threshold","prime_threshold",
        ]
        sels[[x for x in keep if x in sels.columns]].sort_values(
            ["fold","tier","ensemble_score"], ascending=[True,True,False]
        ).to_csv(out / "walkforward_selected.csv", index=False)

        monthly = []
        for tier in ["Watch","Prime"]:
            z = sels[sels["tier"] == tier].copy()
            md = pd.to_datetime(z["date"], errors="coerce")
            for month in sorted(md.dropna().dt.to_period("M").astype(str).unique()):
                zz = z[md.dt.to_period("M").astype(str) == month]
                monthly.append(metrics("4H_WALKFORWARD", tier, month, zz, TARGET))
        pd.DataFrame(monthly).to_csv(out / "walkforward_monthly.csv", index=False)

    meta = {
        "raw_start": str(raw["date"].min()),
        "raw_end": str(raw["date"].max()),
        "candidate_pool_n": int(len(c)),
        "target_threshold": TARGET,
        "watch_quantile": WATCH_Q,
        "prime_quantile": PRIME_Q,
        "seeds": SEEDS,
        "folds": FOLDS,
        "leakage_guard": "training target_date strictly before test_start",
        "production_writes": False,
        "warning": "2025H2 and 2026 have been inspected in earlier research; this is a causal walk-forward audit, not a pristine holdout.",
    }
    (out / "walkforward_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print("\nFOLDS")
    print(fold_df.to_string(index=False))
    print("\nPER-FOLD METRICS")
    print(per_fold.to_string(index=False))
    print("\nAGGREGATE OOS")
    print(aggregate.to_string(index=False))


if __name__ == "__main__":
    main()
