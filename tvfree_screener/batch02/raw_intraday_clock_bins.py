"""Deterministic raw-hourly clock-bin builder for TV-free research."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
import math
from typing import Iterable, Mapping
from zoneinfo import ZoneInfo

XTKS_TZ = ZoneInfo("Asia/Tokyo")


@dataclass(frozen=True)
class ClockBin:
    session_date: date
    symbol: str
    bin_name: str
    source_tag: str
    feature_cutoff_jst: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    row_count: int


BIN_HOURS = {
    "AM_09_13": (9, 10, 11, 12),
    "PM_13_CLOSE": (13, 14, 15),
}


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _timestamp(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=XTKS_TZ)
    return parsed.astimezone(XTKS_TZ)


def _symbol(value: object) -> str:
    text = str(value or "").strip().upper()
    if ":" in text:
        text = text.rsplit(":", 1)[1]
    if text.endswith(".T"):
        text = text[:-2]
    return text


def _is_snapshot(row: Mapping[str, object]) -> bool:
    raw = row.get("is_closing_snapshot", 0)
    try:
        return int(float(raw)) == 1
    except (TypeError, ValueError):
        return False


def _valid_bar(row: Mapping[str, object]) -> bool:
    values = [_number(row.get(key)) for key in ("open", "high", "low", "close", "volume")]
    if any(value is None for value in values):
        return False
    op, high, low, close, volume = values
    return (
        op > 0
        and high >= max(op, close)
        and low <= min(op, close)
        and high >= low
        and volume >= 0
    )


def _cutoff(day: date, bin_name: str) -> datetime:
    # Raw source timestamps are interval starts. The AM 12:00 bar completes at
    # 13:00. The PM 15:00 bar is conservatively treated as unavailable until
    # 16:00 until provider publication latency is verified.
    cutoff = time(13, 0) if bin_name == "AM_09_13" else time(16, 0)
    return datetime.combine(day, cutoff, tzinfo=XTKS_TZ)


def build_clock_bins(
    rows: Iterable[Mapping[str, object]],
) -> tuple[list[ClockBin], list[dict[str, object]]]:
    groups: dict[tuple[date, str], list[tuple[datetime, Mapping[str, object]]]] = {}
    for row in rows:
        if _is_snapshot(row):
            continue
        try:
            stamp = _timestamp(row.get("timestamp"))
        except (TypeError, ValueError):
            continue
        symbol = _symbol(row.get("symbol"))
        if not symbol:
            continue
        groups.setdefault((stamp.date(), symbol), []).append((stamp, row))

    bins: list[ClockBin] = []
    diagnostics: list[dict[str, object]] = []
    for (day, symbol), items in sorted(groups.items()):
        by_hour: dict[int, list[tuple[datetime, Mapping[str, object]]]] = {}
        for stamp, row in items:
            if stamp.minute == 0 and stamp.second == 0:
                by_hour.setdefault(stamp.hour, []).append((stamp, row))

        for bin_name, hours in BIN_HOURS.items():
            selected: list[tuple[datetime, Mapping[str, object]]] = []
            status = "COMPLETE"
            for hour in hours:
                candidates = by_hour.get(hour, [])
                if len(candidates) == 0:
                    status = "MISSING_REQUIRED_HOUR"
                    break
                if len(candidates) > 1:
                    status = "DUPLICATE_REQUIRED_HOUR"
                    break
                if not _valid_bar(candidates[0][1]):
                    status = "INVALID_REQUIRED_BAR"
                    break
                selected.append(candidates[0])

            diagnostics.append({
                "session_date": day.isoformat(),
                "symbol": symbol,
                "bin_name": bin_name,
                "status": status,
                "required_hours": list(hours),
                "feature_cutoff_jst": _cutoff(day, bin_name).isoformat(),
            })
            if status != "COMPLETE":
                continue

            selected.sort(key=lambda item: item[0])
            first, last = selected[0][1], selected[-1][1]
            bins.append(ClockBin(
                session_date=day,
                symbol=symbol,
                bin_name=bin_name,
                source_tag="RAW_CAUSAL_INTRADAY",
                feature_cutoff_jst=_cutoff(day, bin_name),
                open=float(first["open"]),
                high=max(float(row["high"]) for _, row in selected),
                low=min(float(row["low"]) for _, row in selected),
                close=float(last["close"]),
                volume=sum(float(row["volume"]) for _, row in selected),
                row_count=len(selected),
            ))
    return bins, diagnostics
