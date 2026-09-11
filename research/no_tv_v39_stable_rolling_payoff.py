from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

import no_tv_v11_independent_selector as v11
import no_tv_v37_stable_bottom_gate as v37
import no_tv_v38_stable_payoff_rank as v38

FOLDS = [
    {
        "id": "test_2026_05",
        "train_start": "2026-03-05", "train_end": "2026-03-31",
        "valid_start": "2026-04-01", "valid_end": "2026-04-30",
        "test_start": "2026-05-01", "test_end": "2026-05-31",
    },
    {
        "id": "test_2026_06",
        "train_start": "2026-03-05", "train_end": "2026-04-30",
        "valid_start": "2026-05-01", "valid_end": "2026-05-31",
        "test_start": "2026-06-01", "test_end": "2026-06-30",
    },
    {
        "id": "test_2026_07",
        "train_start": "2026-03-05", "train_end": "2026-05-31",
        "valid_start": "2026-06-01", "valid_end": "2026-06-30",
        "test_start": "2026-07-01", "test_end": "2026-07-31",
    },
    {
        "id": "test_2026_08",
        "train_start": "2026-03-05", "train_end": "2026-06-30",
        "valid_start": "2026-07-01", "valid_end": "2026-07-31",
        "test_start": "2026-08-01", "test_end": "2026-08-31",
    },
]


def purged(frame: pd.DataFrame, start: str, end: str, outcome_before: str):
    x = frame[
        frame["date"].between(start, end)
        & frame["perf_5bd"].notna()
    ].copy()
    ex = pd.to_datetime(x["exit_date_5bd"], errors="coerce")
    return x[ex < pd.Timestamp(outcome_before)].copy()


def raw_test(frame: pd.DataFrame, start: str, end: str):
    return frame[
        frame["date"].between(start, end)
        & frame["perf_5bd"].notna()
    ].copy()


def bottom_model(train: pd.DataFrame):
    m = HistGradientBoostingClassifier(
        learning_rate=.05,
        max_iter=260,
        max_leaf_nodes=31,
        min_samples_leaf=20,
        l2_regularization=2.0,
        random_state=42,
    )
    y = train["label_bottom"].to_numpy(int)
    m.fit(
        train[v37.FEATURES].astype(float),
        y,
        sample_weight=v37.weights(y),
    )
    return m


def attach_bottom(df: pd.DataFrame, model):
    o = df.copy()
    o["bottom_prob"] = model.predict_proba(
        o[v37.FEATURES].astype(float)
    )[:, 1]
    return o


def fixed_policies():
    rows = []
    for stable_floor in v38.STABLE_FLOORS:
        for family, weights in v38.SCORE_FAMILIES.items():
            for topn in v38.TOPN_PER_SESSION:
                rows.append({
                    "stable_floor": stable_floor,
                    "score_family": family,
                    "weights": weights,
                    "topn_per_session": topn,
                })
    return rows


def policy_id(p):
    return f"s{p['stable_floor']}_{p['score_family']}_top{p['topn_per_session']}"


