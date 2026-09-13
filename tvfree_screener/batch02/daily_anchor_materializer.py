"""Deterministic daily-anchor reconstruction materializer for TV-free research.

This module separates two concepts that must never be conflated:
1) post-close reconstruction quality; and
2) causal eligibility at a feature cutoff.

Raw hourly rows are immutable. Repaired rows are emitted as copies with
explicit tags. A daily fallback is emitted as ONE daily-resolution row only;
it is never duplicated into pseudo AM/PM or pseudo-4H bars.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from statistics import median
from typing import Iterable, Mapping
from zoneinfo import ZoneInfo

XTKS_TZ = ZoneInfo("Asia/Tokyo")
EXPECTED_HOURS = (9, 10, 11, 12, 13, 14, 15)
SCALE_SPREAD_TOL = 0.02
VOLUME_FACTOR_MIN = 0.5
VOLUME_FACTOR_MAX = 2.0


@dataclass(frozen=True)
class MaterializedSession:
    rows: tuple[dict[str, object], ...]
    reconstruction_tier: str
    causal_signal_eligibility: str
    complete_coverage: bool
    scale_applied: bool
    scale_factor: float | None
    volume_reconciled: bool
    volume_factor: float | None
    source_tags: tuple[str, ...]
    diagnostics: dict[str, object]


def _number(value: object) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _timestamp(value: object) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=XTKS_TZ)
    return dt.astimezone(XTKS_TZ)


def _valid_ohlc(row: Mapping[str, object]) -> bool:
    vals = [_number(row.get(k)) for k in ("open", "high", "low", "close")]
    if any(v is None for v in vals):
        return False
    op, hi, lo, cl = vals
    return op > 0 and hi >= max(op, cl) and lo <= min(op, cl) and hi >= lo


def _valid_daily(row: Mapping[str, object] | None) -> bool:
    if row is None or not _valid_ohlc(row):
        return False
    vol = _number(row.get("volume"))
    return vol is not None and vol >= 0


def _is_snapshot(row: Mapping[str, object]) -> bool:
    try:
        return int(float(row.get("is_closing_snapshot", 0))) == 1
    except (TypeError, ValueError):
        return False


def _hourly_by_required_hour(
    rows: Iterable[Mapping[str, object]],
) -> tuple[list[dict[str, object]], bool, str]:
    by_hour: dict[int, list[dict[str, object]]] = {}
    for raw in rows:
        if _is_snapshot(raw):
            continue
        try:
            stamp = _timestamp(raw.get("timestamp"))
        except (TypeError, ValueError):
            continue
        if stamp.minute or stamp.second or stamp.hour not in EXPECTED_HOURS:
            continue
        row = dict(raw)
        row["_timestamp_jst"] = stamp
        by_hour.setdefault(stamp.hour, []).append(row)

    selected: list[dict[str, object]] = []
    for hour in EXPECTED_HOURS:
        candidates = by_hour.get(hour, [])
        if len(candidates) != 1:
            return [], False, (
                "MISSING_REQUIRED_HOUR" if not candidates else "DUPLICATE_REQUIRED_HOUR"
            )
        row = candidates[0]
        if not _valid_ohlc(row) or (_number(row.get("volume")) is None):
            return [], False, "INVALID_REQUIRED_BAR"
        selected.append(row)
    selected.sort(key=lambda r: r["_timestamp_jst"])
    return selected, True, "COMPLETE"


def _aggregate(rows: list[dict[str, object]]) -> dict[str, float]:
    return {
        "open": float(rows[0]["open"]),
        "high": max(float(r["high"]) for r in rows),
        "low": min(float(r["low"]) for r in rows),
        "close": float(rows[-1]["close"]),
        "volume": sum(float(r["volume"]) for r in rows),
    }


def _scale_diagnostic(
    hourly_agg: Mapping[str, float],
    daily: Mapping[str, object],
) -> tuple[bool, float | None, float | None]:
    ratios: list[float] = []
    for key in ("open", "high", "low", "close"):
        hv = _number(hourly_agg.get(key))
        dv = _number(daily.get(key))
        if hv is None or dv is None or hv <= 0 or dv <= 0:
            return False, None, None
        ratios.append(dv / hv)
    factor = median(ratios)
    if factor <= 0:
        return False, None, None
    normalized_spread = max(abs(r / factor - 1.0) for r in ratios)
    return normalized_spread <= SCALE_SPREAD_TOL, factor, normalized_spread


def _copy_public(row: Mapping[str, object]) -> dict[str, object]:
    return {k: v for k, v in row.items() if not str(k).startswith("_")}


def _apply_scale(rows: list[dict[str, object]], factor: float) -> None:
    for row in rows:
        for key in ("open", "high", "low", "close"):
            row[key] = float(row[key]) * factor


def _anchor_endpoints(rows: list[dict[str, object]], daily: Mapping[str, object]) -> None:
    rows[0]["open"] = float(daily["open"])
    rows[-1]["close"] = float(daily["close"])
    rows[0]["high"] = max(float(rows[0]["high"]), float(rows[0]["open"]), float(rows[0]["close"]))
    rows[0]["low"] = min(float(rows[0]["low"]), float(rows[0]["open"]), float(rows[0]["close"]))
    rows[-1]["high"] = max(float(rows[-1]["high"]), float(rows[-1]["open"]), float(rows[-1]["close"]))
    rows[-1]["low"] = min(float(rows[-1]["low"]), float(rows[-1]["open"]), float(rows[-1]["close"]))


def _anchor_extrema(rows: list[dict[str, object]], daily: Mapping[str, object]) -> None:
    daily_high = float(daily["high"])
    daily_low = float(daily["low"])
    high_i = max(range(len(rows)), key=lambda i: float(rows[i]["high"]))
    low_i = min(range(len(rows)), key=lambda i: float(rows[i]["low"]))
    for row in rows:
        op, cl = float(row["open"]), float(row["close"])
        row["high"] = max(op, cl, min(float(row["high"]), daily_high))
        row["low"] = min(op, cl, max(float(row["low"]), daily_low))
    rows[high_i]["high"] = daily_high
    rows[low_i]["low"] = daily_low


def _volume_factor(
    rows: list[dict[str, object]], daily: Mapping[str, object]
) -> tuple[bool, float | None]:
    hv = sum(float(r["volume"]) for r in rows)
    dv = float(daily["volume"])
    if hv <= 0 or dv < 0:
        return False, None
    factor = dv / hv
    return VOLUME_FACTOR_MIN <= factor <= VOLUME_FACTOR_MAX, factor


def _reconcile_volume(rows: list[dict[str, object]], factor: float) -> None:
    for row in rows:
        row["volume"] = float(row["volume"]) * factor


def _daily_fallback(daily: Mapping[str, object]) -> dict[str, object]:
    row = {
        "resolution": "1D",
        "open": float(daily["open"]),
        "high": float(daily["high"]),
        "low": float(daily["low"]),
        "close": float(daily["close"]),
        "volume": float(daily["volume"]),
        "source_tag": "C_DAILY_RESOLUTION_FALLBACK",
        "causal_use": "DAILY_ONLY_AFTER_FINAL_AVAILABLE",
    }
    for key in ("date", "session_date", "symbol"):
        if key in daily:
            row[key] = daily[key]
    return row


def materialize_session(
    hourly_rows: Iterable[Mapping[str, object]],
    daily_row: Mapping[str, object] | None,
    *,
    feature_cutoff_jst: datetime | None = None,
    daily_final_available_at_jst: datetime | None = None,
) -> MaterializedSession:
    """Materialize one symbol-session without mutating raw rows."""
    hourly = list(hourly_rows)
    selected, complete, coverage_status = _hourly_by_required_hour(hourly)
    valid_daily = _valid_daily(daily_row)

    if not complete or not valid_daily:
        if valid_daily:
            fallback = _daily_fallback(daily_row)
            return MaterializedSession(
                rows=(fallback,),
                reconstruction_tier="C_DAILY_RESOLUTION_FALLBACK",
                causal_signal_eligibility="DAILY_ONLY_AFTER_FINAL_AVAILABLE",
                complete_coverage=complete,
                scale_applied=False,
                scale_factor=None,
                volume_reconciled=False,
                volume_factor=None,
                source_tags=("C_DAILY_RESOLUTION_FALLBACK",),
                diagnostics={"coverage_status": coverage_status, "valid_daily": True},
            )
        return MaterializedSession(
            rows=(),
            reconstruction_tier="D_UNUSABLE",
            causal_signal_eligibility="UNUSABLE",
            complete_coverage=complete,
            scale_applied=False,
            scale_factor=None,
            volume_reconciled=False,
            volume_factor=None,
            source_tags=("D_UNUSABLE",),
            diagnostics={"coverage_status": coverage_status, "valid_daily": False},
        )

    assert daily_row is not None
    raw_agg = _aggregate(selected)
    scale_ok, scale_factor, scale_spread = _scale_diagnostic(raw_agg, daily_row)

    if not scale_ok or scale_factor is None:
        fallback = _daily_fallback(daily_row)
        return MaterializedSession(
            rows=(fallback,),
            reconstruction_tier="C_DAILY_RESOLUTION_FALLBACK",
            causal_signal_eligibility="DAILY_ONLY_AFTER_FINAL_AVAILABLE",
            complete_coverage=True,
            scale_applied=False,
            scale_factor=scale_factor,
            volume_reconciled=False,
            volume_factor=None,
            source_tags=("SCALE_INCONSISTENT", "C_DAILY_RESOLUTION_FALLBACK"),
            diagnostics={
                "coverage_status": coverage_status,
                "valid_daily": True,
                "scale_normalized_spread": scale_spread,
            },
        )

    repaired = [_copy_public(r) for r in selected]
    _apply_scale(repaired, scale_factor)
    _anchor_endpoints(repaired, daily_row)
    _anchor_extrema(repaired, daily_row)
    volume_ok, volume_factor = _volume_factor(repaired, daily_row)
    if volume_ok and volume_factor is not None:
        _reconcile_volume(repaired, volume_factor)

    postclose_daily_is_causal = (
        feature_cutoff_jst is not None
        and daily_final_available_at_jst is not None
        and feature_cutoff_jst.astimezone(XTKS_TZ)
        >= daily_final_available_at_jst.astimezone(XTKS_TZ)
    )
    causal_status = "POSTCLOSE_CAUSAL_OK" if postclose_daily_is_causal else "POSTCLOSE_RECON_ONLY"
    tier = "A_FULL_RECON_POSTCLOSE" if volume_ok else "B_PRICE_RECON_POSTCLOSE"
    tags = [
        "COMMON_OHLC_SCALE",
        "DAILY_OPEN_CLOSE_ANCHOR",
        "DAILY_EXTREMA_ANCHOR",
        tier,
        causal_status,
    ]
    if volume_ok:
        tags.append("DAILY_VOLUME_PROPORTIONAL_RECON")
    else:
        tags.append("VOLUME_UNTRUSTED")

    for row in repaired:
        row["resolution"] = "1H"
        row["reconstruction_tier"] = tier
        row["causal_signal_eligibility"] = causal_status
        row["scale_factor"] = scale_factor
        row["volume_factor"] = volume_factor if volume_ok else None
        row["source_tag"] = "|".join(tags)

    return MaterializedSession(
        rows=tuple(repaired),
        reconstruction_tier=tier,
        causal_signal_eligibility=causal_status,
        complete_coverage=True,
        scale_applied=True,
        scale_factor=scale_factor,
        volume_reconciled=volume_ok,
        volume_factor=volume_factor,
        source_tags=tuple(tags),
        diagnostics={
            "coverage_status": coverage_status,
            "valid_daily": True,
            "scale_normalized_spread": scale_spread,
            "raw_aggregate": raw_agg,
        },
    )
