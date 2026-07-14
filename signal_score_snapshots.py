#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finalize immutable point-in-time signal scores.

The 4-hour sheet remains the primary price source.  For completed trading days
strictly before the signal date, an incomplete 09:00/13:00 pair is replaced by
that day's Yahoo Finance daily OHLCV.  The signal date itself is never filled
from daily data.  Final rows are append-only and the first FINAL row for an
``alert_id`` is authoritative.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pandas as pd

import optimize_screener as opt


JST = ZoneInfo("Asia/Tokyo")
BASE_DIR = Path(__file__).resolve().parent
SNAPSHOT_SHEET_NAME = os.environ.get(
    "SIGNAL_FEATURE_SNAPSHOT_SHEET_NAME",
    "signal_feature_snapshots",
)
SCHEMA_VERSION = "1"
FINAL_STATUS = "FINAL"
EXPECTED_SESSION_HOURS = (9, 13)
YAHOO_LOOKBACK_CALENDAR_DAYS = 300
YAHOO_WORKERS = 8

SNAPSHOT_HEADERS = [
    "schema_version",
    "alert_id",
    "symbol",
    "signal_date",
    "received_at",
    "feature_cutoff",
    "status",
    "stable_score",
    "sniper_score",
    "stable_filters_json",
    "sniper_filters_json",
    "modes_json",
    "features_json",
    "fallback_dates_json",
    "input_quality",
    "logic_hash",
    "input_hash",
    "finalized_at",
]

SNAPSHOT_JSON_COLUMNS = {
    "stable_filters_json": "stable_filters",
    "sniper_filters_json": "sniper_filters",
    "modes_json": "modes",
    "features_json": "features",
    "fallback_dates_json": "fallback_dates",
}

SNAPSHOT_FEATURE_KEYS = set(opt.BOOL_CONDS) | {
    "_vsurge",
    "_atr",
    "_body",
    "_rsi",
    "_stoch",
    "_bbpct",
    "_rci9",
    "_rci26",
    "_cci",
    "_vp_support",
    "_vp_overhead",
    "_vp_poc_abs",
}


def normalize_date(value) -> str:
    return str(value or "").strip().replace("/", "-")[:10]


def clean_symbol(value) -> str:
    text = str(value or "").strip()
    if ":" in text:
        text = text.rsplit(":", 1)[-1]
    if text.upper().endswith(".T"):
        text = text[:-2]
    return text.strip()


