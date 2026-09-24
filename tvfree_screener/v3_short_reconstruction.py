#!/usr/bin/env python3
"""Reproducible TradingView-free V3 Short reconstruction (TEST ONLY).

This runner deliberately does NOT attempt to reproduce the historical Short V3
+5.42% result because its exact parameters were never committed.

Frozen research decision represented here:
  exact 45-feature monthly causal model
  -> relative top-decile 5BD head
  -> -10% loss-risk head
  -> prediction-day percentile normalization
  -> Core score = r_top10 - 2 * r_loss10
  -> daily best pick
  -> one-selection-day same-symbol cooldown

A contemporaneously observable market gate (median TSE 5-day return >= -1%) is
reported as a defensive supporting lane. Recent-outcome Meta and Attack are
explicitly inactive/rejected.

All evaluation uses next-session-open -> 5BD close. 2026 has already been
inspected in prior research and is reported only as contaminated fixed-side
evidence; no threshold is selected from 2026.

No Discord, Spreadsheet, TradingView, or production writes exist in this file.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

import run as base

OUT = Path("tvfree_screener/out")

# Frozen from pre-2026 research. Do not tune from 2026.
CORE_LOSS_PENALTY = 2.0
DEFENSIVE_MED_RET5_MIN = -0.01
PRICE_CAP = 1000.0
MODEL_START = pd.Timestamp("2025-01-01")
MODEL_END = pd.Timestamp("2026-08-31")

REPORT_PERIODS = {
    "2025H1_development": ("2025-01-01", "2025-06-30"),
    "2025H2_validation": ("2025-07-01", "2025-12-31"),
    "2026_MarAug_contaminated_fixed": ("2026-03-01", "2026-08-31"),
}


def exact_model(seed: int = 42) -> XGBClassifier:
    """Same model shape as the original exact-feature prototype."""
    return XGBClassifier(
        n_estimators=180,
        max_depth=3,
        learning_rate=0.04,
        subsample=0.80,
        colsample_bytree=0.80,
        min_child_weight=25,
        reg_lambda=5,
        reg_alpha=0.2,
        objective="binary:logistic",
        eval_metric="logloss",
        n_jobs=4,
        random_state=seed,
    )


def eligible_exact(features: pd.DataFrame) -> pd.DataFrame:
    """Apply the historical Short universe constraints before modelling."""
    q = base.eligible_rows(features, price_cap=PRICE_CAP).copy()
    q = q.dropna(subset=["target5_no", "target_end_date"])
    q["date"] = pd.to_datetime(q["date"])
    q["target_end_date"] = pd.to_datetime(q["target_end_date"])
    return q


def attach_training_heads(q: pd.DataFrame) -> pd.DataFrame:
    """Create a cross-sectional future-return top-decile label.

    The label is only consumed after target_end_date is before a prediction
    month, so future information never leaks into a prediction period.
    """
    out = q.copy()
    out["target5_pctile"] = out.groupby("date")["target5_no"].rank(
        pct=True, method="average"
    )
    out["y_top10"] = (out["target5_pctile"] >= 0.90).astype(int)
    out["y_loss10"] = (out["target5_no"] <= -0.10).astype(int)
    return out


def daily_percentile(s: pd.Series) -> pd.Series:
    if len(s) <= 1:
        return pd.Series(np.ones(len(s)), index=s.index, dtype=float)
    return s.rank(pct=True, method="average")


def fit_month(train: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
    out = pred.copy()
    for target, col in [("y_top10", "p_top10"), ("y_loss10", "p_loss10")]:
        y = train[target].astype(int)
        # If a degenerate training target ever occurs, fail loudly rather than
        # silently changing model semantics.
        if y.nunique() < 2:
            raise RuntimeError(f"degenerate training target {target}")
        model = exact_model()
        model.fit(train[base.FEATURES], y, verbose=False)
        out[col] = model.predict_proba(out[base.FEATURES])[:, 1]

    # Retrained raw probabilities are not comparable across months. Normalize
    # cross-sectionally on each observable prediction day.
    out["r_top10"] = out.groupby("date")["p_top10"].transform(daily_percentile)
    out["r_loss10"] = out.groupby("date")["p_loss10"].transform(daily_percentile)
    out["core_score"] = out["r_top10"] - CORE_LOSS_PENALTY * out["r_loss10"]
    return out


def causal_monthly_scores(q: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for period in pd.period_range(MODEL_START.to_period("M"), MODEL_END.to_period("M"), freq="M"):
        start = period.start_time
        end = period.end_time.normalize()
        train = q[(q["target_end_date"] < start)].copy()
        pred = q[(q["date"] >= start) & (q["date"] <= end)].copy()
        train = train.dropna(subset=base.FEATURES + ["y_top10", "y_loss10"])
        pred = pred.dropna(subset=base.FEATURES)
        if len(train) < 10000 or pred.empty:
            print(f"skip {period}: train={len(train)} pred={len(pred)}")
            continue
        print(f"fit {period}: train={len(train)} pred={len(pred)}")
        scored = fit_month(train, pred)
        scored["model_period"] = str(period)
        parts.append(scored)
    if not parts:
        raise RuntimeError("no Short monthly prediction periods generated")
    return pd.concat(parts, ignore_index=True)


def select_daily_best(scored: pd.DataFrame) -> pd.DataFrame:
    """Select one pick/day and block the same symbol on the next selection day."""
    rows = []
    prev_selected: set[str] = set()
    for _, day in scored.sort_values(
        ["date", "core_score"], ascending=[True, False]
    ).groupby("date", sort=True):
        chosen = None
        for _, row in day.sort_values("core_score", ascending=False).iterrows():
            if str(row["symbol"]) in prev_selected:
                continue
            chosen = row
            break
        prev_selected = {str(chosen["symbol"])} if chosen is not None else set()
        if chosen is not None:
            rows.append(chosen)
    return pd.DataFrame(rows).reset_index(drop=True)


def stats(x: pd.Series) -> dict:
    x = pd.to_numeric(x, errors="coerce").dropna()
    if x.empty:
        return {"n": 0}
    return {
        "n": int(len(x)),
        "mean": float(x.mean()),
        "median": float(x.median()),
        "win_rate": float((x > 0).mean()),
        "hit5_rate": float((x >= 0.05).mean()),
        "hit10_rate": float((x >= 0.10).mean()),
        "hit20_rate": float((x >= 0.20).mean()),
        "loss10_rate": float((x <= -0.10).mean()),
        "max": float(x.max()),
        "min": float(x.min()),
    }


def period_stats(picks: pd.DataFrame) -> dict:
    out = {}
    for name, (a, b) in REPORT_PERIODS.items():
        z = picks[(picks["date"] >= a) & (picks["date"] <= b)]
        out[name] = stats(z["target5_no"])
    return out


def monthly_stats(picks: pd.DataFrame, a: str, b: str) -> dict:
    z = picks[(picks["date"] >= a) & (picks["date"] <= b)].copy()
    out = {}
    for month, g in z.groupby(z["date"].dt.to_period("M")):
        out[str(month)] = stats(g["target5_no"])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default="tvfree_screener/out/tse_daily.csv")
    args = ap.parse_args()

    raw = pd.read_csv(args.cache, parse_dates=["date"], dtype={"symbol": str})
    for c in ["open", "high", "low", "close", "volume"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw = raw.dropna(subset=["date", "symbol", "close"])

    features = base.build_features(raw)
    eligible = attach_training_heads(eligible_exact(features))
    scored = causal_monthly_scores(eligible)
    core = select_daily_best(scored)
    defensive = core[core["med_ret5"] >= DEFENSIVE_MED_RET5_MIN].copy()

    report = {
        "status": "research_only_no_production_writes",
        "entry": "next_session_open_to_5BD_close",
        "historical_old_short_reference": {
            "reproducible": False,
            "2026_MarAug": {
                "n": 29,
                "mean": 0.0542,
                "median": 0.0206,
                "win_rate": 0.655,
                "hit10_rate": 0.138,
                "loss10_rate": 0.069,
            },
            "note": "Exact old parameters were never committed; this runner does not recreate them.",
        },
        "frozen_reconstruction": {
            "features": "same 45 run.py features",
            "model": "monthly causal XGBClassifier 180/depth3/lr0.04/min_child25/lambda5/alpha0.2",
            "heads": ["relative top-decile next-open->5BD return", "-10% next-open->5BD loss"],
            "normalization": "prediction-day percentile ranks",
            "core_score": "r_top10 - 2.0*r_loss10",
            "cooldown": "same symbol blocked on next trading selection day only",
            "recent_outcome_meta": "rejected_inactive",
            "attack": "none_unaccepted",
        },
        "core": {
            "periods": period_stats(core),
            "2026_MarAug_monthly": monthly_stats(core, "2026-03-01", "2026-08-31"),
        },
        "defensive_market_gate": {
            "rule": "med_ret5 >= -0.01, contemporaneously observable at signal close",
            "role": "supporting_lane_only_not_primary",
            "periods": period_stats(defensive),
            "2026_MarAug_monthly": monthly_stats(defensive, "2026-03-01", "2026-08-31"),
        },
        "notes": [
            "Core loss penalty 2.0 and defensive market gate -1% were frozen from pre-2026 research.",
            "2026 is contaminated fixed-side evidence and is never used for selection in this runner.",
            "No active Attack or recent-outcome Meta is included because those lanes failed validation.",
        ],
    }

    OUT.mkdir(parents=True, exist_ok=True)
    keep = [
        "date", "symbol", "prev_close", "close", "volume", "med_ret5",
        "r_top10", "r_loss10", "core_score", "next_open", "target5_no",
        "target_end_date", "model_period",
    ]
    core[[c for c in keep if c in core.columns]].to_csv(
        OUT / "v3_short_reconstruction_core.csv", index=False
    )
    defensive[[c for c in keep if c in defensive.columns]].to_csv(
        OUT / "v3_short_reconstruction_defensive.csv", index=False
    )
    with open(OUT / "v3_short_reconstruction_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
