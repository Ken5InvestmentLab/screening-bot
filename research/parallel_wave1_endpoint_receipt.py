#!/usr/bin/env python3
"""Outcome-blind Parallel Wave-1 endpoint completeness verifier.

This tool NEVER computes returns. It binds:
  pinned XTKS calendar bytes + frozen daily-source bytes + causal pick-ledger bytes
to deterministic signal -> next XTKS open -> fifth XTKS close endpoint keys.

It fails closed on any hash/schema/session/endpoint-integrity mismatch.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

CALENDAR_SHA256 = "58e67bd20be08d04c143fa7e8f707bb3b82c21c2de2af9dfd7c2a05a406de71b"
DAILY_SHA256 = "6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0"
DAILY_HEADER = ["date", "open", "high", "low", "close", "volume", "symbol"]
PICKS_HEADER = ["family", "signal_date", "symbol"]
ALLOWED_FAMILIES = {"A1", "B1", "E1"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_sha(rows: list[dict]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def finite_positive(value: str) -> bool:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(x) and x > 0


def load_calendar(path: Path) -> tuple[list[str], dict[str, int]]:
    if sha256_file(path) != CALENDAR_SHA256:
        raise SystemExit("FAIL_CLOSED: pinned XTKS calendar SHA-256 mismatch")
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header != ["session"]:
            raise SystemExit(f"FAIL_CLOSED: calendar header mismatch: {header!r}")
        sessions = [row[0] for row in reader if row]
    if not sessions or sessions != sorted(sessions) or len(sessions) != len(set(sessions)):
        raise SystemExit("FAIL_CLOSED: calendar sessions must be unique and strictly ordered")
    return sessions, {d: i for i, d in enumerate(sessions)}


def load_picks(path: Path, session_index: dict[str, int], sessions: list[str]) -> tuple[list[dict], str]:
    pick_sha = sha256_file(path)
    rows: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != PICKS_HEADER:
            raise SystemExit(f"FAIL_CLOSED: pick-ledger header mismatch: {reader.fieldnames!r}")
        for row in reader:
            family = (row["family"] or "").strip()
            signal = (row["signal_date"] or "").strip()
            symbol = (row["symbol"] or "").strip()
            if family not in ALLOWED_FAMILIES or not symbol or signal not in session_index:
                raise SystemExit(f"FAIL_CLOSED: invalid pick row: {row!r}")
            key = (family, signal, symbol)
            if key in seen:
                raise SystemExit(f"FAIL_CLOSED: duplicate pick row: {key!r}")
            seen.add(key)
            i = session_index[signal]
            if i + 5 >= len(sessions):
                raise SystemExit(f"FAIL_CLOSED: calendar lacks fifth-close horizon for {key!r}")
            rows.append({
                "family": family,
                "signal_date": signal,
                "symbol": symbol,
                "entry_session": sessions[i + 1],
                "exit_session": sessions[i + 5],
            })
    rows.sort(key=lambda r: (r["signal_date"], r["family"], r["symbol"]))
    return rows, pick_sha


def verify_daily_endpoints(path: Path, endpoint_rows: list[dict]) -> dict:
    if sha256_file(path) != DAILY_SHA256:
        raise SystemExit("FAIL_CLOSED: frozen daily source SHA-256 mismatch")

    wanted: dict[tuple[str, str], set[str]] = {}
    for row in endpoint_rows:
        wanted.setdefault((row["symbol"], row["entry_session"]), set()).add("open")
        wanted.setdefault((row["symbol"], row["exit_session"]), set()).add("close")

    found: set[tuple[str, str, str]] = set()
    duplicate_keys: set[tuple[str, str]] = set()
    seen_keys: set[tuple[str, str]] = set()

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != DAILY_HEADER:
            raise SystemExit(f"FAIL_CLOSED: daily header mismatch: {reader.fieldnames!r}")
        for row in reader:
            key = ((row["symbol"] or "").strip(), (row["date"] or "").strip())
            if key in wanted:
                if key in seen_keys:
                    duplicate_keys.add(key)
                seen_keys.add(key)
                for col in wanted[key]:
                    if not finite_positive(row[col]):
                        raise SystemExit(f"FAIL_CLOSED: invalid {col} for endpoint {key!r}")
                    found.add((key[0], key[1], col))

    if duplicate_keys:
        raise SystemExit(f"FAIL_CLOSED: duplicate endpoint symbol/date rows: {sorted(duplicate_keys)[:10]!r}")

    missing = []
    for (symbol, session), cols in sorted(wanted.items()):
        for col in sorted(cols):
            if (symbol, session, col) not in found:
                missing.append({"symbol": symbol, "session": session, "column": col})
    if missing:
        raise SystemExit("FAIL_CLOSED: missing endpoint rows/columns: " + json.dumps(missing[:20], ensure_ascii=False))

    endpoint_keys = [
        {
            "family": r["family"],
            "signal_date": r["signal_date"],
            "symbol": r["symbol"],
            "entry_session": r["entry_session"],
            "exit_session": r["exit_session"],
        }
        for r in endpoint_rows
    ]
    return {
        "pick_count": len(endpoint_rows),
        "endpoint_key_count": len(wanted),
        "endpoint_keys_sha256": canonical_sha(endpoint_keys),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calendar", type=Path, required=True)
    ap.add_argument("--daily", type=Path, required=True)
    ap.add_argument("--picks", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    sessions, session_index = load_calendar(args.calendar)
    endpoint_rows, pick_sha = load_picks(args.picks, session_index, sessions)
    verified = verify_daily_endpoints(args.daily, endpoint_rows)

    receipt = {
        "contract_version": 1,
        "status": "PASS_ENDPOINT_SESSION_COMPLETENESS",
        "performance_opened": False,
        "return_computed": False,
        "transaction_cost_pct": 0.0,
        "win_definition": "gross_return > 0",
        "calendar": {
            "path": str(args.calendar),
            "sha256": CALENDAR_SHA256,
            "first_session": sessions[0],
            "last_session": sessions[-1],
            "session_count": len(sessions),
        },
        "daily_source": {"path": str(args.daily), "sha256": DAILY_SHA256},
        "pick_ledger": {"path": str(args.picks), "sha256": pick_sha},
        "endpoint_contract": "signal -> next XTKS open -> fifth XTKS close (entry counts as session 1)",
        **verified,
    }
    args.out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
