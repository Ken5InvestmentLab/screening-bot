#!/usr/bin/env python3
"""Causal right-tail winner research for the TradingView-free screener.

TEST ONLY. No production writes.

Goal:
  Explicitly model the rare winners that can lift portfolio mean, instead of
  rejecting a method merely because a few +20%/+50% names drive performance.

Protocol:
  * fixed run-80 OHLCV input
  * observable broad opportunity filter only
  * causal half-year models for +20%, +50%, and -10% 5BD outcomes
  * 2024 development ranks a small predeclared variant set
  * only top 2 2024 variants may expose 2025
  * at most one variant is locked from 2025
  * 2026 Mar-Aug is reported only after the 2025 validation gate passes
  * 2026 never selects a feature, threshold, model, or score

Entry/evaluation:
  next-session open -> fifth subsequent session close.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

import short_event_experiment as ev

OUT = Path("tvfree_screener/out")

FEATURES = [
    "ret1","ret3","ret5","ret10","ret20","ret40","prev_ret5",
    "volr5","volr10","volr20","rv10","rv40","range_pct","avg_range10",
    "close_loc","gap","pos20","pos60","break20","break60",
    "rv_ratio","range_expansion","ret5_pct","ret20_pct","volr20_pct","pos60_pct",
]

DEV_PERIODS = {
    "2024H1": ("2024-01-01", "2024-06-30"),
    "2024H2": ("2024-07-01", "2024-12-31"),
}
VAL_PERIODS = {
    "2025H1": ("2025-01-01", "2025-06-30"),
    "2025H2": ("2025-07-01", "2025-12-31"),
}

# Fixed before any new 2026 evaluation. Gates are deliberately extreme so this
# lane stays sparse and behaves like an Attack/right-tail selector.
VARIANTS = {
    "tail20_q999":   {"w20": 1.00, "w50": 0.00, "wloss": 1.00, "gate": 0.9990},
    "tail50_q999":   {"w20": 0.25, "w50": 1.00, "wloss": 0.75, "gate": 0.9990},
    "blend_q999":    {"w20": 0.75, "w50": 1.00, "wloss": 1.00, "gate": 0.9990},
    "blend_q9995":   {"w20": 0.75, "w50": 1.00, "wloss": 1.00, "gate": 0.9995},
}


def model(y: pd.Series) -> XGBClassifier:
    pos = max(int(y.sum()), 1)
    neg = max(int(len(y) - pos), 1)
    return XGBClassifier(
        n_estimators=160,
        max_depth=3,
        learning_rate=0.035,
        subsample=0.80,
        colsample_bytree=0.80,
        min_child_weight=20,
        reg_lambda=8,
        reg_alpha=0.5,
        objective="binary:logistic",
        eval_metric="logloss",
        scale_pos_weight=min(neg / pos, 20.0),
        n_jobs=4,
        random_state=42,
    )


def attach_target_end(q: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    z = raw[["date","symbol"]].sort_values(["symbol","date"]).copy()
    z["target_end_date"] = z.groupby("symbol", sort=False)["date"].shift(-5)
    return q.merge(z, on=["date","symbol"], how="left", validate="many_to_one")


def build_opportunities(q: pd.DataFrame) -> pd.DataFrame:
    z = q.copy()
    z["rv_ratio"] = z["rv10"] / z["rv40"].replace(0, np.nan)
    z["range_expansion"] = z["range_pct"] / z["avg_range10"].replace(0, np.nan)
    for c in ["ret5","ret20","volr20","pos60"]:
        z[f"{c}_pct"] = z.groupby("date")[c].rank(pct=True, method="average")

    # Broad observable union. It includes momentum ignition/breakout as well as
    # capitulation/reversal so the tail model is not tied to one chart pattern.
    opportunity = (
        (z["ret1"] >= 0.015)
        | (z["ret5"] >= 0.04)
        | (z["volr20"] >= 1.50)
        | (z["break20"] >= -0.01)
        | ((z["prev_ret5"] <= -0.08) & (z["ret1"] >= 0.01))
    )
    z = z[opportunity.fillna(False)].copy()
    z = z.dropna(subset=FEATURES + ["target5_no","target_end_date"])
    z["y_hit20"] = (z["target5_no"] >= 0.20).astype(int)
    z["y_hit50"] = (z["target5_no"] >= 0.50).astype(int)
    z["y_loss10"] = (z["target5_no"] <= -0.10).astype(int)
    return z


def empirical_cdf(reference: np.ndarray, values: np.ndarray) -> np.ndarray:
    ref = np.asarray(reference, dtype=float)
    ref = ref[np.isfinite(ref)]
    ref.sort()
    if len(ref) == 0:
        raise RuntimeError("empty CDF reference")
    return np.searchsorted(ref, np.asarray(values, dtype=float), side="right") / len(ref)


def fit_period(train: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
    train = train.dropna(subset=FEATURES).copy()
    pred = pred.dropna(subset=FEATURES).copy()
    out = pred.copy()
    train_cdfs: dict[str, np.ndarray] = {}
    for target in ["y_hit20","y_hit50","y_loss10"]:
        y = train[target].astype(int)
        if y.nunique() < 2:
            raise RuntimeError(f"degenerate target {target}")
        m = model(y)
        m.fit(train[FEATURES], y, verbose=False)
        tr = m.predict_proba(train[FEATURES])[:, 1]
        pr = m.predict_proba(pred[FEATURES])[:, 1]
        train_cdfs[target] = empirical_cdf(tr, tr)
        out[f"p_{target}"] = pr
        out[f"cdf_{target}"] = empirical_cdf(tr, pr)

    # Final sparse tail gate is also calibrated ONLY against causal training
    # scores. Never rank against the full prediction half-year.
    for name, spec in VARIANTS.items():
        tr_raw = (
            spec["w20"] * train_cdfs["y_hit20"]
            + spec["w50"] * train_cdfs["y_hit50"]
            - spec["wloss"] * train_cdfs["y_loss10"]
        )
        pr_raw = (
            spec["w20"] * out["cdf_y_hit20"].to_numpy()
            + spec["w50"] * out["cdf_y_hit50"].to_numpy()
            - spec["wloss"] * out["cdf_y_loss10"].to_numpy()
        )
        out[f"tail_raw__{name}"] = pr_raw
        out[f"tail_q__{name}"] = empirical_cdf(tr_raw, pr_raw)
    return out


def causal_scores(q: pd.DataFrame) -> pd.DataFrame:
    parts = []
    periods = [
        ("2024H1","2024-01-01","2024-06-30"),
        ("2024H2","2024-07-01","2024-12-31"),
        ("2025H1","2025-01-01","2025-06-30"),
        ("2025H2","2025-07-01","2025-12-31"),
        ("2026H1","2026-01-01","2026-06-30"),
        ("2026H2","2026-07-01","2026-12-31"),
    ]
    for label, a, b in periods:
        start, end = pd.Timestamp(a), pd.Timestamp(b)
        train = q[(q["target_end_date"] < start)].copy()
        pred = q[(q["date"] >= start) & (q["date"] <= end)].copy()
        if len(train) < 30000 or pred.empty:
            print(f"skip {label}: train={len(train)} pred={len(pred)}")
            continue
        print(f"fit {label}: train={len(train)} pred={len(pred)}")
        x = fit_period(train, pred)
        x["model_period"] = label
        parts.append(x)
    if not parts:
        raise RuntimeError("no causal tail periods generated")
    return pd.concat(parts, ignore_index=True)


def score_variant(scored: pd.DataFrame, spec: dict[str, float], reference: pd.DataFrame) -> pd.DataFrame:
    z = scored.copy()
    r = reference.copy()
    for x in [z, r]:
        x["tail_raw"] = (
            spec["w20"] * x["cdf_y_hit20"]
            + spec["w50"] * x["cdf_y_hit50"]
            - spec["wloss"] * x["cdf_y_loss10"]
        )
    z["tail_q"] = empirical_cdf(r["tail_raw"].to_numpy(), z["tail_raw"].to_numpy())
    return z


def select_sparse(scored: pd.DataFrame, gate: float, trading_dates: pd.Index) -> pd.DataFrame:
    z = scored[scored["tail_q"] >= gate].copy()
    if z.empty:
        return z
    date_idx = {pd.Timestamp(d): i for i, d in enumerate(pd.Index(trading_dates).sort_values())}
    rows = []
    last_symbol = None
    last_idx = None
    for date, day in z.sort_values(["date","tail_q","tail_raw"], ascending=[True,False,False]).groupby("date", sort=True):
        idx = date_idx[pd.Timestamp(date)]
        chosen = None
        for _, row in day.sort_values(["tail_q","tail_raw"], ascending=False).iterrows():
            if last_idx is not None and idx == last_idx + 1 and str(row["symbol"]) == last_symbol:
                continue
            chosen = row
            break
        if chosen is not None:
            rows.append(chosen)
            last_symbol = str(chosen["symbol"])
            last_idx = idx
    return pd.DataFrame(rows).reset_index(drop=True)


def summarize(s: pd.Series) -> dict:
    x = pd.to_numeric(s, errors="coerce").dropna()
    if x.empty:
        return {"n": 0}
    return {
        "n": int(len(x)),
        "mean": float(x.mean()),
        "median": float(x.median()),
        "win_rate": float((x > 0).mean()),
        "hit10_rate": float((x >= 0.10).mean()),
        "hit20_rate": float((x >= 0.20).mean()),
        "hit50_rate": float((x >= 0.50).mean()),
        "hit100_rate": float((x >= 1.00).mean()),
        "loss10_rate": float((x <= -0.10).mean()),
        "max": float(x.max()),
        "min": float(x.min()),
    }


def stats_periods(picks: pd.DataFrame, periods: dict[str, tuple[str,str]]) -> dict:
    out = {}
    for name, (a,b) in periods.items():
        z = picks[(picks["date"] >= a) & (picks["date"] <= b)]
        out[name] = summarize(z["target5_no"])
    return out


def development_utility(ps: dict, pooled: dict) -> float | None:
    h1, h2 = ps["2024H1"], ps["2024H2"]
    if h1.get("n",0) < 8 or h2.get("n",0) < 8:
        return None
    if h1["mean"] <= 0 or h2["mean"] <= 0:
        return None
    if pooled["mean"] < 0.02:
        return None
    if max(h1["loss10_rate"], h2["loss10_rate"]) > 0.20:
        return None
    # Reward actual tail capture; do not penalize a positive skew merely because
    # the mean is driven by large winners.
    return float(
        min(h1["mean"], h2["mean"])
        + 0.50 * pooled["mean"]
        + 0.08 * pooled["hit20_rate"]
        + 0.12 * pooled["hit50_rate"]
        - 0.08 * max(h1["loss10_rate"], h2["loss10_rate"])
    )


def validation_pass(ps: dict, pooled: dict) -> bool:
    h1, h2 = ps["2025H1"], ps["2025H2"]
    return bool(
        h1.get("n",0) >= 8
        and h2.get("n",0) >= 8
        and h1["mean"] > 0
        and h2["mean"] > 0
        and pooled["mean"] >= 0.02
        and pooled["hit20_rate"] >= 0.05
        and max(h1["loss10_rate"], h2["loss10_rate"]) <= 0.20
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(OUT / "tse_daily.csv"))
    ap.add_argument("--symbol-batch", type=int, default=200)
    args = ap.parse_args()

    raw = pd.read_csv(args.cache, parse_dates=["date"], dtype={"symbol": str})
    for c in ["open","high","low","close","volume"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw = raw.dropna(subset=["date","symbol","open","high","low","close","volume"])
    raw = raw.sort_values(["symbol","date"]).reset_index(drop=True)
    trading_dates = pd.Index(pd.to_datetime(raw["date"].unique())).sort_values()

    base = ev.build_candidates(raw, args.symbol_batch)
    q = attach_target_end(base, raw)
    q = build_opportunities(q)
    scored = causal_scores(q)

    # Reference distributions are always strictly earlier than each evaluated
    # half-year. We use the scored training-side candidates only indirectly via
    # CDF heads; the variant blend itself is ranked on 2024 only.
    candidates = {}
    for name, spec in VARIANTS.items():
        s = scored.copy()
        s["tail_raw"] = s[f"tail_raw__{name}"]
        s["tail_q"] = s[f"tail_q__{name}"]
        picks = select_sparse(s, spec["gate"], trading_dates)
        dev = stats_periods(picks, DEV_PERIODS)
        pool = summarize(picks[(picks["date"] >= "2024-01-01") & (picks["date"] <= "2024-12-31")]["target5_no"])
        candidates[name] = {
            "spec": spec,
            "picks": picks,
            "development_2024": dev,
            "development_2024_pooled": pool,
            "development_utility": development_utility(dev, pool),
        }

    ranked = sorted(
        [(c["development_utility"], name) for name,c in candidates.items() if c["development_utility"] is not None],
        reverse=True,
    )
    opened = [name for _,name in ranked[:2]]
    accepted = []
    for name in opened:
        c = candidates[name]
        val = stats_periods(c["picks"], VAL_PERIODS)
        pool = summarize(c["picks"][(c["picks"]["date"] >= "2025-01-01") & (c["picks"]["date"] <= "2025-12-31")]["target5_no"])
        c["validation_2025"] = val
        c["validation_2025_pooled"] = pool
        c["validation_pass"] = validation_pass(val, pool)
        if c["validation_pass"]:
            accepted.append((min(val["2025H1"]["mean"], val["2025H2"]["mean"]), pool["mean"], name))

    locked = sorted(accepted, reverse=True)[0][2] if accepted else None
    report = {
        "status": "research_only_no_production_writes",
        "purpose": "explicit right-tail capture; large winners are a valid source of positive skew",
        "entry": "next_session_open_to_5BD_close",
        "protocol": "2024 development -> top2 only 2025 -> at most one lock -> 2026 only after validation pass",
        "opportunity_rows": int(len(q)),
        "positive_counts_training_and_eval": {
            "hit20": int(q["y_hit20"].sum()),
            "hit50": int(q["y_hit50"].sum()),
            "loss10": int(q["y_loss10"].sum()),
        },
        "development_ranked": [{"name":n,"utility":float(u)} for u,n in ranked],
        "validation_opened": opened,
        "locked_candidate": locked,
        "candidates": {},
    }

    for name,c in candidates.items():
        item = {
            "spec": c["spec"],
            "development_2024": c["development_2024"],
            "development_2024_pooled": c["development_2024_pooled"],
            "development_utility": c["development_utility"],
        }
        if name in opened:
            item["validation_2025"] = c["validation_2025"]
            item["validation_2025_pooled"] = c["validation_2025_pooled"]
            item["validation_pass"] = c["validation_pass"]
        if name == locked:
            fixed = c["picks"][(c["picks"]["date"] >= "2026-03-01") & (c["picks"]["date"] <= "2026-08-31")].copy()
            item["fixed_2026_MarAug"] = summarize(fixed["target5_no"])
            item["fixed_2026_monthly"] = {
                str(m): summarize(g["target5_no"])
                for m,g in fixed.groupby(fixed["date"].dt.to_period("M"))
            }
            fixed.to_csv(OUT / "v5_tail_winner_locked_2026.csv", index=False)
        report["candidates"][name] = item

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "v5_tail_winner_report.json","w",encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
