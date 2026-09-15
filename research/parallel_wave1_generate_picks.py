#!/usr/bin/env python3
"""Generate the frozen Parallel Wave-1 A1/B1/E1 causal pick ledger.

Outcome-blind by construction:
- reads only same/past-session OHLCV for A1/B1/E1 state construction;
- never reads an entry/exit return or computes any future return;
- uses the pinned XTKS calendar for exact session offsets;
- excludes 2022 from Wave-1 evaluation and marks 2026 as robustness-only;
- picks at most one symbol per family/session using frozen symbol-ascending fallback.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

DAILY_SHA256 = "6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0"
CALENDAR_SHA256 = "58e67bd20be08d04c143fa7e8f707bb3b82c21c2de2af9dfd7c2a05a406de71b"
DAILY_HEADER = ["date", "open", "high", "low", "close", "volume", "symbol"]
PICK_HEADER = ["family", "signal_date", "symbol"]
SIGNAL_START = "2023-01-04"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_calendar(path: Path) -> tuple[list[str], dict[str, int]]:
    actual_sha256 = sha256_file(path)\n    if actual_sha256 != CALENDAR_SHA256:\n        raise SystemExit(f"FAIL_CLOSED: pinned XTKS calendar SHA-256 mismatch: actual={actual_sha256} expected={CALENDAR_SHA256}")
    cal = pd.read_csv(path, dtype={"session": "string"})
    if list(cal.columns) != ["session"]:
        raise SystemExit(f"FAIL_CLOSED: calendar header mismatch: {list(cal.columns)!r}")
    sessions = cal["session"].astype(str).tolist()
    if not sessions or sessions != sorted(sessions) or len(sessions) != len(set(sessions)):
        raise SystemExit("FAIL_CLOSED: calendar sessions must be unique and ordered")
    return sessions, {d: i for i, d in enumerate(sessions)}


def load_daily(path: Path, session_index: dict[str, int]) -> pd.DataFrame:
    if sha256_file(path) != DAILY_SHA256:
        raise SystemExit("FAIL_CLOSED: frozen daily SHA-256 mismatch")

    z = pd.read_csv(
        path,
        dtype={"date": "string", "symbol": "string"},
        low_memory=False,
    )
    if list(z.columns) != DAILY_HEADER:
        raise SystemExit(f"FAIL_CLOSED: daily header mismatch: {list(z.columns)!r}")
    if len(z) != 4_061_361:
        raise SystemExit(f"FAIL_CLOSED: daily row-count mismatch: {len(z)}")

    z["date"] = z["date"].astype(str).str.strip()
    z["symbol"] = z["symbol"].astype(str).str.strip()
    if z["symbol"].eq("").any() or z["date"].eq("").any():
        raise SystemExit("FAIL_CLOSED: blank date/symbol")

    for col in ["open", "high", "low", "close", "volume"]:
        z[col] = pd.to_numeric(z[col], errors="coerce")
    ohlc = z[["open", "high", "low", "close"]]
    if not np.isfinite(ohlc.to_numpy()).all() or (ohlc <= 0).any().any():
        raise SystemExit("FAIL_CLOSED: non-finite/non-positive OHLC")
    if not np.isfinite(z["volume"].to_numpy()).all() or (z["volume"] < 0).any():
        raise SystemExit("FAIL_CLOSED: invalid volume")
    if (z["high"] < z[["open", "low", "close"]].max(axis=1)).any():
        raise SystemExit("FAIL_CLOSED: high violates OHLC ordering")
    if (z["low"] > z[["open", "high", "close"]].min(axis=1)).any():
        raise SystemExit("FAIL_CLOSED: low violates OHLC ordering")
    if z.duplicated(["symbol", "date"]).any():
        raise SystemExit("FAIL_CLOSED: duplicate symbol/date")

    z["_session_i"] = z["date"].map(session_index)
    if z["_session_i"].isna().any():
        bad = z.loc[z["_session_i"].isna(), "date"].drop_duplicates().head(10).tolist()
        raise SystemExit(f"FAIL_CLOSED: daily rows outside pinned XTKS calendar: {bad!r}")
    z["_session_i"] = z["_session_i"].astype(np.int32)
    z = z.sort_values(["symbol", "_session_i"], kind="stable").reset_index(drop=True)
    return z


def causal_pick_ledger(daily: pd.DataFrame, sessions: list[str], session_index: dict[str, int]) -> tuple[pd.DataFrame, dict[str, object]]:
    source_min = str(daily["date"].min())
    source_max = str(daily["date"].max())
    if source_min != "2022-01-04" or source_max != "2026-09-11":
        raise SystemExit(f"FAIL_CLOSED: unexpected source date bounds: {source_min}..{source_max}")
    if source_max not in session_index:
        raise SystemExit("FAIL_CLOSED: source max date missing from pinned calendar")

    max_i = session_index[source_max]
    if max_i < 5:
        raise SystemExit("FAIL_CLOSED: source has no fifth-close horizon")
    max_signal = sessions[max_i - 5]

    g = daily.groupby("symbol", sort=False, group_keys=False)
    session_i = daily["_session_i"]

    # Exact-session continuity guards prevent row-shift substitution over missing sessions.
    prev1_i = g["_session_i"].shift(1)
    prev5_i = g["_session_i"].shift(5)
    prev20_i = g["_session_i"].shift(20)
    prev21_i = g["_session_i"].shift(21)
    cont1 = (session_i - prev1_i).eq(1)
    cont5 = (session_i - prev5_i).eq(5)
    cont20 = (session_i - prev20_i).eq(20)
    cont21 = (session_i - prev21_i).eq(21)

    prev_close = g["close"].shift(1)
    range_pct = (daily["high"] - daily["low"]) / prev_close
    prior_range = range_pct.groupby(daily["symbol"], sort=False).shift(1)
    compress5 = prior_range.groupby(daily["symbol"], sort=False).transform(
        lambda s: s.rolling(5, min_periods=5).median()
    )
    baseline20 = prior_range.groupby(daily["symbol"], sort=False).transform(
        lambda s: s.rolling(20, min_periods=20).median()
    )

    a1 = (
        cont21
        & np.isfinite(range_pct)
        & np.isfinite(compress5)
        & np.isfinite(baseline20)
        & baseline20.gt(0)
        & (compress5 / baseline20).le(0.75)
        & (range_pct / baseline20).ge(1.25)
    )

    close1 = g["close"].shift(1)
    close5 = g["close"].shift(5)
    ret1 = daily["close"] / close1 - 1.0
    ret5 = daily["close"] / close5 - 1.0
    b_valid = cont1 & cont5 & np.isfinite(ret1) & np.isfinite(ret5)
    mkt_ret1 = ret1.where(b_valid).groupby(daily["date"], sort=False).transform("median")
    mkt_ret5 = ret5.where(b_valid).groupby(daily["date"], sort=False).transform("median")
    b1 = b_valid & (ret5 - mkt_ret5).le(-0.05) & (ret1 - mkt_ret1).ge(0.0)

    prior_low = g["low"].transform(lambda s: s.shift(1).rolling(20, min_periods=20).min())
    dist_low = daily["close"] / prior_low - 1.0
    e1 = (
        cont20
        & np.isfinite(prior_low)
        & prior_low.gt(0)
        & np.isfinite(dist_low)
        & dist_low.ge(0.0)
        & dist_low.le(0.05)
    )

    signal_mask = daily["date"].ge(SIGNAL_START) & daily["date"].le(max_signal)

    pieces: list[pd.DataFrame] = []
    for family, cond in [("A1", a1), ("B1", b1), ("E1", e1)]:
        q = daily.loc[signal_mask & cond, ["date", "symbol"]].copy()
        q = q.sort_values(["date", "symbol"], kind="stable").drop_duplicates("date", keep="first")
        q.insert(0, "family", family)
        q = q.rename(columns={"date": "signal_date"})
        pieces.append(q[PICK_HEADER])

    picks = pd.concat(pieces, ignore_index=True)
    picks = picks.sort_values(["signal_date", "family", "symbol"], kind="stable").reset_index(drop=True)
    if picks.duplicated(PICK_HEADER).any():
        raise SystemExit("FAIL_CLOSED: duplicate pick ledger rows")
    if picks.groupby(["family", "signal_date"]).size().gt(1).any():
        raise SystemExit("FAIL_CLOSED: more than one pick per family/date")

    by_family = {k: int(v) for k, v in picks["family"].value_counts().sort_index().items()}
    years = picks["signal_date"].str.slice(0, 4)
    by_year_family: dict[str, dict[str, int]] = {}
    for year in sorted(years.unique()):
        sub = picks.loc[years.eq(year)]
        by_year_family[str(year)] = {
            family: int((sub["family"] == family).sum()) for family in ["A1", "B1", "E1"]
        }

    receipt: dict[str, object] = {
        "contract_version": 1,
        "status": "CAUSAL_PICK_LEDGER_FROZEN_PERFORMANCE_UNOPENED",
        "performance_opened": False,
        "return_computed": False,
        "source": {
            "sha256": DAILY_SHA256,
            "rows": int(len(daily)),
            "min_date": source_min,
            "max_date": source_max,
            "header": DAILY_HEADER,
        },
        "calendar": {
            "sha256": CALENDAR_SHA256,
            "sessions": len(sessions),
        },
        "signal_period": {
            "start": SIGNAL_START,
            "end": max_signal,
            "end_rule": "latest signal XTKS session whose fifth-session close is no later than frozen source max date",
        },
        "evaluation_policy": {
            "2022": "EXCLUDED_ENTIRELY_FROM_WAVE1_EVALUATION",
            "2023_2025": "PRIMARY_ONE_SHOT_DIAGNOSTIC; annual slices fixed before outcomes",
            "2026": "REPORT_ROBUSTNESS_ONLY",
            "promotion_note": "No untouched confirmation block is asserted by this ledger; performance remains diagnostic unless a separate locked confirmation contract exists.",
        },
        "thresholds": {
            "A1": "compress5/baseline20 <= 0.75 AND signal_range/baseline20 >= 1.25",
            "B1": "rel5 <= -0.05 AND rel1 >= 0.00",
            "E1": "0.00 <= close/prior20_low-1 <= 0.05",
        },
        "continuity_policy": "exact pinned-XTKS session offsets; missing sessions make that symbol/date ineligible rather than row-shifting",
        "candidate_tiebreak": "symbol ascending; bound source has no tail_p",
        "pick_count": int(len(picks)),
        "pick_count_by_family": by_family,
        "pick_count_by_year_family": by_year_family,
        "transaction_cost_pct": 0.0,
        "win_definition": "gross_return > 0",
        "next_boundary": "bind pick-ledger SHA then pass endpoint-session completeness verifier before any performance calculation",
    }
    return picks, receipt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily", type=Path, required=True)
    ap.add_argument("--calendar", type=Path, required=True)
    ap.add_argument("--picks-out", type=Path, required=True)
    ap.add_argument("--receipt-out", type=Path, required=True)
    args = ap.parse_args()

    sessions, session_index = load_calendar(args.calendar)
    daily = load_daily(args.daily, session_index)
    picks, receipt = causal_pick_ledger(daily, sessions, session_index)

    args.picks_out.parent.mkdir(parents=True, exist_ok=True)
    picks.to_csv(args.picks_out, index=False, lineterminator="\n")
    receipt["pick_ledger"] = {
        "path": str(args.picks_out),
        "sha256": sha256_file(args.picks_out),
        "header": PICK_HEADER,
    }
    args.receipt_out.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
