#!/usr/bin/env python3
"""Audit causal V7 Tail detector regime drift across 2023-2025 (TEST ONLY).

Diagnostic only. No threshold selection and no production writes.
Reads the reusable causal Tail cache plus frozen daily dates for exact
one-business-day same-symbol cooldown semantics.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("tvfree_screener/out")

PERIODS = [
    ("2023H1", "2023-01-01", "2023-06-30"),
    ("2023H2", "2023-07-01", "2023-12-31"),
    ("2024H1", "2024-01-01", "2024-06-30"),
    ("2024H2", "2024-07-01", "2024-12-31"),
    ("2025H1", "2025-01-01", "2025-06-30"),
    ("2025H2", "2025-07-01", "2025-12-31"),
]

KEY_FEATURES = [
    "ret1","ret5","ret20","ma20_gap","volr20","rsi14","atr14p",
    "body_pct","lower_wick","upper_wick","range_pct","gap",
    "pos20","dd20","bounce20","bbpct","bbwidth","volz20","log_dv",
    "med_ret5","breadth_ma20","tail_p","tail_cdf",
]


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
        "loss20_rate": float((x <= -0.20).mean()),
        "max": float(x.max()),
        "min": float(x.min()),
    }


def one_per_day(cache: pd.DataFrame, trading_dates: pd.Index) -> pd.DataFrame:
    if cache.empty:
        return cache.copy()
    date_idx = {pd.Timestamp(d): i for i, d in enumerate(trading_dates)}
    rows = []
    last_symbol = None
    last_idx = None
    for date, day in cache.sort_values(
        ["date","tail_cdf","tail_p"], ascending=[True,False,False]
    ).groupby("date", sort=True):
        idx = date_idx.get(pd.Timestamp(date))
        if idx is None:
            continue
        chosen = None
        for _, row in day.sort_values(
            ["tail_cdf","tail_p"], ascending=False
        ).iterrows():
            if (
                last_idx is not None
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


def feature_snapshot(z: pd.DataFrame) -> dict:
    out = {}
    for c in KEY_FEATURES:
        if c not in z.columns:
            continue
        x = pd.to_numeric(z[c], errors="coerce").dropna()
        if x.empty:
            continue
        out[c] = {
            "n": int(len(x)),
            "mean": float(x.mean()),
            "median": float(x.median()),
            "q25": float(x.quantile(.25)),
            "q75": float(x.quantile(.75)),
        }
    return out


def robust_shift(base: pd.DataFrame, other: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for c in KEY_FEATURES:
        if c not in base.columns or c not in other.columns:
            continue
        a = pd.to_numeric(base[c], errors="coerce").dropna()
        b = pd.to_numeric(other[c], errors="coerce").dropna()
        if len(a) < 20 or len(b) < 20:
            continue
        med_a = float(a.median())
        med_b = float(b.median())
        iqr = float(a.quantile(.75) - a.quantile(.25))
        if not np.isfinite(iqr) or iqr == 0:
            iqr = float(a.std(ddof=0))
        if not np.isfinite(iqr) or iqr == 0:
            iqr = 1.0
        rows.append({
            "feature": c,
            "base_median_2024": med_a,
            "median_2025": med_b,
            "robust_shift_iqr": (med_b - med_a) / iqr,
            "abs_shift_iqr": abs((med_b - med_a) / iqr),
        })
    return pd.DataFrame(rows).sort_values("abs_shift_iqr", ascending=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tail-cache", required=True)
    ap.add_argument("--daily", required=True)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    cache = pd.read_csv(args.tail_cache, parse_dates=["date","target_end_date"], dtype={"symbol": str})
    daily = pd.read_csv(args.daily, usecols=["date"], parse_dates=["date"])
    trading_dates = pd.Index(pd.to_datetime(daily["date"].dropna().unique())).sort_values()

    cache = cache.sort_values(["date","tail_cdf","tail_p"], ascending=[True,False,False])
    picks = one_per_day(cache, trading_dates)

    rows = []
    feature_periods = {}
    for name, a, b in PERIODS:
        raw = cache[(cache["date"] >= a) & (cache["date"] <= b)].copy()
        sel = picks[(picks["date"] >= a) & (picks["date"] <= b)].copy()
        days = int(raw["date"].nunique())
        month_counts = raw.groupby(raw["date"].dt.to_period("M")).size()
        day_counts = raw.groupby("date").size()
        rows.append({
            "period": name,
            "raw_tail_n": int(len(raw)),
            "tail_days": days,
            "raw_per_tail_day": float(len(raw)/days) if days else None,
            "median_candidates_per_tail_day": float(day_counts.median()) if len(day_counts) else None,
            "max_candidates_on_day": int(day_counts.max()) if len(day_counts) else 0,
            "mean_monthly_tail_n": float(month_counts.mean()) if len(month_counts) else None,
            **{f"raw_{k}": v for k,v in summarize(raw["target5_no"]).items()},
            **{f"pick_{k}": v for k,v in summarize(sel["target5_no"]).items()},
            "tail_p_median": float(pd.to_numeric(raw["tail_p"], errors="coerce").median()) if len(raw) else None,
            "tail_p_q90": float(pd.to_numeric(raw["tail_p"], errors="coerce").quantile(.90)) if len(raw) else None,
            "market_med_ret5_median": float(pd.to_numeric(raw["med_ret5"], errors="coerce").median()) if len(raw) and "med_ret5" in raw else None,
            "market_breadth20_median": float(pd.to_numeric(raw["breadth_ma20"], errors="coerce").median()) if len(raw) and "breadth_ma20" in raw else None,
        })
        feature_periods[name] = feature_snapshot(raw)

    period_df = pd.DataFrame(rows)
    period_df.to_csv(outdir / "tail_regime_periods.csv", index=False)

    monthly = []
    for month, z in cache.groupby(cache["date"].dt.to_period("M")):
        sel = picks[picks["date"].dt.to_period("M") == month]
        sraw = summarize(z["target5_no"])
        ssel = summarize(sel["target5_no"])
        monthly.append({
            "month": str(month),
            "raw_n": int(len(z)),
            "days": int(z["date"].nunique()),
            "raw_hit20": sraw.get("hit20_rate"),
            "raw_hit50": sraw.get("hit50_rate"),
            "raw_loss10": sraw.get("loss10_rate"),
            "raw_mean": sraw.get("mean"),
            "pick_n": ssel.get("n",0),
            "pick_mean": ssel.get("mean"),
            "pick_hit20": ssel.get("hit20_rate"),
            "pick_loss10": ssel.get("loss10_rate"),
            "tail_p_median": float(pd.to_numeric(z["tail_p"], errors="coerce").median()),
            "med_ret5_median": float(pd.to_numeric(z["med_ret5"], errors="coerce").median()) if "med_ret5" in z else None,
            "breadth_ma20_median": float(pd.to_numeric(z["breadth_ma20"], errors="coerce").median()) if "breadth_ma20" in z else None,
        })
    pd.DataFrame(monthly).to_csv(outdir / "tail_regime_monthly.csv", index=False)

    y2024 = cache[(cache["date"] >= "2024-01-01") & (cache["date"] <= "2024-12-31")]
    y2025 = cache[(cache["date"] >= "2025-01-01") & (cache["date"] <= "2025-12-31")]
    shift = robust_shift(y2024, y2025)
    shift.to_csv(outdir / "tail_feature_shift_2024_vs_2025.csv", index=False)

    # Tail-p bins derived from 2024 distribution only; diagnostic calibration check.
    tp = pd.to_numeric(y2024["tail_p"], errors="coerce").dropna()
    qs = [float(tp.quantile(q)) for q in [0,.25,.5,.75,1.0]]
    # de-duplicate edges to keep pd.cut valid
    edges = sorted(set(qs))
    cal_rows = []
    if len(edges) >= 2:
        for year, z in [("2024", y2024.copy()), ("2025", y2025.copy())]:
            z["tail_p_bin"] = pd.cut(
                pd.to_numeric(z["tail_p"], errors="coerce"),
                bins=edges,
                include_lowest=True,
                duplicates="drop",
            )
            for bucket, g in z.groupby("tail_p_bin", observed=True):
                s = summarize(g["target5_no"])
                cal_rows.append({
                    "year": year,
                    "tail_p_bin": str(bucket),
                    "n": int(len(g)),
                    "mean": s.get("mean"),
                    "hit20": s.get("hit20_rate"),
                    "hit50": s.get("hit50_rate"),
                    "loss10": s.get("loss10_rate"),
                })
    pd.DataFrame(cal_rows).to_csv(outdir / "tail_score_calibration_2024_2025.csv", index=False)

    meta = {
        "status": "research_only_no_production_writes",
        "cache_rows": int(len(cache)),
        "pick_rows": int(len(picks)),
        "periods": [x[0] for x in PERIODS],
        "diagnostic_only": True,
        "no_threshold_selection": True,
        "feature_shift_reference": "2024 raw Tail pool vs 2025 raw Tail pool",
    }
    (outdir / "tail_regime_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print("\nPERIODS")
    print(period_df.to_string(index=False))
    print("\nTOP FEATURE SHIFTS")
    print(shift.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
