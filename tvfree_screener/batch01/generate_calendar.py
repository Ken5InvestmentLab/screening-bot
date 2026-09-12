"""Generate and freeze a reviewed XTKS calendar for historical batch01 work."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import exchange_calendars as xc
import pandas as pd


DEFAULT_START = "2022-01-04"
DEFAULT_END = "2026-12-30"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "reference" / "xtks_sessions.csv"
JPX_REFERENCE = "https://www.jpx.co.jp/english/corporate/about-jpx/calendar/"
JPX_TRADING_RULES = "https://www.jpx.co.jp/english/equities/trading/domestic/01.html"


def generate(start: str, end: str, output: Path) -> dict[str, object]:
    calendar = xc.get_calendar("XTKS", start=start, end=end)
    sessions = calendar.sessions_in_range(start, end)
    frame = pd.DataFrame({
        "date": sessions.strftime("%Y-%m-%d"),
        "session_index": range(len(sessions)),
    })
    if frame.empty or frame["date"].duplicated().any():
        raise ValueError("generated XTKS calendar is empty or duplicated")
    generated_days = set(frame["date"])
    # JPX's published cash-equity calendar identifies these holidays. These
    # sentinels also catch the common Saturday/Sunday-only calendar mistake.
    if {"2024-01-08", "2026-09-22"} & generated_days:
        raise ValueError("calendar included a JPX-published market holiday")
    if "2024-01-09" not in generated_days or "2024-01-05" not in generated_days:
        raise ValueError("calendar omitted an expected ordinary XTKS session")

    output.parent.mkdir(parents=True, exist_ok=True)
    csv_bytes = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    output.write_bytes(csv_bytes)
    digest = hashlib.sha256(csv_bytes).hexdigest()
    manifest = {
        "calendar_id": "XTKS",
        "generator": "exchange_calendars",
        "generator_version": xc.__version__,
        "source_urls": [JPX_REFERENCE, JPX_TRADING_RULES],
        "date_range": {"start": start, "end": end},
        "session_count": int(len(frame)),
        "first_session": str(frame.iloc[0]["date"]),
        "last_session": str(frame.iloc[-1]["date"]),
        "csv_sha256": digest,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "reviewed_holiday_sentinels": ["2024-01-08", "2026-09-22"],
        "status": "frozen historical plus known 2026 forward sessions; refresh from reviewed JPX source before later forward runs",
    }
    manifest_path = output.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = generate(args.start, args.end, args.output)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
