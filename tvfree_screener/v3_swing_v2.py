#!/usr/bin/env python3
"""TV-Free V3 Swing v2 research runner (TEST ONLY).

Promising 10BD architecture discovered after rejecting whole-universe rankers,
absolute probability thresholds, outcome-only Meta gates, and Deep Reversal.

Pipeline:
  MomCross transition event
  -> causal semiannual event-quality retraining
  -> model-output empirical CDF normalization on the training sample
  -> daily best event
  -> Breadth Meta (>= 40% of universe above MA20)
  -> locked quality gate score_R >= 0.20
  -> one-trading-selection-day same-symbol cooldown

The 0.20 quality threshold is locked from pre-2026 development/validation.
2026 has already been inspected in this research project and is therefore
reported as contaminated fixed-side evidence, not a pristine holdout.

No Discord/Sheets/production writes are present in this file.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBClassifier, XGBRegressor

import v3_swing as base

OUT = Path("tvfree_screener/out")

# Frozen research constants. Do not tune from 2026 results.
BREADTH_MA20_MIN = 0.40
LOCKED_SCORE_R_MIN = 0.20
THRESHOLD_SWEEP = [-0.50, -0.25, 0.00, 0.10, 0.20, 0.30]
MIN_HALF_YEAR_N = 30

FEATURES = [
    "ret1", "ret5", "ret10", "ret20", "ret40",
    "ma5_gap", "ma20_gap", "ma40_gap",
    "volr5", "volr20", "volr40",
    "rsi5", "rsi14", "atr14p", "pos20", "pos60",
    "prev_ret5", "prev_volr20", "prev_rsi5", "prev_pos20", "prev_ma20_gap",
    "breadth_ret1_pos", "med_ret1", "breadth_ma20",
]

PREDICTION_PERIODS = [
    ("2025H1", "2025-01-01", "2025-06-30"),
    ("2025H2", "2025-07-01", "2025-12-31"),
    ("2026H1", "2026-01-01", "2026-06-30"),
    ("2026H2", "2026-07-01", "2026-12-31"),
]

REPORT_PERIODS = {
    "2025H1_development": ("2025-01-01", "2025-06-30"),
    "2025H2_validation": ("2025-07-01", "2025-12-31"),
    "2026_MarAug_contaminated": ("2026-03-01", "2026-08-31"),
}


def quality_regressor() -> XGBRegressor:
    return XGBRegressor(
        n_estimators=140,
        max_depth=2,
        learning_rate=0.035,
        subsample=0.80,
        colsample_bytree=0.80,
        min_child_weight=12,
        reg_lambda=8,
        reg_alpha=0.5,
        objective="reg:squarederror",
        n_jobs=4,
        random_state=42,
    )


def loss_classifier(y: pd.Series) -> XGBClassifier:
    pos = max(int(y.sum()), 1)
    neg = max(int(len(y) - pos), 1)
    return XGBClassifier(
        n_estimators=140,
        max_depth=2,
        learning_rate=0.04,
        subsample=0.80,
        colsample_bytree=0.80,
        min_child_weight=10,
        reg_lambda=8,
        reg_alpha=0.5,
        objective="binary:logistic",
        eval_metric="logloss",
        scale_pos_weight=min(neg / pos, 8.0),
        n_jobs=4,
        random_state=42,
    )


def empirical_cdf(reference: np.ndarray, values: np.ndarray) -> np.ndarray:
    ref = np.sort(np.asarray(reference, dtype=float))
    return np.searchsorted(ref, np.asarray(values, dtype=float), side="right") / len(ref)


def fit_period(train: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
    """Fit only on outcomes fully known before the prediction period."""
    out = pred.copy()

    reg = quality_regressor()
    y_ret = train["target10_no"].clip(-0.30, 0.50)
    reg.fit(train[FEATURES], y_ret)
    train_ret = reg.predict(train[FEATURES])
    pred_ret = reg.predict(out[FEATURES])
    out["cdf_ret"] = empirical_cdf(train_ret, pred_ret)

    y_loss = (train["target10_no"] <= -0.10).astype(int)
    clf = loss_classifier(y_loss)
    clf.fit(train[FEATURES], y_loss)
    train_loss = clf.predict_proba(train[FEATURES])[:, 1]
    pred_loss = clf.predict_proba(out[FEATURES])[:, 1]
    out["cdf_loss10"] = empirical_cdf(train_loss, pred_loss)

    # Percentile-based quality. No raw probability threshold is used.
    out["score_R"] = out["cdf_ret"] - out["cdf_loss10"]
    return out


def causal_quality_predictions(events: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for label, a, b in PREDICTION_PERIODS:
        start = pd.Timestamp(a)
        end = pd.Timestamp(b)
        train = events[
            (events["target10_end"] < start)
            & events["target10_no"].notna()
        ].copy()
        pred = events[(events["date"] >= start) & (events["date"] <= end)].copy()
        pred = pred.dropna(subset=FEATURES)
        train = train.dropna(subset=FEATURES)
        if len(train) < 300 or pred.empty:
            print(f"skip {label}: train={len(train)} pred={len(pred)}")
            continue
        print(f"fit {label}: train={len(train)} pred={len(pred)}")
        scored = fit_period(train, pred)
        scored["quality_model_period"] = label
        parts.append(scored)
    if not parts:
        raise RuntimeError("no causal Swing v2 prediction periods were generated")
    return pd.concat(parts, ignore_index=True)


def select_daily_best(scored: pd.DataFrame) -> pd.DataFrame:
    """Daily top event with one-selection-day same-symbol cooldown."""
    rows = []
    prev_selected: set[str] = set()
    for _, day in scored.sort_values(
        ["date", "score_R"], ascending=[True, False]
    ).groupby("date", sort=True):
        chosen = None
        for _, row in day.sort_values("score_R", ascending=False).iterrows():
            if str(row.symbol) in prev_selected:
                continue
            chosen = row
            break
        prev_selected = {str(chosen.symbol)} if chosen is not None else set()
        if chosen is not None:
            rows.append(chosen)
    return pd.DataFrame(rows).reset_index(drop=True)


def stats_series(x: pd.Series) -> dict:
    x = pd.to_numeric(x, errors="coerce").dropna()
    if x.empty:
        return {"n": 0}
    return {
        "n": int(len(x)),
        "mean": float(x.mean()),
        "median": float(x.median()),
        "win_rate": float((x > 0).mean()),
        "hit10_rate": float((x >= 0.10).mean()),
        "hit20_rate": float((x >= 0.20).mean()),
        "loss10_rate": float((x <= -0.10).mean()),
        "max": float(x.max()),
        "min": float(x.min()),
    }


def stats_horizons(z: pd.DataFrame) -> dict:
    return {
        f"{h}BD": stats_series(z[f"target{h}_no"])
        for h in [5, 10, 20, 40]
        if f"target{h}_no" in z.columns
    }


def period_slice(z: pd.DataFrame, a: str, b: str) -> pd.DataFrame:
    return z[(z["date"] >= a) & (z["date"] <= b)]


def robust_threshold_utility(dev: dict, val: dict) -> float | None:
    if dev.get("n", 0) < MIN_HALF_YEAR_N or val.get("n", 0) < MIN_HALF_YEAR_N:
        return None
    return (
        min(dev["mean"], val["mean"])
        + 0.40 * min(dev["median"], val["median"])
        + 0.02 * min(dev["win_rate"], val["win_rate"])
        + 0.03 * min(dev["hit10_rate"], val["hit10_rate"])
        - 0.08 * max(dev["loss10_rate"], val["loss10_rate"])
    )


def threshold_sweep(daily: pd.DataFrame) -> list[dict]:
    rows = []
    for threshold in THRESHOLD_SWEEP:
        z = daily[
            (daily["breadth_ma20"] > BREADTH_MA20_MIN)
            & (daily["score_R"] >= threshold)
        ]
        dev = stats_series(period_slice(z, "2025-01-01", "2025-06-30")["target10_no"])
        val = stats_series(period_slice(z, "2025-07-01", "2025-12-31")["target10_no"])
        rows.append({
            "score_R_min": threshold,
            "development": dev,
            "validation": val,
            "robust_utility": robust_threshold_utility(dev, val),
        })
    return rows


def monthly_10bd(z: pd.DataFrame) -> dict:
    out = {}
    for month, g in z.groupby(z["date"].dt.to_period("M")):
        out[str(month)] = stats_series(g["target10_no"])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default="tvfree_screener/out/tse_daily.csv")
    ap.add_argument("--symbol-batch", type=int, default=200)
    args = ap.parse_args()

    raw = pd.read_csv(args.cache, parse_dates=["date"], dtype={"symbol": str})
    for c in ["open", "high", "low", "close", "volume"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw = raw.dropna(subset=["date", "symbol", "close"])

    candidates = base.add_cross_sectional_factors(
        base.build_candidates_lowmem(raw, args.symbol_batch)
    )
    events = candidates[candidates["momcross"]].copy()
    scored = causal_quality_predictions(events)
    daily = select_daily_best(scored)

    sweep = threshold_sweep(daily)
    valid_sweep = [r for r in sweep if r["robust_utility"] is not None]
    selected_pre2026 = max(valid_sweep, key=lambda r: r["robust_utility"])

    swing_s = daily[
        (daily["breadth_ma20"] > BREADTH_MA20_MIN)
        & (daily["score_R"] >= LOCKED_SCORE_R_MIN)
    ].copy()

    period_report = {}
    for name, (a, b) in REPORT_PERIODS.items():
        z = period_slice(swing_s, a, b)
        period_report[name] = stats_horizons(z)

    test = period_slice(swing_s, "2026-03-01", "2026-08-31")
    report = {
        "status": "research_only_no_production_writes",
        "architecture": "MomCross -> causal semiannual quality model -> train-CDF score_R -> Breadth Meta -> locked quality gate",
        "entry": "next_session_open",
        "breadth_ma20_min": BREADTH_MA20_MIN,
        "locked_score_R_min": LOCKED_SCORE_R_MIN,
        "cooldown": "same symbol blocked for next trading selection day only",
        "threshold_selection_check": {
            "minimum_n_each_2025_half": MIN_HALF_YEAR_N,
            "sweep": sweep,
            "best_pre2026_under_robust_utility": selected_pre2026,
            "locked_threshold_matches_best_pre2026": bool(
                np.isclose(selected_pre2026["score_R_min"], LOCKED_SCORE_R_MIN)
            ),
        },
        "periods": period_report,
        "2026_MarAug_monthly_10BD": monthly_10bd(test),
        "notes": [
            "2026 was already inspected in earlier experiments and is not a pristine holdout.",
            "score_R uses empirical CDFs of each period's training predictions; raw probability scales are never thresholded.",
            "The 10BD quality model is retrained semiannually using only outcomes ending before that half-year starts.",
            "Breadth Meta is contemporaneously observable at signal close and contains no future outcome data.",
            "Attack/big-winner heads remain rejected; do not promote them from this runner.",
        ],
    }

    OUT.mkdir(parents=True, exist_ok=True)
    swing_s.to_csv(OUT / "v3_swing_v2_s_picks.csv", index=False)
    with open(OUT / "v3_swing_v2_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
