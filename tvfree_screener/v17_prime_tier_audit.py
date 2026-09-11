#!/usr/bin/env python3
"""V17 Prime-tier audit on top of V16 Watch (TEST ONLY).

Watch is frozen V16:
- V7 extreme Tail
- market gate med_ret5 <= 0
- same-day lowest volr20
- one-business-day same-symbol cooldown

Prime feature selection uses PRE-2025 ONLY:
- periods: 2022H2, 2023H1, 2023H2, 2024H1, 2024H2
- for each candidate feature, evaluate low-half and high-half using a threshold
  fixed from the pooled pre-2025 V16 Watch distribution (median)
- eligible Prime rule must:
  * have >= 4 observations in every pre-2025 period,
  * have positive mean in every pre-2025 period,
  * beat the corresponding Watch mean in at least 3/5 periods,
  * have pooled pre-2025 mean > Watch pooled mean.
- choose the eligible rule maximizing:
    min_period_mean + 0.5*pooled_mean + 0.1*pooled_hit20 - 0.05*pooled_loss10

Only after the rule is selected from pre-2025 data, report it on 2025 and 2026.
No production writes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import v9_conditional_quality_research as v9
import v16_pre2025_volr20_rank as v16

OUT = Path("tvfree_screener/out")

FEATURES = [
    "tail_p",
    "ret1", "ret3", "ret5", "ret10", "ret20",
    "ma5_gap", "ma20_gap",
    "rsi14", "atr14p",
    "body_pct", "lower_wick", "upper_wick", "range_pct", "gap",
    "pos20", "dd20", "bounce20",
    "bbpct", "bbwidth", "volz20", "log_dv",
    "breadth_ret1_pos", "med_ret5", "breadth_ma20",
]

PRE_PERIODS = {
    "2022H2": ("2022-07-01", "2022-12-31"),
    "2023H1": ("2023-01-01", "2023-06-30"),
    "2023H2": ("2023-07-01", "2023-12-31"),
    "2024H1": ("2024-01-01", "2024-06-30"),
    "2024H2": ("2024-07-01", "2024-12-31"),
}

REPORT_PERIODS = {
    "2025H1": ("2025-01-01", "2025-06-30"),
    "2025H2": ("2025-07-01", "2025-12-31"),
    "2026H1": ("2026-01-01", "2026-06-30"),
    "2026_JulAug": ("2026-07-01", "2026-08-31"),
    "2026_MarAug": ("2026-03-01", "2026-08-31"),
}


def stats(s):
    x = pd.to_numeric(s, errors="coerce").dropna()
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
        "hit50_rate": float((x >= .50).mean()),
        "hit100_rate": float((x >= 1.0).mean()),
        "loss10_rate": float((x <= -.10).mean()),
        "loss20_rate": float((x <= -.20).mean()),
        "max": float(x.max()),
        "min": float(x.min()),
        "top1_removed_mean": float(y.iloc[1:].mean()) if len(y) > 1 else None,
        "top3_removed_mean": float(y.iloc[3:].mean()) if len(y) > 3 else None,
    }


def period_stats(df, periods):
    return {
        name: stats(df[(df.date >= a) & (df.date <= b)]["target5_no"])
        for name, (a, b) in periods.items()
    }


def build_watch(
    raw: pd.DataFrame,
    hist_tail: pd.DataFrame,
):
    trading_dates = pd.Index(pd.to_datetime(raw["date"].unique())).sort_values()

    # Build 2022 Tail causally from source data; reuse cached Tail for 2023-2025.
    q = v9.prepare(raw)
    tail22 = v9.generate_tail_pool(q, "2022-01-01", "2022-12-31")
    watch22 = v16.select(tail22, trading_dates)

    watch23_25 = []
    for year in [2023, 2024, 2025]:
        t = hist_tail[
            (hist_tail.date >= f"{year}-01-01")
            & (hist_tail.date <= f"{year}-12-31")
        ].copy()
        watch23_25.append(v16.select(t, trading_dates))

    tail26 = v9.generate_tail_pool(q, "2026-01-01", "2026-08-31")
    watch26 = v16.select(tail26, trading_dates)

    watch = pd.concat(
        [watch22] + watch23_25 + [watch26],
        ignore_index=True,
        sort=False,
    )
    return watch.sort_values("date").reset_index(drop=True)


def select_prime_rule(watch: pd.DataFrame):
    pre = watch[
        (watch.date >= "2022-07-01")
        & (watch.date <= "2024-12-31")
    ].copy()

    watch_period = period_stats(pre, PRE_PERIODS)
    watch_pool = stats(pre["target5_no"])

    rows = []
    for feat in FEATURES:
        if feat not in pre.columns:
            continue
        x = pd.to_numeric(pre[feat], errors="coerce")
        threshold = float(x.median())
        if not np.isfinite(threshold):
            continue

        for direction in ["low", "high"]:
            if direction == "low":
                z = pre[pd.to_numeric(pre[feat], errors="coerce") <= threshold].copy()
            else:
                z = pre[pd.to_numeric(pre[feat], errors="coerce") >= threshold].copy()

            ps = period_stats(z, PRE_PERIODS)
            pool = stats(z["target5_no"])
            period_means = [ps[p].get("mean") for p in PRE_PERIODS]
            period_ns = [ps[p].get("n", 0) for p in PRE_PERIODS]
            if any(n < 4 for n in period_ns):
                eligible = False
                beats = 0
            else:
                positive_all = all(m is not None and m > 0 for m in period_means)
                beats = sum(
                    1 for p in PRE_PERIODS
                    if ps[p].get("mean") is not None
                    and watch_period[p].get("mean") is not None
                    and ps[p]["mean"] > watch_period[p]["mean"]
                )
                eligible = bool(
                    positive_all
                    and beats >= 3
                    and pool.get("mean", -999) > watch_pool.get("mean", 999)
                )

            utility = None
            if eligible:
                utility = float(
                    min(period_means)
                    + 0.5 * pool["mean"]
                    + 0.1 * pool["hit20_rate"]
                    - 0.05 * pool["loss10_rate"]
                )

            rows.append({
                "feature": feat,
                "direction": direction,
                "threshold": threshold,
                "eligible": eligible,
                "beats_watch_periods": beats,
                "utility": utility,
                "pooled_n": pool.get("n", 0),
                "pooled_mean": pool.get("mean"),
                "pooled_hit20": pool.get("hit20_rate"),
                "pooled_hit50": pool.get("hit50_rate"),
                "pooled_loss10": pool.get("loss10_rate"),
                "min_period_mean": min(period_means) if all(m is not None for m in period_means) else None,
                **{f"{p}_n": ps[p].get("n", 0) for p in PRE_PERIODS},
                **{f"{p}_mean": ps[p].get("mean") for p in PRE_PERIODS},
            })

    table = pd.DataFrame(rows)
    eligible = table[table["eligible"]].copy()
    if eligible.empty:
        return None, table, watch_period, watch_pool
    best = eligible.sort_values(
        ["utility", "pooled_mean", "pooled_hit20"],
        ascending=False,
    ).iloc[0].to_dict()
    return best, table, watch_period, watch_pool


def apply_rule(watch: pd.DataFrame, rule):
    if rule is None:
        return watch.iloc[0:0].copy()
    feat = rule["feature"]
    thr = float(rule["threshold"])
    x = pd.to_numeric(watch[feat], errors="coerce")
    if rule["direction"] == "low":
        return watch[x <= thr].copy()
    return watch[x >= thr].copy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily", required=True)
    ap.add_argument("--tail-cache", required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()

    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(a.daily, parse_dates=["date"], dtype={"symbol": str})
    for c in ["open", "high", "low", "close", "volume"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw = raw.dropna(
        subset=["date","symbol","open","high","low","close","volume"]
    ).sort_values(["symbol","date"]).reset_index(drop=True)

    hist_tail = pd.read_csv(
        a.tail_cache,
        parse_dates=["date","target_end_date"],
        dtype={"symbol": str},
    )

    watch = build_watch(raw, hist_tail)
    rule, audit, watch_pre_period, watch_pre_pool = select_prime_rule(watch)
    audit.to_csv(out / "v17_prime_feature_audit.csv", index=False)

    prime = apply_rule(watch, rule)

    pre_prime = prime[
        (prime.date >= "2022-07-01")
        & (prime.date <= "2024-12-31")
    ]
    report_prime = prime[
        (prime.date >= "2025-01-01")
        & (prime.date <= "2026-08-31")
    ]

    report = {
        "status": "research_only_no_production_writes",
        "component": "V17 Prime tier on frozen V16 Watch",
        "watch_rule": {
            "tail_gate": 0.999,
            "market_gate": "med_ret5 <= 0",
            "same_day_rank": "lowest volr20",
        },
        "prime_selection_source": "2022H2 through 2024H2 only",
        "prime_rule": rule,
        "watch_pre2025_periods": watch_pre_period,
        "watch_pre2025_pooled": watch_pre_pool,
        "prime_pre2025_periods": period_stats(pre_prime, PRE_PERIODS),
        "prime_pre2025_pooled": stats(pre_prime["target5_no"]),
        "prime_reporting_periods": period_stats(report_prime, REPORT_PERIODS),
        "prime_2025_pooled": stats(
            prime[(prime.date >= "2025-01-01") & (prime.date <= "2025-12-31")]["target5_no"]
        ),
        "prime_2026_JanAug": stats(
            prime[(prime.date >= "2026-01-01") & (prime.date <= "2026-08-31")]["target5_no"]
        ),
        "watch_2025_pooled": stats(
            watch[(watch.date >= "2025-01-01") & (watch.date <= "2025-12-31")]["target5_no"]
        ),
        "watch_2026_JanAug": stats(
            watch[(watch.date >= "2026-01-01") & (watch.date <= "2026-08-31")]["target5_no"]
        ),
        "production_writes": False,
        "warning": "2025/2026 are reporting only and were seen in earlier research; Prime selection code never uses them.",
    }

    watch.to_csv(out / "v17_watch_all.csv", index=False)
    prime.to_csv(out / "v17_prime_all.csv", index=False)
    (out / "v17_prime_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
