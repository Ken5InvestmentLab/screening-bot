#!/usr/bin/env python3
"""Deterministic point-in-time dilution/fundamental overlay (TEST ONLY).

This module intentionally contains no AI and no production writes.  It consumes
normalized company snapshots whose ``available_date`` is the first date the
information was public.  For each technical signal, only snapshots with
``available_date <= signal date`` are eligible; the latest such snapshot wins.

The first research use is comparative only:
- technical baseline unchanged,
- dilution-risk exclusion as a separate lane,
- financial-risk exclusion as a separate lane,
- combined exclusion as a separate lane.

No threshold is selected from 2026.  Candidate thresholds are declared here so
pre-2026 robustness can be compared without hidden tuning.
"""
from __future__ import annotations

from dataclasses import dataclass
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("tvfree_screener/out")

# Predeclared research grid.  Do not choose among these using 2026 results.
DILUTION_LIMITS = (0.20, 0.35, 0.50, 1.00)
MIN_EQUITY_RATIO = 0.10
MAX_NEGATIVE_SIGNAL_COUNT = 2

SNAPSHOT_REQUIRED = [
    "symbol",
    "available_date",
    "shares_outstanding",
    "remaining_warrant_shares",
    "ms_warrant_flag",
    "equity",
    "assets",
    "revenue",
    "operating_income",
    "net_income",
    "operating_cf",
]


