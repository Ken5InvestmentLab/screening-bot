"""Build local dry-run candidates from the canonical ledger; never send/import.

Output is PRIVATE server input, not a public report asset. Dates use the same
calendar and receipt verifiers as the report. Research reconstructions are never
notification candidates. This script has no network or D1 write path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd
from weak_early_beta.bank_calendar import add_bank_business_days, is_bank_business_day
from weak_early_beta.endpoint_receipts import signal_actual_close_verified, sixth_endpoint_verified
from weak_early_beta.forward_price_overlay import apply_reviewed_forward_close
from weak_early_beta.ledger import read_ledger
from weak_early_beta.trade_basis import is_frozen_trade


def build_events(ledger: pd.DataFrame, source_sha256: str, as_of: pd.Timestamp) -> list[dict]:
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    if not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
        raise ValueError("source ledger SHA-256 is required")
    today = as_of.tz_convert("Asia/Tokyo").date()
    if not is_bank_business_day(today):
        return []
    # Use the same reviewed signal-price view as the report. The observation
    # cutoff below prevents this later receipt from being available earlier.
    # The original ledger revision and canonical bytes remain unchanged.
    ledger = apply_reviewed_forward_close(ledger)
    events = []
    seen_signals: dict[str, dict] = {}
    for _, row in ledger.iterrows():
        if row.get("source_scope") != "FORWARD_CAUSAL":
            continue
        signal = pd.Timestamp(row["signal_date"]).date()
        if signal.year == 2022 or signal > today:
            continue
        fifth = add_bank_business_days(signal, 5).isoformat()
        sixth = add_bank_business_days(signal, 6).isoformat()
        # Refuse recorded dates that contradict the authoritative calendar.
        for column, expected in (("fifth_xtks_exit_date", fifth), ("sixth_xtks_exit_date", sixth)):
            value = row.get(column)
            if pd.notna(value) and pd.Timestamp(value).date().isoformat() != expected:
                raise ValueError(f"endpoint date mismatch: {row['detection_id']} {column}")
        signal_verified = signal_actual_close_verified(row)
        d6_verified = sixth_endpoint_verified(row)
        signal_observed = pd.Timestamp(row.get("signal_actual_close_observed_at")) if signal_verified else None
        d6_observed = pd.Timestamp(row.get("sixth_xtks_exit_observed_at")) if d6_verified else None
        signal_verified = signal_verified and signal_observed <= as_of
        d6_verified = d6_verified and d6_observed <= as_of
        d5_observed = pd.Timestamp(row.get("d5_price_observed_at"))
        close_time = "15:00" if fifth < "2024-11-05" else "15:30"
        d5_verified = bool(is_frozen_trade(row) and pd.notna(d5_observed) and d5_observed.tzinfo is not None
            and pd.Timestamp(f"{fifth}T{close_time}:00+09:00") <= d5_observed <= as_of
            and re.fullmatch(r"[0-9a-f]{64}", str(row.get("price_basis_source_sha256", ""))))
        base = {
            "adapter_version": "cloud-ledger-v1", "source_ledger_revision": source_sha256,
            # A stock detected by several modes remains one notification.
            "signal_id": f"{signal.isoformat()}|{row['symbol']}", "detection_date": signal.isoformat(),
            "signal_actual_close": float(row["signal_actual_close"]) if signal_verified else None,
            "signal_price_status": "verified" if signal_verified else "missing",
            "endpoints": {
                # Existing frozen D5 rows without an acquisition timestamp stay
                # missing. updated_at can move when D6 is appended; never use it.
                "d5_close": {"date": fifth,
                             "actual_price": float(row["fifth_xtks_exit_close"]) if d5_verified else None,
                             "status": "verified" if d5_verified else "missing",
                             "fetched_at": d5_observed.isoformat() if d5_verified else None,
                             "source": str(row["price_basis_source_sha256"]) if d5_verified else None},
                "d6_open": {"date": sixth,
                            "actual_price": float(row["sixth_xtks_exit_open"]) if d6_verified else None,
                            "status": "verified" if d6_verified else "missing",
                            "fetched_at": d6_observed.isoformat() if d6_verified else None,
                            "source": str(row["sixth_xtks_exit_source_sha256"]) if d6_verified else None},
            },
        }
        prior = seen_signals.get(base["signal_id"])
        if prior is not None:
            if prior != base:
                raise ValueError(f"conflicting overlapping endpoint receipts: {base['signal_id']}")
            continue
        seen_signals[base["signal_id"]] = base
        if signal == today:
            events.append({**base, "kind": "new_detection"})
        if today.isoformat() in {fifth, sixth}:
            events.append({**base, "kind": "reminder"})
    return events


def build_sql_plan(events: list[dict], source_sha256: str, as_of: pd.Timestamp) -> str:
    """Produce a private, reviewable import plan. Never connect to or execute D1."""
    if as_of.tzinfo is None or not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
        raise ValueError("timezone-aware cutoff and source SHA-256 are required")
    quote = lambda text: "'" + str(text).replace("'", "''") + "'"
    statements = ["-- PRIVATE canonical notification plan. No execution or sending.", "BEGIN TRANSACTION;"]
    available = as_of.tz_convert("UTC").isoformat(timespec="milliseconds").replace("+00:00", "Z")
    seen = set()
    for event in events:
        if event.get("adapter_version") != "cloud-ledger-v1" or event.get("source_ledger_revision") != source_sha256 or event.get("kind") not in {"new_detection", "reminder"}:
            raise ValueError("canonical event evidence is required")
        # Immutable signal/kind identity; a later ledger revision does not create
        # another alert. The dispatch receipt key is independent of this revision.
        identity = str(event["signal_id"]) + ":" + str(event["kind"])
        key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        if key in seen:
            raise ValueError("duplicate canonical notification event")
        seen.add(key)
        payload = json.dumps(event, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
        statements.append("INSERT INTO cloud_notification_events (source_event_key,event_json,available_at,source_ledger_revision) VALUES ("
            + ",".join(quote(value) for value in (key, payload, available, source_sha256))
            + ") ON CONFLICT(source_event_key) DO UPDATE SET event_json=excluded.event_json, source_ledger_revision=excluded.source_ledger_revision;" )
    statements.append("COMMIT;")
    return "\n".join(statements) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--as-of", required=True, help="Timezone-aware observation cutoff")
    parser.add_argument("--sql-plan", type=Path, help="Optional private SQL file for review only; no execution")
    args = parser.parse_args()
    ledger_path, output_path = args.ledger.resolve(), args.output.resolve()
    if ledger_path == output_path:
        raise ValueError("output must not overwrite the ledger")
    if {"public", "reports"}.intersection(part.lower() for part in output_path.parts):
        raise ValueError("notification candidates must not be written to public assets")
    plan_path = args.sql_plan.resolve() if args.sql_plan else None
    if plan_path and (plan_path in {ledger_path, output_path} or {"public", "reports"}.intersection(part.lower() for part in plan_path.parts)):
        raise ValueError("SQL plan must be separate from source/output and public assets")
    digest = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    events = build_events(read_ledger(ledger_path), digest, pd.Timestamp(args.as_of))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({"schema_version": 1, "delivery_mode": "dry_run",
        "source_ledger_revision": digest, "events": events}, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")
    if plan_path:
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(build_sql_plan(events, digest, pd.Timestamp(args.as_of)), encoding="utf-8")
    print(json.dumps({"events": len(events), "sent": 0, "source_ledger_revision": digest}))


if __name__ == "__main__":
    main()
