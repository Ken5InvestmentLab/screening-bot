from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import average_precision_score, roc_auc_score, mean_absolute_error

import no_tv_v10_standalone as base

OUTCOME_FEATURES = base.FEATURES + ["stable_score"]
WEIGHT_SETS = [
    (0.50, 0.30, 0.20),
    (0.40, 0.40, 0.20),
    (0.40, 0.25, 0.35),
    (0.30, 0.50, 0.20),
    (0.30, 0.30, 0.40),
]
TOPN = [1, 2, 3, 5, 8]


def safe_auc(y, p):
    y = np.asarray(y, int)
    if len(np.unique(y)) < 2:
        return None
    return float(roc_auc_score(y, p))


def safe_ap(y, p):
    y = np.asarray(y, int)
    return float(average_precision_score(y, p)) if y.sum() > 0 else None


def outcome_models(train_bottom):
    x = train_bottom[OUTCOME_FEATURES].astype(float)
    ret = pd.to_numeric(train_bottom.perf_5bd, errors="coerce").to_numpy(float)
    y_win = (ret > 0).astype(int)
    y_hit = (ret >= 0.10).astype(int)

    win = HistGradientBoostingClassifier(
        learning_rate=.04, max_iter=220, max_leaf_nodes=15,
        min_samples_leaf=20, l2_regularization=1.5, random_state=71,
    )
    hit = HistGradientBoostingClassifier(
        learning_rate=.04, max_iter=240, max_leaf_nodes=15,
        min_samples_leaf=18, l2_regularization=2.0, random_state=72,
    )
    reg = HistGradientBoostingRegressor(
        learning_rate=.035, max_iter=240, max_leaf_nodes=15,
        min_samples_leaf=20, l2_regularization=2.0, random_state=73,
        loss="squared_error",
    )
    win.fit(x, y_win, sample_weight=base.balanced_weights(y_win))
    hit.fit(x, y_hit, sample_weight=base.balanced_weights(y_hit))
    reg.fit(x, np.clip(ret, -0.20, 0.30))
    return win, hit, reg


def attach_outcome_scores(df, win, hit, reg):
    out = df.copy()
    x = out[OUTCOME_FEATURES].astype(float)
    out["p_win"] = win.predict_proba(x)[:, 1]
    out["p_hit10"] = hit.predict_proba(x)[:, 1]
    out["pred_ret"] = reg.predict(x)
    out["ret_component"] = 0.5 + 0.5 * np.tanh(out.pred_ret.to_numpy(float) / 0.08)
    return out


def select_topn(df, score_col, n):
    if df.empty:
        return df
    return (
        df.sort_values(["date", score_col], ascending=[True, False])
          .groupby("date", sort=False)
          .head(n)
          .copy()
    )


def policy_objective(stats):
    if stats["n"] < 20:
        return -999.0
    return (
        0.60 * stats["robust_avg"]
        + 0.40 * stats["avg"]
        + 0.015 * (stats["wr"] - 0.50)
        + 0.020 * stats["target_rate"]
    )


def choose_policy(valid_actual_bottom):
    best = None
    trials = []
    for ww, wh, wr in WEIGHT_SETS:
        col = f"score_{ww:.2f}_{wh:.2f}_{wr:.2f}"
        valid_actual_bottom[col] = (
            ww * valid_actual_bottom.p_win
            + wh * valid_actual_bottom.p_hit10
            + wr * valid_actual_bottom.ret_component
        )
        for n in TOPN:
            sel = select_topn(valid_actual_bottom, col, n)
            st = base.trade_stats(sel)
            obj = policy_objective(st)
            rec = {"weights": [ww, wh, wr], "topn": n, "score_col": col, "objective": obj, "stats": st}
            trials.append(rec)
            if best is None or obj > best["objective"]:
                best = rec
    return best, trials


def score_with_policy(df, policy):
    ww, wh, wr = policy["weights"]
    out = df.copy()
    out["outcome_score"] = ww * out.p_win + wh * out.p_hit10 + wr * out.ret_component
    return select_topn(out, "outcome_score", int(policy["topn"]))


