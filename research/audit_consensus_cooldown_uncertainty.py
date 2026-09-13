from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ATR_CAP = 2.8640659721217943
BOOTSTRAPS = 20000
SEED_FULL = 20260914
SEED_H2 = 20260915


def load_selected(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path, dtype={"symbol": str})
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d["symbol"] = d["symbol"].astype(str).str.replace(r"\.0$", "", regex=True)
    return d[d["date"].notna()].copy()


def attach_nextopen(d: pd.DataFrame, daily_path: Path) -> tuple[pd.DataFrame, dict[pd.Timestamp, int]]:
    syms = set(d["symbol"])
    parts = []
    all_dates = set()
    for c in pd.read_csv(
        daily_path,
        usecols=["date", "open", "close", "symbol"],
        dtype={"symbol": str},
        chunksize=500_000,
    ):
        c["date"] = pd.to_datetime(c["date"], errors="coerce")
        all_dates.update(c["date"].dropna().tolist())
        c["symbol"] = c["symbol"].astype(str).str.replace(r"\.0$", "", regex=True)
        q = c[c["symbol"].isin(syms)].copy()
        if len(q):
            parts.append(q)
    daily = pd.concat(parts, ignore_index=True).sort_values(["symbol", "date"])
    g = daily.groupby("symbol", sort=False)
    daily["next_open"] = g["open"].shift(-1)
    daily["d5_close"] = g["close"].shift(-5)
    x = d.merge(
        daily[["symbol", "date", "next_open", "d5_close"]],
        on=["symbol", "date"],
        how="left",
        validate="many_to_one",
    )
    x["ret"] = x["d5_close"] / x["next_open"] - 1
    dates = sorted(pd.Timestamp(v) for v in all_dates)
    return x, {v: i for i, v in enumerate(dates)}


def cooldown(d: pd.DataFrame, day_index: dict[pd.Timestamp, int], cd: int = 5) -> pd.DataFrame:
    last = {}
    keep = []
    for idx, row in d.sort_values(["date", "session"]).iterrows():
        di = day_index[row["date"]]
        sym = str(row["symbol"])
        if sym in last and di - last[sym] < cd:
            continue
        keep.append(idx)
        last[sym] = di
    return d.loc[keep].sort_values(["date", "session"]).copy()


def interval(a: np.ndarray) -> dict:
    return {
        "p025_mean_pct": float(np.quantile(a, 0.025) * 100),
        "p50_mean_pct": float(np.quantile(a, 0.50) * 100),
        "p975_mean_pct": float(np.quantile(a, 0.975) * 100),
        "positive_fraction": float(np.mean(a > 0)),
    }


def uncertainty(d: pd.DataFrame, seed: int) -> dict:
    x = d.copy()
    x["month"] = x["date"].dt.to_period("M").astype(str)
    x["week"] = x["date"].dt.to_period("W").astype(str)
    vals = x["ret"].dropna().to_numpy(float)
    rng = np.random.default_rng(seed)

    iid_idx = rng.integers(0, len(vals), size=(BOOTSTRAPS, len(vals)))
    iid = vals[iid_idx].mean(axis=1)

    def cluster(col: str) -> np.ndarray:
        groups = {str(k): g["ret"].dropna().to_numpy(float) for k, g in x.groupby(col)}
        keys = list(groups)
        out = np.empty(BOOTSTRAPS)
        for i in range(BOOTSTRAPS):
            sample = rng.choice(keys, size=len(keys), replace=True)
            out[i] = np.concatenate([groups[k] for k in sample]).mean()
        return out

    def leave_one(col: str) -> dict:
        rows = []
        for key in x[col].astype(str).unique():
            q = x[x[col].astype(str) != key]["ret"].dropna()
            rows.append({"removed": key, "n": int(len(q)), "mean_pct": float(q.mean() * 100)})
        return {
            "minimum": min(rows, key=lambda z: z["mean_pct"]),
            "maximum": max(rows, key=lambda z: z["mean_pct"]),
        }

    return {
        "n": int(len(vals)),
        "mean_pct": float(vals.mean() * 100),
        "median_pct": float(np.median(vals) * 100),
        "iid_bootstrap": interval(iid),
        "symbol_cluster_bootstrap": interval(cluster("symbol")),
        "month_cluster_bootstrap": interval(cluster("month")),
        "week_cluster_bootstrap": interval(cluster("week")),
        "leave_one_symbol": leave_one("symbol"),
        "leave_one_month": leave_one("month"),
        "leave_one_week": leave_one("week"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selected-min95", required=True, type=Path)
    ap.add_argument("--frozen-daily", required=True, type=Path)
    ap.add_argument("--output", type=Path)
    a = ap.parse_args()

    selected = load_selected(a.selected_min95)
    selected = selected[pd.to_numeric(selected["market_median_atr"], errors="coerce") <= ATR_CAP]
    selected, day_index = attach_nextopen(selected, a.frozen_daily)
    selected = cooldown(selected, day_index, 5)
    full = uncertainty(selected, SEED_FULL)
    h2 = uncertainty(selected[selected["date"] >= "2025-07-01"].copy(), SEED_H2)

    result = {
        "scope": "descriptive uncertainty only; no policy selection",
        "atr_cap": ATR_CAP,
        "cooldown_sessions": 5,
        "replacement": False,
        "bootstraps": BOOTSTRAPS,
        "full_2025": full,
        "h2_2025": h2,
        "production_writes": False,
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
