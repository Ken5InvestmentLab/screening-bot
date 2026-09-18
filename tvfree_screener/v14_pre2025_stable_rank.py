#!/usr/bin/env python3
"""V14 pre-2025 stable Tail rank (TEST ONLY).

Feature/rule discovery used 2023-2024 only:
- V7 extreme Tail candidates (cdf >= 0.999)
- keep days with cross-sectional median 5D return <= 0
- within-day prefer lower relative:
    1) volr20
    2) ret1
- average the two percentile ranks
- tie-break by higher Tail CDF / Tail probability
- one-business-day same-symbol cooldown

The two rank features were the only signal-time features among the existing
45-feature set whose single-feature low-rank lane had positive mean in all
four pre-2025 half-years under the same market gate.

2025 and 2026 are reporting only in this runner. No production writes.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd
import v9_conditional_quality_research as v9

OUT = Path("tvfree_screener/out")
RANK_FEATURES = ["volr20", "ret1"]

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
        "hit100_rate": float((x >= 1).mean()),
        "loss10_rate": float((x <= -.10).mean()),
        "loss20_rate": float((x <= -.20).mean()),
        "max": float(x.max()),
        "min": float(x.min()),
        "top1_removed_mean": float(y.iloc[1:].mean()) if len(y) > 1 else None,
        "top3_removed_mean": float(y.iloc[3:].mean()) if len(y) > 3 else None,
    }

def select(tail: pd.DataFrame, trading_dates: pd.Index) -> pd.DataFrame:
    z = tail[tail["med_ret5"] <= 0].copy()
    if z.empty:
        return z
    rank_cols = []
    for c in RANK_FEATURES:
        rc = f"rank_{c}"
        z[rc] = z.groupby("date")[c].rank(
            pct=True, method="average", ascending=True
        )
        rank_cols.append(rc)
    z["stable_rank"] = z[rank_cols].mean(axis=1)
    z = z.sort_values(
        ["date", "stable_rank", "tail_cdf", "tail_p"],
        ascending=[True, True, False, False],
    )

    date_idx = {pd.Timestamp(d): i for i, d in enumerate(trading_dates)}
    rows = []
    last_symbol = None
    last_idx = None

    # Keep top backups so cooldown can skip same-symbol repeat.
    top = z.groupby("date", sort=True, as_index=False).head(4)
    for date, day in top.groupby("date", sort=True):
        idx = date_idx.get(pd.Timestamp(date))
        if idx is None:
            continue
        chosen = None
        for _, row in day.iterrows():
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

def period_stats(picks, periods):
    return {
        name: stats(picks[(picks.date >= a) & (picks.date <= b)]["target5_no"])
        for name, (a, b) in periods.items()
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--tail-cache", required=True)
    args = ap.parse_args()

    raw = pd.read_csv(args.cache, parse_dates=["date"], dtype={"symbol": str})
    for c in ["open","high","low","close","volume"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw = raw.dropna(
        subset=["date","symbol","open","high","low","close","volume"]
    ).sort_values(["symbol","date"]).reset_index(drop=True)
    trading_dates = pd.Index(pd.to_datetime(raw["date"].unique())).sort_values()

    hist_tail = pd.read_csv(
        args.tail_cache,
        parse_dates=["date","target_end_date"],
        dtype={"symbol": str},
    )
    tail_2025 = hist_tail[
        (hist_tail["date"] >= "2025-01-01")
        & (hist_tail["date"] <= "2025-12-31")
    ].copy()
    picks_2025 = select(tail_2025, trading_dates)

    q = v9.prepare(raw)
    tail_2026 = v9.generate_tail_pool(q, "2026-01-01", "2026-08-31")
    picks_2026 = select(tail_2026, trading_dates)

    periods_2025 = {
        "2025H1": ("2025-01-01","2025-06-30"),
        "2025H2": ("2025-07-01","2025-12-31"),
    }
    periods_2026 = {
        "2026H1": ("2026-01-01","2026-06-30"),
        "2026_JulAug": ("2026-07-01","2026-08-31"),
        "2026_MarAug": ("2026-03-01","2026-08-31"),
    }

    monthly_2026 = {
        str(m): stats(g["target5_no"])
        for m, g in picks_2026.groupby(picks_2026.date.dt.to_period("M"))
    }

    report = {
        "status": "research_only_no_production_writes",
        "component": "V14 pre-2025-stable V7 Tail rank",
        "feature_selection_source": "2023-2024 only",
        "market_gate": "med_ret5 <= 0",
        "rank_features": RANK_FEATURES,
        "rank_direction": "lower within-day percentile preferred",
        "entry": "next_session_open_to_5BD_close",
        "pre2025_reference": {
            "2023H1_mean": 0.002361098218199675,
            "2023H2_mean": 0.0033880536698512667,
            "2024H1_mean": 0.05293726237271965,
            "2024H2_mean": 0.015608299981283116,
            "2023_2024_pooled_mean": 0.019883970880659876,
        },
        "2025": period_stats(picks_2025, periods_2025),
        "2025_pooled": stats(picks_2025["target5_no"]),
        "2026": period_stats(picks_2026, periods_2026),
        "2026_JanAug": stats(picks_2026["target5_no"]),
        "2026_monthly": monthly_2026,
        "production_writes": False,
        "warning": "2025/2026 are reporting only; do not tune V14 from these results.",
    }

    OUT.mkdir(parents=True, exist_ok=True)
    picks_2025.to_csv(OUT / "v14_stable_2025_picks.csv", index=False)
    picks_2026.to_csv(OUT / "v14_stable_2026_picks.csv", index=False)
    (OUT / "v14_stable_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
