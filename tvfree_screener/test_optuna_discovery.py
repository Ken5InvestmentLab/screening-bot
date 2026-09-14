from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tvfree_screener.optuna_discovery import run_study, validate_discovery_frame


def _synthetic_panel() -> pd.DataFrame:
    rng = np.random.default_rng(20260914)
    days = pd.bdate_range("2022-07-01", periods=110)
    rows = []
    for day in days:
        for symbol_index in range(4):
            f1 = rng.normal()
            f2 = rng.normal()
            noise = rng.normal(scale=0.025)
            ret = 0.018 * f1 - 0.006 * f2 + noise
            rows.append(
                {
                    "date": day,
                    "exit_date": day + pd.offsets.BDay(5),
                    "symbol": f"{1000 + symbol_index}",
                    "f1": f1,
                    "f2": f2,
                    "endpoint_gross_return": ret,
                    "endpoint_label_resolved": True,
                }
            )
    return pd.DataFrame(rows)


def test_optuna_discovery_runs_only_on_locked_discovery_period() -> None:
    panel = _synthetic_panel()
    summary, trials = run_study(
        panel,
        feature_columns=["f1", "f2"],
        n_splits=3,
        test_dates=15,
        n_trials=8,
        top_n=1,
        round_trip_cost=0.001,
    )

    assert summary["status"] == "DISCOVERY_ONLY_NOT_PROMOTED"
    assert summary["guardrails"]["uses_2024_for_selection"] is False
    assert summary["guardrails"]["promotion_authorized"] is False
    assert summary["search"]["only_optimized_parameter"] == "C"
    assert summary["search"]["n_trials_completed"] >= 2
    assert len(trials) == 8
    assert summary["best_trial"]["C"] > 0
    assert all(row["temporal_leakage_free"] for row in summary["walk_forward"]["audit"])


def test_optuna_discovery_rejects_2024_candidate_or_label() -> None:
    panel = _synthetic_panel()

    bad_candidate = panel.copy()
    bad_candidate.loc[0, "date"] = pd.Timestamp("2024-01-05")
    with pytest.raises(ValueError, match="candidate dates"):
        validate_discovery_frame(
            bad_candidate,
            feature_columns=["f1", "f2"],
        )

    bad_label = panel.copy()
    bad_label.loc[0, "exit_date"] = pd.Timestamp("2024-01-05")
    with pytest.raises(ValueError, match="labels must resolve"):
        validate_discovery_frame(
            bad_label,
            feature_columns=["f1", "f2"],
        )


def test_optuna_discovery_rejects_unresolved_rows() -> None:
    panel = _synthetic_panel()
    panel.loc[0, "endpoint_label_resolved"] = False
    with pytest.raises(ValueError, match="unresolved endpoint"):
        validate_discovery_frame(
            panel,
            feature_columns=["f1", "f2"],
        )
