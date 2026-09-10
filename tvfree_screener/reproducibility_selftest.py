#!/usr/bin/env python3
"""Synthetic self-checks for the test-only reproducibility manifest.

These checks use tiny fabricated CSVs only. They verify that:
- changing historical OHLCV changes the OHLCV fingerprint but not coverage,
- appending rows after the frozen cutoff does not change historical hashes,
- changing historical model-output rows changes the output fingerprint.

No network, Discord, Spreadsheet, TradingView, or production writes are used.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd

import reproducibility_manifest as manifest


def write_cache(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def write_output(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        cache = root / "tse_daily.csv"
        output = root / "picks.csv"

        base_rows = [
            {"date": "2026-08-28", "symbol": "1111", "open": 100.0, "high": 105.0, "low": 99.0, "close": 104.0, "volume": 10000},
            {"date": "2026-08-31", "symbol": "2222", "open": 200.0, "high": 202.0, "low": 195.0, "close": 198.0, "volume": 20000},
        ]
        write_cache(cache, base_rows)
        base_cache = manifest.cache_manifest(cache)

        revised_rows = [dict(r) for r in base_rows]
        revised_rows[0]["close"] = 103.5
        write_cache(cache, revised_rows)
        revised_cache = manifest.cache_manifest(cache)

        assert base_cache["historical_date_symbol_sha256"] == revised_cache["historical_date_symbol_sha256"], (
            "coverage hash changed after value-only revision"
        )
        assert base_cache["historical_ohlcv_sha256"] != revised_cache["historical_ohlcv_sha256"], (
            "OHLCV hash failed to detect historical value revision"
        )

        appended_rows = base_rows + [
            {"date": "2026-09-01", "symbol": "1111", "open": 104.0, "high": 106.0, "low": 103.0, "close": 105.0, "volume": 12000},
        ]
        write_cache(cache, appended_rows)
        appended_cache = manifest.cache_manifest(cache)
        assert base_cache["historical_date_symbol_sha256"] == appended_cache["historical_date_symbol_sha256"], (
            "future append changed historical coverage hash"
        )
        assert base_cache["historical_ohlcv_sha256"] == appended_cache["historical_ohlcv_sha256"], (
            "future append changed historical OHLCV hash"
        )

        base_picks = [
            {"date": "2026-08-31", "symbol": "1111", "target5_no": 0.05, "model_period": "2026-08"},
        ]
        write_output(output, base_picks)
        base_output = manifest.canonical_hash(output, manifest.CUTOFF)

        write_output(
            output,
            base_picks + [
                {"date": "2026-09-01", "symbol": "2222", "target5_no": -0.02, "model_period": "2026-09"},
            ],
        )
        appended_output = manifest.canonical_hash(output, manifest.CUTOFF)
        assert base_output["historical_sha256"] == appended_output["historical_sha256"], (
            "future output append changed historical output hash"
        )

        revised_picks = [dict(base_picks[0])]
        revised_picks[0]["target5_no"] = 0.04
        write_output(output, revised_picks)
        revised_output = manifest.canonical_hash(output, manifest.CUTOFF)
        assert base_output["historical_sha256"] != revised_output["historical_sha256"], (
            "historical output revision was not detected"
        )

    print("reproducibility manifest self-test: PASS")


if __name__ == "__main__":
    main()
