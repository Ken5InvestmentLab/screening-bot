from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tvfree_screener.batch01.evaluation import build_five_session_labels, label_summary
from tvfree_screener.batch01.feature_panel import build_market_return_table
from tvfree_screener.batch01.session_calendar import SessionCalendar

EXPECTED = {
    "daily": "6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0",
    "tail": "0398969e13cc4b79f64cf8ad3b300ab34c0270ac70d20367994979478b60849d",
    "calendar": "74ab2aaf72a0c055af31b461dd1b5776cf83eebc9576830954248aa03f518f68",
}
RET10_MAX = 0.5735294117647058
TAIL_GATE = 0.999
COST = 0.005
YEAR_CUTOFFS = {
    2023: pd.Timestamp("2023-12-29"),
    2024: pd.Timestamp("2024-12-30"),
    2025: pd.Timestamp("2025-12-30"),
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def build_pool(tail_path: Path, daily_path: Path, calendar: SessionCalendar) -> pd.DataFrame:
    bars = pd.read_csv(
        daily_path,
        usecols=["date", "symbol", "close"],
        dtype={"symbol": "string", "close": "float64"},
        parse_dates=["date"],
    )
    bars["date"] = pd.to_datetime(bars["date"], errors="raise").dt.normalize()
    market = build_market_return_table(bars, sessions=calendar.sessions)

    cols = ["date", "symbol", "ret10", "volr20", "tail_cdf", "tail_p", "med_ret5"]
    tail = pd.read_csv(tail_path, usecols=cols, parse_dates=["date"], dtype={"symbol": "string"})
    tail["date"] = pd.to_datetime(tail["date"], errors="raise").dt.normalize()
    tail = tail.merge(
        market[["date", "market_median_ret5_lag1"]],
        on="date",
        how="left",
        validate="many_to_one",
    )
    for c in ("ret10", "volr20", "tail_cdf", "tail_p", "market_median_ret5_lag1"):
        tail[c] = pd.to_numeric(tail[c], errors="coerce")

    return tail.loc[
        tail["tail_cdf"].ge(TAIL_GATE)
        & tail["market_median_ret5_lag1"].notna()
        & tail["market_median_ret5_lag1"].le(0)
        & tail["ret10"].notna()
        & tail["ret10"].le(RET10_MAX)
    ].copy()


def select_all_with_one_session_cooldown(pool: pd.DataFrame, calendar: SessionCalendar) -> pd.DataFrame:
    work = pool.copy()
    work["date"] = pd.to_datetime(work["date"], errors="raise").dt.normalize()
    work["symbol"] = work["symbol"].astype("string")
    groups = {pd.Timestamp(d): g.copy() for d, g in work.groupby("date", sort=False)}
    previous_selected: set[str] = set()
    selected: list[pd.DataFrame] = []

    for day in calendar.sessions:
        group = groups.get(pd.Timestamp(day))
        if group is None or group.empty:
            previous_selected = set()
            continue
        group = group.sort_values("symbol", kind="mergesort")
        blocked = group["symbol"].astype(str).isin(previous_selected)
        chosen = group.loc[~blocked].copy()
        if not chosen.empty:
            selected.append(chosen)
        previous_selected = set(chosen["symbol"].astype(str))

    return pd.concat(selected, ignore_index=True) if selected else work.iloc[0:0].copy()


def price_subset(daily_path: Path, signals: pd.DataFrame, calendar: SessionCalendar) -> pd.DataFrame:
    symbols = set(signals["symbol"].astype(str))
    needed_dates: set[str] = set()
    for value in pd.to_datetime(signals["date"]).dt.normalize().unique():
        pos = calendar.position(value)
        for offset in range(0, 6):
            if pos + offset < len(calendar.sessions):
                needed_dates.add(pd.Timestamp(calendar.sessions[pos + offset]).strftime("%Y-%m-%d"))

    pieces = []
    for chunk in pd.read_csv(
        daily_path,
        usecols=["date", "symbol", "open", "high", "low", "close", "volume"],
        dtype={"date": "string", "symbol": "string"},
        chunksize=250_000,
        low_memory=False,
    ):
        keep = chunk["symbol"].isin(symbols) & chunk["date"].isin(needed_dates)
        if keep.any():
            pieces.append(chunk.loc[keep].copy())
    price = pd.concat(pieces, ignore_index=True)
    price["date"] = pd.to_datetime(price["date"], errors="raise").dt.normalize()
    for c in ("open", "high", "low", "close", "volume"):
        price[c] = pd.to_numeric(price[c], errors="coerce")
    return price


def periodized(rows: pd.DataFrame, year: int) -> pd.DataFrame:
    out = rows.loc[pd.to_datetime(rows["date"]).dt.year.eq(year)].copy()
    cutoff = YEAR_CUTOFFS[year]
    crosses = out["exit_date"].notna() & pd.to_datetime(out["exit_date"]).gt(cutoff)
    out.loc[crosses, "label_resolved"] = False
    out.loc[crosses, "label_status"] = "PURGED_SPLIT_BOUNDARY"
    out.loc[crosses, "gross_return"] = np.nan
    return out


def locked_gate(summary_2025: dict) -> dict:
    net = summary_2025["round_trip_cost_scenarios"]["0.005"]
    checks = {
        "resolved_n_min_30": int(summary_2025["resolved_count"]) >= 30,
        "mean_gt_0": float(net["mean"]) > 0,
        "plus20_rate_min_0_10": float(net["plus20_rate"]) >= 0.10,
        "minus10_rate_max_0_40": float(net["minus10_rate"]) <= 0.40,
        "mean_excluding_top1_winner_gt_0": float(net["mean_excluding_top1_winner"]) > 0,
    }
    checks["all_pass"] = all(checks.values())
    return checks


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tail", type=Path, required=True)
    p.add_argument("--daily", type=Path, required=True)
    p.add_argument("--calendar", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()

    actual = {
        "tail": sha256_file(a.tail),
        "daily": sha256_file(a.daily),
        "calendar": sha256_file(a.calendar),
    }
    for key, expected in EXPECTED.items():
        if actual[key] != expected:
            raise RuntimeError(f"{key} SHA mismatch: {actual[key]}")

    calendar = SessionCalendar.from_csv(a.calendar, expected_sha256=EXPECTED["calendar"])
    pool = build_pool(a.tail, a.daily, calendar)
    counts = {
        str(y): {
            "pool_rows": int(len(pool.loc[pd.to_datetime(pool["date"]).dt.year.eq(y)])),
            "pool_dates": int(pool.loc[pd.to_datetime(pool["date"]).dt.year.eq(y), "date"].nunique()),
        }
        for y in (2023, 2024, 2025)
    }
    if counts["2023"]["pool_rows"] != 69 or counts["2024"]["pool_rows"] != 138:
        raise RuntimeError(f"canonical v1 pool receipt mismatch: {counts}")

    selected = select_all_with_one_session_cooldown(pool, calendar)
    prices = price_subset(a.daily, selected, calendar)
    signals = selected[["date", "symbol"]].drop_duplicates().copy()
    labels = build_five_session_labels(prices, signals, calendar)
    joined = selected.merge(labels, on=["date", "symbol"], how="left", validate="one_to_one")

    result = {
        "experiment_id": "MONSTER-CANONICAL-V2-ALL-WEAK-EARLY-EXACT-REPLAY-20260914",
        "parent_spec": "monster_weak_early_all_candidates_canonical_v2",
        "input_sha256": actual,
        "pool_receipt": counts,
        "selection_policy": "ALL_WEAK_EARLY with one immediately preceding official-session same-symbol cooldown",
        "periods": {},
        "2026_outcomes_opened": False,
        "production_modified": False,
    }

    for y in (2023, 2024, 2025):
        year_rows = periodized(joined, y)
        result["periods"][str(y)] = {
            "selected_count": int(len(year_rows)),
            "summary": label_summary(year_rows, costs=(0.0, 0.005, 0.01)),
        }

    result["locked_2025_gate"] = locked_gate(result["periods"]["2025"]["summary"])
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