def build_dataset(args):
    teacher = base.load_teacher(args.teacher)
    wl, _, wl_stats = base.load_exact_watchlists(args.watchlist_repo, base.TRAIN_START, base.TEST_END)

    monitor_keys = set()
    union = set()
    for d, symbols in wl.items():
        if base.TRAIN_START <= d <= base.TEST_END:
            union.update(symbols)
            monitor_keys.update(f"{d}|{s}" for s in symbols)

    teacher["monitor_key"] = teacher.signal_date + "|" + teacher.symbol_code
    teacher_mon = teacher[
        teacher.monitor_key.isin(monitor_keys)
        & (teacher.signal_date >= base.TRAIN_START)
        & (teacher.signal_date <= base.TEST_END)
    ].copy()
    positive_keys = set(teacher_mon.key)

    if args.max_symbols:
        freq = {s: 0 for s in union}
        for symbols in wl.values():
            for s in symbols:
                if s in freq:
                    freq[s] += 1
        must = set(teacher_mon.loc[
            (teacher_mon.signal_date >= base.TEST_START)
            & (teacher_mon.signal_date <= base.TEST_END),
            "symbol_code",
        ])
        ordered = sorted(union, key=lambda s: (s not in must, -freq[s], s))[:args.max_symbols]
        union = set(ordered)
        monitor_keys = {k for k in monitor_keys if k.split("|", 1)[1] in union}
        positive_keys = {k for k in positive_keys if k.split("|", 1)[0] in union}

    frames = []
    errors = {}
    ok = 0
    codes = sorted(union)
    with ThreadPoolExecutor(max_workers=args.max_workers) as ex:
        fut = {ex.submit(base.fetch_one, c, base.TRAIN_START, base.FETCH_END): c for c in codes}
        for n, f in enumerate(as_completed(fut), 1):
            try:
                fr, err = f.result()
            except Exception as exc:
                fr, err = None, type(exc).__name__
            if fr is not None:
                ok += 1
                if not fr.empty:
                    frames.append(fr)
            elif err:
                errors[err] = errors.get(err, 0) + 1
            if n % 100 == 0:
                print(f"progress {n}/{len(codes)} frames={len(frames)}", flush=True)

    if not frames:
        raise RuntimeError("no candidate rows")

    data = pd.concat(frames, ignore_index=True)
    data["monitor_key"] = data.date.astype(str) + "|" + data.symbol.astype(str)
    data = data[
        data.monitor_key.isin(monitor_keys)
        & (data.date >= base.TRAIN_START)
        & (data.date <= base.TEST_END)
    ].copy()
    data["key"] = (
        data.symbol.astype(str) + "|" + data.date.astype(str) + "|" + data.session.astype(int).astype(str)
    )
    data["label"] = data.key.isin(positive_keys).astype(int)

    train = data[(data.date >= base.TRAIN_START) & (data.date <= base.TRAIN_END)].copy()
    valid = data[(data.date >= base.VALID_START) & (data.date <= base.VALID_END)].copy()
    test = data[(data.date >= base.TEST_START) & (data.date <= base.TEST_END)].copy()
    return teacher, wl_stats, data, train, valid, test, {"requested": len(codes), "ok": ok, "errors": errors}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", required=True)
    ap.add_argument("--watchlist-repo", required=True)
    ap.add_argument("--max-symbols", type=int)
    ap.add_argument("--max-workers", type=int, default=20)
    ap.add_argument("--output-dir", default="research_artifacts/stage2")
    args = ap.parse_args()

    teacher, wl_stats, data, train, valid, test, yahoo = build_dataset(args)
    print(f"split train={len(train)}/{train.label.sum()} valid={len(valid)}/{valid.label.sum()} test={len(test)}/{test.label.sum()}", flush=True)

    # Stage 1: reproduce BOTTOM-like candidates. July fixes threshold, August remains untouched.
    s1 = HistGradientBoostingClassifier(
        learning_rate=.05, max_iter=260, max_leaf_nodes=31,
        min_samples_leaf=35, l2_regularization=1.5, random_state=42,
    )
    ytr = train.label.to_numpy(int)
    s1.fit(train[base.FEATURES].astype(float), ytr, sample_weight=base.balanced_weights(ytr))
    p_valid = s1.predict_proba(valid[base.FEATURES].astype(float))[:, 1]
    s1_policy = base.choose_threshold(valid.label.to_numpy(int), p_valid)
    p_test = s1.predict_proba(test[base.FEATURES].astype(float))[:, 1]
    valid["p_bottom"] = p_valid
    test["p_bottom"] = p_test
    valid_s1 = valid[valid.p_bottom >= s1_policy["threshold"]].copy()
    test_s1 = test[test.p_bottom >= s1_policy["threshold"]].copy()

    # Stage 2 is trained ONLY on historical actual Tenchi BOTTOMs with known 5BD outcome.
    train_bottom = train[(train.label == 1) & train.perf_5bd.notna()].copy()
    valid_bottom = valid[(valid.label == 1) & valid.perf_5bd.notna()].copy()
    test_bottom = test[(test.label == 1) & test.perf_5bd.notna()].copy()
    if min(len(train_bottom), len(valid_bottom), len(test_bottom)) < 20:
        raise RuntimeError("too few actual BOTTOM rows for Stage 2")

    win, hit, reg = outcome_models(train_bottom)
    valid_bottom = attach_outcome_scores(valid_bottom, win, hit, reg)
    test_bottom = attach_outcome_scores(test_bottom, win, hit, reg)
    valid_s1 = attach_outcome_scores(valid_s1, win, hit, reg)
    test_s1 = attach_outcome_scores(test_s1, win, hit, reg)

    # Policy is selected only on July ACTUAL BOTTOMs. This isolates scoring quality from Stage 1 errors.
    policy, trials = choose_policy(valid_bottom)
    test_bottom_selected = score_with_policy(test_bottom, policy)
    test_end2end_selected = score_with_policy(test_s1, policy)

    y_win_test = (test_bottom.perf_5bd.to_numpy(float) > 0).astype(int)
    y_hit_test = (test_bottom.perf_5bd.to_numpy(float) >= 0.10).astype(int)
    result = {
        "generated_at_jst": base.now_jst().isoformat(timespec="seconds"),
        "scope": "Tenchi Kyokuchi BOTTOM + scoring replacement; M-shiki is not a target",
        "teacher": {
            "rows": int(len(teacher)),
            "symbols": int(teacher.symbol_code.nunique()),
            "date_min": teacher.signal_date.min(),
            "date_max": teacher.signal_date.max(),
        },
        "watchlists": wl_stats,
        "yahoo": yahoo,
        "candidate_rows": int(len(data)),
        "split": {
            "train": {"n": int(len(train)), "bottom": int(train.label.sum()), "stage2_bottom": int(len(train_bottom))},
            "valid": {"n": int(len(valid)), "bottom": int(valid.label.sum()), "stage1_candidates": int(len(valid_s1)), "stage2_bottom": int(len(valid_bottom))},
            "test": {"n": int(len(test)), "bottom": int(test.label.sum()), "stage1_candidates": int(len(test_s1)), "stage2_bottom": int(len(test_bottom))},
        },
        "stage1": {
            "threshold": s1_policy,
            "validation": base.class_stats(valid, p_valid, s1_policy["threshold"]),
            "test": base.class_stats(test, p_test, s1_policy["threshold"]),
        },
        "stage2_models": {
            "win_auc": safe_auc(y_win_test, test_bottom.p_win),
            "win_pr_auc": safe_ap(y_win_test, test_bottom.p_win),
            "hit10_auc": safe_auc(y_hit_test, test_bottom.p_hit10),
            "hit10_pr_auc": safe_ap(y_hit_test, test_bottom.p_hit10),
            "return_mae": float(mean_absolute_error(test_bottom.perf_5bd, test_bottom.pred_ret)),
            "return_corr": float(np.corrcoef(test_bottom.perf_5bd, test_bottom.pred_ret)[0, 1]) if len(test_bottom) > 2 else None,
        },
        "stage2_policy": policy,
        "validation_policy_trials": sorted(trials, key=lambda x: x["objective"], reverse=True)[:12],
        "current_champion": base.CHAMPION,
        "trading_test": {
            "actual_bottom_all": base.trade_stats(test_bottom),
            "actual_bottom_reconstructed_stable6": base.trade_stats(test_bottom[test_bottom.stable_score == 6]),
            "stage2_actual_bottom_selected": base.trade_stats(test_bottom_selected),
            "stage1_all": base.trade_stats(test_s1),
            "stage2_end_to_end_selected": base.trade_stats(test_end2end_selected),
        },
        "selected_actual_bottom": test_bottom_selected.sort_values(["date", "outcome_score"], ascending=[True, False])[
            ["date", "session", "symbol", "outcome_score", "p_win", "p_hit10", "pred_ret", "stable_score", "perf_5bd"]
        ].to_dict("records"),
        "selected_end_to_end": test_end2end_selected.sort_values(["date", "outcome_score"], ascending=[True, False])[
            ["date", "session", "symbol", "p_bottom", "outcome_score", "p_win", "p_hit10", "pred_ret", "stable_score", "label", "perf_5bd"]
        ].to_dict("records"),
    }

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "stage2_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    summary = {
        "split": result["split"],
        "stage1": result["stage1"],
        "stage2_models": result["stage2_models"],
        "stage2_policy": result["stage2_policy"],
        "trading_test": result["trading_test"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
