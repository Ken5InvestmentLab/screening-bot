from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def stats(df: pd.DataFrame):
    if df is None or df.empty or "perf_5bd" not in df:
        return {"n": 0}
    x = pd.to_numeric(df["perf_5bd"], errors="coerce").dropna()
    if x.empty:
        return {"n": 0}
    y = x.sort_values(ascending=False).reset_index(drop=True)
    return {
        "n": int(len(x)),
        "mean": float(x.mean()),
        "median": float(x.median()),
        "win_rate": float((x > 0).mean()),
        "hit10_rate": float((x >= .10).mean()),
        "hit20_rate": float((x >= .20).mean()),
        "loss10_rate": float((x <= -.10).mean()),
        "loss20_rate": float((x <= -.20).mean()),
        "min": float(x.min()),
        "max": float(x.max()),
        "p10": float(x.quantile(.10)),
        "p25": float(x.quantile(.25)),
        "p75": float(x.quantile(.75)),
        "p90": float(x.quantile(.90)),
        "top1_removed_mean": float(y.iloc[1:].mean()) if len(y) > 1 else None,
        "top3_removed_mean": float(y.iloc[3:].mean()) if len(y) > 3 else None,
    }


def norm_selected(path: str) -> pd.DataFrame:
    d = pd.read_csv(path, dtype={"symbol": str})
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d["perf_5bd"] = pd.to_numeric(d["perf_5bd"], errors="coerce")
    if "session" in d:
        d["session"] = pd.to_numeric(d["session"], errors="coerce").astype("Int64")
    d = d[d["date"].notna() & d["perf_5bd"].notna()].copy()
    d["date_s"] = d["date"].dt.strftime("%Y-%m-%d")
    d["month"] = d["date"].dt.strftime("%Y-%m")
    d["week_start"] = (
        d["date"] - pd.to_timedelta(d["date"].dt.weekday, unit="D")
    ).dt.strftime("%Y-%m-%d")
    return d


def norm_stable(path: str) -> pd.DataFrame:
    t = pd.read_csv(path, dtype={"symbol": str})
    date_col = "signal_date" if "signal_date" in t.columns else "date"
    symbol_col = "symbol_code" if "symbol_code" in t.columns else "symbol"
    t["date"] = pd.to_datetime(t[date_col], errors="coerce")
    t["symbol_norm"] = (
        t[symbol_col].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    )
    t["perf_5bd"] = pd.to_numeric(t["perf_5bd"], errors="coerce")
    if "session" not in t.columns and "received_at" in t.columns:
        rt = pd.to_datetime(t["received_at"], errors="coerce")
        t["session"] = np.where(rt.dt.hour < 14, 9, 13)
    t["session"] = pd.to_numeric(t["session"], errors="coerce").astype("Int64")
    t = t[t["date"].notna() & t["perf_5bd"].notna()].copy()
    t["date_s"] = t["date"].dt.strftime("%Y-%m-%d")
    t["month"] = t["date"].dt.strftime("%Y-%m")
    return t


def group_stats(df: pd.DataFrame, col: str):
    if col not in df.columns:
        return {}
    out = {}
    for k, g in df.groupby(col, dropna=False):
        out[str(k)] = stats(g)
    return out


def remove_group(df: pd.DataFrame, group_col: str, group_value):
    return df[df[group_col].astype(str) != str(group_value)].copy()


def contribution_table(df: pd.DataFrame, group_col: str):
    rows = []
    for k, g in df.groupby(group_col):
        x = pd.to_numeric(g["perf_5bd"], errors="coerce").dropna()
        rows.append({
            group_col: str(k),
            "n": int(len(x)),
            "sum_return": float(x.sum()),
            "mean": float(x.mean()) if len(x) else None,
        })
    return sorted(rows, key=lambda r: r["sum_return"], reverse=True)


def best_group_removal(df: pd.DataFrame, group_col: str):
    tab = contribution_table(df, group_col)
    if not tab:
        return {"removed": None, "stats": stats(df)}
    best = tab[0][group_col]
    return {
        "removed": str(best),
        "removed_group": tab[0],
        "stats": stats(remove_group(df, group_col, best)),
    }


def remove_best_k_groups(df: pd.DataFrame, group_col: str, k: int):
    tab = contribution_table(df, group_col)
    removed = [r[group_col] for r in tab[:k]]
    keep = ~df[group_col].astype(str).isin(set(map(str, removed)))
    return {
        "removed": removed,
        "removed_groups": tab[:k],
        "stats": stats(df[keep].copy()),
    }


