from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

FETCH_START = "2024-01-01"
FETCH_END_EXCLUSIVE = "2026-09-12"
PRIMARY_START = "2025-01-01"
PRIMARY_END = "2025-12-31"
DEV_END = "2025-06-30"
VALID_START = "2025-07-01"
MIN_COVERAGE = 0.95
BATCH = 80
KNOWN = {"3350", "2334", "6574", "7273", "4935", "6039"}


def clean_symbol(x: object) -> str:
    return str(x).replace(".0", "").strip()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def chunks(xs: list[str], n: int):
    for i in range(0, len(xs), n):
        yield xs[i:i+n]


def extract_split_rows(data: pd.DataFrame, tickers: list[str]) -> list[dict]:
    rows: list[dict] = []
    if data is None or data.empty:
        return rows

    if isinstance(data.columns, pd.MultiIndex):
        lvl0 = set(map(str, data.columns.get_level_values(0)))
        lvl1 = set(map(str, data.columns.get_level_values(1)))
        ticker_outer = any(t in lvl0 for t in tickers)

        for ticker in tickers:
            code = ticker.removesuffix(".T")
            try:
                if ticker_outer:
                    if ticker not in lvl0:
                        continue
                    z = data[ticker]
                else:
                    if ticker not in lvl1:
                        continue
                    z = data.xs(ticker, axis=1, level=1)
            except Exception:
                continue

            split_col = next((c for c in z.columns if str(c).lower() == "stock splits"), None)
            if split_col is None:
                continue
            s = pd.to_numeric(z[split_col], errors="coerce").fillna(0.0)
            for idx, val in s[s != 0].items():
                rows.append({
                    "symbol": code,
                    "event_date": pd.Timestamp(idx).tz_localize(None).strftime("%Y-%m-%d"),
                    "split_ratio": float(val),
                })
        return rows

    # Single-ticker fallback.
    split_col = next((c for c in data.columns if str(c).lower() == "stock splits"), None)
    if split_col is not None and len(tickers) == 1:
        code = tickers[0].removesuffix(".T")
        s = pd.to_numeric(data[split_col], errors="coerce").fillna(0.0)
        for idx, val in s[s != 0].items():
            rows.append({
                "symbol": code,
                "event_date": pd.Timestamp(idx).tz_localize(None).strftime("%Y-%m-%d"),
                "split_ratio": float(val),
            })
    return rows


def fetch_splits(symbols: list[str], batch: int) -> tuple[pd.DataFrame, dict]:
    tickers = [s + ".T" for s in symbols]
    all_rows: list[dict] = []
    covered: set[str] = set()
    failures: list[dict] = []

    parts = list(chunks(tickers, batch))
    for no, part in enumerate(parts, 1):
        data = None
        last = None
        for attempt in range(3):
            try:
                data = yf.download(
                    part,
                    start=FETCH_START,
                    end=FETCH_END_EXCLUSIVE,
                    interval="1d",
                    group_by="ticker",
                    auto_adjust=False,
                    actions=True,
                    threads=True,
                    progress=False,
                    timeout=30,
                )
                if data is not None and not data.empty:
                    break
            except Exception as e:
                last = f"{type(e).__name__}: {e}"
            time.sleep(2 ** attempt)

        if data is None or data.empty:
            failures.append({"batch": no, "tickers": part, "error": last or "empty"})
            print(f"split batch {no}/{len(parts)} EMPTY", flush=True)
            continue

        # Coverage is based on ticker presence in returned MultiIndex, not on
        # whether a split happened.
        if isinstance(data.columns, pd.MultiIndex):
            l0 = set(map(str, data.columns.get_level_values(0)))
            l1 = set(map(str, data.columns.get_level_values(1)))
            if any(t in l0 for t in part):
                covered.update(t.removesuffix(".T") for t in part if t in l0)
            elif any(t in l1 for t in part):
                covered.update(t.removesuffix(".T") for t in part if t in l1)
        elif len(part) == 1:
            covered.add(part[0].removesuffix(".T"))

        all_rows.extend(extract_split_rows(data, part))
        print(
            f"split batch {no}/{len(parts)} covered={len(covered)} events={len(all_rows)}",
            flush=True,
        )

    splits = pd.DataFrame(all_rows, columns=["symbol", "event_date", "split_ratio"])
    if not splits.empty:
        splits["symbol"] = splits["symbol"].map(clean_symbol)
        splits["event_date"] = pd.to_datetime(splits["event_date"])
        splits["split_ratio"] = pd.to_numeric(splits["split_ratio"], errors="coerce")
        splits = (
            splits.dropna()
            .drop_duplicates(["symbol", "event_date", "split_ratio"])
            .sort_values(["symbol", "event_date"])
            .reset_index(drop=True)
        )

    receipt = {
        "requested_symbols": len(symbols),
        "covered_symbols": len(covered),
        "coverage_fraction": float(len(covered) / len(symbols)) if symbols else 0.0,
        "failed_batches": failures,
        "split_events": int(len(splits)),
        "symbols_with_splits": int(splits["symbol"].nunique()) if len(splits) else 0,
    }
    if receipt["coverage_fraction"] < MIN_COVERAGE:
        raise RuntimeError(f"split download coverage too low: {receipt}")
    if len(splits) and ((splits["split_ratio"] <= 0) | ~np.isfinite(splits["split_ratio"])).any():
        raise RuntimeError("invalid split ratio")
    return splits, receipt


