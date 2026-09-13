"""Offline comparison of raw hourly and daily OHLCV by XTKS symbol/session."""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import date, datetime, time, timedelta
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import tempfile
from typing import Iterable
from zoneinfo import ZoneInfo

XTKS_TZ = ZoneInfo("Asia/Tokyo")
CHANGE_DATE = date(2024, 11, 5)
REQUIRED_DAILY = {"date", "symbol", "open", "high", "low", "close", "volume"}
REQUIRED_HOURLY = {"timestamp", "symbol", "open", "high", "low", "close", "volume"}
FIELDS = ("open", "high", "low", "close", "volume")


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
    return parsed.astimezone(XTKS_TZ) if parsed.tzinfo is not None else parsed.replace(tzinfo=XTKS_TZ)


def parse_number(value: object) -> float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def valid_ohlcv(values: Iterable[object]) -> bool:
    nums = [parse_number(value) for value in values]
    if any(value is None for value in nums):
        return False
    op, high, low, close, volume = nums
    return (
        op > 0 and high > 0 and low > 0 and close > 0 and volume >= 0
        and low <= min(op, close) and high >= max(op, close) and high >= low
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_calendar(path: Path) -> tuple[list[date], set[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        names = [str(item).strip().lower() for item in (reader.fieldnames or [])]
        if "date" not in names:
            raise ValueError("calendar CSV needs a date column")
        date_index = names.index("date")
        sessions = [parse_day(list(row.values())[date_index]) for row in reader]
    if not sessions or sessions != sorted(sessions) or len(sessions) != len(set(sessions)):
        raise ValueError("calendar sessions must be nonempty, sorted, and unique")
    return sessions, {item.isoformat() for item in sessions}


def session_overlap(
    stamp: datetime, interval_minutes: int, timestamp_label: str
) -> tuple[bool, bool]:
    """Return (overlaps trading, crosses a session boundary) without splitting a bar."""
    delta = timedelta(minutes=interval_minutes)
    start = stamp if timestamp_label == "start" else stamp - delta
    end = start + delta
    day = stamp.date()
    close = time(15, 0) if day < CHANGE_DATE else time(15, 30)
    segments = (
        (datetime.combine(day, time(9, 0), tzinfo=XTKS_TZ), datetime.combine(day, time(11, 30), tzinfo=XTKS_TZ)),
        (datetime.combine(day, time(12, 30), tzinfo=XTKS_TZ), datetime.combine(day, close, tzinfo=XTKS_TZ)),
    )
    overlaps_market = any(max(start, left) < min(end, right) for left, right in segments)
    fully_inside_one_session = any(start >= left and end <= right for left, right in segments)
    return overlaps_market, overlaps_market and not fully_inside_one_session


def create_db(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.execute("""CREATE TABLE daily (
        date TEXT NOT NULL, symbol TEXT NOT NULL, rows INTEGER NOT NULL,
        open REAL, high REAL, low REAL, close REAL, volume REAL,
        PRIMARY KEY(date, symbol))""")
    db.execute("""CREATE TABLE hourly (
        date TEXT NOT NULL, symbol TEXT NOT NULL,
        raw_rows INTEGER NOT NULL, usable_rows INTEGER NOT NULL,
        invalid_rows INTEGER NOT NULL, outside_rows INTEGER NOT NULL,
        boundary_rows INTEGER NOT NULL, duplicate_timestamps INTEGER NOT NULL,
        first_ts TEXT, first_open REAL, last_ts TEXT, last_close REAL,
        high REAL, low REAL, volume_sum REAL,
        PRIMARY KEY(date, symbol))""")
    db.execute("""CREATE TABLE stamps (
        date TEXT NOT NULL, symbol TEXT NOT NULL, timestamp TEXT NOT NULL,
        rows INTEGER NOT NULL, PRIMARY KEY(date, symbol, timestamp))""")
    return db


def add_daily(db: sqlite3.Connection, path: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        reader.fieldnames = [str(name).strip().lower() for name in (reader.fieldnames or [])]
        missing = REQUIRED_DAILY.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"daily CSV missing columns: {sorted(missing)}")
        with db:
            for row in reader:
                counts["rows"] += 1
                try:
                    day, symbol = parse_day(row["date"]).isoformat(), normalize_symbol(row["symbol"])
                except ValueError:
                    counts["unkeyable_rows"] += 1
                    continue
                values = [parse_number(row[name]) for name in FIELDS]
                db.execute(
                    """INSERT INTO daily VALUES (?, ?, 1, ?, ?, ?, ?, ?)
                       ON CONFLICT(date, symbol) DO UPDATE SET rows=daily.rows+1""",
                    (day, symbol, *values),
                )
    return dict(counts)


def add_hourly(
    db: sqlite3.Connection,
    path: Path,
    session_keys: set[str],
    interval_minutes: int,
    timestamp_label: str,
) -> dict[str, object]:
    counts: Counter[str] = Counter()
    minimum: str | None = None
    maximum: str | None = None
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        reader.fieldnames = [str(name).strip().lower() for name in (reader.fieldnames or [])]
        missing = REQUIRED_HOURLY.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"hourly CSV missing columns: {sorted(missing)}")
        with db:
            for row in reader:
                counts["rows"] += 1
                try:
                    stamp, symbol = parse_timestamp(row["timestamp"]), normalize_symbol(row["symbol"])
                except ValueError:
                    counts["unkeyable_rows"] += 1
                    continue
                day = stamp.date().isoformat()
                minimum = day if minimum is None else min(minimum, day)
                maximum = day if maximum is None else max(maximum, day)
                if day not in session_keys:
                    counts["non_xtks_session_rows"] += 1
                    continue

                stamp_text = stamp.isoformat()
                prior = db.execute(
                    "SELECT rows FROM stamps WHERE date=? AND symbol=? AND timestamp=?",
                    (day, symbol, stamp_text),
                ).fetchone()
                duplicate = int(prior is not None)
                db.execute(
                    """INSERT INTO stamps VALUES (?, ?, ?, 1)
                       ON CONFLICT(date, symbol, timestamp) DO UPDATE SET rows=stamps.rows+1""",
                    (day, symbol, stamp_text),
                )
                values = [parse_number(row[name]) for name in FIELDS]
                is_valid = valid_ohlcv(row[name] for name in FIELDS)
                in_session, crosses_boundary = session_overlap(
                    stamp, interval_minutes, timestamp_label
                )
                current = db.execute(
                    "SELECT * FROM hourly WHERE date=? AND symbol=?", (day, symbol)
                ).fetchone()
                if current is None:
                    current = (day, symbol, 0, 0, 0, 0, 0, 0, None, None, None, None, None, None, 0.0)
                raw_rows, usable_rows = current[2] + 1, current[3]
                invalid_rows = current[4] + int(not is_valid)
                outside_rows = current[5] + int(not in_session)
                boundary_rows = current[6] + int(crosses_boundary)
                duplicate_rows = current[7] + duplicate
                first_ts, first_open = current[8], current[9]
                last_ts, last_close = current[10], current[11]
                high, low, volume_sum = current[12], current[13], current[14]

                if is_valid and in_session:
                    usable_rows += 1
                    op, bar_high, bar_low, close, volume = values
                    if first_ts is None or stamp_text < first_ts:
                        first_ts, first_open = stamp_text, op
                    if last_ts is None or stamp_text > last_ts:
                        last_ts, last_close = stamp_text, close
                    high = bar_high if high is None else max(high, bar_high)
                    low = bar_low if low is None else min(low, bar_low)
                    volume_sum += volume

                db.execute(
                    """INSERT INTO hourly VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(date, symbol) DO UPDATE SET
                         raw_rows=excluded.raw_rows, usable_rows=excluded.usable_rows,
                         invalid_rows=excluded.invalid_rows, outside_rows=excluded.outside_rows,
                         boundary_rows=excluded.boundary_rows,
                         duplicate_timestamps=excluded.duplicate_timestamps,
                         first_ts=excluded.first_ts, first_open=excluded.first_open,
                         last_ts=excluded.last_ts, last_close=excluded.last_close,
                         high=excluded.high, low=excluded.low, volume_sum=excluded.volume_sum""",
                    (day, symbol, raw_rows, usable_rows, invalid_rows, outside_rows,
                     boundary_rows, duplicate_rows, first_ts, first_open, last_ts, last_close,
                     high, low, volume_sum),
                )
    if minimum is None or maximum is None:
        raise ValueError("hourly file contains no parseable timestamps")
    return {**dict(counts), "min_date": minimum, "max_date": maximum}


def daily_status(rows: int, values: tuple[object, ...]) -> tuple[str, bool]:
    if rows == 0:
        return "MISSING_DAILY_ROW", False
    if rows > 1:
        return "DUPLICATE_DAILY_KEY", False
    if not valid_ohlcv(values):
        return "INVALID_DAILY_OHLCV", False
    if parse_number(values[-1]) == 0:
        return "AVAILABLE_ZERO_VOLUME", True
    return "AVAILABLE_VALID_OHLCV", True


def hourly_status(raw: int, usable: int, invalid: int, duplicates: int) -> str:
    if raw == 0:
        return "NO_HOURLY_ROWS"
    if usable == 0:
        return "NO_USABLE_IN_SESSION_ROWS"
    if invalid:
        return "INVALID_HOURLY_ROW_PRESENT"
    if duplicates:
        return "DUPLICATE_HOURLY_TIMESTAMP"
    return "USABLE_ROWS_COVERAGE_UNVERIFIED"


def audit_files(
    hourly_csv: str | Path,
    daily_csv: str | Path,
    calendar_csv: str | Path,
    output_dir: str | Path,
    interval_minutes: int,
    timestamp_label: str,
) -> dict[str, object]:
    if not 1 <= interval_minutes <= 60:
        raise ValueError("interval_minutes must be between 1 and 60 for hourly-or-finer inputs")
    if timestamp_label not in {"start", "end"}:
        raise ValueError("timestamp_label must be 'start' or 'end'")
    hourly_path, daily_path, calendar_path = map(Path, (hourly_csv, daily_csv, calendar_csv))
    for path in (hourly_path, daily_path, calendar_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sessions, session_keys = read_calendar(calendar_path)

    with tempfile.TemporaryDirectory(prefix="hourly_daily_audit_", dir=out_dir) as temporary:
        db = create_db(Path(temporary) / "audit.sqlite")
        daily_input = add_daily(db, daily_path)
        hourly_input = add_hourly(
            db, hourly_path, session_keys, interval_minutes, timestamp_label
        )
        first, last = hourly_input["min_date"], hourly_input["max_date"]
        if first not in session_keys or last not in session_keys:
            raise ValueError("hourly date span endpoints must be official XTKS sessions")

        output_csv = out_dir / "hourly_daily_consistency_by_symbol_session.csv"
        fieldnames = [
            "date", "symbol", "daily_status", "hourly_status", "comparison_status",
            "hourly_raw_rows", "hourly_usable_session_rows", "hourly_invalid_rows",
            "hourly_outside_session_rows", "hourly_session_boundary_crossing_rows",
            "hourly_duplicate_timestamps",
            "hourly_first_timestamp_jst", "hourly_last_timestamp_jst",
            "daily_open", "daily_high", "daily_low", "daily_close", "daily_volume",
            "hourly_open", "hourly_high", "hourly_low", "hourly_close", "hourly_volume_sum",
        ]
        for field in FIELDS:
            fieldnames.extend([
                f"{field}_difference_hourly_minus_daily",
                f"{field}_absolute_difference",
                f"{field}_absolute_pct_difference",
            ])
        counts: Counter[str] = Counter()
        metrics = {
            field: {
                "comparable_count": 0, "exact_match_count": 0,
                "absolute_difference_sum": 0.0, "maximum_absolute_difference": 0.0,
                "absolute_pct_count": 0, "absolute_pct_sum": 0.0,
                "maximum_absolute_pct_difference": 0.0,
            }
            for field in FIELDS
        }
        with output_csv.open("w", encoding="utf-8-sig", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=fieldnames)
            writer.writeheader()
            keys = db.execute(
                """SELECT date,symbol FROM daily WHERE date>=? AND date<=?
                   UNION SELECT date,symbol FROM hourly WHERE date>=? AND date<=?
                   ORDER BY date,symbol""",
                (first, last, first, last),
            )
            for day, symbol in keys:
                if day not in session_keys:
                    continue
                d = db.execute(
                    "SELECT rows,open,high,low,close,volume FROM daily WHERE date=? AND symbol=?",
                    (day, symbol),
                ).fetchone()
                h = db.execute(
                    """SELECT raw_rows,usable_rows,invalid_rows,outside_rows,boundary_rows,
                              duplicate_timestamps,
                              first_ts,first_open,last_ts,last_close,high,low,volume_sum
                       FROM hourly WHERE date=? AND symbol=?""",
                    (day, symbol),
                ).fetchone()
                if d is None:
                    d = (0, None, None, None, None, None)
                if h is None:
                    h = (0, 0, 0, 0, 0, 0, None, None, None, None, None, None, None)
                d_status, d_valid = daily_status(d[0], d[1:])
                h_status = hourly_status(h[0], h[1], h[2], h[5])
                h_values = (h[7], h[10], h[11], h[9], h[12])
                h_clean = h[1] > 0 and h[2] == 0 and h[5] == 0
                comparable = d_valid and h_clean and all(value is not None for value in h_values)
                comparison_status = (
                    "SOURCE_INTERNAL_COMPARISON_ONLY" if comparable
                    else "UNASSESSABLE_OR_ROW_QUALITY_LIMIT"
                )
                row = {
                    "date": day, "symbol": symbol, "daily_status": d_status,
                    "hourly_status": h_status, "comparison_status": comparison_status,
                    "hourly_raw_rows": h[0], "hourly_usable_session_rows": h[1],
                    "hourly_invalid_rows": h[2], "hourly_outside_session_rows": h[3],
                    "hourly_session_boundary_crossing_rows": h[4],
                    "hourly_duplicate_timestamps": h[5],
                    "hourly_first_timestamp_jst": h[6], "hourly_last_timestamp_jst": h[8],
                    "daily_open": d[1], "daily_high": d[2], "daily_low": d[3],
                    "daily_close": d[4], "daily_volume": d[5],
                    "hourly_open": h_values[0], "hourly_high": h_values[1],
                    "hourly_low": h_values[2], "hourly_close": h_values[3],
                    "hourly_volume_sum": h_values[4],
                }
                counts["symbol_session_pairs"] += 1
                counts[f"daily::{d_status}"] += 1
                counts[f"hourly::{h_status}"] += 1
                counts[f"comparison::{comparison_status}"] += 1
                if comparable:
                    for field, daily_value, hourly_value in zip(FIELDS, d[1:], h_values):
                        difference = float(hourly_value) - float(daily_value)
                        absolute = abs(difference)
                        pct = absolute / abs(float(daily_value)) * 100 if float(daily_value) else None
                        row[f"{field}_difference_hourly_minus_daily"] = difference
                        row[f"{field}_absolute_difference"] = absolute
                        row[f"{field}_absolute_pct_difference"] = pct
                        stats = metrics[field]
                        stats["comparable_count"] += 1
                        stats["exact_match_count"] += int(absolute == 0)
                        stats["absolute_difference_sum"] += absolute
                        stats["maximum_absolute_difference"] = max(
                            stats["maximum_absolute_difference"], absolute
                        )
                        if pct is not None:
                            stats["absolute_pct_count"] += 1
                            stats["absolute_pct_sum"] += pct
                            stats["maximum_absolute_pct_difference"] = max(
                                stats["maximum_absolute_pct_difference"], pct
                            )
                else:
                    for field in FIELDS:
                        row[f"{field}_difference_hourly_minus_daily"] = None
                        row[f"{field}_absolute_difference"] = None
                        row[f"{field}_absolute_pct_difference"] = None
                writer.writerow(row)
        db.close()

    for stats in metrics.values():
        comparable_count = stats.pop("comparable_count")
        pct_count = stats.pop("absolute_pct_count")
        difference_sum = stats.pop("absolute_difference_sum")
        pct_sum = stats.pop("absolute_pct_sum")
        stats["mean_absolute_difference"] = (
            difference_sum / comparable_count if comparable_count else None
        )
        stats["mean_absolute_pct_difference"] = pct_sum / pct_count if pct_count else None
        stats["daily_source_is_ground_truth"] = False

    summary = {
        "experiment_id": "DATA-QUALITY-HOURLY-DAILY-CONSISTENCY-20260913-01",
        "audit_start_date": first,
        "audit_end_date": last,
        "session_regime_change_date": CHANGE_DATE.isoformat(),
        "hourly_timestamp_policy": "Naive timestamps treated as JST; offset-aware timestamps converted to Asia/Tokyo.",
        "hourly_interval_minutes": interval_minutes,
        "hourly_timestamp_label": timestamp_label,
        "aggregation_policy": "Open=first valid overlapping bar open; high=max; low=min; close=last valid overlapping bar close; volume=sum overlapping bar volume. A bar overlapping trading time is included whole, flagged if it crosses a session boundary, and never split.",
        "session_policy": "A bar interval is included if it overlaps official 09:00-11:30 or 12:30-15:00 before 2024-11-05 or 12:30-15:30 from 2024-11-05.",
        "daily_vs_hourly_is_internal_consistency_not_truth": True,
        "session_coverage_verified": False,
        "corporate_action_adjustment_basis_verified": False,
        "summary_counts": dict(sorted(counts.items())),
        "field_error_metrics": metrics,
        "daily_input": {"file": daily_path.name, "sha256": sha256_file(daily_path), **daily_input},
        "hourly_input": {"file": hourly_path.name, "sha256": sha256_file(hourly_path), **hourly_input},
        "calendar_input": {"file": calendar_path.name, "sha256": sha256_file(calendar_path), "session_count": len(sessions)},
        "output": output_csv.name,
        "scope_limit": "Only symbol/session keys present in either input are audited; absence from both requires a point-in-time universe.",
        "external_fetch": False,
        "production_modified": False,
        "legacy_data_mutated": False,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hourly-csv", required=True)
    parser.add_argument("--daily-csv", required=True)
    parser.add_argument("--calendar-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--interval-minutes", required=True, type=int,
                        help="Explicit source bar length; 1 through 60 minutes.")
    parser.add_argument("--timestamp-label", required=True, choices=("start", "end"),
                        help="Whether each timestamp marks the start or end of its bar.")
    args = parser.parse_args()
    print(json.dumps(
        audit_files(args.hourly_csv, args.daily_csv, args.calendar_csv, args.output_dir,
                    args.interval_minutes, args.timestamp_label),
        ensure_ascii=False, indent=2, allow_nan=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
