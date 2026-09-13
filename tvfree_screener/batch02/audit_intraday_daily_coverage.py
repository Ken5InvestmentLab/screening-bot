"""Offline CSV audit of missing XTKS four-hour bars against same-day daily OHLCV."""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import tempfile
from typing import Iterable
from zoneinfo import ZoneInfo

XTKS_TIMEZONE = ZoneInfo("Asia/Tokyo")


REQUIRED_DAILY = {"date", "symbol", "open", "high", "low", "close", "volume"}
REQUIRED_FOUR_HOUR = {"timestamp", "symbol", "open", "high", "low", "close", "volume"}
BATCH = Path(__file__).resolve().parent
DEFAULT_CALENDAR = BATCH.parent / "batch01" / "reference" / "xtks_sessions.csv"


def normalize_symbol(value: object) -> str:
    text = str(value or "").strip().upper()
    if ":" in text:
        text = text.rsplit(":", 1)[1]
    if text.endswith(".T"):
        text = text[:-2]
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".", 1)[0]
    if not text or text in {"NAN", "NONE"}:
        raise ValueError("missing symbol")
    return text


def parse_day(value: object) -> date:
    text = str(value or "").strip().replace("/", "-")
    try:
        return datetime.fromisoformat(text[:10]).date()
    except ValueError as exc:
        raise ValueError(f"invalid date: {value}") from exc


def parse_timestamp(value: object) -> datetime:
    text = str(value or "").strip().replace("/", "-")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"invalid timestamp: {value}") from exc
    # Naive timestamps are defined as Japan local time; offset-aware timestamps
    # are normalized before deriving the XTKS session date and bar slot.
    return parsed.astimezone(XTKS_TIMEZONE) if parsed.tzinfo is not None else parsed