def _json_value(value):
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_value(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (TypeError, ValueError):
            pass
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def compact_json(value) -> str:
    return json.dumps(
        _json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_hash(value) -> str:
    return hashlib.sha256(compact_json(value).encode("utf-8")).hexdigest()


def _parse_json(value, default):
    if isinstance(value, (dict, list)):
        return value
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def load_snapshot_map(rows: list[list]) -> dict[str, dict]:
    """Parse the snapshot Sheet, preserving the first FINAL row per alert."""
    if not rows:
        return {}
    header_index = -1
    header: list[str] = []
    for index, row in enumerate(rows[:10]):
        candidate = [str(cell or "").strip().lower() for cell in row]
        if "alert_id" in candidate:
            header_index = index
            header = candidate
            break
    if header_index < 0:
        return {}

    indexes = {name: header.index(name) if name in header else -1 for name in SNAPSHOT_HEADERS}
    result: dict[str, dict] = {}
    for row in rows[header_index + 1 :]:
        def cell(name):
            index = indexes.get(name, -1)
            return row[index] if 0 <= index < len(row) else ""

        alert_id = str(cell("alert_id") or "").strip()
        status = str(cell("status") or "").strip().upper()
        if not alert_id or alert_id in result or status != FINAL_STATUS:
            continue
        try:
            stable_score = int(float(cell("stable_score")))
        except (TypeError, ValueError):
            continue
        try:
            sniper_score = int(float(cell("sniper_score")))
        except (TypeError, ValueError):
            sniper_score = -1

        snapshot = {
            "schema_version": str(cell("schema_version") or ""),
            "alert_id": alert_id,
            "symbol": clean_symbol(cell("symbol")),
            "signal_date": normalize_date(cell("signal_date")),
            "received_at": str(cell("received_at") or "").strip(),
            "feature_cutoff": str(cell("feature_cutoff") or "").strip(),
            "status": status,
            "stable_score": stable_score,
            "sniper_score": sniper_score,
            "input_quality": str(cell("input_quality") or "").strip(),
            "logic_hash": str(cell("logic_hash") or "").strip(),
            "input_hash": str(cell("input_hash") or "").strip(),
            "finalized_at": str(cell("finalized_at") or "").strip(),
        }
        for column, key in SNAPSHOT_JSON_COLUMNS.items():
            default = {} if key == "features" else []
            snapshot[key] = _parse_json(cell(column), default)
        result[alert_id] = snapshot
    return result


def snapshot_to_row(snapshot: dict) -> list:
    values = dict(snapshot)
    for column, key in SNAPSHOT_JSON_COLUMNS.items():
        values[column] = compact_json(snapshot.get(key, {} if key == "features" else []))
    return [values.get(header, "") for header in SNAPSHOT_HEADERS]


def is_valid_bar(bar: dict) -> bool:
    try:
        open_ = float(bar.get("open"))
        high = float(bar.get("high"))
        low = float(bar.get("low"))
        close = float(bar.get("close"))
        volume = float(bar.get("volume"))
    except (TypeError, ValueError):
        return False
    return (
        all(math.isfinite(value) and value > 0 for value in (open_, high, low, close))
        and math.isfinite(volume)
        and volume >= 0
        and high >= max(open_, close, low)
        and low <= min(open_, close, high)
    )


def normalized_bar(bar: dict, date_key: str | None = None) -> dict:
    return {
        "date": date_key or normalize_date(bar.get("date")),
        "open": float(bar.get("open")),
        "high": float(bar.get("high")),
        "low": float(bar.get("low")),
        "close": float(bar.get("close")),
        "volume": float(bar.get("volume")),
    }


def _timestamp(value):
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else pd.Timestamp(parsed)


def session_hour(row: dict) -> int | None:
    ts = _timestamp(row.get("timestamp"))
    return None if ts is None else int(ts.hour)


def dedupe_sessions(rows: list[dict]) -> list[dict]:
    """Keep the last value for a duplicated date/session hour."""
    by_hour: dict[int, dict] = {}
    extras: list[dict] = []
    for row in sorted(rows, key=lambda item: _timestamp(item.get("timestamp")) or pd.Timestamp.min):
        hour = session_hour(row)
        if hour is None:
            extras.append(row)
        else:
            by_hour[hour] = row
    return [by_hour[hour] for hour in sorted(by_hour)] + extras


def aggregate_sessions(rows: list[dict], date_key: str) -> dict | None:
    valid = [row for row in dedupe_sessions(rows) if is_valid_bar(row)]
    if not valid:
        return None
    valid.sort(key=lambda item: _timestamp(item.get("timestamp")) or pd.Timestamp.min)
    return {
        "date": date_key,
        "open": float(valid[0]["open"]),
        "high": max(float(row["high"]) for row in valid),
        "low": min(float(row["low"]) for row in valid),
        "close": float(valid[-1]["close"]),
        "volume": sum(float(row["volume"]) for row in valid),
    }


def complete_past_sessions(rows: list[dict]) -> bool:
    selected = {session_hour(row): row for row in dedupe_sessions(rows)}
    return all(hour in selected and is_valid_bar(selected[hour]) for hour in EXPECTED_SESSION_HOURS)


def signal_cutoff(signal_date: str, received_at) -> pd.Timestamp | None:
    signal_dt = pd.to_datetime(normalize_date(signal_date), errors="coerce")
    received_dt = _timestamp(received_at)
    if pd.isna(signal_dt) or received_dt is None:
        return None
    hour = 9 if received_dt.hour < 14 else 13
    return pd.Timestamp(signal_dt).replace(hour=hour, minute=0, second=0, microsecond=0)


def build_feature_daily_bars(
    session_rows: list[dict],
    yahoo_daily_rows: list[dict],
    signal_date: str,
    received_at=None,
) -> tuple[list[dict], list[str], dict]:
    """Build point-in-time daily bars with past-day-only daily fallback."""
    signal_key = normalize_date(signal_date)
    cutoff = signal_cutoff(signal_key, received_at)
    sessions_by_date: dict[str, list[dict]] = {}
    for row in session_rows or []:
        date_key = normalize_date(row.get("date") or row.get("timestamp"))
        if not date_key or date_key > signal_key:
            continue
        if date_key == signal_key and cutoff is not None:
            ts = _timestamp(row.get("timestamp"))
            if ts is not None and ts > cutoff:
                continue
        sessions_by_date.setdefault(date_key, []).append(row)

    daily_by_date = {
        normalize_date(row.get("date")): normalized_bar(row)
        for row in (yahoo_daily_rows or [])
        if normalize_date(row.get("date")) and is_valid_bar(row)
    }

    output: dict[str, dict] = {}
    fallback_dates: list[str] = []
    unfilled_partial_dates: list[str] = []
    candidate_dates = set(sessions_by_date)
    # Daily data repairs holes inside the available 4-hour history.  It must not
    # bootstrap an older daily-only history, because 4-hour evaluation is the
    # non-negotiable source of truth.
    coverage_start = min(sessions_by_date) if sessions_by_date else signal_key
    coverage_end = max(sessions_by_date) if sessions_by_date else signal_key
    candidate_dates.update(
        date_key
        for date_key in daily_by_date
        if coverage_start <= date_key <= coverage_end and date_key < signal_key
    )

    for date_key in sorted(candidate_dates):
        rows = sessions_by_date.get(date_key, [])
        if date_key == signal_key:
            # Signal-day OHLCV is always 4-hour data; never use the daily bar.
            aggregate = aggregate_sessions(rows, date_key)
            if aggregate is not None:
                output[date_key] = aggregate
            continue
        if date_key > signal_key:
            continue

        if complete_past_sessions(rows):
            aggregate = aggregate_sessions(rows, date_key)
            if aggregate is not None:
                output[date_key] = aggregate
            continue
        if date_key in daily_by_date:
            output[date_key] = dict(daily_by_date[date_key])
            fallback_dates.append(date_key)
            continue

        aggregate = aggregate_sessions(rows, date_key)
        if aggregate is not None:
            output[date_key] = aggregate
            unfilled_partial_dates.append(date_key)

    diagnostics = {
        "feature_cutoff": cutoff.isoformat() if cutoff is not None else "",
        "unfilled_partial_dates": sorted(unfilled_partial_dates),
        "signal_day_from_daily": False,
        "signal_day_present": signal_key in output,
    }
    return [output[key] for key in sorted(output)], sorted(fallback_dates), diagnostics


def yahoo_ticker(symbol: str) -> str:
    cleaned = clean_symbol(symbol).upper()
    if (
        (cleaned.isdigit() and len(cleaned) in (4, 5))
        or re.fullmatch(r"\d{3}[A-Z]", cleaned)
    ):
        return f"{cleaned}.T"
    return cleaned


def fetch_yahoo_daily(
    symbol: str,
    start_date: date,
    end_date: date,
    *,
    timeout: float = 12.0,
    retries: int = 2,
) -> list[dict]:
    ticker = yahoo_ticker(symbol)
    period1 = int(datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    exclusive_end = end_date + timedelta(days=2)
    period2 = int(datetime.combine(exclusive_end, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    query = urllib.parse.urlencode(
        {
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
    )
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ticker)}?{query}"
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 screening-bot-snapshot/1.0"},
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
            error = payload.get("chart", {}).get("error")
            results = payload.get("chart", {}).get("result") or []
            if error or not results:
                raise RuntimeError(f"Yahoo chart error: {error or 'empty result'}")
            result = results[0]
            timestamps = result.get("timestamp") or []
            quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
            bars: list[dict] = []
            for index, timestamp in enumerate(timestamps):
                try:
                    bar = {
                        "date": datetime.fromtimestamp(int(timestamp), JST).strftime("%Y-%m-%d"),
                        "open": quote.get("open", [])[index],
                        "high": quote.get("high", [])[index],
                        "low": quote.get("low", [])[index],
                        "close": quote.get("close", [])[index],
                        "volume": quote.get("volume", [])[index],
                    }
                except (IndexError, TypeError, ValueError):
                    continue
                if is_valid_bar(bar):
                    bars.append(normalized_bar(bar))
            return bars
        except (OSError, RuntimeError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.35 * (2**attempt))
    raise RuntimeError(f"Yahoo daily fetch failed for {symbol}: {last_error}")


def load_logic() -> dict:
    def read_json(name: str, default):
        try:
            with (BASE_DIR / name).open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return default

    stable_payload = read_json("current_logic.json", {})
    sniper_payload = read_json("current_logic_sniper.json", {})
    mega_payload = read_json("current_logic_mega.json", {})
    stable = [str(item) for item in stable_payload.get("conditions", [])]
    sniper = [str(item) for item in sniper_payload.get("conditions", [])]
    mega = {
        str(mode_id): [str(item) for item in mode.get("conditions", [])]
        for mode_id, mode in (mega_payload.get("modes", {}) or {}).items()
        if isinstance(mode, dict)
    }
    return {
        "stable": stable,
        "sniper": sniper,
        "mega": mega,
        "hash": canonical_hash(
            {
                "stable": stable,
                "sniper": sniper,
                "mega": mega,
                "stable_updated_at": stable_payload.get("updated_at"),
                "sniper_updated_at": sniper_payload.get("updated_at"),
                "mega_updated_at": mega_payload.get("updated_at"),
            }
        ),
    }


def compute_snapshot(
    alert: dict,
    session_rows: list[dict],
    yahoo_daily_rows: list[dict] | None,
    logic: dict,
    *,
    yahoo_error: str = "",
    finalized_at: datetime | None = None,
) -> dict:
    feature_daily, fallback_dates, diagnostics = build_feature_daily_bars(
        session_rows,
        yahoo_daily_rows or [],
        alert.get("date", ""),
        alert.get("received_at", ""),
    )
    # Without a 4-hour signal-day aggregate, get_features() would otherwise
    # mistake the previous completed day for the signal candle.  Daily fallback
    # on the signal date is forbidden, so finalize a degraded empty selection.
    features = (
        opt.get_features(feature_daily, alert.get("date", "")) or {}
        if diagnostics.get("signal_day_present")
        else {}
    )
    stored_features = {
        key: _json_value(value)
        for key, value in features.items()
        if key in SNAPSHOT_FEATURE_KEYS
    }

    stable_conditions = logic.get("stable", [])
    sniper_conditions = logic.get("sniper", [])
    mega_conditions = logic.get("mega", {})
    stable_filters = [key for key in stable_conditions if bool(features.get(key, False))]
    sniper_filters = [key for key in sniper_conditions if bool(features.get(key, False))]
    stable_score = len(stable_filters)
    sniper_score = len(sniper_filters)
    modes: list[str] = []
    if stable_conditions and stable_score == len(stable_conditions):
        modes.append("stable_s6")
    if sniper_conditions and sniper_score == len(sniper_conditions):
        modes.append("sniper")
    for mode_id, conditions in mega_conditions.items():
        if conditions and all(bool(features.get(key, False)) for key in conditions):
            modes.append(mode_id)

    quality_parts: list[str] = []
    if fallback_dates:
        quality_parts.append("PAST_GAPS_FILLED_FROM_1D")
    else:
        quality_parts.append("FOUR_HOUR_ONLY")
    if yahoo_error:
        quality_parts.append("DEGRADED_YAHOO_UNAVAILABLE")
    if diagnostics.get("unfilled_partial_dates"):
        quality_parts.append("DEGRADED_UNFILLED_PAST_GAPS")
    if not diagnostics.get("signal_day_present"):
        quality_parts.append("DEGRADED_SIGNAL_DAY_MISSING")
    if not str(alert.get("received_at", "") or "").strip():
        quality_parts.append("DEGRADED_MISSING_RECEIVED_AT")
    if not features:
        quality_parts.append("DEGRADED_INSUFFICIENT_HISTORY")

    final_time = finalized_at or datetime.now(JST)
    input_payload = {
        "alert_id": alert.get("alert_id", ""),
        "symbol": clean_symbol(alert.get("symbol", "")),
        "signal_date": normalize_date(alert.get("date", "")),
        "received_at": str(alert.get("received_at", "") or ""),
        "feature_cutoff": diagnostics.get("feature_cutoff", ""),
        "bars": feature_daily,
        "fallback_dates": fallback_dates,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "alert_id": str(alert.get("alert_id", "") or "").strip(),
        "symbol": clean_symbol(alert.get("symbol", "")),
        "signal_date": normalize_date(alert.get("date", "")),
        "received_at": str(alert.get("received_at", "") or "").strip(),
        "feature_cutoff": diagnostics.get("feature_cutoff", ""),
        "status": FINAL_STATUS,
        "stable_score": stable_score,
        "sniper_score": sniper_score,
        "stable_filters": stable_filters,
        "sniper_filters": sniper_filters,
        "modes": modes,
        "features": stored_features,
        "fallback_dates": fallback_dates,
        "input_quality": "+".join(quality_parts),
        "logic_hash": logic.get("hash", ""),
        "input_hash": canonical_hash(input_payload),
        "finalized_at": final_time.astimezone(JST).isoformat(timespec="seconds"),
    }


def parse_bottom_alerts(*row_sets: list[list]) -> list[dict]:
    lookup = opt.alert_received_at_lookup(*row_sets)
    alerts: list[dict] = []
    seen: set[str] = set()
    for rows in row_sets:
        frame = opt.parse_alerts(rows, include_unconfirmed=True)
        frame = opt.attach_alert_received_at(frame, lookup)
        for _, item in frame.iterrows():
            alert_id = str(item.get("alert_id", "") or "").strip()
            if not alert_id or alert_id in seen:
                continue
            seen.add(alert_id)
            alerts.append(
                {
                    "alert_id": alert_id,
                    "symbol": clean_symbol(item.get("symbol", "")),
                    "date": normalize_date(item.get("date", "")),
                    "received_at": str(item.get("received_at", "") or "").strip(),
                    "_received_at_dt": item.get("_received_at_dt"),
                }
            )
    return alerts


def credentials_path() -> Path:
    configured = (
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        or os.environ.get("GOOGLE_CREDENTIALS_PATH")
        or os.environ.get("CREDENTIALS_PATH")
    )
    return Path(configured).expanduser().resolve() if configured else BASE_DIR / "credentials.json"


def get_write_service():
    credentials = service_account.Credentials.from_service_account_file(
        str(credentials_path()),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def fetch_values(service, sheet_name: str) -> list[list]:
    response = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=opt.SPREADSHEET_ID, range=sheet_name)
        .execute()
    )
    return response.get("values", [])


def fetch_optional_values(service, sheet_name: str) -> list[list]:
    try:
        return fetch_values(service, sheet_name)
    except HttpError as exc:
        if getattr(exc.resp, "status", None) == 400:
            return []
        raise


def ensure_snapshot_sheet(service) -> list[list]:
    metadata = (
        service.spreadsheets()
        .get(
            spreadsheetId=opt.SPREADSHEET_ID,
            fields="sheets.properties(sheetId,title)",
        )
        .execute()
    )
    titles = {
        str(item.get("properties", {}).get("title", ""))
        for item in metadata.get("sheets", [])
    }
    if SNAPSHOT_SHEET_NAME not in titles:
        service.spreadsheets().batchUpdate(
            spreadsheetId=opt.SPREADSHEET_ID,
            body={"requests": [{"addSheet": {"properties": {"title": SNAPSHOT_SHEET_NAME}}}]},
        ).execute()
    rows = fetch_optional_values(service, SNAPSHOT_SHEET_NAME)
    if not rows:
        service.spreadsheets().values().update(
            spreadsheetId=opt.SPREADSHEET_ID,
            range=f"{SNAPSHOT_SHEET_NAME}!A1",
            valueInputOption="RAW",
            body={"values": [SNAPSHOT_HEADERS]},
        ).execute()
        return [SNAPSHOT_HEADERS]
    header = [str(cell or "").strip() for cell in rows[0]]
    if header[: len(SNAPSHOT_HEADERS)] != SNAPSHOT_HEADERS:
        raise RuntimeError(
            f"Unexpected {SNAPSHOT_SHEET_NAME} header; refusing to overwrite existing data"
        )
    return rows


def append_snapshots(service, snapshots: list[dict]) -> int:
    if not snapshots:
        return 0
    current_rows = ensure_snapshot_sheet(service)
    existing = load_snapshot_map(current_rows)
    remaining = [item for item in snapshots if item["alert_id"] not in existing]
    if not remaining:
        return 0
    service.spreadsheets().values().append(
        spreadsheetId=opt.SPREADSHEET_ID,
        range=f"{SNAPSHOT_SHEET_NAME}!A:{chr(64 + len(SNAPSHOT_HEADERS))}",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [snapshot_to_row(item) for item in remaining]},
    ).execute()
    return len(remaining)


def select_alerts(alerts: list[dict], args, existing: dict[str, dict]) -> list[dict]:
    today = datetime.now(JST).date()
    selected: list[dict] = []
    for alert in alerts:
        if alert["alert_id"] in existing:
            continue
        signal_key = normalize_date(alert.get("date", ""))
        try:
            signal_day = date.fromisoformat(signal_key)
        except ValueError:
            continue
        if args.alert_id and alert["alert_id"] != args.alert_id:
            continue
        if args.symbol and clean_symbol(alert.get("symbol")) != clean_symbol(args.symbol):
            continue
        if args.date and signal_key != normalize_date(args.date):
            continue
        if not args.all_missing and not args.date and not args.alert_id:
            if signal_day < today - timedelta(days=max(0, args.lookback_days)):
                continue
        selected.append(alert)
    return selected


def calculate_missing_from_rows(
    alerts_raw_rows: list[list],
    archive_rows: list[list],
    ohlcv_rows: list[list],
    snapshot_rows: list[list],
    args,
    sessions_by_symbol: dict[str, list[dict]] | None = None,
) -> tuple[list[dict], dict]:
    """Calculate snapshots from already-fetched report inputs.

    The report generator uses this path so finalization adds only Yahoo's small
    daily requests and does not perform another full ``ohlcv_4h`` Sheet read.
    """
    existing = load_snapshot_map(snapshot_rows)
    alerts = parse_bottom_alerts(alerts_raw_rows, archive_rows)
    selected = select_alerts(alerts, args, existing)
    if not selected:
        return [], {"selected": 0, "existing": len(existing), "yahoo_failures": {}}

    if sessions_by_symbol is None:
        sessions_by_symbol = opt.parse_ohlcv_session_rows(ohlcv_rows)
    logic = load_logic()

    date_ranges: dict[str, tuple[date, date]] = {}
    for alert in selected:
        signal_day = date.fromisoformat(normalize_date(alert["date"]))
        symbol = alert["symbol"]
        start = signal_day - timedelta(days=YAHOO_LOOKBACK_CALENDAR_DAYS)
        if symbol not in date_ranges:
            date_ranges[symbol] = (start, signal_day)
        else:
            old_start, old_end = date_ranges[symbol]
            date_ranges[symbol] = (min(old_start, start), max(old_end, signal_day))

    yahoo_by_symbol: dict[str, list[dict]] = {}
    yahoo_failures: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=min(YAHOO_WORKERS, max(1, len(date_ranges)))) as executor:
        futures = {
            executor.submit(fetch_yahoo_daily, symbol, start, end): symbol
            for symbol, (start, end) in date_ranges.items()
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                yahoo_by_symbol[symbol] = future.result()
            except Exception as exc:
                yahoo_by_symbol[symbol] = []
                yahoo_failures[symbol] = str(exc)

    finalized_at = datetime.now(JST)
    snapshots = [
        compute_snapshot(
            alert,
            sessions_by_symbol.get(alert["symbol"], []),
            yahoo_by_symbol.get(alert["symbol"], []),
            logic,
            yahoo_error=yahoo_failures.get(alert["symbol"], ""),
            finalized_at=finalized_at,
        )
        for alert in selected
    ]
    return snapshots, {
        "selected": len(selected),
        "existing": len(existing),
        "yahoo_failures": yahoo_failures,
    }


def finalize_missing(service, args) -> tuple[list[dict], dict]:
    alerts_raw_rows = fetch_values(service, "alerts_raw")
    archive_rows = fetch_optional_values(service, "signals_archive")
    snapshot_rows = fetch_optional_values(service, SNAPSHOT_SHEET_NAME)
    ohlcv_rows = fetch_values(service, "ohlcv_4h")
    return calculate_missing_from_rows(
        alerts_raw_rows,
        archive_rows,
        ohlcv_rows,
        snapshot_rows,
        args,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=0,
        help="Finalize missing alerts since JST today minus N calendar days (default: today only).",
    )
    parser.add_argument("--date", help="Finalize one signal date (YYYY-MM-DD).")
    parser.add_argument("--alert-id", help="Finalize one alert_id.")
    parser.add_argument("--symbol", help="Restrict to one symbol code.")
    parser.add_argument("--all-missing", action="store_true", help="Finalize every missing alert.")
    parser.add_argument("--dry-run", action="store_true", help="Calculate but do not create/append the Sheet.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = get_write_service()
    snapshots, metadata = finalize_missing(service, args)
    appended = 0 if args.dry_run else append_snapshots(service, snapshots)
    summary = {
        "selected": metadata["selected"],
        "calculated": len(snapshots),
        "appended": appended,
        "dry_run": bool(args.dry_run),
        "yahoo_failure_count": len(metadata["yahoo_failures"]),
        "fallback_snapshot_count": sum(bool(item.get("fallback_dates")) for item in snapshots),
        "degraded_snapshot_count": sum("DEGRADED" in item.get("input_quality", "") for item in snapshots),
    }
    print(compact_json(summary))
    for snapshot in snapshots:
        if args.symbol or args.alert_id:
            print(
                compact_json(
                    {
                        "alert_id": snapshot["alert_id"],
                        "symbol": snapshot["symbol"],
                        "stable_score": snapshot["stable_score"],
                        "modes": snapshot["modes"],
                        "fallback_dates": snapshot["fallback_dates"],
                        "input_quality": snapshot["input_quality"],
                    }
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
