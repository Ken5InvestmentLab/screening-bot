from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

import no_tv_v11_independent_selector as v11
import no_tv_v37_stable_bottom_gate as v37

TRAIN_START, TRAIN_END = "2026-03-05", "2026-06-30"
VALID_START, VALID_END = "2026-07-01", "2026-07-31"
TEST_START, TEST_END = "2026-08-01", "2026-08-31"

SCORE_FAMILIES = {
    "balanced": {"p_win": .15, "p_hit10": .30, "p_hit20": .35, "ret_component": .20},
    "attack": {"p_win": .05, "p_hit10": .20, "p_hit20": .55, "ret_component": .20},
    "return": {"p_win": .10, "p_hit10": .20, "p_hit20": .20, "ret_component": .50},
}
STABLE_FLOORS = [5, 6]
TOPN_PER_SESSION = [1, 2]


def perf_stats(df: pd.DataFrame):
    x = pd.to_numeric(df.get("perf_5bd"), errors="coerce").dropna()
    if x.empty:
        return {"n": 0}
    y = x.sort_values(ascending=False).reset_index(drop=True)
    robust = np.clip(x.to_numpy(float), -.20, .30)
    return {
        "n": int(len(x)),
        "mean": float(x.mean()),
        "robust_mean": float(np.mean(robust)),
        "median": float(x.median()),
        "win_rate": float((x > 0).mean()),
        "hit10_rate": float((x >= .10).mean()),
        "hit20_rate": float((x >= .20).mean()),
        "loss10_rate": float((x <= -.10).mean()),
        "max": float(x.max()),
        "min": float(x.min()),
        "top1_removed_mean": float(y.iloc[1:].mean()) if len(y) > 1 else None,
    }


def fit_payoff(train: pd.DataFrame, fcols: list[str]):
    x = train[fcols].astype(float)
    r = train["perf_5bd"].to_numpy(float)

    def clf(target, seed, leaves=15, min_leaf=60):
        y = target.astype(int)
        m = HistGradientBoostingClassifier(
            learning_rate=.035,
            max_iter=240,
            max_leaf_nodes=leaves,
            min_samples_leaf=min_leaf,
            l2_regularization=4.0,
            random_state=seed,
        )
        m.fit(x, y, sample_weight=v37.weights(y))
        return m

    win = clf(r > 0, 381, min_leaf=80)
    hit10 = clf(r >= .10, 382, min_leaf=60)
    hit20 = clf(r >= .20, 383, min_leaf=45)
    reg = HistGradientBoostingRegressor(
        learning_rate=.03,
        max_iter=240,
        max_leaf_nodes=15,
        min_samples_leaf=70,
        l2_regularization=4.0,
        random_state=384,
    )
    reg.fit(x, np.clip(r, -.20, .40))
    return win, hit10, hit20, reg


def attach_payoff(df: pd.DataFrame, models, fcols: list[str]):
    win, hit10, hit20, reg = models
    o = df.copy()
    x = o[fcols].astype(float)
    o["p_win"] = win.predict_proba(x)[:, 1]
    o["p_hit10"] = hit10.predict_proba(x)[:, 1]
    o["p_hit20"] = hit20.predict_proba(x)[:, 1]
    o["pred_ret"] = reg.predict(x)
    o["ret_component"] = .5 + .5 * np.tanh(o["pred_ret"].to_numpy(float) / .08)
    return o


def attach_score(df: pd.DataFrame, weights: dict[str, float], name: str):
    o = df.copy()
    o["payoff_score"] = sum(float(w) * o[c] for c, w in weights.items())
    o["score_family"] = name
    return o


def top_per_session(df: pd.DataFrame, n: int):
    if df.empty:
        return df.copy()
    return (
        df.sort_values(
            ["date", "session", "payoff_score", "bottom_prob"],
            ascending=[True, True, False, False],
        )
        .groupby(["date", "session"], sort=True, as_index=False)
        .head(n)
        .copy()
    )


def utility(st: dict):
    if st.get("n", 0) < 8:
        return -999.0
    # Return-first utility. Risk is a bounded penalty, not the primary objective.
    return float(
        st["mean"]
        + .25 * st["robust_mean"]
        + .02 * st["hit10_rate"]
        + .04 * st["hit20_rate"]
        - .015 * st["loss10_rate"]
    )


def choose_policy(valid: pd.DataFrame, bottom_threshold: float):
    trials = []
    best = None
    gated = valid[valid["bottom_prob"] >= bottom_threshold].copy()

    for stable_floor in STABLE_FLOORS:
        base = gated[gated["stable_score"] >= stable_floor].copy()
        for family, weights in SCORE_FAMILIES.items():
            scored = attach_score(base, weights, family)
            for topn in TOPN_PER_SESSION:
                selected = top_per_session(scored, topn)
                st = perf_stats(selected)
                rec = {
                    "stable_floor": stable_floor,
                    "score_family": family,
                    "weights": weights,
                    "topn_per_session": topn,
                    "stats": st,
                    "utility": utility(st),
                }
                trials.append(rec)
                if best is None or (rec["utility"], st.get("n", 0)) > (
                    best["utility"], best["stats"].get("n", 0)
                ):
                    best = rec
    return best, sorted(trials, key=lambda r: (r["utility"], r["stats"].get("n", 0)), reverse=True)


def apply_policy(df: pd.DataFrame, policy: dict, bottom_threshold: float):
    x = df[
        (df["bottom_prob"] >= bottom_threshold)
        & (df["stable_score"] >= int(policy["stable_floor"]))
    ].copy()
    x = attach_score(x, policy["weights"], policy["score_family"])
    return top_per_session(x, int(policy["topn_per_session"]))


