#!/usr/bin/env python3
"""Synthetic self-checks for the test-only reproducibility manifest.

These checks use tiny fabricated CSVs only. They verify that:
- changing historical OHLCV changes the OHLCV fingerprint but not coverage,
- appending rows after the frozen cutoff does not change historical hashes,
- maturing forward entry/outcome labels does not change a frozen selection hash,
- changing a signal-time model score or historical selection does change it.

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
            {
                "date": "2026-08-28", "symbol": "1111", "core_score": 0.75,
                "target5_no": float("nan"), "target10_no": float("nan"),
                "target10_end": float("nan"), "next_open": float("nan"),
                "model_period": "2026-08",
            },
        ]
        write_output(output, base_picks)
        base_output = manifest.canonical_hash(output, manifest.CUTOFF)
        assert set(base_output["excluded_forward_columns"]) == {
            "target5_no", "target10_no", "target10_end", "next_open"
        }

        # Future rows after cutoff must not affect the frozen hash.
        write_output(
            output,
            base_picks + [
                {
                    "date": "2026-09-01", "symbol": "2222", "core_score": 0.10,
                    "target5_no": -0.02, "target10_no": 0.03,
                    "target10_end": "2026-09-15", "next_open": 200.0,
                    "model_period": "2026-09",
                },
            ],
        )
        appended_output = manifest.canonical_hash(output, manifest.CUTOFF)
        assert base_output["historical_sha256"] == appended_output["historical_sha256"], (
            "future output append changed historical selection hash"
        )

        # The same historical pick can acquire its entry/forward outcomes later.
        matured = [dict(base_picks[0])]
        matured[0].update({
            "target5_no": 0.04,
            "target10_no": -0.03,
            "target10_end": "2026-09-11",
            "next_open": 101.0,
        })
        write_output(output, matured)
        matured_output = manifest.canonical_hash(output, manifest.CUTOFF)
        assert base_output["historical_sha256"] == matured_output["historical_sha256"], (
            "forward-label maturation was falsely classified as model-selection drift"
        )

        # A signal-time/model-selection value must still be protected.
        revised_score = [dict(matured[0])]
        revised_score[0]["core_score"] = 0.74
        write_output(output, revised_score)
        revised_output = manifest.canonical_hash(output, manifest.CUTOFF)
        assert base_output["historical_sha256"] != revised_output["historical_sha256"], (
            "signal-time model score revision was not detected"
        )

        # A different selected symbol must also change the hash.
        revised_selection = [dict(matured[0])]
        revised_selection[0]["symbol"] = "9999"
        write_output(output, revised_selection)
        selection_output = manifest.canonical_hash(output, manifest.CUTOFF)
        assert base_output["historical_sha256"] != selection_output["historical_sha256"], (
            "historical selection revision was not detected"
        )

    print("reproducibility manifest self-test: PASS")


if __name__ == "__main__":
    main()
