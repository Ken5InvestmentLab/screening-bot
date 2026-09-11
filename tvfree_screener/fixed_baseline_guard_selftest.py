#!/usr/bin/env python3
"""Synthetic checks for fixed-baseline reproducibility guard."""
from __future__ import annotations

import fixed_baseline_guard as g


def baseline() -> dict:
    return {
        "hashes": {
            "universe_sha256": "u",
            "historical_date_symbol_sha256": "c",
            "historical_ohlcv_sha256": "o",
            "v3_short_reconstruction_core.csv": "s",
            "v3_short_reconstruction_defensive.csv": "d",
            "v3_swing_v2_s_picks.csv": "w",
        }
    }


def manifest(universe="u", coverage="c", ohlcv="o", short="s", defensive="d", swing="w") -> dict:
    return {
        "universe": {"sha256": universe},
        "cache": {
            "historical_date_symbol_sha256": coverage,
            "historical_ohlcv_sha256": ohlcv,
        },
        "outputs": {
            "v3_short_reconstruction_core.csv": {"historical_sha256": short},
            "v3_short_reconstruction_defensive.csv": {"historical_sha256": defensive},
            "v3_swing_v2_s_picks.csv": {"historical_sha256": swing},
        },
    }


def main() -> None:
    exact = g.evaluate(baseline(), manifest())
    assert exact["status"] == "exact_baseline_reproduced"
    assert exact["exact_input_comparable"]
    assert exact["frozen_v3_outputs_match"]

    bad_model = g.evaluate(baseline(), manifest(short="changed"))
    assert bad_model["status"] == "ERROR_model_output_changed_with_identical_inputs"
    assert bad_model["exact_input_comparable"]
    assert not bad_model["frozen_v3_outputs_match"]

    source_drift = g.evaluate(baseline(), manifest(ohlcv="revised", short="changed"))
    assert source_drift["status"] == "source_or_universe_drift_not_exactly_comparable"
    assert not source_drift["exact_input_comparable"]

    universe_drift = g.evaluate(baseline(), manifest(universe="new"))
    assert universe_drift["status"] == "source_or_universe_drift_not_exactly_comparable"

    print("fixed_baseline_guard_selftest: OK")


if __name__ == "__main__":
    main()
