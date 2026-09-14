from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from tvfree_screener.optuna_trial_ledger import (
    build_completed_trial_ledger,
    trial_sharpes_from_receipt,
    validate_completed_trial_ledger,
)


def _trial(number: int, *, sharpe: float, c_value: float):
    return SimpleNamespace(
        number=number,
        state=SimpleNamespace(name="COMPLETE"),
        value=sharpe,
        params={"C": c_value},
        user_attrs={
            "active_days": 30 + number,
            "mean": 0.01 + number * 0.001,
            "median": 0.005,
            "win_rate": 0.5,
            "minus10_rate": 0.0,
            "plus20_rate": 0.0,
            "top3_removed_mean": 0.004,
            "sharpe_per_active_day": sharpe,
        },
    )


def _ledger():
    return build_completed_trial_ledger(
        [_trial(2, sharpe=0.4, c_value=1.2), _trial(0, sharpe=0.2, c_value=0.3)],
        study_name="tvfree-discovery-only-logreg-c",
        sampler="Optuna TPESampler",
        seed=20260914,
        n_trials_requested=3,
    )


def test_completed_trial_ledger_is_deterministic_and_dsr_vector_is_receipt_bound() -> None:
    rows, receipt = _ledger()
    assert [row["trial"] for row in rows] == [0, 2]
    validate_completed_trial_ledger(rows, receipt)
    assert trial_sharpes_from_receipt(rows, receipt) == [0.2, 0.4]
    assert receipt["completed_trial_count"] == 2
    assert len(receipt["ledger_sha256"]) == 64


@pytest.mark.parametrize("mutation", ["missing", "extra", "reordered", "modified"])
def test_completed_trial_ledger_fails_closed_on_tampering(mutation: str) -> None:
    rows, receipt = _ledger()
    tampered = deepcopy(rows)
    if mutation == "missing":
        tampered.pop()
    elif mutation == "extra":
        extra = deepcopy(tampered[-1])
        extra["trial"] = 9
        tampered.append(extra)
    elif mutation == "reordered":
        tampered.reverse()
    else:
        tampered[0]["sharpe_per_active_day"] = 99.0

    with pytest.raises(ValueError):
        trial_sharpes_from_receipt(tampered, receipt)


def test_completed_trial_ledger_rejects_noncomplete_and_duplicate_trials() -> None:
    bad = _trial(0, sharpe=0.2, c_value=0.3)
    bad.state = SimpleNamespace(name="PRUNED")
    with pytest.raises(ValueError, match="non-COMPLETE"):
        build_completed_trial_ledger(
            [bad, _trial(1, sharpe=0.3, c_value=0.4)],
            study_name="x",
            sampler="y",
            seed=1,
            n_trials_requested=2,
        )

    with pytest.raises(ValueError, match="duplicate"):
        build_completed_trial_ledger(
            [_trial(0, sharpe=0.2, c_value=0.3), _trial(0, sharpe=0.3, c_value=0.4)],
            study_name="x",
            sampler="y",
            seed=1,
            n_trials_requested=2,
        )
