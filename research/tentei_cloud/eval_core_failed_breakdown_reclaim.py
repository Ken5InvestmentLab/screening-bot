#!/usr/bin/env python3
"""Frozen failed-breakdown reclaim Core evaluator.

Research-only. Implements CORE_FAILED_BREAKDOWN_RECLAIM_SPEC_20260914.json
without changing candidate rules, thresholds, cooldown, endpoint, or costs.

Default execution opens DEVELOPMENT + INTERNAL_VALIDATION only.
LOCKED_CONFIRMATION can be opened only with --open-locked, and only when both
preconfirmation blocks pass every frozen gate.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from reconstruct_4h_from_1h import load, aggregate, cooldown

COSTS = [0.0, 0.005, 0.01]
PRIMARY_COST = 0.005
PERIODS = {
    "DEVELOPMENT": ("2024-11-01", "2025-03-31"),
    "INTERNAL_VALIDATION": ("2025-04-01", "2025-06-30"),
    "LOCKED_CONFIRMATION": ("2025-07-01", "2025-12-31"),
}


def summarize(gross: pd.Series, cost: float) -> dict:
    r = gross.dropna().astype(float)
    if r.empty:
        return {"n": 0}
    net = r - cost
    rs = net.sort_values(ascending=False).reset_index(drop=True)
    return {
        "n": int(len(net)),
        "mean": float(net.mean()),
        "median": float(net.median()),
        "win": float((net > 0).mean()),
        "gross_ge10": float((r >= 0.10).mean()),
        "gross_ge20": float((r >= 0.20).mean()),
        "gross_le10": float((r <= -0.10).mean()),
        "max": float(net.max()),
        "min": float(net.min()),
        "top1_removed": float(rs.iloc[1:].mean()) if len(rs) > 1 else None,
        "top3_removed": float(rs.iloc[3:].mean()) if len(rs) > 3 else None,
        "top5_removed": float(rs.iloc[5:].mean()) if len(rs) > 5 else None,
    }


def frozen_gate(summary_primary: dict, min_n: int) -> dict:
    checks = {
        "min_resolved_n": int(summary_primary.get("n", 0)) >= int(min_n),
        "net_mean_gt_0": float(summary_primary.get("mean", -999.0)) > 0,
        "net_median_gte_0": float(summary_primary.get("median", -999.0)) >= 0,
        "net_win_rate_gt_0_5": float(summary_primary.get("win", -999.0)) > 0.5,
        "net_top3_removed_mean_gt_0": (
            summary_primary.get("top3_removed") is not None
            and float(summary_primary["top3_removed"]) > 0
        ),
        "gross_loss10_rate_lte_0_10": float(summary_primary.get("gross_le10", 999.0)) <= 0.10,
    }
    checks["all_pass"] = all(checks.values())
    return checks


def add_previous_daily_context(
    sessions: pd.DataFrame, raw: pd.DataFrame
) -> tuple[pd.DataFrame, list[str], pd.DataFrame]:
    daily = (
        raw.sort_values("timestamp")
        .groupby(["symbol", "date"], as_index=False)
        .agg(
            daily_open=("open", "first"),
            daily_low=("low", "min"),
            daily_close=("close", "last"),
            daily_volume=("volume", "sum"),
        )
        .sort_values(["symbol", "date"])
    )
    daily["prev_daily_low"] = daily.groupby("symbol")["daily_low"].shift(1)
    daily["prev_daily_close"] = daily.groupby("symbol")["daily_close"].shift(1)
    daily["prev_daily_volume"] = daily.groupby("symbol")["daily_volume"].shift(1)

    dates = sorted(daily["date"].dropna().unique().tolist())
    x = sessions.merge(
        daily[["symbol", "date", "prev_daily_low", "prev_daily_close", "prev_daily_volume"]],
        on=["symbol", "date"],
        how="left",
        validate="many_to_one",
    )
    return x, dates, daily


def make_candidates(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[str], pd.DataFrame]:
    # Frozen representation: 13:00 split / split_minute=780.
    sessions = aggregate(raw, 780)
    sessions, dates, daily = add_previous_daily_context(sessions, raw)

    eligible = sessions[
        (sessions["prev_daily_close"] <= 1000)
        & (sessions["prev_daily_volume"] >= 10000)
        & (sessions["volume"] >= 5000)
        & sessions["prev_daily_low"].notna()
    ].copy()

    reclaim = (
        (eligible["low"] < eligible["prev_daily_low"])
        & (eligible["close"] > eligible["prev_daily_low"])
        & (eligible["close"] > eligible["open"])
    )
    selected = cooldown(eligible.loc[reclaim].copy(), dates, 5)
    return selected, dates, daily


def attach_canonical_label(
    candidates: pd.DataFrame, dates: list[str], daily: pd.DataFrame
) -> pd.DataFrame:
    pos = {d: i for i, d in enumerate(dates)}
    entry_map = {
        d: (dates[i + 1] if i + 1 < len(dates) else None)
        for d, i in pos.items()
    }
    exit_map = {
        d: (dates[i + 5] if i + 5 < len(dates) else None)
        for d, i in pos.items()
    }

    x = candidates.copy()
    x["entry_date"] = x["date"].map(entry_map)
    x["exit_date"] = x["date"].map(exit_map)

    entry = daily[["symbol", "date", "daily_open"]].rename(
        columns={"date": "entry_date", "daily_open": "entry_open"}
    )
    exit_ = daily[["symbol", "date", "daily_close"]].rename(
        columns={"date": "exit_date", "daily_close": "exit_close"}
    )
    x = x.merge(entry, on=["symbol", "entry_date"], how="left", validate="many_to_one")
    x = x.merge(exit_, on=["symbol", "exit_date"], how="left", validate="many_to_one")

    resolved = (
        x["entry_open"].notna()
        & x["exit_close"].notna()
        & (x["entry_open"] > 0)
        & (x["exit_close"] > 0)
    )
    x["endpoint_status"] = np.where(resolved, "RESOLVED", "UNRESOLVED_ENDPOINT")
    x["canonical_ret5bd_gross"] = np.where(
        resolved, x["exit_close"] / x["entry_open"] - 1.0, np.nan
    )
    x["date_dt"] = pd.to_datetime(x["date"], errors="coerce")
    return x


def period_result(labeled: pd.DataFrame, name: str) -> dict:
    start, end = PERIODS[name]
    z = labeled[
        (labeled["date_dt"] >= pd.Timestamp(start))
        & (labeled["date_dt"] <= pd.Timestamp(end))
    ].copy()
    resolved = z[z["endpoint_status"] == "RESOLVED"].copy()
    scenarios = {
        f"{cost:.3f}": summarize(resolved["canonical_ret5bd_gross"], cost)
        for cost in COSTS
    }
    primary = scenarios[f"{PRIMARY_COST:.3f}"]
    min_n = 30 if name == "LOCKED_CONFIRMATION" else 20
    return {
        "period": name,
        "start": start,
        "end": end,
        "selected_n": int(len(z)),
        "resolved_n": int(len(resolved)),
        "unresolved_n": int(len(z) - len(resolved)),
        "cost_scenarios": scenarios,
        "frozen_gate": frozen_gate(primary, min_n=min_n),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", action="append", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--open-locked", action="store_true")
    a = ap.parse_args()

    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)

    raw = load(a.inputs)
    candidates, dates, daily = make_candidates(raw)
    labeled = attach_canonical_label(candidates, dates, daily)

    dev = period_result(labeled, "DEVELOPMENT")
    val = period_result(labeled, "INTERNAL_VALIDATION")
    preconfirmation_pass = bool(
        dev["frozen_gate"]["all_pass"] and val["frozen_gate"]["all_pass"]
    )

    result = {
        "experiment_id": "CORE-FAILED-BREAKDOWN-RECLAIM-20260914-01",
        "status": "PRECONFIRMATION_ONLY" if not a.open_locked else "LOCKED_CONFIRMATION_REQUESTED",
        "candidate_rule_changed": False,
        "threshold_sweep": False,
        "ranking": "NONE",
        "top_n": "NONE",
        "same_symbol_cooldown_sessions": 5,
        "session_split_minute": 780,
        "endpoint": "next official observed XTKS session open -> signal date + 5 official-session close",
        "primary_round_trip_cost": PRIMARY_COST,
        "periods": {
            "DEVELOPMENT": dev,
            "INTERNAL_VALIDATION": val,
        },
        "preconfirmation_pass": preconfirmation_pass,
        "locked_confirmation_opened": False,
        "year_2026_outcomes_opened": False,
        "production_modified": False,
    }

    if a.open_locked:
        if not preconfirmation_pass:
            raise RuntimeError(
                "LOCKED_CONFIRMATION_BLOCKED: development/internal-validation "
                "did not both pass every frozen gate"
            )
        locked = period_result(labeled, "LOCKED_CONFIRMATION")
        result["periods"]["LOCKED_CONFIRMATION"] = locked
        result["locked_confirmation_opened"] = True
        result["locked_confirmation_pass"] = bool(locked["frozen_gate"]["all_pass"])

    metrics_rows = []
    for period_name, block in result["periods"].items():
        for cost, summary in block["cost_scenarios"].items():
            metrics_rows.append({
                "period": period_name,
                "round_trip_cost": float(cost),
                "selected_n": block["selected_n"],
                "resolved_n": block["resolved_n"],
                "unresolved_n": block["unresolved_n"],
                **summary,
            })

    pd.DataFrame(metrics_rows).to_csv(
        out / "failed_breakdown_reclaim_metrics.csv", index=False
    )
    labeled[[
        "symbol", "date", "session", "session_time",
        "open", "high", "low", "close", "volume",
        "prev_daily_low", "prev_daily_close", "prev_daily_volume",
        "entry_date", "exit_date", "entry_open", "exit_close",
        "endpoint_status", "canonical_ret5bd_gross",
    ]].to_csv(out / "failed_breakdown_reclaim_rows.csv", index=False)

    (out / "failed_breakdown_reclaim_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
