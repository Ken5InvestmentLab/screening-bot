#!/usr/bin/env python3
"""Event-quality relative-ranking recovery for historical TV-Free V3 Short.

TEST ONLY. No production writes.

Recovered old architecture evidence:
  monthly relative-ranking Core
  -> recent confirmed Core Meta
  -> sparse Attack when Meta ON
  -> Deep Reversal when Meta OFF
  -> next-session-open to 5BD close
  -> one-business-day same-symbol cooldown

The previous deterministic recovery failed its 2024 gate. This runner restores
the most likely missing layer: event-specific causal ML quality ranking.

Blind protocol:
  * All model/gate variants are predeclared here.
  * 2024H1/H2 develops/ranks all variants.
  * Only top 3 2024 variants may expose 2025.
  * At most one candidate is locked from 2025.
  * 2026 Mar-Aug is exposed only for that locked candidate.
  * 2026 never selects a feature, model, score, threshold, or Meta rule.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

import short_event_experiment as events
import v3_short_legacy_recovery as legacy

OUT = Path("tvfree_screener/out")

FEATURES = [
    "ret1", "ret3", "ret5", "ret10", "ret20", "ret40", "prev_ret5",
    "volr5", "volr10", "volr20", "rv10", "rv40",
    "range_pct", "avg_range10", "close_loc", "gap",
    "pos20", "pos60", "break20", "break60",
]

META_RULES = {
    "r40_win50": lambda x: x["recent40_win"] >= 0.50,
    "r40_mean0_win50": lambda x: (x["recent40_mean"] >= 0.0) & (x["recent40_win"] >= 0.50),
}
ATTACK_GATES = [0.95, 0.975]
DEEP_GATES = [0.85, 0.90]

DEV_PERIODS = {
    "2024H1": ("2024-01-01", "2024-06-30"),
    "2024H2": ("2024-07-01", "2024-12-31"),
}
VAL_PERIODS = {
    "2025H1": ("2025-01-01", "2025-06-30"),
    "2025H2": ("2025-07-01", "2025-12-31"),
}
FIXED_2026 = ("2026-03-01", "2026-08-31")


def model(seed: int = 42) -> XGBClassifier:
    return XGBClassifier(
        n_estimators=180,
        max_depth=3,
        learning_rate=0.04,
        subsample=0.80,
        colsample_bytree=0.80,
        min_child_weight=15,
        reg_lambda=5,
        reg_alpha=0.2,
        objective="binary:logistic",
        eval_metric="logloss",
        n_jobs=4,
        random_state=seed,
    )


def attach_target_end(q: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    z = raw[["symbol", "date"]].copy()
    z["target_end_date"] = z.groupby("symbol", sort=False)["date"].shift(-5)
    return q.merge(z, on=["symbol", "date"], how="left", validate="many_to_one")


def attack_mask(q: pd.DataFrame) -> pd.Series:
    specs = events.event_specs(q)
    names = [
        "compression_expansion_A",
        "gap_volume_A",
        "lowvol_ignition_A",
        "bounded_breakout_A",
    ]
    m = pd.Series(False, index=q.index)
    for name in names:
        m = m | specs[name][0].fillna(False)
    return m


def deep_mask(q: pd.DataFrame) -> pd.Series:
    # Broad enough to let the quality model rank genuine reversals, but fixed
    # before any 2026 outcome is opened.
    return (
        (q["prev_ret5"] <= -0.06)
        & (q["ret1"] >= 0.01)
        & (q["close_loc"] >= 0.55)
        & (q["gap"] >= -0.05)
        & (q["volr20"] >= 0.80)
    ).fillna(False)


def prepare_lane(q: pd.DataFrame, mask: pd.Series, lane: str) -> pd.DataFrame:
    z = q.loc[mask].copy()
    z = z.dropna(subset=FEATURES + ["target5_no", "target_end_date"])
    z["lane"] = lane
    z["y_win"] = (z["target5_no"] > 0).astype(int)
    z["y_hit10"] = (z["target5_no"] >= 0.10).astype(int)
    z["y_loss10"] = (z["target5_no"] <= -0.10).astype(int)
    return z


def empirical_cdf(values: np.ndarray, reference: np.ndarray) -> np.ndarray:
    ref = np.asarray(reference, dtype=float)
    ref = ref[np.isfinite(ref)]
    if len(ref) == 0:
        raise RuntimeError("empty training score reference")
    ref.sort()
    v = np.asarray(values, dtype=float)
    return np.searchsorted(ref, v, side="right") / len(ref)


def fit_month(train: pd.DataFrame, pred: pd.DataFrame, lane: str) -> pd.DataFrame:
    train = train.dropna(subset=FEATURES).copy()
    pred = pred.dropna(subset=FEATURES).copy()
    if len(train) < 500 or len(pred) == 0:
        return pd.DataFrame()

    probs_train = {}
    probs_pred = {}
    for target in ["y_win", "y_hit10", "y_loss10"]:
        y = train[target].astype(int)
        if y.nunique() < 2:
            return pd.DataFrame()
        m = model()
        m.fit(train[FEATURES], y, verbose=False)
        probs_train[target] = m.predict_proba(train[FEATURES])[:, 1]
        probs_pred[target] = m.predict_proba(pred[FEATURES])[:, 1]

    if lane == "Attack":
        raw_train = (
            probs_train["y_hit10"]
            + 0.50 * probs_train["y_win"]
            - 1.00 * probs_train["y_loss10"]
        )
        raw_pred = (
            probs_pred["y_hit10"]
            + 0.50 * probs_pred["y_win"]
            - 1.00 * probs_pred["y_loss10"]
        )
    else:
        raw_train = (
            probs_train["y_win"]
            + 0.25 * probs_train["y_hit10"]
            - 1.50 * probs_train["y_loss10"]
        )
        raw_pred = (
            probs_pred["y_win"]
            + 0.25 * probs_pred["y_hit10"]
            - 1.50 * probs_pred["y_loss10"]
        )

    out = pred.copy()
    out["quality_raw"] = raw_pred
    out["quality_cdf"] = empirical_cdf(raw_pred, raw_train)
    out["p_win"] = probs_pred["y_win"]
    out["p_hit10"] = probs_pred["y_hit10"]
    out["p_loss10"] = probs_pred["y_loss10"]
    return out


def causal_monthly_scores(lane_df: pd.DataFrame, lane: str) -> pd.DataFrame:
    parts = []
    start = pd.Timestamp("2024-01-01")
    end = pd.Timestamp("2026-08-31")
    for period in pd.period_range(start.to_period("M"), end.to_period("M"), freq="M"):
        a = period.start_time
        b = period.end_time.normalize()
        train = lane_df[lane_df["target_end_date"] < a]
        pred = lane_df[(lane_df["date"] >= a) & (lane_df["date"] <= b)]
        scored = fit_month(train, pred, lane)
        if scored.empty:
            continue
        scored["model_period"] = str(period)
        parts.append(scored)
    if not parts:
        raise RuntimeError(f"no scored monthly periods for {lane}")
    return pd.concat(parts, ignore_index=True)


def select_hybrid(
    attack: pd.DataFrame,
    deep: pd.DataFrame,
    meta: pd.DataFrame,
    meta_rule: str,
    attack_gate: float,
    deep_gate: float,
    trading_dates: pd.Index,
) -> pd.DataFrame:
    m = meta.copy()
    m["meta_on"] = False
    ok = m["recent40_n"] >= 40
    m.loc[ok, "meta_on"] = META_RULES[meta_rule](m.loc[ok])
    state = m.set_index("date")["meta_on"].to_dict()

    a = attack[attack["quality_cdf"] >= attack_gate].copy()
    d = deep[deep["quality_cdf"] >= deep_gate].copy()

    a = a[a["date"].map(state).fillna(False)]
    d = d[~d["date"].map(state).fillna(False)]
    z = pd.concat([a, d], ignore_index=True)
    if z.empty:
        return z

    date_idx = {pd.Timestamp(x): i for i, x in enumerate(pd.Index(trading_dates).sort_values())}
    rows = []
    last_symbol = None
    last_idx = None
    for date, day in z.sort_values(
        ["date", "quality_cdf", "quality_raw"],
        ascending=[True, False, False],
    ).groupby("date", sort=True):
        idx = date_idx.get(pd.Timestamp(date))
        chosen = None
        for _, row in day.sort_values(
            ["quality_cdf", "quality_raw"], ascending=False
        ).iterrows():
            if (
                idx is not None
                and last_idx is not None
                and idx == last_idx + 1
                and str(row["symbol"]) == last_symbol
            ):
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
        "hit5_rate": float((x >= 0.05).mean()),
        "hit10_rate": float((x >= 0.10).mean()),
        "hit20_rate": float((x >= 0.20).mean()),
        "loss10_rate": float((x <= -0.10).mean()),
        "max": float(x.max()),
        "min": float(x.min()),
    }


def period_stats(picks: pd.DataFrame, periods: dict[str, tuple[str, str]]) -> dict:
    return {
        name: summarize(
            picks[(picks["date"] >= a) & (picks["date"] <= b)]["target5_no"]
        )
        for name, (a, b) in periods.items()
    }


def pooled(picks: pd.DataFrame, a: str, b: str) -> dict:
    return summarize(picks[(picks["date"] >= a) & (picks["date"] <= b)]["target5_no"])


def dev_utility(ps: dict, p: dict) -> float | None:
    h1, h2 = ps["2024H1"], ps["2024H2"]
    if h1.get("n", 0) < 5 or h2.get("n", 0) < 5:
        return None
    if h1["mean"] <= 0 or h2["mean"] <= 0:
        return None
    if p.get("mean", -1) < 0.01:
        return None
    if max(h1["loss10_rate"], h2["loss10_rate"]) > 0.15:
        return None
    return float(
        min(h1["mean"], h2["mean"])
        + 0.40 * p["mean"]
        + 0.15 * max(0.0, p["median"])
        + 0.03 * p["hit10_rate"]
        - 0.08 * max(h1["loss10_rate"], h2["loss10_rate"])
    )


def validation_pass(ps: dict, p: dict) -> bool:
    h1, h2 = ps["2025H1"], ps["2025H2"]
    return bool(
        h1.get("n", 0) >= 5
        and h2.get("n", 0) >= 5
        and h1["mean"] > 0
        and h2["mean"] > 0
        and p.get("mean", -1) >= 0.01
        and p.get("win_rate", 0) >= 0.50
        and max(h1["loss10_rate"], h2["loss10_rate"]) <= 0.15
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(OUT / "tse_daily.csv"))
    ap.add_argument("--symbol-batch", type=int, default=200)
    args = ap.parse_args()

    raw = pd.read_csv(args.cache, parse_dates=["date"], dtype={"symbol": str})
    for c in ["open", "high", "low", "close", "volume"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw = raw.dropna(subset=["date", "symbol", "open", "high", "low", "close", "volume"])
    raw = raw.sort_values(["symbol", "date"]).reset_index(drop=True)

    q = events.build_candidates(raw, args.symbol_batch)
    q = attach_target_end(q, raw)

    attack_df = prepare_lane(q, attack_mask(q), "Attack")
    deep_df = prepare_lane(q, deep_mask(q), "DeepReversal")
    attack_scored = causal_monthly_scores(attack_df, "Attack")
    deep_scored = causal_monthly_scores(deep_df, "DeepReversal")

    core = legacy.load_core()
    trading_dates = pd.Index(pd.to_datetime(raw["date"].dropna().unique())).sort_values()
    meta = legacy.recent_confirmed_meta(core, trading_dates)

    candidates = {}
    for meta_rule in META_RULES:
        for attack_gate in ATTACK_GATES:
            for deep_gate in DEEP_GATES:
                name = f"{meta_rule}__A{attack_gate:.3f}__D{deep_gate:.2f}"
                picks = select_hybrid(
                    attack_scored,
                    deep_scored,
                    meta,
                    meta_rule,
                    attack_gate,
                    deep_gate,
                    trading_dates,
                )
                dev = period_stats(picks, DEV_PERIODS)
                dev_pool = pooled(picks, "2024-01-01", "2024-12-31")
                candidates[name] = {
                    "meta_rule": meta_rule,
                    "attack_gate": attack_gate,
                    "deep_gate": deep_gate,
                    "picks": picks,
                    "development_2024": dev,
                    "development_2024_pooled": dev_pool,
                    "development_utility": dev_utility(dev, dev_pool),
                }

    ranked = sorted(
        [
            (c["development_utility"], name)
            for name, c in candidates.items()
            if c["development_utility"] is not None
        ],
        reverse=True,
    )
    validation_opened = [name for _, name in ranked[:3]]
    accepted = []
    for name in validation_opened:
        c = candidates[name]
        val = period_stats(c["picks"], VAL_PERIODS)
        val_pool = pooled(c["picks"], "2025-01-01", "2025-12-31")
        c["validation_2025"] = val
        c["validation_2025_pooled"] = val_pool
        c["validation_pass"] = validation_pass(val, val_pool)
        if c["validation_pass"]:
            accepted.append((
                min(val["2025H1"]["mean"], val["2025H2"]["mean"]),
                val_pool["mean"],
                name,
            ))

    locked = sorted(accepted, reverse=True)[0][2] if accepted else None
    report = {
        "status": "research_only_no_production_writes",
        "historical_reference": {
            "2026_MarAug": {
                "n": 29,
                "mean": 0.0542,
                "median": 0.0206,
                "win_rate": 0.655,
                "hit10_rate": 0.138,
                "loss10_rate": 0.069,
            },
            "exact_old_thresholds_recovered": False,
        },
        "recovered_hypothesis": "event-specific monthly causal ML -> training-score CDF quality gate -> recent-40 Meta -> Attack/DeepReversal",
        "protocol": "2024 all fixed variants -> top3 only 2025 -> lock at most one -> 2026 only after pass",
        "development_ranked": [
            {"name": name, "utility": float(score)}
            for score, name in ranked
        ],
        "validation_opened": validation_opened,
        "locked_candidate": locked,
        "lane_counts": {
            "attack_candidates": int(len(attack_df)),
            "deep_candidates": int(len(deep_df)),
            "attack_scored": int(len(attack_scored)),
            "deep_scored": int(len(deep_scored)),
        },
        "candidates": {},
    }

    for name, c in candidates.items():
        item = {
            "meta_rule": c["meta_rule"],
            "attack_gate": c["attack_gate"],
            "deep_gate": c["deep_gate"],
            "development_2024": c["development_2024"],
            "development_2024_pooled": c["development_2024_pooled"],
            "development_utility": c["development_utility"],
        }
        if name in validation_opened:
            item["validation_2025"] = c["validation_2025"]
            item["validation_2025_pooled"] = c["validation_2025_pooled"]
            item["validation_pass"] = c["validation_pass"]
        if name == locked:
            fixed = c["picks"][
                (c["picks"]["date"] >= FIXED_2026[0])
                & (c["picks"]["date"] <= FIXED_2026[1])
            ].copy()
            item["fixed_2026_MarAug"] = summarize(fixed["target5_no"])
            item["fixed_2026_monthly"] = {
                str(month): summarize(group["target5_no"])
                for month, group in fixed.groupby(fixed["date"].dt.to_period("M"))
            }
            fixed.to_csv(OUT / "v3_short_legacy_rank_recovery_locked_2026.csv", index=False)
        report["candidates"][name] = item

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "v3_short_legacy_rank_recovery_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
