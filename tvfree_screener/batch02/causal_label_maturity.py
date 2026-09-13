"""Causal maturity rules for retrospective train/validation splits.

A training row may only be used by a model evaluated from validation_start if
its target label was fully observable before validation_start.  Signal-date
splits alone are insufficient for multi-session forward labels.
"""
from __future__ import annotations

from datetime import date


def mature_before_validation(*, exit_date: str | date, validation_start: str | date) -> bool:
    """Return True only when the target exit precedes validation_start.

    Equality is intentionally rejected: a close-based endpoint on the first
    validation session is not known before that session begins.
    """
    exit_day = date.fromisoformat(exit_date) if isinstance(exit_date, str) else exit_date
    start_day = date.fromisoformat(validation_start) if isinstance(validation_start, str) else validation_start
    return exit_day < start_day


def causal_training_row(
    *,
    signal_date: str | date,
    exit_date: str | date,
    train_start: str | date,
    train_end: str | date,
    validation_start: str | date,
) -> bool:
    """Frozen V2 training eligibility independent of strategy outcome value."""
    signal_day = date.fromisoformat(signal_date) if isinstance(signal_date, str) else signal_date
    start_day = date.fromisoformat(train_start) if isinstance(train_start, str) else train_start
    end_day = date.fromisoformat(train_end) if isinstance(train_end, str) else train_end
    return start_day <= signal_day <= end_day and mature_before_validation(
        exit_date=exit_date,
        validation_start=validation_start,
    )
