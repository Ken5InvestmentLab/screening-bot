#!/usr/bin/env python3
"""Canonical endpoint audit for the fixed reconstructed Core candidate set.

Research-only. Candidate logic is unchanged. This script changes only the label:
entry = next official observed XTKS session open;
exit = fifth official observed XTKS session close after entry (signal date + 5 sessions).

Current research contract (2026-09-14):
- all newly computed performance uses transaction cost 0% only;
- win = gross return > 0;
- 2026 is report-only and must not be used for selection or tuning;
- legacy costed evidence may be retained elsewhere but is never recomputed here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from reconstruct_4h_from_1h import load, aggregate, enrich_session, add_daily_context, cooldown

PERIODS = [
    ("DEV", "2024-11-01", "2025-06-30"),
    ("2025H2", "2025-07-01", "2025-12-31"),
    ("2026_YTD_REPORT_ONLY", "2026-01-01", "2026-08-31"),
]
COST_PCT_POINTS = 0.0


def summarize(r: pd.Series) -> dict:
    r = r.dropna().astype(float)
    if r.empty:
        return {"n": 0}
    rs = r.sort_values(ascending=False).reset_index(drop=True)
    return {
        "n": int(len(r)),
        "mean": float(r.mean()),
        "median": float(r.median()),
        "win": float((r > 0).mean()),
        "ge10": float((r >= 0.10).mean()),
        "ge20": float((r >= 0.20).mean()),
        "ge50": float((r >= 0.50).mean()),
        "le10": float((r <= -0.10).mean()),
        "le20": float((r <= -0.20).mean()),
        "max": float(r.max()),
        "min": float(r.min()),
        "top1_removed": float(rs.iloc[1:].mean()) if len(rs) > 1 else None,
        "top3_removed": float(rs.iloc[3:].mean()) if len(rs) > 3 else None,
    }


def make_fixed_core(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    s = aggregate(raw, 780)
    s = enrich_session(s)
    s, dates = add_daily_context(s, raw)
    eligible = s[
        (s["prev_daily_close"] <= 1000)
        & (s["prev_daily_volume"] >= 10000)
        & (s["volume"] >= 5000)
    ].copy()
    gate = (
        (eligible["rsi12"] < 45)
        & eligible["pre_down3"].fillna(False)
        & (eligible["close"] > eligible["bb_mid"])
        & (eligible["atr14_pct"] < 0.05)
    )
    q = cooldown(eligible[gate].copy(), dates, 5)
    return q, dates


def attach_canonical_label(q: pd.DataFrame, raw: pd.DataFrame, dates: list[str]) -> pd.DataFrame:
    daily = (
        raw.sort_values("timestamp")
        .groupby(["symbol", "date"], as_index=False)
        .agg(daily_open=("open", "first"), daily_close=("close", "last"))
    )
    pos = {d: i for i, d in enumerate(dates)}
    entry_map = {d: (dates[i + 1] if i + 1 < len(dates) else None) for d, i in pos.items()}
    exit_map = {d: (dates[i + 5] if i + 5 < len(dates) else None) for d, i in pos.items()}

    x = q.copy()
    x["entry_date"] = x["date"].map(entry_map)
    x["exit_date"] = x["date"].map(exit_map)

    entry = daily[["symbol", "date", "daily_open"]].rename(
        columns={"date": "entry_date", "daily_open": "entry_open"}
    )
    exit_ = daily[["symbol", "date", "daily_close"]].rename(
        columns={"date": "exit_date", "daily_close": "exit_close"}
    )
    x = x.merge(entry, on=["symbol", "entry_date"], how="left")
    x = x.merge(exit_, on=["symbol", "exit_date"], how="left")
    x["canonical_ret5bd"] = x["exit_close"] / x["entry_open"] - 1.0
    x["date_dt"] = pd.to_datetime(x["date"], errors="coerce")
    return x


def dependence_tables(resolved: pd.DataFrame, period: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    z = resolved.copy()
    z["month"] = z["date_dt"].dt.to_period("M").astype(str)
    iso = z["date_dt"].dt.isocalendar()
    z["week"] = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)

    month_rows = []
    for key, g in z.groupby("month", sort=True):
        month_rows.append({"period": period, "month": key, **summarize(g["canonical_ret5bd"])})

    week_rows = []
    for key, g in z.groupby("week", sort=True):
        week_rows.append({"period": period, "week": key, **summarize(g["canonical_ret5bd"])})

    return pd.DataFrame(month_rows), pd.DataFrame(week_rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", action="append", required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()

    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    raw = load(a.inputs)
    core, dates = make_fixed_core(raw)
    labeled = attach_canonical_label(core, raw, dates)

    rows = []
    monthly_parts = []
    weekly_parts = []
    for name, start, end in PERIODS:
        z = labeled[(labeled["date_dt"] >= pd.Timestamp(start)) & (labeled["date_dt"] <= pd.Timestamp(end))].copy()
        unresolved = int(z["canonical_ret5bd"].isna().sum())
        resolved = z[z["canonical_ret5bd"].notna()].copy()
        rows.append({
            "period": name,
            "round_trip_cost": COST_PCT_POINTS,
            "selected_n": int(len(z)),
            "resolved_n": int(len(resolved)),
            "unresolved_n": unresolved,
            **summarize(resolved["canonical_ret5bd"]),
        })
        m, w = dependence_tables(resolved, name)
        if not m.empty:
            monthly_parts.append(m)
        if not w.empty:
            weekly_parts.append(w)

    result = pd.DataFrame(rows)
    result.to_csv(out / "core_canonical_endpoint_metrics.csv", index=False)
    pd.concat(monthly_parts, ignore_index=True).to_csv(out / "core_canonical_endpoint_monthly.csv", index=False) if monthly_parts else None
    pd.concat(weekly_parts, ignore_index=True).to_csv(out / "core_canonical_endpoint_weekly.csv", index=False) if weekly_parts else None
    labeled[[
        "symbol", "date", "session", "session_time", "entry_date", "exit_date",
        "entry_open", "exit_close", "canonical_ret5bd"
    ]].to_csv(out / "core_canonical_endpoint_rows.csv", index=False)

    meta = {
        "status": "CANONICAL_ENDPOINT_AUDIT_COST0_ONLY",
        "candidate_selection_changed": False,
        "threshold_tuning": False,
        "entry": "next observed official XTKS session open",
        "exit": "signal date + 5 official XTKS sessions close (fifth holding session close)",
        "round_trip_cost": COST_PCT_POINTS,
        "win_definition": "gross return > 0",
        "legacy_costed_recomputation": False,
        "2026_policy": "REPORT_ONLY",
        "production_writes": False,
        "raw_start": str(raw["date"].min()),
        "raw_end": str(raw["date"].max()),
        "selected_total": int(len(labeled)),
    }
    (out / "core_canonical_endpoint_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()
