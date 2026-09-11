#!/usr/bin/env python3
"""V4 multi-event causal quality research (TEST ONLY).

Motivation:
- fixed-start V3 Short is reproducible but weak;
- fixed-start Swing S did not reproduce its old rolling-window advantage;
- the prior Short event experiment used fixed hand-written scores and all ten
  variants failed pre-2026 robustness.

V4 is deliberately different:
1. define a small set of BROAD event families from observable daily OHLCV only;
2. take the union of those events;
3. fit causal half-year models for return quality, +10% hit probability and
   -10% loss probability using only labels completed before each prediction half;
4. normalize model outputs against training predictions by empirical CDF;
5. choose among a tiny predeclared score/gate set using 2024 only;
6. validate the locked choice on 2025;
7. score/report 2026 only if the locked choice passes the predeclared 2025 gate.

No production writes. No TradingView. No 2026 tuning.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBClassifier, XGBRegressor

import short_event_experiment as ev

OUT = Path("tvfree_screener/out")

MODEL_FEATURES = [
    "ret1", "ret3", "ret5", "ret10", "ret20", "ret40", "prev_ret5",
    "volr5", "volr10", "volr20", "rv_ratio", "range_expansion",
    "close_loc", "gap", "pos20", "pos60", "break20", "break60",
    "ret5_pct", "ret20_pct", "volr20_pct", "pos60_pct",
    "evt_reversal", "evt_ignition", "evt_breakout", "evt_gap_hold",
    "evt_compression_release", "evt_pullback_resume", "event_count",
]

PRE2026_PERIODS = [
    ("2024H1", "2024-01-01", "2024-06-30"),
    ("2024H2", "2024-07-01", "2024-12-31"),
    ("2025H1", "2025-01-01", "2025-06-30"),
    ("2025H2", "2025-07-01", "2025-12-31"),
]
REPORT_2026_PERIODS = [
    ("2026H1", "2026-01-01", "2026-06-30"),
    ("2026H2", "2026-07-01", "2026-12-31"),
]

# Fixed before looking at V4 results. 2024 selects one; 2025 validates it.
VARIANTS = {
    "balanced": {"ret": 1.00, "hit10": 0.00, "loss10": 1.00, "gate": 0.15},
    "winner_aware": {"ret": 1.00, "hit10": 0.50, "loss10": 1.00, "gate": 0.20},
    "defensive": {"ret": 1.00, "hit10": 0.25, "loss10": 1.50, "gate": 0.10},
    "balanced_high_gate": {"ret": 1.00, "hit10": 0.00, "loss10": 1.00, "gate": 0.30},
}


def regressor() -> XGBRegressor:
    return XGBRegressor(
        n_estimators=180,
        max_depth=2,
        learning_rate=0.035,
        subsample=0.80,
        colsample_bytree=0.80,
        min_child_weight=15,
        reg_lambda=8,
        reg_alpha=0.5,
        objective="reg:squarederror",
        n_jobs=4,
        random_state=42,
    )


def classifier(y: pd.Series) -> XGBClassifier:
    pos = max(int(y.sum()), 1)
    neg = max(int(len(y) - pos), 1)
    return XGBClassifier(
        n_estimators=180,
        max_depth=2,
        learning_rate=0.04,
        subsample=0.80,
        colsample_bytree=0.80,
        min_child_weight=12,
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


def attach_target_end(q: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    dates = raw[["date", "symbol"]].sort_values(["symbol", "date"]).copy()
    dates["target5_end"] = dates.groupby("symbol", sort=False)["date"].shift(-5)
    return q.merge(dates, on=["date", "symbol"], how="left", validate="many_to_one")


def add_event_union(q: pd.DataFrame) -> pd.DataFrame:
    z = q.copy()
    z["rv_ratio"] = z["prev_rv10"] / z["prev_rv40"].replace(0, np.nan)
    z["range_expansion"] = z["range_pct"] / z["prev_avg_range10"].replace(0, np.nan)

    # Broad, predeclared families. These are intentionally looser than the
    # rejected A/B hand-score variants; model quality decides among candidates.
    z["evt_reversal"] = (
        (z["prev_ret5"] <= -0.04)
        & (z["ret1"] >= 0.01)
        & (z["close_loc"] >= 0.55)
        & (z["gap"] >= -0.06)
    )
    z["evt_ignition"] = (
        z["ret5"].between(0.02, 0.15)
        & (z["ret1"] >= 0.015)
        & (z["volr20"] >= 1.10)
        & (z["pos60"] >= 0.50)
        & (z["close_loc"] >= 0.55)
    )
    z["evt_breakout"] = (
        z["break20"].between(0.0, 0.08)
        & z["volr20"].between(1.0, 5.0)
        & (z["close_loc"] >= 0.60)
    )
    z["evt_gap_hold"] = (
        z["gap"].between(0.01, 0.12)
        & (z["ret1"] > 0)
        & (z["close_loc"] >= 0.60)
    )
    z["evt_compression_release"] = (
        (z["rv_ratio"] <= 1.0)
        & (z["range_expansion"] >= 1.15)
        & (z["ret1"] >= 0.015)
        & (z["volr20"] >= 1.10)
        & (z["close_loc"] >= 0.55)
    )
    z["evt_pullback_resume"] = (
        (z["ret20"] >= 0.08)
        & (z["prev_ret5"] <= 0.0)
        & (z["ret1"] >= 0.015)
        & (z["pos60"] >= 0.50)
    )

    event_cols = [c for c in z.columns if c.startswith("evt_")]
    for c in event_cols:
        z[c] = z[c].fillna(False).astype(int)
    z["event_count"] = z[event_cols].sum(axis=1).astype(int)

    for c in ["ret5", "ret20", "volr20", "pos60"]:
        z[f"{c}_pct"] = z.groupby("date")[c].rank(pct=True, method="average")
    return z[z["event_count"] > 0].replace([np.inf, -np.inf], np.nan)


def fit_half(train: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
    out = pred.copy()

    reg = regressor()
    y_ret = train["target5_no"].clip(-0.30, 0.50)
    reg.fit(train[MODEL_FEATURES], y_ret)
    tr_ret = reg.predict(train[MODEL_FEATURES])
    pr_ret = reg.predict(out[MODEL_FEATURES])
    out["cdf_ret"] = empirical_cdf(tr_ret, pr_ret)

    for target_name, condition in [
        ("hit10", train["target5_no"] >= 0.10),
        ("loss10", train["target5_no"] <= -0.10),
    ]:
        y = condition.astype(int)
        if y.nunique() < 2:
            raise RuntimeError(f"degenerate V4 training head: {target_name}")
        clf = classifier(y)
        clf.fit(train[MODEL_FEATURES], y)
        tr = clf.predict_proba(train[MODEL_FEATURES])[:, 1]
        pr = clf.predict_proba(out[MODEL_FEATURES])[:, 1]
        out[f"cdf_{target_name}"] = empirical_cdf(tr, pr)

    return out


def score_periods(events: pd.DataFrame, periods: list[tuple[str, str, str]]) -> pd.DataFrame:
    parts = []
    for label, a, b in periods:
        start = pd.Timestamp(a)
        end = pd.Timestamp(b)
        train = events[
            (events["target5_end"] < start) & events["target5_no"].notna()
        ].dropna(subset=MODEL_FEATURES)
        pred = events[
            (events["date"] >= start) & (events["date"] <= end)
        ].dropna(subset=MODEL_FEATURES)
        if len(train) < 1000 or pred.empty:
            print(f"skip V4 {label}: train={len(train)} pred={len(pred)}")
            continue
        print(f"fit V4 {label}: train={len(train)} pred={len(pred)}")
        scored = fit_half(train, pred)
        scored["model_period"] = label
        parts.append(scored)
    if not parts:
        raise RuntimeError("no V4 prediction periods generated")
    return pd.concat(parts, ignore_index=True)


def select_variant(scored: pd.DataFrame, spec: dict[str, float]) -> pd.DataFrame:
    z = scored.copy()
    z["v4_score"] = (
        spec["ret"] * z["cdf_ret"]
        + spec["hit10"] * z["cdf_hit10"]
        - spec["loss10"] * z["cdf_loss10"]
    )
    z = z[z["v4_score"] >= spec["gate"]]
    rows = []
    prev_selected: set[str] = set()
    for _, day in z.sort_values(
        ["date", "v4_score"], ascending=[True, False]
    ).groupby("date", sort=True):
        chosen = None
        for _, row in day.sort_values("v4_score", ascending=False).iterrows():
            if str(row["symbol"]) in prev_selected:
                continue
            chosen = row
            break
        prev_selected = {str(chosen["symbol"])} if chosen is not None else set()
        if chosen is not None:
            rows.append(chosen)
    return pd.DataFrame(rows).reset_index(drop=True)


def period_stats(picks: pd.DataFrame, a: str, b: str) -> dict:
    z = picks[(picks["date"] >= a) & (picks["date"] <= b)]
    return ev.summarize(z["target5_no"]) if not z.empty else {"n": 0}


def development_utility(h1: dict, h2: dict) -> float | None:
    if h1.get("n", 0) < 20 or h2.get("n", 0) < 20:
        return None
    if min(h1["mean"], h2["mean"]) < -0.005:
        return None
    return float(
        min(h1["mean"], h2["mean"])
        + 0.40 * min(h1["median"], h2["median"])
        + 0.025 * min(h1["win_rate"], h2["win_rate"])
        + 0.035 * min(h1["hit10_rate"], h2["hit10_rate"])
        - 0.10 * max(h1["loss10_rate"], h2["loss10_rate"])
    )


def validation_pass(h1: dict, h2: dict) -> bool:
    if h1.get("n", 0) < 15 or h2.get("n", 0) < 15:
        return False
    if h1["mean"] <= 0 or h2["mean"] <= 0:
        return False
    if max(h1["loss10_rate"], h2["loss10_rate"]) > 0.10:
        return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(OUT / "tse_daily.csv"))
    ap.add_argument("--symbol-batch", type=int, default=200)
    args = ap.parse_args()

    raw = pd.read_csv(args.cache, parse_dates=["date"], dtype={"symbol": str})
    for c in ["open", "high", "low", "close", "volume"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw = raw.dropna(subset=["date", "symbol", "open", "high", "low", "close", "volume"])

    q = ev.build_candidates(raw, args.symbol_batch)
    q = attach_target_end(q, raw)
    events = add_event_union(q)

    pre = score_periods(events, PRE2026_PERIODS)
    variants = {}
    selections = {}
    for name, spec in VARIANTS.items():
        picks = select_variant(pre, spec)
        selections[name] = picks
        stats = {
            label: period_stats(picks, a, b)
            for label, a, b in PRE2026_PERIODS
        }
        util = development_utility(stats["2024H1"], stats["2024H2"])
        variants[name] = {
            "spec": spec,
            "periods": stats,
            "development_utility_2024": util,
        }

    eligible = [
        (v["development_utility_2024"], name)
        for name, v in variants.items()
        if v["development_utility_2024"] is not None
    ]
    locked = max(eligible)[1] if eligible else None

    report = {
        "status": "research_only_no_production_writes",
        "architecture": "broad event union -> causal 3-head half-year quality -> train CDF -> locked score/gate",
        "entry": "next_session_open_to_5BD_close",
        "event_rows": int(len(events)),
        "selection_rule": "variant selected using 2024 only; locked variant validated on 2025 before any 2026 scoring",
        "variants": variants,
        "locked_variant": locked,
        "validation_pass_2025": False,
        "fixed_2026_MarAug": None,
    }

    locked_picks = pd.DataFrame()
    if locked is not None:
        locked_picks = selections[locked]
        h1 = variants[locked]["periods"]["2025H1"]
        h2 = variants[locked]["periods"]["2025H2"]
        passed = validation_pass(h1, h2)
        report["validation_pass_2025"] = bool(passed)

        if passed:
            future = score_periods(events, REPORT_2026_PERIODS)
            future_picks = select_variant(future, VARIANTS[locked])
            fixed = future_picks[
                (future_picks["date"] >= "2026-03-01")
                & (future_picks["date"] <= "2026-08-31")
            ]
            report["fixed_2026_MarAug"] = ev.summarize(fixed["target5_no"])
            report["fixed_2026_monthly"] = {
                str(month): ev.summarize(g["target5_no"])
                for month, g in fixed.groupby(fixed["date"].dt.to_period("M"))
            }
        else:
            report["fixed_2026_reason"] = "locked 2024-selected variant failed predeclared 2025 validation; 2026 not scored"

    OUT.mkdir(parents=True, exist_ok=True)
    if not locked_picks.empty:
        locked_picks.to_csv(OUT / "v4_event_quality_locked_pre2026.csv", index=False)
    with open(OUT / "v4_event_quality_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
