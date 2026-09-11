from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix

import no_tv_v10_standalone as base
import no_tv_v13_official_daily as v13

TRAIN_START, TRAIN_END = "2026-03-05", "2026-06-30"
VALID_START, VALID_END = "2026-07-01", "2026-07-31"
TEST_START, TEST_END = "2026-08-01", "2026-08-31"
FETCH_END = "2026-09-10"

FEATURES = base.FEATURES + ["stable_score"]


def normalize_teacher(path: str) -> pd.DataFrame:
    t = pd.read_csv(path, dtype={"symbol": str})
    t["symbol_code"] = (
        t["symbol"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    )
    t["signal_date"] = pd.to_datetime(t["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    rt = pd.to_datetime(t["received_at"], errors="coerce")
    # Production timing convention in the preserved alert history:
    # ~13:00 delivery = completed 09:00 session, >=14:00 = completed 13:00 session.
    t["session"] = np.where(rt.dt.hour < 14, 9, 13)
    t = t[t["signal_date"].notna() & t["session"].isin([9, 13])].copy()
    t["key"] = (
        t["symbol_code"] + "|" + t["signal_date"] + "|" + t["session"].astype(str)
    )
    return t.drop_duplicates("key", keep="last")


def stable_symbols(path: str) -> set[str]:
    s = normalize_teacher(path)
    return set(s["symbol_code"].astype(str))


def build_codes(watchlist_repo: str, stable_syms: set[str], max_symbols: int):
    wl, _, wl_stats = base.load_exact_watchlists(watchlist_repo, TRAIN_START, TEST_END)
    freq: dict[str, int] = {}
    union: set[str] = set()
    for d, syms in wl.items():
        if TRAIN_START <= d <= TEST_END:
            union.update(syms)
            for s in syms:
                freq[s] = freq.get(s, 0) + 1

    must = sorted(stable_syms & union)
    rest = [s for s in sorted(union, key=lambda x: (-freq.get(x, 0), x)) if s not in set(must)]
    if max_symbols:
        room = max(0, max_symbols - len(must))
        codes = must + rest[:room]
    else:
        codes = must + rest

    return wl, wl_stats, codes, must


def build_dataset(
    bottom_teacher: pd.DataFrame,
    watchlist_repo: str,
    stable_syms: set[str],
    max_symbols: int,
    max_workers: int,
):
    wl, wl_stats, codes, must = build_codes(watchlist_repo, stable_syms, max_symbols)
    universe = set(codes)

    monitor_keys: set[str] = set()
    for d, syms in wl.items():
        if TRAIN_START <= d <= TEST_END:
            monitor_keys.update(f"{d}|{s}" for s in syms if s in universe)

    teacher = bottom_teacher[
        bottom_teacher["symbol_code"].isin(universe)
        & bottom_teacher["signal_date"].between(TRAIN_START, TEST_END)
    ].copy()
    positive_keys = set(teacher["key"])

    frames = []
    errors: dict[str, int] = {}
    failed = []
    ok = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        fut = {
            ex.submit(v13.fetch_one, code, TRAIN_START, FETCH_END, False): code
            for code in codes
        }
        for i, f in enumerate(as_completed(fut), 1):
            code = fut[f]
            try:
                fr, err = f.result()
            except Exception as exc:
                fr, err = None, type(exc).__name__
            if fr is not None:
                ok += 1
                if not fr.empty:
                    frames.append(fr)
            else:
                e = err or "unknown"
                errors[e] = errors.get(e, 0) + 1
                failed.append({"symbol": code, "error": e})
            if i % 100 == 0:
                print(f"V37 fetch {i}/{len(codes)} ok={ok} frames={len(frames)}", flush=True)

    if not frames:
        raise RuntimeError("no V37 candidate frames")

    data = pd.concat(frames, ignore_index=True)
    data["monitor_key"] = data["date"].astype(str) + "|" + data["symbol"].astype(str)
    data = data[
        data["monitor_key"].isin(monitor_keys)
        & data["date"].between(TRAIN_START, TEST_END)
    ].copy()
    data["key"] = (
        data["symbol"].astype(str)
        + "|"
        + data["date"].astype(str)
        + "|"
        + data["session"].astype(int).astype(str)
    )
    data["label_bottom"] = data["key"].isin(positive_keys).astype(int)

    observed = set(data.loc[data["label_bottom"] == 1, "key"])
    coverage = {
        "teacher_bottom_keys": len(positive_keys),
        "observed_bottom_keys": len(observed),
        "recall": len(observed) / len(positive_keys) if positive_keys else None,
        "missing": len(positive_keys - observed),
        "missing_examples": sorted(positive_keys - observed)[:40],
    }

    return data, {
        "watchlists": wl_stats,
        "requested_symbols": len(codes),
        "must_include_stable_symbols": len(must),
        "yahoo_ok": ok,
        "errors": errors,
        "failed_examples": failed[:40],
        "bottom_coverage": coverage,
    }


def weights(y: np.ndarray):
    y = np.asarray(y, dtype=int)
    n = len(y)
    pos = max(1, int(y.sum()))
    neg = max(1, n - pos)
    return np.where(y == 1, n / (2 * pos), n / (2 * neg))


def choose_threshold(y, p, min_recall=0.50, min_pred=5):
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    candidates = sorted(
        set(np.linspace(0.01, 0.99, 250).tolist())
        | set(np.quantile(p, np.linspace(0.10, 0.99, 180)).tolist())
    )
    rows = []
    for th in candidates:
        pred = (p >= th).astype(int)
        n = int(pred.sum())
        if n < min_pred:
            continue
        precision = float(precision_score(y, pred, zero_division=0))
        recall = float(recall_score(y, pred, zero_division=0))
        f1 = float(f1_score(y, pred, zero_division=0))
        rows.append(
            {
                "threshold": float(th),
                "predicted": n,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "eligible": recall >= min_recall,
            }
        )
    eligible = [r for r in rows if r["eligible"]]
    if eligible:
        eligible.sort(
            key=lambda r: (r["precision"], r["f1"], r["recall"], -r["predicted"]),
            reverse=True,
        )
        return eligible[0], rows
    if rows:
        rows.sort(key=lambda r: (r["f1"], r["precision"], r["recall"]), reverse=True)
        out = dict(rows[0])
        out["fallback_no_min_recall"] = True
        return out, rows
    return {"threshold": 0.5, "predicted": 0, "precision": 0, "recall": 0, "f1": 0}, []


def class_stats(df: pd.DataFrame, probs: np.ndarray, threshold: float):
    if df.empty:
        return {"n": 0}
    y = df["label_bottom"].to_numpy(int)
    pred = (np.asarray(probs) >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {
        "n": int(len(df)),
        "positive": int(y.sum()),
        "predicted": int(pred.sum()),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def trade_stats(df: pd.DataFrame):
    x = pd.to_numeric(df.get("perf_5bd"), errors="coerce").dropna()
    if x.empty:
        return {"n": 0}
    s = x.sort_values(ascending=False).reset_index(drop=True)
    return {
        "n": int(len(x)),
        "mean": float(x.mean()),
        "median": float(x.median()),
        "win_rate": float((x > 0).mean()),
        "hit10_rate": float((x >= 0.10).mean()),
        "loss10_rate": float((x <= -0.10).mean()),
        "max": float(x.max()),
        "min": float(x.min()),
        "top1_removed_mean": float(s.iloc[1:].mean()) if len(s) > 1 else None,
    }


def strict_stable6_metrics(selected: pd.DataFrame, production_keys: set[str], all_prod_keys: set[str]):
    skeys = set(selected["key"]) if not selected.empty else set()
    overlap = skeys & production_keys
    return {
        "selected": len(skeys),
        "production_stable6_available": len(production_keys),
        "overlap": len(overlap),
        "strict_precision": len(overlap) / len(skeys) if skeys else None,
        "strict_recall": len(overlap) / len(production_keys) if production_keys else None,
        "all_production_stable6_rows_in_sample": len(all_prod_keys),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bottom-teacher", required=True)
    ap.add_argument("--stable6-teacher", required=True)
    ap.add_argument("--watchlist-repo", required=True)
    ap.add_argument("--max-symbols", type=int, default=500)
    ap.add_argument("--max-workers", type=int, default=20)
    ap.add_argument("--output-dir", default="research_artifacts/v37_stable_bottom_gate")
    a = ap.parse_args()

    bottom = normalize_teacher(a.bottom_teacher)
    stable6 = normalize_teacher(a.stable6_teacher)
    stable_syms = set(stable6["symbol_code"])

    data, coverage = build_dataset(
        bottom, a.watchlist_repo, stable_syms, a.max_symbols, a.max_workers
    )

    # Stable-focused population only; outcome returns are not used for training.
    focus = data[data["stable_score"] >= 4].copy()
    train = focus[focus["date"].between(TRAIN_START, TRAIN_END)].copy()
    valid = focus[focus["date"].between(VALID_START, VALID_END)].copy()
    test = focus[focus["date"].between(TEST_START, TEST_END)].copy()

    if min(int(train["label_bottom"].sum()), int(valid["label_bottom"].sum()), int(test["label_bottom"].sum())) < 3:
        raise RuntimeError(
            f"too few Bottom positives in stable-focused split: "
            f"train={train.label_bottom.sum()} valid={valid.label_bottom.sum()} test={test.label_bottom.sum()}"
        )

    model = HistGradientBoostingClassifier(
        learning_rate=0.05,
        max_iter=260,
        max_leaf_nodes=31,
        min_samples_leaf=20,
        l2_regularization=2.0,
        random_state=42,
    )
    ytr = train["label_bottom"].to_numpy(int)
    model.fit(
        train[FEATURES].astype(float),
        ytr,
        sample_weight=weights(ytr),
    )
    pv = model.predict_proba(valid[FEATURES].astype(float))[:, 1]
    threshold, trials = choose_threshold(valid["label_bottom"].to_numpy(int), pv)

    pt = model.predict_proba(test[FEATURES].astype(float))[:, 1]
    test = test.copy()
    test["bottom_prob"] = pt

    valid6 = valid[valid["stable_score"] == 6].copy()
    test6 = test[test["stable_score"] == 6].copy()
    pvalid6 = model.predict_proba(valid6[FEATURES].astype(float))[:, 1] if len(valid6) else np.array([])
    ptest6 = test6["bottom_prob"].to_numpy(float) if len(test6) else np.array([])

    selected4 = test[test["bottom_prob"] >= threshold["threshold"]].copy()
    selected6 = test6[test6["bottom_prob"] >= threshold["threshold"]].copy()

    prod_test = stable6[stable6["signal_date"].between(TEST_START, TEST_END)].copy()
    prod_val = stable6[stable6["signal_date"].between(VALID_START, VALID_END)].copy()
    prod_test_keys = set(prod_test["key"])
    prod_val_keys = set(prod_val["key"])

    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    result = {
        "scope": (
            "Stable-focused Bottom gate. Exact historical watchlist is authoritative "
            "for previous-day eligibility; Yahoo official daily + synthetic 09/13 sessions "
            "generate features. No return outcome is used to fit or choose the threshold."
        ),
        "sampling": {
            "max_symbols": a.max_symbols,
            "stable6_symbols_must_include": len(stable_syms),
        },
        "coverage": coverage,
        "focus_rule": "Yahoo stable_score >= 4",
        "features": FEATURES,
        "split": {
            "train": {"n": len(train), "bottom": int(train.label_bottom.sum())},
            "valid": {"n": len(valid), "bottom": int(valid.label_bottom.sum())},
            "test": {"n": len(test), "bottom": int(test.label_bottom.sum())},
        },
        "threshold_policy": (
            "July validation only: maximize Bottom precision subject to recall >= 50% "
            "and at least 5 predicted rows. August is untouched test."
        ),
        "threshold": threshold,
        "classification": {
            "validation_stable4plus": class_stats(valid, pv, threshold["threshold"]),
            "validation_stable6": class_stats(valid6, pvalid6, threshold["threshold"]) if len(valid6) else {"n": 0},
            "test_stable4plus": class_stats(test, pt, threshold["threshold"]),
            "test_stable6": class_stats(test6, ptest6, threshold["threshold"]) if len(test6) else {"n": 0},
        },
        "trading_test_reporting_only": {
            "all_yahoo_stable6": trade_stats(test6),
            "bottom_gated_yahoo_stable6": trade_stats(selected6),
            "bottom_gated_stable4plus": trade_stats(selected4),
        },
        "strict_production_stable6": {
            "validation": strict_stable6_metrics(
                valid6[pvalid6 >= threshold["threshold"]] if len(valid6) else valid6,
                prod_val_keys,
                set(stable6["key"]),
            ),
            "test": strict_stable6_metrics(
                selected6, prod_test_keys, set(stable6["key"])
            ),
        },
        "production_writes": False,
    }

    (out / "v37_stable_bottom_gate.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    test.sort_values("bottom_prob", ascending=False).to_csv(
        out / "v37_test_stable4plus.csv", index=False
    )
    selected6.to_csv(out / "v37_test_selected_stable6.csv", index=False)
    pd.DataFrame(trials).to_csv(out / "v37_threshold_trials.csv", index=False)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