def parse_number(value: object) -> float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def valid_ohlcv(values: Iterable[object]) -> bool:
    numbers = [parse_number(value) for value in values]
    if any(value is None for value in numbers):
        return False
    open_price, high, low, close, volume = numbers
    return (
        open_price > 0
        and high > 0
        and low > 0
        and close > 0
        and volume >= 0
        and low <= min(open_price, close)
        and high >= max(open_price, close)
        and high >= low
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _open_dict_reader(path: Path) -> tuple[object, csv.DictReader]:
    stream = path.open("r", encoding="utf-8-sig", newline="")
    reader = csv.DictReader(stream)
    reader.fieldnames = [str(name).strip().lower() for name in (reader.fieldnames or [])]
    return stream, reader


def _check_headers(path: Path, reader: csv.DictReader, required: set[str]) -> None:
    missing = sorted(required.difference(reader.fieldnames or []))
    if missing:
        raise ValueError(f"{path.name} is missing columns: {missing}")


def _read_calendar(path: Path) -> tuple[list[date], set[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = {str(field).strip().lower() for field in (reader.fieldnames or [])}
        if "date" not in fields:
            raise ValueError("calendar CSV must contain a date column")
        sessions = [parse_day(row["date"]) for row in reader]
    if not sessions or len(sessions) != len(set(sessions)) or sessions != sorted(sessions):
        raise ValueError("official session calendar must be nonempty, unique, and sorted")
    return sessions, {day.isoformat() for day in sessions}


def _new_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("""
        CREATE TABLE daily (
            date TEXT NOT NULL, symbol TEXT NOT NULL, row_count INTEGER NOT NULL,
            open REAL, high REAL, low REAL, close REAL, volume REAL,
            PRIMARY KEY (date, symbol)
        )
    """)
    connection.execute("""
        CREATE TABLE intraday (
            date TEXT NOT NULL, symbol TEXT NOT NULL,
            morning_count INTEGER NOT NULL, afternoon_count INTEGER NOT NULL,
            other_count INTEGER NOT NULL, invalid_count INTEGER NOT NULL,
            total_count INTEGER NOT NULL,
            PRIMARY KEY (date, symbol)
        )
    """)
    return connection


def _add_daily(connection: sqlite3.Connection, path: Path) -> dict[str, int]:
    stream, reader = _open_dict_reader(path)
    counts = Counter()
    try:
        _check_headers(path, reader, REQUIRED_DAILY)
        with connection:
            for row in reader:
                counts["rows"] += 1
                try:
                    day = parse_day(row["date"]).isoformat()
                    symbol = normalize_symbol(row["symbol"])
                except ValueError:
                    counts["unkeyable_rows"] += 1
                    continue
                values = [parse_number(row[name]) for name in ("open", "high", "low", "close", "volume")]
                connection.execute(
                    """
                    INSERT INTO daily VALUES (?, ?, 1, ?, ?, ?, ?, ?)
                    ON CONFLICT(date, symbol) DO UPDATE SET row_count = daily.row_count + 1
                    """,
                    (day, symbol, *values),
                )
    finally:
        stream.close()
    return dict(counts)


def _add_four_hour(
    connection: sqlite3.Connection,
    path: Path,
    calendar_days: set[str],
) -> dict[str, object]:
    stream, reader = _open_dict_reader(path)
    counts = Counter()
    minimum_day: str | None = None
    maximum_day: str | None = None
    try:
        _check_headers(path, reader, REQUIRED_FOUR_HOUR)
        with connection:
            for row in reader:
                counts["rows"] += 1
                try:
                    timestamp = parse_timestamp(row["timestamp"])
                    symbol = normalize_symbol(row["symbol"])
                except ValueError:
                    counts["unkeyable_rows"] += 1
                    continue
                day = timestamp.date().isoformat()
                minimum_day = day if minimum_day is None else min(minimum_day, day)
                maximum_day = day if maximum_day is None else max(maximum_day, day)
                if day not in calendar_days:
                    counts["non_session_rows"] += 1
                slot = "morning" if timestamp.hour == 9 else "afternoon" if timestamp.hour == 13 else "other"
                valid = valid_ohlcv(row[name] for name in ("open", "high", "low", "close", "volume"))
                connection.execute(
                    """
                    INSERT INTO intraday VALUES (
                        ?, ?, ?, ?, ?, ?, 1
                    )
                    ON CONFLICT(date, symbol) DO UPDATE SET
                        morning_count = intraday.morning_count + excluded.morning_count,
                        afternoon_count = intraday.afternoon_count + excluded.afternoon_count,
                        other_count = intraday.other_count + excluded.other_count,
                        invalid_count = intraday.invalid_count + excluded.invalid_count,
                        total_count = intraday.total_count + 1
                    """,
                    (
                        day, symbol,
                        int(slot == "morning"), int(slot == "afternoon"),
                        int(slot == "other"), int(not valid),
                    ),
                )
    finally:
        stream.close()
    if minimum_day is None or maximum_day is None:
        raise ValueError("four-hour CSV contains no parseable symbol/timestamp rows")
    return {
        **dict(counts),
        "min_date": minimum_day,
        "max_date": maximum_day,
    }


def _daily_status(row_count: int, values: tuple[object, ...]) -> tuple[str, bool]:
    if row_count == 0:
        return "MISSING_DAILY_ROW", False
    if row_count > 1:
        return "DUPLICATE_DAILY_KEY", False
    if not valid_ohlcv(values):
        return "INVALID_DAILY_OHLCV", False
    if parse_number(values[-1]) == 0:
        return "AVAILABLE_ZERO_VOLUME", True
    return "AVAILABLE_VALID_OHLCV", True


def _four_hour_status(
    morning: int, afternoon: int, other: int, invalid: int
) -> str:
    if invalid:
        return "INVALID_4H_OHLCV"
    if morning == 0 and afternoon == 0 and other == 0:
        return "NO_4H_BARS"
    if morning > 1 or afternoon > 1 or other > 0:
        return "DUPLICATE_OR_UNEXPECTED_4H_BARS"
    if morning == 0:
        return "MISSING_MORNING_BAR"
    if afternoon == 0:
        return "MISSING_AFTERNOON_BAR"
    return "COMPLETE_EXPECTED_SLOTS"


def audit_csv_files(
    four_hour_csv: str | Path,
    daily_csv: str | Path,
    calendar_csv: str | Path,
    output_dir: str | Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, object]:
    four_path, daily_path, calendar_path = map(Path, (four_hour_csv, daily_csv, calendar_csv))
    for path in (four_path, daily_path, calendar_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sessions, session_keys = _read_calendar(calendar_path)

    with tempfile.TemporaryDirectory(prefix="intraday_daily_audit_", dir=out_dir) as temp:
        connection = _new_database(Path(temp) / "coverage.sqlite")
        daily_input = _add_daily(connection, daily_path)
        intraday_input = _add_four_hour(connection, four_path, session_keys)
        observed_start = start_date or str(intraday_input["min_date"])
        observed_end = end_date or str(intraday_input["max_date"])
        first = parse_day(observed_start).isoformat()
        last = parse_day(observed_end).isoformat()
        if first > last:
            raise ValueError("audit start date is after end date")
        if first not in session_keys or last not in session_keys:
            raise ValueError("audit range endpoints must be official XTKS sessions")
        if not any(first <= day.isoformat() <= last for day in sessions):
            raise ValueError("audit date range contains no official sessions")

        missing_path = out_dir / "missing_four_hour_symbol_sessions.csv"
        four_only_path = out_dir / "four_hour_keys_without_daily.csv"
        daily_status_counts: Counter[str] = Counter()
        four_status_counts: Counter[str] = Counter()
        daily_pair_count = 0
        gap_pair_count = 0
        daily_available_for_gaps = 0
        zero_volume_for_gaps = 0
        daily_unavailable_for_gaps = 0

        with missing_path.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=[
                "date", "symbol", "four_hour_status", "morning_bar_count",
                "afternoon_bar_count", "other_hour_bar_count", "invalid_four_hour_bar_count",
                "four_hour_bar_count", "daily_status", "daily_ohlcv_available",
                "daily_open", "daily_high", "daily_low", "daily_close", "daily_volume",
            ])
            writer.writeheader()
            query = connection.execute(
                """
                SELECT d.date, d.symbol, d.row_count, d.open, d.high, d.low, d.close, d.volume,
                       COALESCE(h.morning_count, 0), COALESCE(h.afternoon_count, 0),
                       COALESCE(h.other_count, 0), COALESCE(h.invalid_count, 0),
                       COALESCE(h.total_count, 0)
                  FROM daily d
                  LEFT JOIN intraday h ON h.date = d.date AND h.symbol = d.symbol
                 WHERE d.date >= ? AND d.date <= ?
                 ORDER BY d.date, d.symbol
                """,
                (first, last),
            )
            for record in query:
                day, symbol, row_count, open_price, high, low, close, volume, morning, afternoon, other, invalid, total = record
                if day not in session_keys:
                    continue
                daily_pair_count += 1
                daily_status, daily_available = _daily_status(
                    row_count, (open_price, high, low, close, volume)
                )
                four_status = _four_hour_status(morning, afternoon, other, invalid)
                daily_status_counts[daily_status] += 1
                four_status_counts[four_status] += 1
                if four_status == "COMPLETE_EXPECTED_SLOTS":
                    continue
                gap_pair_count += 1
                daily_available_for_gaps += int(daily_available)
                zero_volume_for_gaps += int(daily_status == "AVAILABLE_ZERO_VOLUME")
                daily_unavailable_for_gaps += int(not daily_available)
                writer.writerow({
                    "date": day,
                    "symbol": symbol,
                    "four_hour_status": four_status,
                    "morning_bar_count": morning,
                    "afternoon_bar_count": afternoon,
                    "other_hour_bar_count": other,
                    "invalid_four_hour_bar_count": invalid,
                    "four_hour_bar_count": total,
                    "daily_status": daily_status,
                    "daily_ohlcv_available": str(daily_available).lower(),
                    "daily_open": open_price,
                    "daily_high": high,
                    "daily_low": low,
                    "daily_close": close,
                    "daily_volume": volume,
                })

        four_only_count = 0
        with four_only_path.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=[
                "date", "symbol", "four_hour_status", "morning_bar_count",
                "afternoon_bar_count", "other_hour_bar_count", "invalid_four_hour_bar_count",
                "four_hour_bar_count", "daily_status",
            ])
            writer.writeheader()
            query = connection.execute(
                """
                SELECT h.date, h.symbol, h.morning_count, h.afternoon_count,
                       h.other_count, h.invalid_count, h.total_count
                  FROM intraday h
                  LEFT JOIN daily d ON d.date = h.date AND d.symbol = h.symbol
                 WHERE h.date >= ? AND h.date <= ? AND d.symbol IS NULL
                 ORDER BY h.date, h.symbol
                """,
                (first, last),
            )
            for day, symbol, morning, afternoon, other, invalid, total in query:
                if day not in session_keys:
                    continue
                four_only_count += 1
                writer.writerow({
                    "date": day, "symbol": symbol,
                    "four_hour_status": _four_hour_status(morning, afternoon, other, invalid),
                    "morning_bar_count": morning, "afternoon_bar_count": afternoon,
                    "other_hour_bar_count": other, "invalid_four_hour_bar_count": invalid,
                    "four_hour_bar_count": total, "daily_status": "MISSING_DAILY_ROW",
                })
        connection.close()

    summary: dict[str, object] = {
        "experiment_id": "DATA-QUALITY-INTRADAY-DAILY-COVERAGE-20260913-01",
        "audit_start_date": first,
        "audit_end_date": last,
        "expected_session_slots_per_symbol_day": ["09:00 morning", "13:00 afternoon"],
        "daily_symbol_session_pairs_in_scope": daily_pair_count,
        "symbol_session_pairs_with_missing_partial_or_invalid_four_hour_data": gap_pair_count,
        "daily_ohlcv_available_for_four_hour_gaps": daily_available_for_gaps,
        "daily_ohlcv_unavailable_or_invalid_for_four_hour_gaps": daily_unavailable_for_gaps,
        "zero_volume_daily_bars_among_four_hour_gaps": zero_volume_for_gaps,
        "four_hour_observed_keys_without_same_day_daily_row": four_only_count,
        "four_hour_status_counts_over_daily_pairs": dict(sorted(four_status_counts.items())),
        "daily_status_counts_over_daily_pairs": dict(sorted(daily_status_counts.items())),
        "four_hour_input": {
            "path_name": four_path.name,
            "sha256": sha256_file(four_path),
            **intraday_input,
        },
        "daily_input": {
            "path_name": daily_path.name,
            "sha256": sha256_file(daily_path),
            **daily_input,
        },
        "calendar_input": {
            "path_name": calendar_path.name,
            "sha256": sha256_file(calendar_path),
            "session_count": len(sessions),
        },
        "outputs": {
            "missing_four_hour_symbol_sessions": missing_path.name,
            "four_hour_keys_without_daily": four_only_path.name,
        },
        "scope_limit": (
            "Expected symbol/session pairs are defined by daily rows plus observed four-hour-only keys. "
            "A symbol/session missing from both inputs cannot be inferred without a separate point-in-time universe."
        ),
        "cross_source_adjustment_comparability": (
            "NOT_ASSESSED_BY_COVERAGE_AUDIT; verify source adjustment metadata before mixing prices or features."
        ),
        "external_fetch": False,
        "production_modified": False,
    }
    summary_path = out_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--four-hour-csv", required=True, help="Local CSV export with timestamp,symbol,OHLCV columns.")
    parser.add_argument("--daily-csv", required=True, help="Local daily CSV with date,symbol,OHLCV columns.")
    parser.add_argument("--calendar-csv", default=str(DEFAULT_CALENDAR), help="Frozen XTKS date,session_index CSV.")
    parser.add_argument("--output-dir", required=True, help="Write ignored audit outputs here.")
    parser.add_argument("--start-date", help="Optional inclusive XTKS session start; default is first observed 4-hour date.")
    parser.add_argument("--end-date", help="Optional inclusive XTKS session end; default is last observed 4-hour date.")
    args = parser.parse_args()
    summary = audit_csv_files(
        args.four_hour_csv, args.daily_csv, args.calendar_csv, args.output_dir,
        start_date=args.start_date, end_date=args.end_date,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