def production_subset(stable6_teacher: pd.DataFrame, start: str, end: str):
    return stable6_teacher[
        stable6_teacher["signal_date"].between(start, end)
    ].copy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bottom-teacher", required=True)
    ap.add_argument("--stable6-teacher", required=True)
    ap.add_argument("--watchlist-repo", required=True)
    ap.add_argument("--max-symbols", type=int, default=500)
    ap.add_argument("--max-workers", type=int, default=20)
    ap.add_argument("--output-dir", default="research_artifacts/v39_stable_rolling_payoff")
    a = ap.parse_args()

    bottom = v37.normalize_teacher(a.bottom_teacher)
    stable6_teacher = v37.normalize_teacher(a.stable6_teacher)
    stable_syms = set(stable6_teacher["symbol_code"])

    data, coverage = v37.build_dataset(
        bottom, a.watchlist_repo, stable_syms, a.max_symbols, a.max_workers
    )
    focus = data[data["stable_score"] >= 4].copy()
    focus = v11.enrich_cross_sectional(focus)

    fixed = fixed_policies()
    fixed_parts = {policy_id(p): [] for p in fixed}
    adaptive_parts = []
    fold_reports = []

    for fold in FOLDS:
        train = purged(
            focus, fold["train_start"], fold["train_end"], fold["valid_start"]
        )
        valid = purged(
            focus, fold["valid_start"], fold["valid_end"], fold["test_start"]
        )
        test = raw_test(focus, fold["test_start"], fold["test_end"])

        if min(len(train), len(valid), len(test)) == 0:
            raise RuntimeError(f"empty split in {fold['id']}")
        if min(int(train.label_bottom.sum()), int(valid.label_bottom.sum())) < 3:
            raise RuntimeError(
                f"too few Bottom positives in {fold['id']}: "
                f"train={train.label_bottom.sum()} valid={valid.label_bottom.sum()}"
            )

        bm = bottom_model(train)
        valid = attach_bottom(valid, bm)
        test = attach_bottom(test, bm)

        threshold, _ = v37.choose_threshold(
            valid["label_bottom"].to_numpy(int),
            valid["bottom_prob"].to_numpy(float),
        )
        bth = float(threshold["threshold"])

        payoff = v38.fit_payoff(train, v11.features())
        valid = v38.attach_payoff(valid, payoff, v11.features())
        test = v38.attach_payoff(test, payoff, v11.features())

        adaptive, validation_trials = v38.choose_policy(valid, bth)
        adaptive_sel = v38.apply_policy(test, adaptive, bth)
        adaptive_sel = adaptive_sel.assign(fold=fold["id"])
        adaptive_parts.append(adaptive_sel)

        fixed_test = {}
        for p in fixed:
            sel = v38.apply_policy(test, p, bth).assign(fold=fold["id"])
            fixed_parts[policy_id(p)].append(sel)
            fixed_test[policy_id(p)] = v38.perf_stats(sel)

        prod = production_subset(
            stable6_teacher, fold["test_start"], fold["test_end"]
        )

        fold_reports.append({
            "fold": fold["id"],
            "dates": fold,
            "purged_split": {
                "train_n": len(train),
                "train_bottom": int(train.label_bottom.sum()),
                "valid_n": len(valid),
                "valid_bottom": int(valid.label_bottom.sum()),
                "test_n": len(test),
                "test_bottom": int(test.label_bottom.sum()),
            },
            "bottom_threshold": threshold,
            "adaptive_policy_from_validation": adaptive,
            "adaptive_test": v38.perf_stats(adaptive_sel),
            "fixed_policy_test_reporting": fixed_test,
            "production_stable6_test_month": v38.perf_stats(prod),
            "validation_top5": validation_trials[:5],
        })

    adaptive_all = (
        pd.concat(adaptive_parts, ignore_index=True)
        if adaptive_parts else pd.DataFrame()
    )
    fixed_combined = {}
    for pid, parts in fixed_parts.items():
        z = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
        fixed_combined[pid] = v38.perf_stats(z)

    fixed_ranked = sorted(
        [
            {"policy_id": pid, "stats": st}
            for pid, st in fixed_combined.items()
        ],
        key=lambda r: (
            r["stats"].get("mean", -999),
            r["stats"].get("hit20_rate", -999),
            -r["stats"].get("loss10_rate", 999),
        ),
        reverse=True,
    )

    prod_all = production_subset(stable6_teacher, "2026-05-01", "2026-08-31")

    result = {
        "scope": (
            "V39 expanding/purged monthly architecture audit. "
            "Every training/validation row must have its 5BD outcome end before "
            "the next period begins. No production writes."
        ),
        "warning": (
            "2026 has already been inspected in earlier research; these test months "
            "are reporting/architecture evidence only, not promotion-grade blind OOS."
        ),
        "goal": "Return-first Stable replacement; stability is a constraint, not the objective.",
        "coverage": coverage,
        "folds": fold_reports,
        "combined": {
            "adaptive_validation_selected": v38.perf_stats(adaptive_all),
            "fixed_policy_reporting_ranked": fixed_ranked,
            "production_stable6_may_aug": v38.perf_stats(prod_all),
        },
        "production_stable6_mar_aug": v38.perf_stats(
            production_subset(stable6_teacher, "2026-03-05", "2026-08-31")
        ),
        "production_writes": False,
    }

    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "v39_stable_rolling_payoff.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    if len(adaptive_all):
        adaptive_all.to_csv(out / "v39_adaptive_selected.csv", index=False)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
