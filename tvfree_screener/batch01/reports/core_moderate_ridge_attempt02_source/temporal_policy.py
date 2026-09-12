"""Fail-closed research-period access and purge rules."""
from __future__ import annotations

from collections.abc import Sequence

import pandas as pd


DISCOVERY_START = pd.Timestamp("2022-07-01")
DISCOVERY_END = pd.Timestamp("2023-12-31")
LOCKED_VALIDATION_START = pd.Timestamp("2024-01-01")
LOCKED_REPLAY_START = pd.Timestamp("2025-01-01")
REPORT_ONLY_START = pd.Timestamp("2026-01-01")
FROZEN_TRAINING_CUTOFF = pd.Timestamp("2025-12-31")

MODEL_SELECTION_INTENTS = {"select_candidate", "select_features", "select_policy", "tune_threshold"}


def validate_period_access(
    *,
    intent: str,
    start: object,
    end: object,
    spec_sha256: str,
    frozen_spec_sha256: str | None = None,
    spec_frozen_at: object | None = None,
    phase_opened_at: object | None = None,
    model_fit_through: object | None = None,
) -> dict[str, str]:
    """Authorize use of date ranges without letting later data select a model."""
    first = pd.Timestamp(start).normalize()
    last = pd.Timestamp(end).normalize()
    if first > last:
        raise ValueError("period start must not be after its end")
    if not spec_sha256:
        raise ValueError("spec hash is required for every period access")

    if intent in MODEL_SELECTION_INTENTS:
        if first < DISCOVERY_START or last > DISCOVERY_END:
            raise ValueError("model or policy selection is limited to 2022H2-2023 discovery")
        return {"intent": intent, "access": "DISCOVERY_SELECTION", "spec_sha256": spec_sha256}

    if intent == "locked_validation":
        if first < LOCKED_VALIDATION_START:
            raise ValueError("locked validation begins in 2024")
        if frozen_spec_sha256 != spec_sha256:
            raise ValueError("validation spec does not match the frozen discovery spec hash")
        _require_lock_before_phase_open(spec_frozen_at, phase_opened_at)
        return {"intent": intent, "access": "LOCKED_CONFIRMATION", "spec_sha256": spec_sha256}

    if intent == "replay_2025":
        if first < LOCKED_REPLAY_START or last > pd.Timestamp("2025-12-31"):
            raise ValueError("locked replay is limited to calendar year 2025")
        if frozen_spec_sha256 != spec_sha256:
            raise ValueError("2025 replay spec differs from the frozen discovery spec")
        _require_lock_before_phase_open(spec_frozen_at, phase_opened_at)
        return {"intent": intent, "access": "LOCKED_HISTORICAL_REPLAY", "spec_sha256": spec_sha256}

    if intent == "report_2026":
        if first < REPORT_ONLY_START:
            raise ValueError("2026 is reserved for frozen-candidate reporting")
        if frozen_spec_sha256 != spec_sha256:
            raise ValueError("2026 report spec differs from the frozen candidate")
        _require_lock_before_phase_open(spec_frozen_at, phase_opened_at)
        if model_fit_through is None or pd.Timestamp(model_fit_through).normalize() > FROZEN_TRAINING_CUTOFF:
            raise ValueError("2026 coefficients or transforms use labels later than 2025-12-31")
        return {"intent": intent, "access": "REPORT_ONLY_FROZEN", "spec_sha256": spec_sha256}

    raise ValueError(f"unknown temporal access intent: {intent}")


def _require_lock_before_phase_open(spec_frozen_at: object | None, phase_opened_at: object | None) -> None:
    """Require an auditable in-run order without falsifying historical timestamps."""
    if spec_frozen_at is None or phase_opened_at is None:
        raise ValueError("actual spec-freeze and phase-open timestamps are required")
    frozen = pd.Timestamp(spec_frozen_at)
    opened = pd.Timestamp(phase_opened_at)
    if frozen.tz != opened.tz:
        raise ValueError("spec-freeze and phase-open timestamps must use the same timezone")
    if frozen >= opened:
        raise ValueError("spec must be frozen before the phase is opened")


def purge_training_rows(
    labels: pd.DataFrame,
    *,
    prediction_timestamp: object,
    availability_column: str = "label_available_at",
) -> pd.DataFrame:
    """Keep only labels available strictly before a validation decision time."""
    if availability_column not in labels.columns:
        raise ValueError(f"missing point-in-time label availability column: {availability_column}")
    cutoff = pd.Timestamp(prediction_timestamp)
    availability = pd.to_datetime(labels[availability_column], errors="coerce")
    if availability.isna().any():
        raise ValueError("missing or invalid label availability must not enter model fitting")
    if (availability == availability.dt.normalize()).all() and cutoff == cutoff.normalize():
        # Date-only labels have no reliable intraday order; require the prior
        # business date rather than treating midnight as an earlier timestamp.
        eligible = availability.dt.normalize() < cutoff.normalize()
    else:
        if getattr(availability.dt, "tz", None) != cutoff.tz:
            raise ValueError("label and prediction timestamps must use the same timezone")
        eligible = availability < cutoff
    return labels.loc[eligible].copy()


def assert_report_only_dates(dates: Sequence[object]) -> None:
    if not dates:
        raise ValueError("report period is empty")
    normalized = pd.DatetimeIndex(pd.to_datetime(list(dates), errors="raise")).normalize()
    if (normalized < REPORT_ONLY_START).any():
        raise ValueError("2026 reporting helper cannot be used on discovery or validation dates")
