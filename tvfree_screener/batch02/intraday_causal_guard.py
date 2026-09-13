"""Causal-eligibility guard for TV-free intraday research features.

This module deliberately does not repair prices. It answers only whether a
candidate input is allowed at a feature cutoff. Reconstruction quality and
signal-time causal eligibility are separate concerns.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Mapping
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


def classify_materialized_feature_input(row: Mapping[str, object]) -> CausalDecision:
    """Fail closed when a materialized data-quality row reaches a 4H feature boundary.

    The daily-anchor materializer emits explicit resolution and causal tags.
    This guard prevents callers from accidentally treating a post-close repair
    or a single daily fallback as a causal intraday/4H observation.
    """
    resolution = str(row.get("resolution", "")).strip().upper()
    status = str(row.get("causal_signal_eligibility", row.get("causal_use", ""))).strip().upper()
    source = str(row.get("source_tag", "")).strip().upper()

    if resolution == "1D" or "C_DAILY_RESOLUTION_FALLBACK" in source:
        return CausalDecision(False, "DAILY_RESOLUTION_NOT_INTRADAY")
    if status == "POSTCLOSE_RECON_ONLY" or "POSTCLOSE_RECON_ONLY" in source:
        return CausalDecision(False, "POSTCLOSE_RECON_NOT_CAUSAL_FOR_INTRADAY")
    if status == "DAILY_ONLY_AFTER_FINAL_AVAILABLE":
        return CausalDecision(False, "DAILY_RESOLUTION_NOT_INTRADAY")
    if status in {"POSTCLOSE_CAUSAL_OK", "RAW_CAUSAL_INTRADAY"}:
        return CausalDecision(True, status)
    if "RAW_CAUSAL_INTRADAY" in source:
        return CausalDecision(True, "RAW_CAUSAL_INTRADAY")
    return CausalDecision(False, "UNKNOWN_CAUSAL_MATERIALIZATION_STATUS")
