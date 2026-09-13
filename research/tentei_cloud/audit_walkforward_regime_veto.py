#!/usr/bin/env python3
"""Causal previous-day market-regime veto audit for fixed 4H walk-forward tiers.

Research-only. No production writes.

This audit intentionally does NOT retune the 4H model or its tier quantiles.
It reconstructs the exact fixed walk-forward 4H ensemble, attaches only prior-
trading-day market context, and compares a tiny preregistered set of interpretable
vetoes. Missing regime context is fail-open (candidate is kept) so data gaps are
not mistaken for a bearish regime.

Important: the 2025H2/2026 outcome blocks have already been inspected in prior
research. Results are retrospective causal evidence, not a pristine holdout.
No veto is promoted automatically from this script.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from reconstruct_4h_from_1h import load
from mtf_monster_model import make_candidate_pool, metrics
from walkforward_4h_ensemble import (
    FOLDS,
    TARGET,
    MIN_TRAIN,
    MIN_POS,
    fit_ensemble,
    score_ensemble,
)
from audit_market_regime import build_market_regime, attach_regime


VETO_DEFINITIONS = {
    "NONE": "keep all fixed 4H tier selections",
    "VETO_RISK_OFF_MOMENTUM": (
        "exclude only when prior-day median_ret5<=0 AND breadth20_delta5<=0"
    ),
    "VETO_WEAK_NARROW_FALLING": (
        "exclude only when prior-day median_ret5<=0 AND breadth20<0.50 "
        "AND breadth20_delta5<=0"
    ),
    "VETO_BREADTH_BREAKDOWN": (
        "exclude only when prior-day breadth20<0.50 AND breadth20_delta5<=0"
    ),
}


def veto_masks(x: pd.DataFrame) -> dict[str, pd.Series]:
    idx = x.index
    known_r5 = x["median_ret5"].notna()
    known_b20 = x["breadth20"].notna()
    known_delta = x["breadth20_delta5"].notna()

    weak = known_r5 & (x["median_ret5"] <= 0)
    narrow = known_b20 & (x["breadth20"] < 0.50)
    falling = known_delta & (x["breadth20_delta5"] <= 0)

    # Fail-open on missing regime components: a veto only fires when every
    # component required by that veto is observed and the full condition holds.
    risk_off = weak & falling
    weak_narrow_falling = weak & narrow & falling
    breadth_breakdown = narrow & falling

    return {
        "NONE": pd.Series(True, index=idx),
        "VETO_RISK_OFF_MOMENTUM": ~risk_off,
        "VETO_WEAK_NARROW_FALLING": ~weak_narrow_falling,
        "VETO_BREADTH_BREAKDOWN": ~breadth_breakdown,
    }


def add_context(selected: pd.DataFrame, regime: pd.DataFrame) -> pd.DataFrame:
    if selected.empty:
        return selected.copy()
    x = attach_regime(selected, regime)
    x["regime_context_complete"] = (
        x["median_ret5"].notna()
        & x["breadth20"].notna()
        & x["breadth20_delta5"].notna()
    )
    return x


def evaluate_block(
    rows: list[dict],
    model: str,
    tier: str,
    period: str,
    frame: pd.DataFrame,
) -> None:
    base_n = int(len(frame))
    masks = veto_masks(frame)
    for policy, mask in masks.items():
        q = frame[mask.fillna(True)].copy()
        m = metrics(model, f"{tier}:{policy}", period, q, TARGET)
        m["tier_name"] = tier
        m["veto_policy"] = policy
        m["base_tier_n"] = base_n
        m["coverage"] = (len(q) / base_n) if base_n else None
        m["regime_context_complete_n"] = int(frame.get("regime_context_complete", pd.Series(False, index=frame.index)).sum())
        rows.append(m)


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

    regime = build_market_regime(raw)

    metric_rows: list[dict] = []
    selected_parts: list[pd.DataFrame] = []
    fold_meta: list[dict] = []

    for fold, test_start, test_end in FOLDS:
        ts = pd.Timestamp(test_start)
        te = pd.Timestamp(test_end)

        train = c[
            (c["date_dt"] >= pd.Timestamp("2024-11-01"))
            & (c["target_date_dt"] < ts)
        ].copy()
        test = c[(c["date_dt"] >= ts) & (c["date_dt"] <= te)].copy()

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
            "watch_threshold": float(watch_thr),
            "prime_threshold": float(prime_thr),
        })
        fold_meta.append(fm)

        for tier, threshold in [("Watch", watch_thr), ("Prime", prime_thr)]:
            z = test[test["ensemble_score"] >= threshold].copy()
            z["tier_name"] = tier
            z = add_context(z, regime)
            evaluate_block(metric_rows, "4H_WALKFORWARD_REGIME", tier, fold, z)
            selected_parts.append(z)

    fold_df = pd.DataFrame(fold_meta)
    fold_df.to_csv(out / "walkforward_regime_folds.csv", index=False)

    by_fold = pd.DataFrame(metric_rows)
    by_fold.to_csv(out / "walkforward_regime_by_fold.csv", index=False)

    if selected_parts:
        selected = pd.concat(selected_parts, ignore_index=True, sort=False)
        selected = selected.drop_duplicates(["fold", "tier_name", "symbol", "date", "session"])
    else:
        selected = pd.DataFrame()

    aggregate_rows: list[dict] = []
    if not selected.empty:
        for tier in ["Watch", "Prime"]:
            z = selected[selected["tier_name"] == tier].copy()
            evaluate_block(
                aggregate_rows,
                "4H_WALKFORWARD_REGIME",
                tier,
                "ALL_OOS",
                z,
            )

        keep = [
            "fold", "tier_name", "date", "session", "session_time", "last_ts",
            "symbol", "close", "ret5bd", "ensemble_score", "score_std",
            "watch_threshold", "prime_threshold", "regime_date",
            "median_ret1", "median_ret5", "median_ret20", "adv_frac",
            "breadth5", "breadth20", "breadth20_delta5",
            "median_abs_ret1", "regime_context_complete",
        ]
        selected[[k for k in keep if k in selected.columns]].sort_values(
            ["fold", "tier_name", "date", "symbol"]
        ).to_csv(out / "walkforward_regime_selected_context.csv", index=False)

    aggregate = pd.DataFrame(aggregate_rows)

    # Add explicit deltas versus NONE within each tier for easier review.
    if not aggregate.empty:
        baseline = (
            aggregate[aggregate["veto_policy"] == "NONE"]
            .set_index("tier_name")[["mean", "median", "win", "ge10", "ge20", "le10", "top3_removed", "n"]]
        )
        for metric in ["mean", "median", "win", "ge10", "ge20", "le10", "top3_removed"]:
            aggregate[f"delta_{metric}_vs_none"] = aggregate.apply(
                lambda r: (
                    r[metric] - baseline.loc[r["tier_name"], metric]
                    if r["tier_name"] in baseline.index
                    and pd.notna(r.get(metric))
                    and pd.notna(baseline.loc[r["tier_name"], metric])
                    else np.nan
                ),
                axis=1,
            )
        aggregate["delta_n_vs_none"] = aggregate.apply(
            lambda r: (
                r["n"] - baseline.loc[r["tier_name"], "n"]
                if r["tier_name"] in baseline.index else np.nan
            ),
            axis=1,
        )

    aggregate.to_csv(out / "walkforward_regime_aggregate.csv", index=False)

    meta = {
        "raw_start": str(raw["date"].min()),
        "raw_end": str(raw["date"].max()),
        "candidate_pool_n": int(len(c)),
        "target_threshold": TARGET,
        "fixed_walkforward_folds": FOLDS,
        "fixed_veto_definitions": VETO_DEFINITIONS,
        "regime_information_timing": "previous trading day only",
        "missing_regime_policy": "fail-open; veto fires only when all required components are observed",
        "selection_policy": "exact fixed 4H walk-forward ensemble Watch/Prime; no model or quantile retuning",
        "status": "RETROSPECTIVE_CAUSAL_EXPLORATION_ONLY",
        "production_writes": False,
        "warning": (
            "2025H2 and 2026 outcomes were already inspected in earlier research. "
            "Use this audit to nominate at most one forward-test veto; do not claim pristine validation."
        ),
    }
    (out / "walkforward_regime_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print("\nFOLDS")
    print(fold_df.to_string(index=False))
    print("\nBY FOLD")
    print(by_fold.to_string(index=False))
    print("\nAGGREGATE")
    print(aggregate.to_string(index=False))


if __name__ == "__main__":
    main()
