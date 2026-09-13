from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.utils.class_weight import compute_sample_weight

FEATURES = [
    "bar_log_return",
    "range_pct",
    "upper_wick_pct",
    "lower_wick_pct",
    "prev4_log_return_mean",
    "prev4_range_mean",
    "log_range_vs_prior20",
]
BINS = ["AM_09_13", "PM_13_CLOSE"]
TOP_NS = [1, 2, 3, 5]
EPS = 1e-6
MODEL_PARAMS = dict(
    learning_rate=0.05,
    max_iter=150,
    max_leaf_nodes=15,
    min_samples_leaf=200,
    l2_regularization=1.0,
    max_bins=63,
    early_stopping=False,
    random_state=0,
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_candidates(pattern: str) -> pd.DataFrame:
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(pattern)
    parts = [pd.read_csv(f, dtype={"symbol": "string"}) for f in files]
    df = pd.concat(parts, ignore_index=True)
    df["symbol"] = df["symbol"].astype(str).str.replace(r"\.0$", "", regex=True).str.upper()
    df["date"] = df["date"].astype(str).str[:10]
    for c in FEATURES + ["bin_volume", "prior_daily_close", "prior_daily_volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    complete = np.isfinite(df[FEATURES]).all(axis=1)
    gate = (
        complete
        & np.isfinite(df["prior_daily_close"])
        & (df["prior_daily_close"] <= 1000)
        & np.isfinite(df["prior_daily_volume"])
        & (df["prior_daily_volume"] >= 10000)
    )
    return df.loc[gate].copy()


def load_daily(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path, dtype={"symbol": "string"}, low_memory=False)
    d["symbol"] = d["symbol"].astype(str).str.replace(r"\.0$", "", regex=True).str.upper()
    d["date"] = d["date"].astype(str).str[:10]
    for c in ["open", "high", "low", "close", "volume"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    return d


def attach_endpoint_labels(cand: pd.DataFrame, daily: pd.DataFrame):
    sessions = sorted(daily["date"].dropna().unique().tolist())
    session_idx = {d: i for i, d in enumerate(sessions)}
    map_entry = {sessions[i]: sessions[i + 1] for i in range(len(sessions) - 5)}
    map_exit = {sessions[i]: sessions[i + 5] for i in range(len(sessions) - 5)}
    out = cand.copy()
    out["entry_date"] = out["date"].map(map_entry)
    out["exit_date"] = out["date"].map(map_exit)
    entry = daily[["symbol", "date", "open"]].rename(columns={"date": "entry_date", "open": "entry_open"})
    exit_ = daily[["symbol", "date", "close"]].rename(columns={"date": "exit_date", "close": "exit_close"})
    out = out.merge(entry, on=["symbol", "entry_date"], how="left").merge(exit_, on=["symbol", "exit_date"], how="left")
    resolved = (
        np.isfinite(out["entry_open"])
        & (out["entry_open"] > 0)
        & np.isfinite(out["exit_close"])
        & (out["exit_close"] > 0)
    )
    out["endpoint_status"] = np.where(resolved, "RESOLVED", "UNRESOLVED_ENDPOINT")
    out["ret5bd_gross"] = np.where(resolved, out["exit_close"] / out["entry_open"] - 1.0, np.nan)
    return out, session_idx


def _fit_predict(train: pd.DataFrame, valid: pd.DataFrame, target: str) -> np.ndarray:
    y = train[target].to_numpy(dtype=int)
    if len(np.unique(y)) < 2:
        return np.full(len(valid), float(y[0]) if len(y) else 0.0)
    w = compute_sample_weight(class_weight="balanced", y=y)
    model = HistGradientBoostingClassifier(**MODEL_PARAMS)
    model.fit(train[FEATURES], y, sample_weight=w)
    return model.predict_proba(valid[FEATURES])[:, 1]


def score_period(train: pd.DataFrame, valid: pd.DataFrame) -> pd.DataFrame:
    scored = valid.copy()
    scored["p_positive"] = np.nan
    scored["p_plus20"] = np.nan
    scored["p_loss10"] = np.nan
    for bin_name in BINS:
        tr = train[train["bin_name"] == bin_name].copy()
        va_idx = scored.index[scored["bin_name"] == bin_name]
        if tr.empty or len(va_idx) == 0:
            continue
        va = scored.loc[va_idx]
        tr["target_positive"] = (tr["ret5bd_gross"] > 0).astype(int)
        tr["target_plus20"] = (tr["ret5bd_gross"] >= 0.20).astype(int)
        tr["target_loss10"] = (tr["ret5bd_gross"] <= -0.10).astype(int)
        scored.loc[va_idx, "p_positive"] = _fit_predict(tr, va, "target_positive")
        scored.loc[va_idx, "p_plus20"] = _fit_predict(tr, va, "target_plus20")
        scored.loc[va_idx, "p_loss10"] = _fit_predict(tr, va, "target_loss10")
    for c in ["p_positive", "p_plus20", "p_loss10"]:
        scored[c] = scored[c].clip(EPS, 1 - EPS)
    loss_logit = np.log(scored["p_loss10"] / (1 - scored["p_loss10"]))
    for head, gain in [("core", "p_positive"), ("monster", "p_plus20")]:
        gain_logit = np.log(scored[gain] / (1 - scored[gain]))
        scored[f"score_{head}"] = gain_logit - loss_logit
    return scored


def select_policy(scored: pd.DataFrame, session_idx: dict[str, int], head: str, top_n: int) -> pd.DataFrame:
    score = f"score_{head}"
    ordered = scored.sort_values(["date", "bin_name", score, "symbol"], ascending=[True, True, False, True], kind="stable")
    groups = {(d, b): g.to_dict("records") for (d, b), g in ordered.groupby(["date", "bin_name"], sort=False)}
    blocked: dict[str, int] = {}
    rows = []
    for date in sorted(scored["date"].unique()):
        di = session_idx[date]
        for bin_name in BINS:
            picked = 0
            for r in groups.get((date, bin_name), ()):
                sym = r["symbol"]
                if blocked.get(sym, -999999) > di:
                    continue
                rows.append(r)
                blocked[sym] = di + 5
                picked += 1
                if picked >= top_n:
                    break
    return pd.DataFrame(rows)


def metrics(sel: pd.DataFrame, cost: float = 0.005) -> dict:
    if sel.empty:
        return {"requested": 0, "resolved": 0, "unresolved": 0}
    r = sel[sel["endpoint_status"] == "RESOLVED"].copy()
    out = {"requested": int(len(sel)), "resolved": int(len(r)), "unresolved": int(len(sel) - len(r))}
    if r.empty:
        return out
    v = r["ret5bd_gross"].to_numpy(float)
    net = v - cost
    desc = np.sort(net)[::-1]
    rr = r.assign(net=net, month=r["date"].str[:7])
    mm = rr.groupby("month")["net"].mean()
    vc = r["symbol"].value_counts(normalize=True)
    out.update(
        net_mean=float(net.mean()),
        net_median=float(np.median(net)),
        net_win_rate=float((net > 0).mean()),
        gross_ge10_rate=float((v >= 0.10).mean()),
        gross_ge20_rate=float((v >= 0.20).mean()),
        gross_ge50_rate=float((v >= 0.50).mean()),
        gross_le10_rate=float((v <= -0.10).mean()),
        gross_le20_rate=float((v <= -0.20).mean()),
        top1_removed_net_mean=float(desc[1:].mean()) if len(desc) > 1 else None,
        top3_removed_net_mean=float(desc[3:].mean()) if len(desc) > 3 else None,
        top5_removed_net_mean=float(desc[5:].mean()) if len(desc) > 5 else None,
        monthly_positive_mean_fraction=float((mm > 0).mean()),
        top_symbol_fraction=float(vc.iloc[0]),
        top5_symbol_fraction=float(vc.iloc[:5].sum()),
    )
    return out


def passes(head: str, m: dict) -> bool:
    if head == "core":
        return (
            m.get("resolved", 0) >= 50
            and m.get("net_mean", -math.inf) > 0
            and m.get("net_median", -math.inf) >= 0
            and m.get("net_win_rate", -math.inf) > 0.5
            and m.get("top3_removed_net_mean", -math.inf) > 0
            and m.get("gross_le10_rate", math.inf) <= 0.2
        )
    return (
        m.get("resolved", 0) >= 30
        and m.get("net_mean", -math.inf) > 0
        and m.get("gross_ge20_rate", -math.inf) >= 0.1
        and m.get("top1_removed_net_mean", -math.inf) > 0
        and m.get("gross_le10_rate", math.inf) <= 0.4
    )


def evaluate_window(cand: pd.DataFrame, session_idx: dict[str, int], *, train_start: str, train_end: str, maturity_cutoff: str, eval_start: str, eval_end: str) -> dict:
    train = cand[
        (cand["date"] >= train_start)
        & (cand["date"] <= train_end)
        & (cand["exit_date"] < maturity_cutoff)
        & (cand["endpoint_status"] == "RESOLVED")
    ].copy()
    valid = cand[(cand["date"] >= eval_start) & (cand["date"] <= eval_end)].copy()
    scored = score_period(train, valid)
    results = {}
    for head in ["core", "monster"]:
        results[head] = {}
        for n in TOP_NS:
            sel = select_policy(scored, session_idx, head, n)
            m = metrics(sel, 0.005)
            m["passes_comparability_gates"] = passes(head, m)
            m["cost0"] = metrics(sel, 0.0)
            m["cost1pct"] = metrics(sel, 0.01)
            results[head][str(n)] = m
    return {
        "train_rows": int(len(train)),
        "eval_rows": int(len(valid)),
        "train_targets": {
            "positive": int((train["ret5bd_gross"] > 0).sum()),
            "plus20": int((train["ret5bd_gross"] >= 0.20).sum()),
            "loss10": int((train["ret5bd_gross"] <= -0.10).sum()),
        },
        "results": results,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--candidates", required=True)
    p.add_argument("--daily", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    daily_path = Path(args.daily)
    expected_daily = "6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0"
    actual_daily = sha256_file(daily_path)
    if actual_daily != expected_daily:
        raise RuntimeError(f"daily SHA mismatch {actual_daily}")

    cand = load_candidates(args.candidates)
    daily = load_daily(daily_path)
    cand, session_idx = attach_endpoint_labels(cand, daily)

    windows = {
        "h1_fold_1_mar_apr": dict(train_start="2025-01-01", train_end="2025-02-28", maturity_cutoff="2025-03-01", eval_start="2025-03-01", eval_end="2025-04-30"),
        "h1_fold_2_may_jun": dict(train_start="2025-01-01", train_end="2025-04-30", maturity_cutoff="2025-05-01", eval_start="2025-05-01", eval_end="2025-06-30"),
        "h2_retrospective": dict(train_start="2025-01-01", train_end="2025-06-30", maturity_cutoff="2025-07-01", eval_start="2025-07-01", eval_end="2025-12-31"),
    }
    summary = {
        "experiment_id": "CAUSAL-4H-SCORING-V3-NONLINEAR-RISK-20260913",
        "daily_sha256": actual_daily,
        "features": FEATURES,
        "model_params": MODEL_PARAMS,
        "risk_score": "logit(p_gain)-logit(p_loss10)",
        "h2_role": "RETROSPECTIVE_REFUTATION_ONLY_NOT_PROMOTABLE",
        "2026_outcomes_opened": False,
        "production_modified": False,
        "windows": {},
    }
    for name, kw in windows.items():
        print(f"RUN {name}", flush=True)
        summary["windows"][name] = evaluate_window(cand, session_idx, **kw)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