def future_factor_map(splits: pd.DataFrame, max_date: pd.Timestamp) -> dict[str, list[tuple[pd.Timestamp, float]]]:
    out: dict[str, list[tuple[pd.Timestamp, float]]] = {}
    if splits.empty:
        return out
    q = splits[splits["event_date"] <= max_date].copy()
    for symbol, g in q.groupby("symbol", sort=False):
        out[str(symbol)] = [
            (pd.Timestamp(r.event_date), float(r.split_ratio))
            for r in g.itertuples(index=False)
        ]
    return out


def factor_for_date(events: list[tuple[pd.Timestamp, float]], date: pd.Timestamp) -> float:
    factor = 1.0
    for event_date, ratio in events:
        if event_date > date:
            factor *= ratio
    return factor


def synthetic_self_check() -> None:
    events = [
        (pd.Timestamp("2025-04-01"), 10.0),
        (pd.Timestamp("2026-01-15"), 2.0),
    ]
    assert math.isclose(factor_for_date(events, pd.Timestamp("2025-03-31")), 20.0)
    assert math.isclose(factor_for_date(events, pd.Timestamp("2025-04-01")), 2.0)
    assert math.isclose(factor_for_date(events, pd.Timestamp("2026-01-15")), 1.0)

    reverse = [(pd.Timestamp("2025-08-01"), 0.1)]
    assert math.isclose(factor_for_date(reverse, pd.Timestamp("2025-07-31")), 0.1)
    assert math.isclose(factor_for_date(reverse, pd.Timestamp("2025-08-01")), 1.0)


def load_daily(path: Path) -> pd.DataFrame:
    d = pd.read_csv(
        path,
        usecols=["date", "close", "volume", "symbol"],
        dtype={"symbol": str},
        low_memory=False,
    )
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d["symbol"] = d["symbol"].map(clean_symbol)
    d["close"] = pd.to_numeric(d["close"], errors="coerce")
    d["volume"] = pd.to_numeric(d["volume"], errors="coerce")
    d = d.dropna(subset=["date", "symbol", "close", "volume"])
    d = d.sort_values(["symbol", "date"]).drop_duplicates(["symbol", "date"], keep="last")
    g = d.groupby("symbol", sort=False)
    d["prev_date"] = g["date"].shift(1)
    d["prev_close_adjusted"] = g["close"].shift(1)
    d["prev_volume"] = g["volume"].shift(1)
    return d


def add_pit_eligibility(d: pd.DataFrame, fmap: dict[str, list[tuple[pd.Timestamp, float]]]) -> pd.DataFrame:
    x = d.copy()
    factors = []
    for row in x[["symbol", "prev_date"]].itertuples(index=False):
        if pd.isna(row.prev_date):
            factors.append(np.nan)
            continue
        factors.append(factor_for_date(fmap.get(str(row.symbol), []), pd.Timestamp(row.prev_date)))
    x["future_split_factor_from_prev_date"] = factors
    x["prev_close_pit"] = x["prev_close_adjusted"] * x["future_split_factor_from_prev_date"]
    x["eligible_adjusted"] = (
        (x["prev_close_adjusted"] <= 1000)
        & (x["prev_volume"] >= 10000)
    )
    x["eligible_pit"] = (
        (x["prev_close_pit"] <= 1000)
        & (x["prev_volume"] >= 10000)
    )
    return x


