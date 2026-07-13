#!/usr/bin/env python3
"""Block report generation until today's premium snapshots are posted."""

from __future__ import annotations

import argparse
import os
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import optimize_screener as opt
from generate_mega_validation_report import PREMIUM_LOG_SPREADSHEET_ID_DEFAULT


JST = ZoneInfo("Asia/Tokyo")
DATE_PREFIX_RE = re.compile(r"^\s*(\d{4})[\/.-](\d{1,2})[\/.-](\d{1,2})")


def cell(row: list[str], index: int) -> str:
    return str(row[index]).strip() if 0 <= index < len(row) else ""


def columns(rows: list[list[str]], header_row: int, required: tuple[str, ...]) -> dict[str, int]:
    if len(rows) <= header_row:
        raise RuntimeError(f"sheet has no header row {header_row + 1}")

    header = [str(value).strip().lower() for value in rows[header_row]]
    missing = [name for name in required if name not in header]
    if missing:
        raise RuntimeError(f"sheet is missing required columns: {', '.join(missing)}")
    return {name: header.index(name) for name in required}


def normalized_date_prefix(value: str) -> str:
    match = DATE_PREFIX_RE.match(str(value or ""))
    if not match:
        return ""

    year, month, day = (int(part) for part in match.groups())
    try:
        parsed = datetime(year, month, day)
    except ValueError:
        return ""
    return parsed.strftime("%Y-%m-%d")


def expected_bottom_alert_ids(rows: list[list[str]], target_date: str) -> set[str]:
    col = columns(rows, 3, ("alert_id", "received_at", "signal_type"))
    result: set[str] = set()
    for row in rows[4:]:
        alert_id = cell(row, col["alert_id"])
        if not alert_id:
            continue
        if cell(row, col["signal_type"]).upper() != "BOTTOM":
            continue
        if normalized_date_prefix(cell(row, col["received_at"])) != target_date:
            continue
        result.add(alert_id)
    return result


def posted_bottom_alert_ids(rows: list[list[str]]) -> set[str]:
    col = columns(rows, 0, ("event_type", "alert_id", "signal_type"))
    result: set[str] = set()
    for row in rows[1:]:
        if cell(row, col["event_type"]).upper() != "POSTED":
            continue
        if cell(row, col["signal_type"]).upper() not in ("", "BOTTOM"):
            continue
        alert_id = cell(row, col["alert_id"])
        if alert_id:
            result.add(alert_id)
    return result


def fetch_premium_log_rows(service, spreadsheet_id: str, sheet_name: str) -> list[list[str]]:
    response = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"{sheet_name}!A:K")
        .execute()
    )
    return response.get("values", [])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target-date",
        default=datetime.now(JST).strftime("%Y-%m-%d"),
        help="JST signal date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--max-wait-seconds",
        type=int,
        default=int(os.environ.get("PREMIUM_SNAPSHOT_WAIT_SECONDS", "3600")),
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=int(os.environ.get("PREMIUM_SNAPSHOT_POLL_SECONDS", "30")),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        target_date = datetime.strptime(args.target_date, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError as err:
        raise SystemExit(f"invalid --target-date: {err}") from err
    if args.max_wait_seconds <= 0 or args.poll_seconds <= 0:
        raise SystemExit("wait and poll durations must be positive")

    premium_spreadsheet_id = os.environ.get(
        "PREMIUM_LOG_SPREADSHEET_ID",
        PREMIUM_LOG_SPREADSHEET_ID_DEFAULT,
    ).strip()
    premium_sheet_name = os.environ.get("PREMIUM_LOG_SHEET_NAME", "premium_alert_log").strip()
    if not premium_spreadsheet_id or not premium_sheet_name:
        raise SystemExit("premium log spreadsheet configuration is empty")

    service = opt.get_service()
    expected = expected_bottom_alert_ids(opt.fetch(service, "alerts_raw"), target_date)
    if not expected:
        print(f"No BOTTOM alerts found for {target_date}; premium snapshot barrier is clear")
        return 0

    print(f"Waiting for {len(expected)} premium snapshot POSTED event(s) for {target_date}")
    deadline = time.monotonic() + args.max_wait_seconds
    last_missing: set[str] | None = None
    last_error = ""

    while True:
        try:
            rows = fetch_premium_log_rows(service, premium_spreadsheet_id, premium_sheet_name)
            posted = posted_bottom_alert_ids(rows)
            missing = expected - posted
            last_error = ""
            if not missing:
                print(f"Premium snapshot barrier cleared: {len(expected)} of {len(expected)} POSTED")
                return 0
            if missing != last_missing:
                print(
                    f"Premium snapshot pending: {len(expected) - len(missing)} of {len(expected)} POSTED; "
                    f"missing={','.join(sorted(missing))}"
                )
                last_missing = missing
        except Exception as err:
            last_error = str(err)
            print(f"::warning::Premium log read failed; retrying: {last_error}")

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            detail = (
                f"missing={','.join(sorted(last_missing or expected))}"
                if not last_error
                else f"last_error={last_error}"
            )
            print(
                f"::error::Premium snapshot barrier timed out after {args.max_wait_seconds}s; "
                f"{detail}. Report generation and Discord notice are blocked."
            )
            return 1
        time.sleep(min(args.poll_seconds, remaining))


if __name__ == "__main__":
    raise SystemExit(main())