def symbol_concentration(df: pd.DataFrame):
    if "symbol" not in df.columns:
        return {}
    g = (
        df.groupby("symbol")["perf_5bd"]
        .agg(["count", "sum", "mean"])
        .sort_values("sum", ascending=False)
    )
    total = float(df["perf_5bd"].sum())
    top = []
    for sym, r in g.head(10).iterrows():
        top.append({
            "symbol": str(sym),
            "n": int(r["count"]),
            "sum_return": float(r["sum"]),
            "mean": float(r["mean"]),
            "share_of_net_sum": float(r["sum"] / total) if total else None,
        })
    return {
        "unique_symbols": int(df["symbol"].nunique()),
        "repeat_trade_rate": float(1 - df["symbol"].nunique() / len(df)) if len(df) else None,
        "top10_by_net_contribution": top,
    }


def day_block_bootstrap(df: pd.DataFrame, seed=4101, samples=5000):
    if df.empty:
        return {}
    day = df.groupby("date_s")["perf_5bd"].agg(["sum", "count"])
    if len(day) < 3:
        return {"days": int(len(day)), "mean_ci95": None}
    rng = np.random.default_rng(seed)
    sums = day["sum"].to_numpy(float)
    counts = day["count"].to_numpy(float)
    means = np.empty(samples)
    n = len(day)
    for i in range(samples):
        idx = rng.integers(0, n, size=n)
        means[i] = sums[idx].sum() / counts[idx].sum()
    return {
        "days": int(n),
        "samples": int(samples),
        "mean_ci95": [
            float(np.quantile(means, .025)),
            float(np.quantile(means, .975)),
        ],
        "bootstrap_mean": float(np.mean(means)),
    }


def overlap_with_stable(df: pd.DataFrame, stable: pd.DataFrame):
    if df.empty or stable.empty:
        return {}
    a = df.copy()
    a["symbol_norm"] = a["symbol"].astype(str).str.replace(r"\.0$", "", regex=True)
    a["key"] = (
        a["date_s"] + "|" + a["symbol_norm"] + "|" + a["session"].astype(str)
    )
    s = stable.copy()
    s["key"] = (
        s["date_s"] + "|" + s["symbol_norm"] + "|" + s["session"].astype(str)
    )
    ak, sk = set(a["key"]), set(s["key"])
    ov = ak & sk
    return {
        "selected": len(ak),
        "stable6": len(sk),
        "overlap": len(ov),
        "precision_vs_stable6": len(ov) / len(ak) if ak else None,
        "recall_vs_stable6": len(ov) / len(sk) if sk else None,
    }


def aligned_stable_stats(stable: pd.DataFrame, selected: pd.DataFrame):
    if selected.empty:
        return {"n": 0}
    lo, hi = selected["date"].min(), selected["date"].max()
    s = stable[stable["date"].between(lo, hi)].copy()
    return {
        "range": [lo.strftime("%Y-%m-%d"), hi.strftime("%Y-%m-%d")],
        "stats": stats(s),
        "monthly": group_stats(s, "month"),
    }


def analyze(name: str, df: pd.DataFrame, stable: pd.DataFrame):
    return {
        "name": name,
        "overall": stats(df),
        "monthly": group_stats(df, "month"),
        "session": group_stats(df, "session"),
        "week_contributions": contribution_table(df, "week_start"),
        "day_contributions_top10": contribution_table(df, "date_s")[:10],
        "remove_best_trade": stats(
            df.drop(index=df["perf_5bd"].idxmax()) if len(df) else df
        ),
        "remove_best_3_trades": stats(
            df.drop(index=df.nlargest(min(3, len(df)), "perf_5bd").index)
            if len(df) else df
        ),
        "remove_best_day": best_group_removal(df, "date_s"),
        "remove_best_3_days": remove_best_k_groups(df, "date_s", 3),
        "remove_best_week": best_group_removal(df, "week_start"),
        "remove_best_2_weeks": remove_best_k_groups(df, "week_start", 2),
        "symbol_concentration": symbol_concentration(df),
        "day_block_bootstrap": day_block_bootstrap(df),
        "production_stable6_same_range": aligned_stable_stats(stable, df),
        "overlap_with_production_stable6": overlap_with_stable(df, stable),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min97", required=True)
    ap.add_argument("--min98", required=True)
    ap.add_argument("--stable6-teacher", required=True)
    ap.add_argument("--output-dir", default="research_artifacts/v41_stress")
    a = ap.parse_args()

    d97 = norm_selected(a.min97)
    d98 = norm_selected(a.min98)
    stable = norm_stable(a.stable6_teacher)

    result = {
        "scope": (
            "V41 destructive stress audit of V40 full-universe fixed consensus. "
            "No threshold tuning, no production writes. Stress tests explicitly remove "
            "best trades/days/weeks to measure concentration."
        ),
        "min97": analyze("fixed_min97_both", d97, stable),
        "min98": analyze("fixed_min98_both", d98, stable),
        "promotion_guard": {
            "principle": (
                "Do not promote merely because raw mean is high. Prefer a candidate whose "
                "mean remains economically meaningful after removing the strongest week "
                "and whose performance is not dominated by one symbol/date."
            )
        },
        "production_writes": False,
    }

    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "v41_stress.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
