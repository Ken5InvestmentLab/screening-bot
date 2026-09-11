#!/usr/bin/env python3
"""Measure Yahoo Finance coverage for historical JPX delistings (TEST ONLY).

Purpose: quantify survivorship-bias risk before historical point-in-time
membership is used in model research.

Four-character codes with later listing episodes/current reuse are quarantined
before Yahoo lookup because one ".T" ticker cannot be assumed to preserve issuer
identity across code reuse. Price series continuing materially after the
official delisting date are also marked suspicious rather than accepted.

No production writes and no model thresholds are changed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
import yfinance as yf

OUT = Path("tvfree_screener/out")
NEAR_DELIST_CALENDAR_DAYS = 45
MAX_LAST_PRICE_GAP_DAYS = 14


def load_inputs(events_path: str, snapshot_path: str) -> tuple[pd.DataFrame, set[str]]:
    events = pd.read_csv(events_path, dtype={"code": str})
    need = {"event_date", "code", "event"}
    missing = sorted(need - set(events.columns))
    if missing:
        raise ValueError(f"events missing required columns: {missing}")
    events["event_date"] = pd.to_datetime(events["event_date"], errors="coerce").dt.normalize()
    if events["event_date"].isna().any():
        raise ValueError("events contain invalid event_date")
    events["code"] = events["code"].astype(str).str.strip().str.upper()

    snap = pd.read_csv(snapshot_path, dtype={"code": str})
    if "code" not in snap.columns:
        raise ValueError("current snapshot missing code")
    current = set(snap["code"].astype(str).str.strip().str.upper())
    return events, current


def build_delisting_candidates(
    events: pd.DataFrame,
    current_codes: set[str],
    start_date: pd.Timestamp,
) -> pd.DataFrame:
    """Create one diagnostic row per official delisting event."""
    z = events.copy()
    z["event_date"] = pd.to_datetime(z["event_date"]).dt.normalize()
    dels = z[(z["event"] == "delisting") & (z["event_date"] >= start_date)].copy()
    dels = dels.drop_duplicates(["event_date", "code"]).sort_values(["event_date", "code"])
    rows = []
    for _, row in dels.iterrows():
        code = str(row["code"])
        dd = pd.Timestamp(row["event_date"])
        later_listing = bool(
            ((z["code"] == code) & (z["event"] == "listing") & (z["event_date"] > dd)).any()
        )
        currently_listed = code in current_codes
        same_code_delistings = int(((z["code"] == code) & (z["event"] == "delisting")).sum())

        reasons = []
        if later_listing:
            reasons.append("later_listing_event")
        if currently_listed:
            reasons.append("code_currently_listed")
        if same_code_delistings > 1:
            reasons.append("multiple_delisting_episodes")

        rows.append({
            "code": code,
            "ticker": f"{code}.T",
            "delisting_date": dd,
            "identity_quarantined": bool(reasons),
            "identity_reasons": "|".join(reasons),
            "later_listing_event": later_listing,
            "currently_listed": currently_listed,
            "delisting_episode_count": same_code_delistings,
        })
    return pd.DataFrame(rows)


def assess_price_frame(prices: pd.DataFrame, delisting_date: pd.Timestamp) -> dict:
    """Assess availability near delisting without claiming full-period coverage."""
    if prices is None or prices.empty:
        return {
            "price_rows": 0,
            "first_price_date": None,
            "last_price_date_on_or_before_delist": None,
            "last_price_gap_days": None,
            "near_delist_rows": 0,
            "post_delist_rows": 0,
            "coverage_status": "missing",
            "usable_near_delist": False,
        }

    p = prices.copy()
    if "date" not in p.columns:
        idx_name = p.index.name or "index"
        p = p.reset_index().rename(columns={idx_name: "date", "Date": "date"})
    p["date"] = pd.to_datetime(p["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    p = p.dropna(subset=["date"])
    close_col = next((c for c in ["close", "Close"] if c in p.columns), None)
    if close_col is not None:
        p = p[p[close_col].notna()]

    before = p[p["date"] <= delisting_date]
    after = p[p["date"] > delisting_date]
    near = before[before["date"] >= delisting_date - pd.Timedelta(days=NEAR_DELIST_CALENDAR_DAYS)]

    first = None if p.empty else p["date"].min()
    last = None if before.empty else before["date"].max()
    gap = None if last is None else int((delisting_date - last).days)
    post_rows = int(len(after))

    if before.empty:
        status = "missing_before_delist"
        usable = False
    elif post_rows > 0:
        status = "suspicious_post_delist_data"
        usable = False
    elif len(near) >= 5 and gap is not None and gap <= MAX_LAST_PRICE_GAP_DAYS:
        status = "usable_near_delist"
        usable = True
    else:
        status = "partial_old_or_sparse"
        usable = False

    return {
        "price_rows": int(len(p)),
        "first_price_date": None if first is None else first.strftime("%Y-%m-%d"),
        "last_price_date_on_or_before_delist": None if last is None else last.strftime("%Y-%m-%d"),
        "last_price_gap_days": gap,
        "near_delist_rows": int(len(near)),
        "post_delist_rows": post_rows,
        "coverage_status": status,
        "usable_near_delist": usable,
    }


def _extract_ticker_frame(download: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if download is None or download.empty:
        return pd.DataFrame()
    if isinstance(download.columns, pd.MultiIndex):
        if ticker not in download.columns.get_level_values(0):
            return pd.DataFrame()
        z = download[ticker].copy()
    else:
        z = download.copy()
    z = z.rename(columns={c: str(c).lower() for c in z.columns}).reset_index()
    z = z.rename(columns={z.columns[0]: "date"})
    return z


def probe_yahoo(
    candidates: pd.DataFrame,
    start_date: str,
    batch_size: int = 50,
    request_pause: float = 1.0,
) -> pd.DataFrame:
    out = candidates.copy()
    for c in [
        "price_rows", "first_price_date", "last_price_date_on_or_before_delist",
        "last_price_gap_days", "near_delist_rows", "post_delist_rows",
        "coverage_status", "usable_near_delist",
    ]:
        out[c] = pd.NA

    probe_idx = out.index[~out["identity_quarantined"]].tolist()
    if not probe_idx:
        return out

    latest = pd.to_datetime(out.loc[probe_idx, "delisting_date"]).max() + pd.Timedelta(days=30)
    end_date = latest.strftime("%Y-%m-%d")
    for start in range(0, len(probe_idx), batch_size):
        idxs = probe_idx[start:start + batch_size]
        tickers = out.loc[idxs, "ticker"].tolist()
        data = None
        try:
            data = yf.download(
                tickers,
                start=pd.Timestamp(start_date).strftime("%Y-%m-%d"),
                end=end_date,
                interval="1d",
                group_by="ticker",
                auto_adjust=False,
                actions=False,
                threads=True,
                progress=False,
                timeout=30,
            )
        except Exception:
            data = pd.DataFrame()

        for idx in idxs:
            ticker = str(out.at[idx, "ticker"])
            frame = _extract_ticker_frame(data, ticker)
            assessed = assess_price_frame(frame, pd.Timestamp(out.at[idx, "delisting_date"]))
            for key, value in assessed.items():
                out.at[idx, key] = value
        if request_pause > 0:
            time.sleep(request_pause)

    out.loc[out["identity_quarantined"], "coverage_status"] = "identity_quarantined"
    out.loc[out["identity_quarantined"], "usable_near_delist"] = False
    return out


def summarize(result: pd.DataFrame) -> dict:
    counts = (
        result["coverage_status"].fillna("not_probed").value_counts().sort_index().to_dict()
        if not result.empty and "coverage_status" in result.columns
        else {}
    )
    return {
        "official_delisting_events": int(len(result)),
        "identity_quarantined": int(result["identity_quarantined"].sum()) if not result.empty else 0,
        "probed_events": int((~result["identity_quarantined"]).sum()) if not result.empty else 0,
        "usable_near_delist": int(result["usable_near_delist"].fillna(False).sum()) if not result.empty else 0,
        "coverage_status_counts": {str(k): int(v) for k, v in counts.items()},
        "near_delist_window_calendar_days": NEAR_DELIST_CALENDAR_DAYS,
        "max_last_price_gap_days": MAX_LAST_PRICE_GAP_DAYS,
        "interpretation": (
            "This measures whether Yahoo retains prices near official delisting. "
            "It does not yet prove complete OHLCV coverage for every historical membership day."
        ),
        "acceptance_rule": (
            "identity-quarantined or suspicious post-delisting series must never be silently "
            "joined into historical backtests"
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default=str(OUT / "jpx_membership_events.csv"))
    ap.add_argument("--current-snapshot", default=str(OUT / "jpx_universe_snapshot.csv"))
    ap.add_argument("--start", default="2022-01-01")
    ap.add_argument("--batch-size", type=int, default=50)
    ap.add_argument("--request-pause", type=float, default=1.0)
    args = ap.parse_args()

    events, current = load_inputs(args.events, args.current_snapshot)
    candidates = build_delisting_candidates(events, current, pd.Timestamp(args.start))
    result = probe_yahoo(
        candidates,
        start_date=args.start,
        batch_size=max(1, args.batch_size),
        request_pause=max(0.0, args.request_pause),
    )
    OUT.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT / "yahoo_delisted_price_coverage.csv", index=False)
    report = summarize(result)
    with open(OUT / "yahoo_delisted_price_coverage_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
