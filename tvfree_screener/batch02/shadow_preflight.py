from __future__ import annotations

from datetime import date, datetime, time, timezone, timedelta
from typing import Mapping

JST = timezone(timedelta(hours=9))
CHANGE_DATE = date(2024, 11, 5)
ALLOWED_BINS = {"AM_09_13", "PM_13_CLOSE"}
ALLOWED_SOURCE_TAG = "RAW_CAUSAL_INTRADAY"


def _parse_signal_date(value: object) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"invalid signal_date: {value!r}") from exc


def _parse_cutoff(value: object) -> datetime:
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"invalid feature_cutoff: {value!r}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("feature_cutoff must be timezone-aware")
    return dt.astimezone(JST)


def expected_bin_cutoff(signal_day: date, bin_name: str) -> datetime:
    if bin_name == "AM_09_13":
        cutoff = time(13, 0)
    elif bin_name == "PM_13_CLOSE":
        cutoff = time(15, 30) if signal_day >= CHANGE_DATE else time(15, 0)
    else:
        raise ValueError(f"unsupported bin_name: {bin_name}")
    return datetime.combine(signal_day, cutoff, tzinfo=JST)


def validate_shadow_export_row(row: Mapping) -> None:
    required = (
        "experiment_id",
        "model_freeze_id",
        "symbol",
        "signal_date",
        "bin_name",
        "feature_cutoff",
        "source_tag",
    )
    missing = [field for field in required if row.get(field) in (None, "")]
    if missing:
        raise ValueError(f"missing required fields: {','.join(missing)}")

    source_tag = str(row["source_tag"])
    if source_tag != ALLOWED_SOURCE_TAG:
        raise ValueError(f"noncausal/unapproved source_tag: {source_tag}")

    bin_name = str(row["bin_name"])
    if bin_name not in ALLOWED_BINS:
        raise ValueError(f"unsupported bin_name: {bin_name}")

    signal_day = _parse_signal_date(row["signal_date"])
    cutoff = _parse_cutoff(row["feature_cutoff"])
    if cutoff.date() != signal_day:
        raise ValueError(
            f"feature_cutoff date mismatch: signal_date={signal_day.isoformat()} cutoff={cutoff.isoformat()}"
        )

    expected = expected_bin_cutoff(signal_day, bin_name)
    if cutoff != expected:
        raise ValueError(
            f"unexpected feature_cutoff for {bin_name}: expected={expected.isoformat()} actual={cutoff.isoformat()}"
        )

    symbol = str(row["symbol"]).strip()
    if not symbol:
        raise ValueError("symbol is empty")

    rank = row.get("rank")
    if rank not in (None, ""):
        try:
            rank_i = int(rank)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid rank: {rank!r}") from exc
        if rank_i < 1:
            raise ValueError(f"rank must be >= 1: {rank_i}")


def validate_shadow_export_rows(rows) -> dict:
    count = 0
    keys: set[tuple[str, str, str, str, str]] = set()
    for row in rows:
        validate_shadow_export_row(row)
        key = (
            str(row["experiment_id"]),
            str(row["model_freeze_id"]),
            str(row["symbol"]),
            str(row["signal_date"]),
            str(row["bin_name"]),
        )
        if key in keys:
            raise ValueError(f"duplicate candidate key in export: {'|'.join(key)}")
        keys.add(key)
        count += 1
    return {"rows": count, "unique_candidate_keys": len(keys), "status": "PASS"}