def normalize_snapshots(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in SNAPSHOT_REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"snapshot missing required columns: {missing}")
    z = df.copy()
    z["symbol"] = z["symbol"].astype(str)
    z["available_date"] = pd.to_datetime(z["available_date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    if z["available_date"].isna().any():
        raise ValueError("snapshot contains invalid available_date")
    if "available_at" in z.columns:
        z["available_at"] = pd.to_datetime(z["available_at"], errors="coerce")
        if getattr(z["available_at"].dt, "tz", None) is not None:
            z["available_at"] = z["available_at"].dt.tz_convert("Asia/Tokyo").dt.tz_localize(None)
    numeric = [
        "shares_outstanding", "remaining_warrant_shares", "equity", "assets",
        "revenue", "operating_income", "net_income", "operating_cf",
    ]
    for c in numeric:
        z[c] = pd.to_numeric(z[c], errors="coerce")
    # Classification may itself be unknown. Never turn missing MS-warrant evidence into False.
    z["ms_warrant_flag"] = z["ms_warrant_flag"].astype("boolean")
    return z.sort_values(["symbol", "available_date"], kind="mergesort").reset_index(drop=True)


def attach_point_in_time_snapshot(
    signals: pd.DataFrame,
    snapshots: pd.DataFrame,
    availability_policy: str = "prior_day_only",
) -> pd.DataFrame:
    """Attach the latest causally available snapshot.

    prior_day_only is the conservative research default: a filing first
    published on the signal date is NOT usable for that signal. This avoids
    same-day timing leakage when a backtest row only carries a calendar date.

    same_day_if_timestamped may be used only when signals contain an explicit
    decision_at timestamp and snapshots contain available_at. Then an exact
    timestamp as-of join is used.
    """
    if availability_policy not in {"prior_day_only", "same_day_if_timestamped"}:
        raise ValueError(f"unknown availability_policy: {availability_policy}")

    s = signals.copy()
    s["symbol"] = s["symbol"].astype(str)
    s["date"] = pd.to_datetime(s["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    if s["date"].isna().any():
        raise ValueError("signal contains invalid date")
    f = normalize_snapshots(snapshots)

    if availability_policy == "same_day_if_timestamped":
        if "decision_at" not in s.columns:
            raise ValueError("same_day_if_timestamped requires signal decision_at")
        if "available_at" not in f.columns:
            raise ValueError("same_day_if_timestamped requires snapshot available_at")
        s["decision_at"] = pd.to_datetime(s["decision_at"], errors="coerce")
        if s["decision_at"].isna().any():
            raise ValueError("signal contains invalid decision_at")
        if f["available_at"].isna().any():
            raise ValueError("snapshot contains invalid available_at")

    parts = []
    for symbol, sg in s.groupby("symbol", sort=False):
        fg = f[f["symbol"] == symbol].copy()
        if fg.empty:
            out = sg.copy()
            for c in [c for c in SNAPSHOT_REQUIRED if c not in ("symbol", "available_date")]:
                out[c] = np.nan
            out["available_date"] = pd.NaT
            if "available_at" in f.columns:
                out["available_at"] = pd.NaT
        elif availability_policy == "prior_day_only":
            sg = sg.sort_values("date", kind="mergesort")
            fg["_eligible_from_date"] = fg["available_date"] + pd.Timedelta(days=1)
            out = pd.merge_asof(
                sg,
                fg.drop(columns=["symbol"]).sort_values("_eligible_from_date"),
                left_on="date",
                right_on="_eligible_from_date",
                direction="backward",
                allow_exact_matches=True,
            ).drop(columns=["_eligible_from_date"])
        else:
            sg = sg.sort_values("decision_at", kind="mergesort")
            fg = fg.sort_values("available_at", kind="mergesort")
            out = pd.merge_asof(
                sg,
                fg.drop(columns=["symbol"]),
                left_on="decision_at",
                right_on="available_at",
                direction="backward",
                allow_exact_matches=True,
            )
        parts.append(out)
    return pd.concat(parts, ignore_index=True).sort_values(["date", "symbol"], kind="mergesort")

def add_overlay_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add transparent metrics while preserving unknown data as unknown."""
    z = df.copy()

    shares = pd.to_numeric(z["shares_outstanding"], errors="coerce")
    remaining = pd.to_numeric(z["remaining_warrant_shares"], errors="coerce")
    assets = pd.to_numeric(z["assets"], errors="coerce")
    equity = pd.to_numeric(z["equity"], errors="coerce")
    revenue = pd.to_numeric(z["revenue"], errors="coerce")
    operating_income = pd.to_numeric(z["operating_income"], errors="coerce")
    net_income = pd.to_numeric(z["net_income"], errors="coerce")
    operating_cf = pd.to_numeric(z["operating_cf"], errors="coerce")

    z["dilution_known"] = (shares.notna() & (shares > 0) & remaining.notna()).astype("boolean")
    z["financial_known"] = (
        assets.notna()
        & (assets > 0)
        & equity.notna()
        & operating_income.notna()
        & net_income.notna()
        & operating_cf.notna()
    ).astype("boolean")
    z["combined_known"] = (z["dilution_known"] & z["financial_known"]).astype("boolean")

    z["dilution_ratio"] = remaining / shares.where(shares > 0)
    z.loc[~z["dilution_known"].fillna(False), "dilution_ratio"] = np.nan
    z["equity_ratio"] = equity / assets.where(assets > 0)
    z["operating_margin"] = operating_income / revenue.replace(0, np.nan)

    # Risk flags are nullable booleans. If the required financial snapshot is
    # incomplete, the flags, count and exclusion decision remain unknown.
    known = z["financial_known"].fillna(False)
    for name, values in {
        "risk_equity_thin": z["equity_ratio"] < MIN_EQUITY_RATIO,
        "risk_operating_loss": operating_income < 0,
        "risk_net_loss": net_income < 0,
        "risk_negative_ocf": operating_cf < 0,
    }.items():
        out = pd.Series(pd.NA, index=z.index, dtype="boolean")
        out.loc[known] = values.loc[known].astype(bool)
        z[name] = out

    risk_cols = ["risk_equity_thin", "risk_operating_loss", "risk_net_loss", "risk_negative_ocf"]
    counts = z[risk_cols].astype("Int64").sum(axis=1, min_count=len(risk_cols)).astype("Int64")
    z["financial_risk_count"] = counts
    exclude = pd.Series(pd.NA, index=z.index, dtype="boolean")
    exclude.loc[known] = (counts.loc[known] >= MAX_NEGATIVE_SIGNAL_COUNT).astype(bool)
    z["financial_risk_exclude"] = exclude
    return z


def build_lanes(signals: pd.DataFrame, snapshots: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build coverage-matched research lanes.

    Unknown observations are never admitted to a filtered lane. Each filtered
    lane has a matching baseline drawn from the exact population for which the
    required overlay is known, preventing missing-data selection from looking
    like alpha.
    """
    z = add_overlay_metrics(attach_point_in_time_snapshot(signals, snapshots))
    dilution_known = z["dilution_known"].fillna(False)
    financial_known = z["financial_known"].fillna(False)
    combined_known = z["combined_known"].fillna(False)
    financial_safe = z["financial_risk_exclude"].eq(False).fillna(False)

    lanes: dict[str, pd.DataFrame] = {
        "baseline": z.copy(),
        "dilution_known_baseline": z[dilution_known].copy(),
        "dilution_unknown": z[~dilution_known].copy(),
        "financial_known_baseline": z[financial_known].copy(),
        "financial_unknown": z[~financial_known].copy(),
        "combined_known_baseline": z[combined_known].copy(),
        "combined_unknown": z[~combined_known].copy(),
    }
    for limit in DILUTION_LIMITS:
        lanes[f"dilution_le_{limit:.2f}"] = z[
            dilution_known & (z["dilution_ratio"] <= limit)
        ].copy()

    lanes["financial_risk_filter"] = z[financial_known & financial_safe].copy()
    lanes["combined_dilution35_finrisk"] = z[
        combined_known
        & (z["dilution_ratio"] <= 0.35)
        & financial_safe
    ].copy()
    return lanes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--signals", required=True, help="CSV with at least date,symbol")
    ap.add_argument("--snapshots", required=True, help="normalized point-in-time fundamental CSV")
    ap.add_argument("--prefix", default="fundamental_overlay")
    args = ap.parse_args()

    signals = pd.read_csv(args.signals, dtype={"symbol": str})
    snapshots = pd.read_csv(args.snapshots, dtype={"symbol": str})
    lanes = build_lanes(signals, snapshots)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, df in lanes.items():
        df.to_csv(OUT / f"{args.prefix}_{name}.csv", index=False)
    print({name: len(df) for name, df in lanes.items()})


if __name__ == "__main__":
    main()
