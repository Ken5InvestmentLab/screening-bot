"""Compile PRIVATE canonical observations/calendar into Worker code, no network.

The Worker imports this module internally; it never enters the ASSETS directory.
Future reminders retain today's observation cutoff (no future receipt lookup).
"""
from __future__ import annotations
import argparse
from datetime import date, timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from weak_early_beta.bank_calendar import is_bank_business_day
from weak_early_beta.ledger import read_ledger

SPEC = importlib.util.spec_from_file_location("canonical_adapter", Path(__file__).with_name("build-notification-events.py"))
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)

def build_calendar(first_year: int = 2025, last_year: int = 2030) -> dict:
    if not 2025 <= first_year <= last_year <= 2030:
        raise ValueError("reviewed calendar range required")
    start, end = date(first_year, 1, 1), date(last_year, 12, 31)
    closed, day = [], start
    while day <= end:
        if day.weekday() < 5 and not is_bank_business_day(day):
            closed.append(day.isoformat())
        day += timedelta(days=1)
    return {"start_date": start.isoformat(), "end_date": end.isoformat(), "closed_dates": closed,
        "source_sha256": hashlib.sha256((ROOT / "weak_early_beta/bank_calendar.py").read_bytes()).hexdigest()}

def build_manifest(ledger: pd.DataFrame, digest: str, as_of: pd.Timestamp) -> dict:
    events = ADAPTER.build_events(ledger, digest, as_of, include_future_reminders=True)
    if len(events) > 1000:
        raise ValueError("canonical manifest exceeds bounded import limit")
    return {"schema_version": 1, "adapter_version": "cloud-ledger-v1", "source_ledger_revision": digest,
        "observed_at": as_of.tz_convert("UTC").isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "events": events}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=ROOT / "weak_early_beta/state/detections.csv")
    parser.add_argument("--as-of", help="Timezone-aware actual observation cutoff; defaults to now")
    # Keep ad-hoc generation outside the checkout. Approved deploy workflows
    # explicitly select the private Worker module, never public ASSETS.
    parser.add_argument("--output", type=Path, default=ROOT.parent / "qa/private-notification-input/cloud-canonical-input.generated.ts")
    args = parser.parse_args()
    source, output = args.ledger.resolve(), args.output.resolve()
    if output == source or {"reports", "public"}.intersection(part.lower() for part in output.parts):
        raise ValueError("canonical input must stay outside public assets")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = build_manifest(read_ledger(source), digest, pd.Timestamp(args.as_of) if args.as_of else pd.Timestamp.now(tz="UTC"))
    calendar = build_calendar()
    encode = lambda value: json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("// PRIVATE generated Worker input. Never copy to ASSETS.\n"
        + "export const CANONICAL_MANIFEST = " + encode(manifest) + " as const;\n"
        + "export const BANK_CALENDAR = " + encode(calendar) + " as const;\n", encoding="utf-8")
    print(json.dumps({"events": len(manifest["events"]), "sent": 0, "calendar_range": [calendar["start_date"], calendar["end_date"]]}))

if __name__ == "__main__":
    main()
