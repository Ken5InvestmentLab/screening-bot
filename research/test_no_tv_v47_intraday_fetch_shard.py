from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import no_tv_v47_intraday_fetch_shard as v47


def test_shards_partition_exactly():
    symbols = ["1000","1001","1002","1003","1004","1005","1006"]
    parts = [
        v47.shard_symbols(symbols, i, 3)
        for i in range(3)
    ]
    flat = [x for p in parts for x in p]
    assert sorted(flat) == sorted(symbols)
    assert len(flat) == len(set(flat))


def test_parse_rows_keeps_short_histories():
    ts = [
        int(pd.Timestamp("2025-01-06 09:00", tz="Asia/Tokyo").tz_convert("UTC").timestamp()),
        int(pd.Timestamp("2025-01-06 10:00", tz="Asia/Tokyo").tz_convert("UTC").timestamp()),
    ]
    chart = {
        "timestamp": ts,
        "open": [100,101],
        "high": [102,103],
        "low": [99,100],
        "close": [101,102],
        "volume": [1000,2000],
    }
    out = v47.parse_rows("1234", chart)
    assert len(out) == 2
    assert set(out["symbol"]) == {"1234"}


def test_parse_rows_drops_outside_window_and_invalid():
    ts = [
        int(pd.Timestamp("2024-08-31 10:00", tz="Asia/Tokyo").tz_convert("UTC").timestamp()),
        int(pd.Timestamp("2025-01-06 10:00", tz="Asia/Tokyo").tz_convert("UTC").timestamp()),
    ]
    chart = {
        "timestamp": ts,
        "open": [100,101],
        "high": [102,100],
        "low": [99,103],
        "close": [101,102],
        "volume": [1000,2000],
    }
    out = v47.parse_rows("1234", chart)
    assert len(out) == 0


def test_systemic_429_requires_all_four_probes():
    assert v47.systemic_429_from_probe(["http_429"] * 4)
    assert not v47.systemic_429_from_probe(["http_429"] * 3)
    assert not v47.systemic_429_from_probe(
        ["http_429", "http_429", "http_200", "http_429"]
    )


def test_preflight_is_transport_only(monkeypatch=None):
    original = v47.probe_transport_status
    try:
        v47.probe_transport_status = lambda code, host: "http_429"
        out = v47.run_transport_preflight(["1000", "1001", "1002"])
        assert out["probe_count"] == 4
        assert out["systemic_http_429"] is True
        assert {x["symbol"] for x in out["observations"]} == {"1000", "1001"}
    finally:
        v47.probe_transport_status = original


def main():
    tests=[
        test_shards_partition_exactly,
        test_parse_rows_keeps_short_histories,
        test_parse_rows_drops_outside_window_and_invalid,
        test_systemic_429_requires_all_four_probes,
        test_preflight_is_transport_only,
    ]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(tests)}/{len(tests)} PASS")


if __name__ == "__main__":
    main()
