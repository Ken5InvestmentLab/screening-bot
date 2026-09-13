from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from tvfree_screener.batch02 import eval_causal_4h_scoring_v3 as v3
from tvfree_screener.batch02 import eval_causal_4h_scoring_v4 as v4
from tvfree_screener.batch02.eval_causal_4h_monster_v8 import pareto_front

INTRADAY_FEATURES = list(v4.FEATURES)
DAILY_FEATURES = [
    "d1_log_return",
    "d5_log_return",
    "d20_log_return",
    "d20_realized_vol",
    "d20_close_position",
    "d5_vs20_volume_log_ratio",
    "d1_range_pct",
]
FEATURES = INTRADAY_FEATURES + DAILY_FEATURES
BINS = ["AM_09_13", "PM_13_CLOSE"]
TOP_NS = [1, 2, 3, 5]
REG_PARAMS = dict(
    learning_rate=0.05,
    max_iter=150,
    max_leaf_nodes=15,
    min_samples_leaf=200,
    l2_regularization=1.0,
    max_bins=63,
    early_stopping=False,
    random_state=0,
)


def build_daily_context(daily: pd.DataFrame) -> pd.DataFrame:
    d = daily.copy().sort_values(["symbol", "date"], kind="stable")
    for c in ["open", "high", "low", "close", "volume"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    g = d.groupby("symbol", sort=False, group_keys=False)
    d["log_close"] = np.log(d["close"].where(d["close"] > 0))
    d["d1_log_return"] = g["log_close"].diff(1)
    d["d5_log_return"] = d["log_close"] - g["log_close"].shift(5)
    d["d20_log_return"] = d["log_close"] - g["log_close"].shift(20)
    d["d20_realized_vol"] = g["d1_log_return"].transform(lambda s: s.rolling(20, min_periods=20).std(ddof=0))
    low20 = g["low"].transform(lambda s: s.rolling(20, min_periods=20).min())
    high20 = g["high"].transform(lambda s: s.rolling(20, min_periods=20).max())
    width = high20 - low20
    d["d20_close_position"] = np.where(width > 0, (d["close"] - low20) / width, np.nan)
    v5 = g["volume"].transform(lambda s: s.rolling(5, min_periods=5).mean())
    v20 = g["volume"].transform(lambda s: s.rolling(20, min_periods=20).mean())
    d["d5_vs20_volume_log_ratio"] = np.where((v5 > 0) & (v20 > 0), np.log(v5 / v20), np.nan)
    d["d1_range_pct"] = np.where(d["close"] > 0, (d["high"] - d["low"]) / d["close"], np.nan)
    return d[["symbol", "date"] + DAILY_FEATURES].rename(columns={"date": "prior_date"})


def prepare(candidates_pattern: str, daily_path: str | Path):
    daily_path = Path(daily_path)
    expected = "6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0"
    actual = v3.sha256_file(daily_path)
    if actual != expected:
        raise RuntimeError(f"daily SHA mismatch: {actual}")
    cand = v4.load_candidates(candidates_pattern)
    daily = v3.load_daily(daily_path)
    ctx = build_daily_context(daily)
    cand["prior_date"] = cand["prior_date"].astype(str).str[:10]
    cand = cand.merge(ctx, on=["symbol", "prior_date"], how="left")
    finite = np.isfinite(cand[FEATURES]).all(axis=1)
    cand = cand.loc[finite].copy()
    cand, session_idx = v3.attach_endpoint_labels(cand, daily)
    return cand, daily, session_idx, actual


def fit_quantile(train: pd.DataFrame, valid: pd.DataFrame, q: float) -> np.ndarray:
    model = HistGradientBoostingRegressor(loss="quantile", quantile=q, **REG_PARAMS)
    model.fit(train[FEATURES], train["ret5bd_gross"].to_numpy(float))
    return model.predict(valid[FEATURES])


def score_month(cand: pd.DataFrame, month: str):
    period = pd.Period(month, freq="M")
    start = period.start_time.date().isoformat()
    end = period.end_time.date().isoformat()
    train = cand[
        (cand["date"] >= "2025-01-01")
        & (cand["date"] < start)
        & (cand["exit_date"] < start)
        & (cand["endpoint_status"] == "RESOLVED")
    ].copy()
    valid = cand[(cand["date"] >= start) & (cand["date"] <= end)].copy()
    out = valid.copy()
    for col in ["q10_raw", "q50_raw", "q90_raw"]:
        out[col] = np.nan
    for bn in BINS:
        tr = train[train["bin_name"] == bn]
        idx = out.index[out["bin_name"] == bn]
        if tr.empty or not len(idx):
            continue
        va = out.loc[idx]
        for q, col in [(0.10, "q10_raw"), (0.50, "q50_raw"), (0.90, "q90_raw")]:
            out.loc[idx, col] = fit_quantile(tr, va, q)
    raw = out[["q10_raw", "q50_raw", "q90_raw"]].to_numpy(float)
    out["quantile_crossed_raw"] = (raw[:, 0] > raw[:, 1]) | (raw[:, 1] > raw[:, 2])
    ordered = np.sort(raw, axis=1)
    out["q10"], out["q50"], out["q90"] = ordered[:, 0], ordered[:, 1], ordered[:, 2]
    out["score_core"] = out["q50"]
    meta = {
        "month": month,
        "month_start": start,
        "month_end": end,
        "train_rows": int(len(train)),
        "eval_rows": int(len(valid)),
        "train_max_candidate_date": str(train["date"].max()),
        "train_max_exit_date": str(train["exit_date"].max()),
        "quantile_crossing_raw_rate": float(out["quantile_crossed_raw"].mean()),
    }
    keep = ["symbol", "date", "bin_name", "endpoint_status", "ret5bd_gross", "q10", "q50", "q90", "score_core", "quantile_crossed_raw"]
    return out[keep].copy(), meta


def select_core(scored: pd.DataFrame, session_idx: dict[str, int], n: int) -> pd.DataFrame:
    x = scored.sort_values(["date", "bin_name", "score_core", "symbol"], ascending=[True, True, False, True], kind="stable")
    groups = {(d, b): g.to_dict("records") for (d, b), g in x.groupby(["date", "bin_name"], sort=False)}
    blocked = {}; rows = []
    for day in sorted(scored["date"].unique()):
        di = session_idx[day]
        for bn in BINS:
            picked = 0
            for row in groups.get((day, bn), ()):
                sym = str(row["symbol"])
                if blocked.get(sym, -999999) > di:
                    continue
                rows.append(row); blocked[sym] = di + 5; picked += 1
                if picked >= n: break
    return pd.DataFrame(rows)


def select_monster(scored: pd.DataFrame, session_idx: dict[str, int], n: int) -> pd.DataFrame:
    fronts = [pareto_front(g) for _, g in scored.groupby(["date", "bin_name"], sort=False)]
    x = pd.concat(fronts, ignore_index=True) if fronts else scored.iloc[0:0].copy()
    x = x.sort_values(["date", "bin_name", "q90", "q10", "symbol"], ascending=[True, True, False, False, True], kind="stable")
    groups = {(d, b): g.to_dict("records") for (d, b), g in x.groupby(["date", "bin_name"], sort=False)}
    blocked = {}; rows = []
    for day in sorted(scored["date"].unique()):
        di = session_idx[day]
        for bn in BINS:
            picked = 0
            for row in groups.get((day, bn), ()):
                sym = str(row["symbol"])
                if blocked.get(sym, -999999) > di:
                    continue
                rows.append(row); blocked[sym] = di + 5; picked += 1
                if picked >= n: break
    return pd.DataFrame(rows)


def aggregate(scored: pd.DataFrame, session_idx: dict[str, int]):
    result = {"core": {}, "monster": {}}
    for n in TOP_NS:
        c = select_core(scored, session_idx, n)
        cm = v3.metrics(c, 0.005); cm["passes_comparability_gates"] = v3.passes("core", cm)
        result["core"][str(n)] = cm
        m = select_monster(scored, session_idx, n)
        mm = v3.metrics(m, 0.005); mm["passes_comparability_gates"] = v3.passes("monster", mm)
        result["monster"][str(n)] = mm
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["month", "aggregate"], required=True)
    p.add_argument("--candidates")
    p.add_argument("--daily", required=True)
    p.add_argument("--month")
    p.add_argument("--scored-output")
    p.add_argument("--meta-output")
    p.add_argument("--scored-glob")
    p.add_argument("--period")
    p.add_argument("--output")
    a = p.parse_args()
    if a.mode == "month":
        cand, _, _, daily_sha = prepare(a.candidates, a.daily)
        scored, meta = score_month(cand, a.month)
        Path(a.scored_output).parent.mkdir(parents=True, exist_ok=True)
        scored.to_csv(a.scored_output, index=False, compression="gzip" if str(a.scored_output).endswith(".gz") else None)
        meta["daily_sha256"] = daily_sha; meta["2026_outcomes_opened"] = False
        Path(a.meta_output).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        return
    files = sorted(glob.glob(a.scored_glob))
    if not files: raise FileNotFoundError(a.scored_glob)
    scored = pd.concat([pd.read_csv(f, dtype={"symbol": "string"}) for f in files], ignore_index=True)
    daily = v3.load_daily(Path(a.daily)); sessions = sorted(daily["date"].dropna().unique().tolist()); session_idx = {d: i for i, d in enumerate(sessions)}
    out = {"experiment_id": "CAUSAL-4H-SCORING-V9-PRIOR-DAILY-CONTEXT-20260913", "period": a.period, "rows": int(len(scored)), "results": aggregate(scored, session_idx), "2026_outcomes_opened": False, "production_modified": False}
    Path(a.output).write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
