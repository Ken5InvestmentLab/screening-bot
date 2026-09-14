"""Immutable provenance receipt for completed Optuna trials.

Research-only helper.  The receipt is deliberately outcome-agnostic beyond the
already-produced Optuna trial diagnostics: it does not select a family, change
thresholds, or authorize promotion.  Its purpose is to make PSR/DSR consume the
exact completed-trial population from a frozen study instead of an ad-hoc
Sharpe vector.
"""

from __future__ import annotations

import hashlib
import json
from typing import Iterable, Mapping, Sequence

import numpy as np

LEDGER_SCHEMA = "tvfree.optuna.completed-trials.v1"
_HASH_ALGO = "sha256"


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_json(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _finite_float(value: object, *, name: str) -> float:
    number = float(value)
    if not np.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def build_completed_trial_ledger(
    completed_trials: Iterable[object],
    *,
    study_name: str,
    sampler: str,
    seed: int,
    n_trials_requested: int,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Create a deterministic ledger and receipt from COMPLETE Optuna trials.

    ``completed_trials`` may contain only COMPLETE trials.  Trial numbers are
    sorted for canonical construction; duplicates, missing required fields, or
    non-finite objective/Sharpe values fail closed.
    """
    rows: list[dict[str, object]] = []
    seen_numbers: set[int] = set()

    for trial in completed_trials:
        state_name = str(getattr(getattr(trial, "state", None), "name", ""))
        if state_name != "COMPLETE":
            raise ValueError("completed-trial ledger received a non-COMPLETE trial")
        number = int(getattr(trial, "number"))
        if number in seen_numbers:
            raise ValueError(f"duplicate Optuna trial number: {number}")
        seen_numbers.add(number)

        params = dict(getattr(trial, "params", {}))
        attrs = dict(getattr(trial, "user_attrs", {}))
        if "C" not in params:
            raise ValueError(f"trial {number} is missing frozen parameter C")
        if "sharpe_per_active_day" not in attrs:
            raise ValueError(f"trial {number} is missing sharpe_per_active_day")

        objective = _finite_float(getattr(trial, "value"), name=f"trial {number} objective")
        sharpe = _finite_float(
            attrs["sharpe_per_active_day"], name=f"trial {number} sharpe_per_active_day"
        )
        c_value = _finite_float(params["C"], name=f"trial {number} C")

        row: dict[str, object] = {
            "trial": number,
            "state": "COMPLETE",
            "objective_sharpe": objective,
            "C": c_value,
            "sharpe_per_active_day": sharpe,
        }
        # These are diagnostics already produced inside the frozen objective.
        # Including them in the hash catches silent post-run mutation without
        # adding any new strategy-selection inputs.
        for key in (
            "active_days",
            "mean",
            "median",
            "win_rate",
            "minus10_rate",
            "plus20_rate",
            "top3_removed_mean",
        ):
            if key in attrs and attrs[key] is not None:
                value = attrs[key]
                if key == "active_days":
                    row[key] = int(value)
                else:
                    row[key] = _finite_float(value, name=f"trial {number} {key}")
        rows.append(row)

    rows.sort(key=lambda row: int(row["trial"]))
    if len(rows) < 2:
        raise ValueError("completed-trial ledger requires at least two trials")

    trial_numbers = [int(row["trial"]) for row in rows]
    payload = {
        "schema": LEDGER_SCHEMA,
        "study_name": str(study_name),
        "sampler": str(sampler),
        "seed": int(seed),
        "n_trials_requested": int(n_trials_requested),
        "completed_trial_count": len(rows),
        "completed_trial_numbers": trial_numbers,
        "rows": rows,
    }
    receipt = {
        "schema": LEDGER_SCHEMA,
        "hash_algorithm": _HASH_ALGO,
        "study_name": str(study_name),
        "sampler": str(sampler),
        "seed": int(seed),
        "n_trials_requested": int(n_trials_requested),
        "completed_trial_count": len(rows),
        "completed_trial_numbers": trial_numbers,
        "ledger_sha256": _sha256_json(payload),
    }
    return rows, receipt


def validate_completed_trial_ledger(
    rows: Sequence[Mapping[str, object]],
    receipt: Mapping[str, object],
) -> None:
    """Fail closed on missing/extra/reordered/modified ledger rows or metadata."""
    if receipt.get("schema") != LEDGER_SCHEMA:
        raise ValueError("unsupported completed-trial ledger schema")
    if receipt.get("hash_algorithm") != _HASH_ALGO:
        raise ValueError("unsupported completed-trial ledger hash algorithm")

    canonical_rows = [dict(row) for row in rows]
    numbers = [int(row.get("trial")) for row in canonical_rows]
    if numbers != sorted(numbers):
        raise ValueError("completed-trial ledger rows are reordered")
    if len(numbers) != len(set(numbers)):
        raise ValueError("completed-trial ledger has duplicate trial numbers")
    if int(receipt.get("completed_trial_count", -1)) != len(canonical_rows):
        raise ValueError("completed-trial ledger count does not match receipt")
    receipt_numbers = [int(x) for x in receipt.get("completed_trial_numbers", [])]
    if receipt_numbers != numbers:
        raise ValueError("completed-trial ledger trial-number set/order does not match receipt")

    for row in canonical_rows:
        if row.get("state") != "COMPLETE":
            raise ValueError("completed-trial ledger contains non-COMPLETE state")
        _finite_float(row.get("objective_sharpe"), name="objective_sharpe")
        _finite_float(row.get("C"), name="C")
        _finite_float(row.get("sharpe_per_active_day"), name="sharpe_per_active_day")

    payload = {
        "schema": LEDGER_SCHEMA,
        "study_name": str(receipt.get("study_name")),
        "sampler": str(receipt.get("sampler")),
        "seed": int(receipt.get("seed")),
        "n_trials_requested": int(receipt.get("n_trials_requested")),
        "completed_trial_count": len(canonical_rows),
        "completed_trial_numbers": numbers,
        "rows": canonical_rows,
    }
    actual = _sha256_json(payload)
    if actual != receipt.get("ledger_sha256"):
        raise ValueError("completed-trial ledger hash mismatch")


def trial_sharpes_from_receipt(
    rows: Sequence[Mapping[str, object]],
    receipt: Mapping[str, object],
) -> list[float]:
    """Return the DSR trial-Sharpe vector only after receipt verification."""
    validate_completed_trial_ledger(rows, receipt)
    return [float(row["sharpe_per_active_day"]) for row in rows]
