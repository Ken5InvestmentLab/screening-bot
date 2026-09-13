"""Causal-eligibility guard for TV-free intraday research features.

This module deliberately does not repair prices. It answers only whether a
candidate input is allowed at a feature cutoff. Reconstruction quality and
signal-time causal eligibility are separate concerns.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

XTKS_TZ = ZoneInfo("Asia/Tokyo")
CLOSE_EXTENSION_DATE = date(2024, 11, 5)


@dataclass(frozen=True)
class CausalDecision:
    eligible: bool
    status: str


def _jst(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=XTKS_TZ)
    return value.astimezone(XTKS_TZ)


def official_close(day: date) -> datetime:
    close = time(15, 0) if day < CLOSE_EXTENSION_DATE else time(15, 30)
    return datetime.combine(day, close, tzinfo=XTKS_TZ)


def classify_causal_use(
    *,
    observation_timestamp: datetime,
    feature_cutoff_timestamp: datetime,
    uses_final_daily_anchor: bool = False,
    anchor_session_date: date | None = None,
    daily_available_at: datetime | None = None,
) -> CausalDecision:
    """Return whether an input may feed a feature at the requested cutoff.

    A same-session finalized daily anchor is not assumed available merely
    because the exchange has closed. Its provider-availability timestamp must
    be explicitly known and no later than the feature cutoff.
    """
    obs = _jst(observation_timestamp)
    cutoff = _jst(feature_cutoff_timestamp)
    if obs > cutoff:
        return CausalDecision(False, "OBSERVATION_AFTER_FEATURE_CUTOFF")

    if not uses_final_daily_anchor:
        return CausalDecision(True, "RAW_CAUSAL_INTRADAY")

    anchor_day = anchor_session_date or obs.date()
    if anchor_day > cutoff.date():
        return CausalDecision(False, "DAILY_ANCHOR_FROM_FUTURE_SESSION")

    if anchor_day < cutoff.date():
        return CausalDecision(True, "PRIOR_COMPLETED_SESSION_DAILY_ANCHOR")

    if daily_available_at is None:
        return CausalDecision(False, "SAME_SESSION_FINAL_DAILY_AVAILABILITY_UNKNOWN")

    available = _jst(daily_available_at)
    if available > cutoff:
        return CausalDecision(False, "SAME_SESSION_FINAL_DAILY_AFTER_FEATURE_CUTOFF")

    if available < official_close(anchor_day):
        return CausalDecision(False, "INVALID_DAILY_AVAILABILITY_BEFORE_OFFICIAL_CLOSE")

    return CausalDecision(True, "SAME_SESSION_FINAL_DAILY_AVAILABLE_BY_CUTOFF")
