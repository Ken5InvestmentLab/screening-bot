#!/usr/bin/env python3
"""Probe Stooq coverage for official JPX delistings (TEST ONLY).

This is a data-source feasibility test, not a model-performance experiment.
It reuses the exact JPX delisting candidate construction and identity quarantine
semantics from ``delisted_price_coverage.py``. 2026 returns are never used for
provider selection.

Stooq's CSV endpoint requires an API key in 2026. The key is read only from an
environment variable and is never printed, persisted, or placed in output
artifacts. Authentication/rate-limit/transport failures are explicitly
separated from true missing-history results so they cannot be misclassified as
coverage failures.

The default live probe is deliberately small and deterministic across pre-2026
delistings. Expand to the full non-quarantined candidate set only after the
small probe proves that Stooq retains historical data for delisted TSE names and
request limits are workable.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import time

import pandas as pd
import requests

from delisted_price_coverage import (
    OUT,
    MAX_LAST_PRICE_GAP_DAYS,
    NEAR_DELIST_CALENDAR_DAYS,
    assess_price_frame,
    build_delisting_candidates,
    load_inputs,
)

STOOQ_URL = "https://stooq.com/q/d/l/"
DEFAULT_SAMPLE_SIZE = 24
DEFAULT_PRE2026_END = pd.Timestamp("2025-12-31")


def _stable_probe_key(code: str, delisting_date: pd.Timestamp) -> str:
    raw = f"{code}|{pd.Timestamp(delisting_date).strftime('%Y-%m-%d')}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def select_deterministic_pre2026_sample(
    candidates: pd.DataFrame,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
) -> pd.DataFrame:
    """Select a deterministic, year-balanced pre-2026 sample.

    Sampling never uses returns or price availability. Identity-quarantined rows
    are excluded before sampling. Within each delisting year rows are ordered by
    a stable SHA-256 key, then selected round-robin across years.
    """
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")
    if candidates.empty:
        return candidates.copy()

    z = candidates.copy()
    z["delisting_date"] = pd.to_datetime(z["delisting_date"]).dt.normalize()
    z = z[
        (~z["identity_quarantined"].astype(bool))
        & (z["delisting_date"] <= DEFAULT_PRE2026_END)
    ].copy()
    if z.empty:
        return z

    z["delisting_year"] = z["delisting_date"].dt.year.astype(int)
    z["probe_key"] = [
        _stable_probe_key(str(c), pd.Timestamp(d))
        for c, d in zip(z["code"], z["delisting_date"])
    ]
    year_rows = {
        int(year): grp.sort_values(["probe_key", "delisting_date", "code"]).index.tolist()
        for year, grp in z.groupby("delisting_year", sort=True)
    }

    chosen: list[int] = []
    offset = 0
    years = sorted(year_rows)
    while len(chosen) < min(sample_size, len(z)):
        progressed = False
        for year in years:
            rows = year_rows[year]
            if offset < len(rows):
                chosen.append(rows[offset])
                progressed = True
                if len(chosen) >= min(sample_size, len(z)):
                    break
        if not progressed:
            break
        offset += 1

    return z.loc[chosen].drop(columns=["probe_key"]).reset_index(drop=True)


def _classify_stooq_text(text: str) -> tuple[str | None, str | None]:
    """Return (coverage_status, safe_error_message) for non-CSV responses."""
    raw = str(text or "").strip()
    low = raw.lower()
    if not raw:
        return "probe_error_empty_response", "empty_response"
    if "get your apikey" in low or "get_apikey" in low:
        return "probe_error_auth", "apikey_required"
    if "invalid apikey" in low or "invalid api key" in low or "wrong apikey" in low:
        return "probe_error_auth", "apikey_rejected"
    if "rate limit" in low or "quota" in low or ("limit" in low and "exceed" in low):
        return "probe_error_rate_limit", "rate_limit_or_quota"
    if low in {"no data", "no data."} or low.startswith("no data"):
        return None, None
    if "date," not in low and not low.startswith("date;"):
        return "probe_error_unexpected_response", "unexpected_non_csv_response"
    return None, None


def parse_stooq_csv(text: str) -> pd.DataFrame:
    status, _ = _classify_stooq_text(text)
    if status is not None:
        return pd.DataFrame()
    raw = str(text or "").strip()
    if not raw or raw.lower().startswith("no data"):
        return pd.DataFrame()
    try:
        frame = pd.read_csv(io.StringIO(raw))
    except Exception:
        return pd.DataFrame()
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    if "date" not in frame.columns:
        return pd.DataFrame()
    return frame


def assess_stooq_ohlcv(prices: pd.DataFrame, delisting_date: pd.Timestamp) -> dict:
    """Apply the Yahoo near-delisting gate plus explicit OHLCV completeness."""
    base = assess_price_frame(prices, delisting_date)
    p = prices.copy() if prices is not None else pd.DataFrame()
    if p.empty:
        base.update({
            "ohlcv_columns_complete": False,
            "near_delist_ohlcv_rows": 0,
            "usable_near_delist_ohlcv": False,
        })
        return base

    p.columns = [str(c).lower() for c in p.columns]
    required = ["date", "open", "high", "low", "close", "volume"]
    columns_complete = all(c in p.columns for c in required)
    near_rows = 0
    if columns_complete:
        p["date"] = pd.to_datetime(p["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
        for col in ["open", "high", "low", "close", "volume"]:
            p[col] = pd.to_numeric(p[col], errors="coerce")
        near = p[
            (p["date"] <= delisting_date)
            & (p["date"] >= delisting_date - pd.Timedelta(days=NEAR_DELIST_CALENDAR_DAYS))
        ].dropna(subset=["open", "high", "low", "close", "volume"])
        near_rows = int(len(near))

    usable = bool(base.get("usable_near_delist", False) and columns_complete and near_rows >= 5)
    base.update({
        "ohlcv_columns_complete": bool(columns_complete),
        "near_delist_ohlcv_rows": near_rows,
        "usable_near_delist_ohlcv": usable,
    })
    if base.get("usable_near_delist", False) and not usable:
        base["coverage_status"] = "partial_missing_ohlcv"
    return base


def _safe_request(
    session: requests.Session,
    *,
    code: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    api_key: str,
    timeout: float,
) -> tuple[pd.DataFrame, str | None, str | None]:
    params = {
        "s": f"{str(code).lower()}.jp",
        "d1": pd.Timestamp(start_date).strftime("%Y%m%d"),
        "d2": pd.Timestamp(end_date).strftime("%Y%m%d"),
        "i": "d",
        "apikey": api_key,
    }
    try:
        response = session.get(
            STOOQ_URL,
            params=params,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 tvfree-research-test"},
        )
    except Exception as exc:
        # Never persist exception text because some HTTP clients include the
        # complete request URL, which would contain the API key.
        return pd.DataFrame(), "probe_error_transport", type(exc).__name__

    if int(getattr(response, "status_code", 0)) != 200:
        return pd.DataFrame(), "probe_error_http", f"http_{getattr(response, 'status_code', 'unknown')}"

    text = str(getattr(response, "text", "") or "")
    status, safe_error = _classify_stooq_text(text)
    if status is not None:
        return pd.DataFrame(), status, safe_error
    frame = parse_stooq_csv(text)
    if frame.empty and not text.strip().lower().startswith("no data"):
        return pd.DataFrame(), "probe_error_parse", "csv_parse_or_schema_failure"
    return frame, None, None


def probe_stooq(
    candidates: pd.DataFrame,
    *,
    api_key: str,
    history_start: str,
    request_pause: float = 0.75,
    timeout: float = 30.0,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    if not api_key:
        raise ValueError("Stooq API key is required")
    out = candidates.copy().reset_index(drop=True)
    result_cols = [
        "price_rows", "first_price_date", "last_price_date_on_or_before_delist",
        "last_price_gap_days", "near_delist_rows", "post_delist_rows",
        "coverage_status", "usable_near_delist", "ohlcv_columns_complete",
        "near_delist_ohlcv_rows", "usable_near_delist_ohlcv", "probe_error",
    ]
    for col in result_cols:
        out[col] = pd.NA
    if out.empty:
        return out

    own_session = session is None
    client = session or requests.Session()
    start = pd.Timestamp(history_start).normalize()
    try:
        for idx, row in out.iterrows():
            if bool(row.get("identity_quarantined", False)):
                out.at[idx, "coverage_status"] = "identity_quarantined"
                out.at[idx, "usable_near_delist"] = False
                out.at[idx, "usable_near_delist_ohlcv"] = False
                continue

            delist = pd.Timestamp(row["delisting_date"]).normalize()
            frame, error_status, safe_error = _safe_request(
                client,
                code=str(row["code"]),
                start_date=start,
                end_date=delist + pd.Timedelta(days=30),
                api_key=api_key,
                timeout=timeout,
            )
            if error_status:
                out.at[idx, "coverage_status"] = error_status
                out.at[idx, "usable_near_delist"] = False
                out.at[idx, "usable_near_delist_ohlcv"] = False
                out.at[idx, "probe_error"] = safe_error
            else:
                assessed = assess_stooq_ohlcv(frame, delist)
                for key, value in assessed.items():
                    out.at[idx, key] = value
            if request_pause > 0:
                time.sleep(request_pause)
    finally:
        if own_session:
            client.close()
    return out


def summarize_stooq(
    result: pd.DataFrame,
    *,
    total_official_candidates: int,
    total_non_quarantined: int,
    requested_sample_size: int,
) -> dict:
    if result.empty:
        status_counts: dict[str, int] = {}
        by_year: dict[str, dict] = {}
    else:
        status_counts = {
            str(k): int(v)
            for k, v in result["coverage_status"].fillna("not_probed").value_counts().sort_index().items()
        }
        years = pd.to_datetime(result["delisting_date"]).dt.year
        by_year = {}
        for year, grp in result.groupby(years):
            by_year[str(int(year))] = {
                "probed": int(len(grp)),
                "usable_ohlcv": int(grp["usable_near_delist_ohlcv"].fillna(False).sum()),
                "probe_errors": int(grp["coverage_status"].fillna("").astype(str).str.startswith("probe_error").sum()),
            }

    usable = int(result["usable_near_delist_ohlcv"].fillna(False).sum()) if not result.empty else 0
    errors = int(result["coverage_status"].fillna("").astype(str).str.startswith("probe_error").sum()) if not result.empty else 0
    evaluated = int(len(result) - errors)
    return {
        "provider": "stooq",
        "mode": "deterministic_pre2026_small_probe",
        "model_selection_used": False,
        "return_data_used_for_provider_selection": False,
        "official_delisting_candidates_all_years": int(total_official_candidates),
        "non_quarantined_candidates_all_years": int(total_non_quarantined),
        "requested_sample_size": int(requested_sample_size),
        "sample_rows": int(len(result)),
        "evaluated_without_probe_error": evaluated,
        "usable_near_delist_ohlcv": usable,
        "probe_errors": errors,
        "coverage_status_counts": status_counts,
        "by_delisting_year": by_year,
        "near_delist_window_calendar_days": NEAR_DELIST_CALENDAR_DAYS,
        "max_last_price_gap_days": MAX_LAST_PRICE_GAP_DAYS,
        "acceptance_rule": (
            "Do not expand or accept Stooq from this small probe unless it actually retains complete OHLCV near "
            "pre-2026 official delistings and auth/rate-limit errors are low enough to make the full 460-event probe feasible."
        ),
        "secret_handling": "STOOQ_APIKEY is environment-only and is never written to artifacts/logs by this script.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default=str(OUT / "jpx_membership_events.csv"))
    ap.add_argument("--current-snapshot", default=str(OUT / "jpx_universe_snapshot.csv"))
    ap.add_argument("--history-start", default="2022-01-01")
    ap.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    ap.add_argument("--request-pause", type=float, default=0.75)
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--api-key-env", default="STOOQ_APIKEY")
    args = ap.parse_args()

    api_key = os.environ.get(args.api_key_env, "").strip()
    if not api_key:
        raise SystemExit(
            f"BLOCKED: {args.api_key_env} is not set. Obtain a free Stooq key manually; never commit or log it."
        )

    events, current = load_inputs(args.events, args.current_snapshot)
    candidates = build_delisting_candidates(events, current, pd.Timestamp(args.history_start))
    non_quarantined = candidates[~candidates["identity_quarantined"].astype(bool)]
    sample = select_deterministic_pre2026_sample(candidates, max(1, args.sample_size))
    result = probe_stooq(
        sample,
        api_key=api_key,
        history_start=args.history_start,
        request_pause=max(0.0, args.request_pause),
        timeout=max(1.0, args.timeout),
    )

    OUT.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT / "stooq_delisted_price_coverage_sample.csv", index=False)
    report = summarize_stooq(
        result,
        total_official_candidates=len(candidates),
        total_non_quarantined=len(non_quarantined),
        requested_sample_size=max(1, args.sample_size),
    )
    with open(OUT / "stooq_delisted_price_coverage_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