def period_stats(x: pd.DataFrame, start: str, end: str) -> dict:
    q = x[x["date"].between(start, end)].copy()
    a = q[q["eligible_adjusted"]]
    p = q[q["eligible_pit"]]
    fp = q[q["eligible_adjusted"] & ~q["eligible_pit"]]
    fn = q[~q["eligible_adjusted"] & q["eligible_pit"]]
    return {
        "calendar_rows": int(len(q)),
        "adjusted_eligible_rows": int(len(a)),
        "pit_eligible_rows": int(len(p)),
        "adjusted_eligible_symbols": int(a["symbol"].nunique()),
        "pit_eligible_symbols": int(p["symbol"].nunique()),
        "adjusted_only_false_positive_rows": int(len(fp)),
        "pit_only_false_negative_rows": int(len(fn)),
        "adjusted_only_symbols": int(fp["symbol"].nunique()),
        "pit_only_symbols": int(fn["symbol"].nunique()),
        "adjusted_only_row_fraction_of_adjusted_eligible": (
            float(len(fp) / len(a)) if len(a) else None
        ),
        "pit_only_row_fraction_of_pit_eligible": (
            float(len(fn) / len(p)) if len(p) else None
        ),
    }


def examples(x: pd.DataFrame, symbols: set[str]) -> list[dict]:
    q = x[
        x["symbol"].isin(symbols)
        & x["date"].between(PRIMARY_START, PRIMARY_END)
        & (x["eligible_adjusted"] != x["eligible_pit"])
    ].copy()
    cols = [
        "date", "symbol", "prev_date", "prev_close_adjusted", "prev_close_pit",
        "prev_volume", "future_split_factor_from_prev_date",
        "eligible_adjusted", "eligible_pit",
    ]
    return q.sort_values(["symbol", "date"])[cols].head(200).to_dict("records")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frozen-daily", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--batch", type=int, default=BATCH)
    a = ap.parse_args()

    synthetic_self_check()
    daily = load_daily(a.frozen_daily)
    symbols = sorted(daily["symbol"].unique())
    max_date = pd.Timestamp(daily["date"].max())

    splits, split_receipt = fetch_splits(symbols, a.batch)
    fmap = future_factor_map(splits, max_date)
    audited = add_pit_eligibility(daily, fmap)

    out = a.output_dir
    out.mkdir(parents=True, exist_ok=True)
    split_csv = out / "v46_split_events.csv"
    splits.to_csv(split_csv, index=False)

    changes = audited[
        audited["date"].between(PRIMARY_START, PRIMARY_END)
        & (audited["eligible_adjusted"] != audited["eligible_pit"])
    ].copy()
    changes.to_csv(out / "v46_eligibility_changes_2025.csv", index=False)

    result = {
        "scope": "outcome-free point-in-time split eligibility audit",
        "frozen_daily": {
            "symbols": int(len(symbols)),
            "min_date": str(daily["date"].min().date()),
            "max_date": str(max_date.date()),
        },
        "split_fetch": split_receipt,
        "split_event_sha256": sha256_file(split_csv),
        "periods": {
            "2025_all": period_stats(audited, PRIMARY_START, PRIMARY_END),
            "2025_h1": period_stats(audited, PRIMARY_START, DEV_END),
            "2025_h2": period_stats(audited, VALID_START, PRIMARY_END),
            "2026_descriptive": period_stats(audited, "2026-01-01", str(max_date.date())),
        },
        "known_symbol_change_examples": examples(audited, KNOWN),
        "strategy_returns_opened": False,
        "model_scores_opened": False,
        "production_writes": False,
        "limitation": (
            "This corrects future-split leakage in the price-threshold test inside "
            "the current-listed run80 universe. It does not repair survivorship bias "
            "from symbols already delisted before the 2026-09-11 JPX snapshot."
        ),
    }
    (out / "v46_pit_split_eligibility.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