def exact_teacher_stats(stable6_teacher: pd.DataFrame, start: str, end: str):
    x = stable6_teacher[
        stable6_teacher["signal_date"].between(start, end)
    ].copy()
    return perf_stats(x.rename(columns={"perf_5bd": "perf_5bd"}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bottom-teacher", required=True)
    ap.add_argument("--stable6-teacher", required=True)
    ap.add_argument("--watchlist-repo", required=True)
    ap.add_argument("--max-symbols", type=int, default=500)
    ap.add_argument("--max-workers", type=int, default=20)
    ap.add_argument("--output-dir", default="research_artifacts/v38_stable_payoff_rank")
    a = ap.parse_args()

    bottom = v37.normalize_teacher(a.bottom_teacher)
    stable6_teacher = v37.normalize_teacher(a.stable6_teacher)
    stable_syms = set(stable6_teacher["symbol_code"])

    data, coverage = v37.build_dataset(
        bottom, a.watchlist_repo, stable_syms, a.max_symbols, a.max_workers
    )
    focus = data[data["stable_score"] >= 4].copy()
    focus = v11.enrich_cross_sectional(focus)

    train = focus[
        focus["date"].between(TRAIN_START, TRAIN_END)
        & focus["perf_5bd"].notna()
    ].copy()
    valid = focus[
        focus["date"].between(VALID_START, VALID_END)
        & focus["perf_5bd"].notna()
    ].copy()
    test = focus[
        focus["date"].between(TEST_START, TEST_END)
        & focus["perf_5bd"].notna()
    ].copy()

    # Bottom model: same architecture and threshold policy as V37.
    bottom_features = v37.FEATURES
    bm = HistGradientBoostingClassifier(
        learning_rate=.05,
        max_iter=260,
        max_leaf_nodes=31,
        min_samples_leaf=20,
        l2_regularization=2.0,
        random_state=42,
    )
    ytr = train["label_bottom"].to_numpy(int)
    bm.fit(train[bottom_features].astype(float), ytr, sample_weight=v37.weights(ytr))

    valid = valid.copy()
    test = test.copy()
    valid["bottom_prob"] = bm.predict_proba(valid[bottom_features].astype(float))[:, 1]
    test["bottom_prob"] = bm.predict_proba(test[bottom_features].astype(float))[:, 1]

    bottom_threshold, bottom_trials = v37.choose_threshold(
        valid["label_bottom"].to_numpy(int),
        valid["bottom_prob"].to_numpy(float),
    )
    bth = float(bottom_threshold["threshold"])

    payoff_features = v11.features()
    payoff_models = fit_payoff(train, payoff_features)
    valid = attach_payoff(valid, payoff_models, payoff_features)
    test = attach_payoff(test, payoff_models, payoff_features)

    policy, trials = choose_policy(valid, bth)
    selected = apply_policy(test, policy, bth)

    yahoo_stable6 = test[test["stable_score"] == 6].copy()
    bottom_gated6 = yahoo_stable6[yahoo_stable6["bottom_prob"] >= bth].copy()

    prod_test_keys = set(
        stable6_teacher[
            stable6_teacher["signal_date"].between(TEST_START, TEST_END)
        ]["key"]
    )
    selected_keys = set(selected["key"])
    overlap = selected_keys & prod_test_keys

    result = {
        "scope": (
            "V38 performance-first Payoff rank on top of V37 Bottom gate. "
            "No production writes. August is reporting only and already contaminated "
            "by prior research; do not use this run alone for promotion."
        ),
        "goal": (
            "Compete with current Stable6 return, not merely reduce drawdown. "
            "Risk is a bounded penalty in validation utility."
        ),
        "coverage": coverage,
        "split": {
            "train": {"n": len(train), "bottom": int(train.label_bottom.sum())},
            "valid": {"n": len(valid), "bottom": int(valid.label_bottom.sum())},
            "test": {"n": len(test), "bottom": int(test.label_bottom.sum())},
        },
        "bottom_threshold": bottom_threshold,
        "payoff_features": payoff_features,
        "score_families": SCORE_FAMILIES,
        "policy": policy,
        "validation_trials": trials,
        "reporting_test": {
            "yahoo_stable6_all": perf_stats(yahoo_stable6),
            "v37_bottom_gated_stable6": perf_stats(bottom_gated6),
            "v38_payoff_rank": perf_stats(selected),
            "production_stable6_exact_august": exact_teacher_stats(
                stable6_teacher, TEST_START, TEST_END
            ),
            "selected_exact_production_overlap": {
                "selected": len(selected_keys),
                "production_stable6": len(prod_test_keys),
                "overlap": len(overlap),
                "precision": len(overlap) / len(selected_keys) if selected_keys else None,
                "recall": len(overlap) / len(prod_test_keys) if prod_test_keys else None,
            },
        },
        "production_reference_mar_aug": exact_teacher_stats(
            stable6_teacher, "2026-03-05", "2026-08-31"
        ),
        "production_writes": False,
    }

    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "v38_stable_payoff_rank.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    selected.sort_values(["date", "session", "payoff_score"], ascending=[True, True, False]).to_csv(
        out / "v38_selected_test.csv", index=False
    )
    pd.DataFrame(trials).to_json(
        out / "v38_validation_trials.json", orient="records", force_ascii=False, indent=2
    )
    pd.DataFrame(bottom_trials).to_csv(out / "v38_bottom_threshold_trials.csv", index=False)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
