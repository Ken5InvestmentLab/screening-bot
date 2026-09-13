from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import no_tv_v46_pit_split_eligibility as v46


def test_future_factor_forward_splits():
    events = [
        (pd.Timestamp("2025-04-01"), 10.0),
        (pd.Timestamp("2026-01-15"), 2.0),
    ]
    assert math.isclose(v46.factor_for_date(events, pd.Timestamp("2025-03-31")), 20.0)
    assert math.isclose(v46.factor_for_date(events, pd.Timestamp("2025-04-01")), 2.0)
    assert math.isclose(v46.factor_for_date(events, pd.Timestamp("2026-01-15")), 1.0)


def test_future_factor_reverse_split():
    events = [(pd.Timestamp("2025-08-01"), 0.1)]
    assert math.isclose(v46.factor_for_date(events, pd.Timestamp("2025-07-31")), 0.1)
    assert math.isclose(v46.factor_for_date(events, pd.Timestamp("2025-08-01")), 1.0)


def test_signal_day_split_restores_previous_close():
    daily = pd.DataFrame({
        "date": pd.to_datetime(["2025-03-31", "2025-04-01"]),
        "close": [500.0, 520.0],
        "volume": [20000, 30000],
        "symbol": ["3350", "3350"],
    })
    g = daily.groupby("symbol", sort=False)
    daily["prev_date"] = g["date"].shift(1)
    daily["prev_close_adjusted"] = g["close"].shift(1)
    daily["prev_volume"] = g["volume"].shift(1)
    fmap = {"3350": [(pd.Timestamp("2025-04-01"), 10.0)]}
    out = v46.add_pit_eligibility(daily, fmap)
    row = out.iloc[1]
    assert math.isclose(row["prev_close_pit"], 5000.0)
    assert bool(row["eligible_adjusted"]) is True
    assert bool(row["eligible_pit"]) is False


def test_reverse_split_can_create_adjusted_false_negative():
    daily = pd.DataFrame({
        "date": pd.to_datetime(["2025-07-31", "2025-08-01"]),
        "close": [5000.0, 5200.0],
        "volume": [20000, 30000],
        "symbol": ["9999", "9999"],
    })
    g = daily.groupby("symbol", sort=False)
    daily["prev_date"] = g["date"].shift(1)
    daily["prev_close_adjusted"] = g["close"].shift(1)
    daily["prev_volume"] = g["volume"].shift(1)
    fmap = {"9999": [(pd.Timestamp("2025-08-01"), 0.1)]}
    out = v46.add_pit_eligibility(daily, fmap)
    row = out.iloc[1]
    assert math.isclose(row["prev_close_pit"], 500.0)
    assert bool(row["eligible_adjusted"]) is False
    assert bool(row["eligible_pit"]) is True


def test_extract_split_rows_ticker_outer_multiindex():
    idx = pd.to_datetime(["2025-03-31", "2025-04-01"])
    cols = pd.MultiIndex.from_product([["3350.T"], ["Close", "Stock Splits"]])
    data = pd.DataFrame([[500.0, 0.0], [52.0, 10.0]], index=idx, columns=cols)
    rows = v46.extract_split_rows(data, ["3350.T"])
    assert rows == [{
        "symbol": "3350",
        "event_date": "2025-04-01",
        "split_ratio": 10.0,
    }]


def main():
    tests = [
        test_future_factor_forward_splits,
        test_future_factor_reverse_split,
        test_signal_day_split_restores_previous_close,
        test_reverse_split_can_create_adjusted_false_negative,
        test_extract_split_rows_ticker_outer_multiindex,
    ]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(tests)}/{len(tests)} PASS")


if __name__ == "__main__":
    main()
