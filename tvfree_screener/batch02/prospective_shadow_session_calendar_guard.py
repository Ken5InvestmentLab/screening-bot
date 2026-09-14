from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Iterable

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_xtks_calendar(
    csv_path: Path,
    manifest_path: Path,
    required_signal_dates: Iterable[str] = (),
) -> tuple[list[str], dict]:
    errors: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [], {
            "calendar_valid": False,
            "decision": "BLOCK_SESSION_CALENDAR",
            "errors": [f"manifest_load_failed:{exc}"],
        }

    if manifest.get("calendar_id") != "XTKS":
        errors.append("calendar_id_must_be_XTKS")

    expected_sha = str(manifest.get("csv_sha256", "")).strip().lower()
    if not SHA256_RE.fullmatch(expected_sha):
        errors.append("manifest_csv_sha256_invalid")
    actual_sha = sha256_file(csv_path)
    if expected_sha and expected_sha != actual_sha:
        errors.append("calendar_csv_sha256_mismatch")

    sessions: list[str] = []
    indices: list[int] = []
    try:
        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None or not {"date", "session_index"}.issubset(set(reader.fieldnames)):
                errors.append("calendar_csv_required_columns_missing")
            else:
                for row_number, row in enumerate(reader, start=2):
                    text = str(row.get("date", "")).strip()
                    try:
                        parsed = date.fromisoformat(text)
                    except ValueError:
                        errors.append(f"invalid_session_date_row_{row_number}")
                        continue
                    try:
                        idx = int(str(row.get("session_index", "")).strip())
                    except ValueError:
                        errors.append(f"invalid_session_index_row_{row_number}")
                        continue
                    sessions.append(parsed.isoformat())
                    indices.append(idx)
    except Exception as exc:
        errors.append(f"calendar_csv_load_failed:{exc}")

    if len(sessions) != len(set(sessions)):
        errors.append("duplicate_session_dates")
    if sessions != sorted(sessions):
        errors.append("session_dates_not_strictly_sorted")
    if indices and indices != list(range(len(indices))):
        errors.append("session_indices_not_zero_based_contiguous")

    expected_count = manifest.get("session_count")
    if expected_count != len(sessions):
        errors.append("session_count_mismatch")
    if sessions:
        if manifest.get("first_session") != sessions[0]:
            errors.append("first_session_mismatch")
        if manifest.get("last_session") != sessions[-1]:
            errors.append("last_session_mismatch")

    index_by_date = {session: i for i, session in enumerate(sessions)}
    missing_required: list[str] = []
    insufficient_horizon: list[str] = []
    for raw in required_signal_dates:
        signal_date = str(raw)[:10]
        i = index_by_date.get(signal_date)
        if i is None:
            missing_required.append(signal_date)
        elif i + 5 >= len(sessions):
            insufficient_horizon.append(signal_date)
    if missing_required:
        errors.append("required_signal_dates_missing")
    if insufficient_horizon:
        errors.append("required_signal_dates_lack_5bd_horizon")

    valid = not errors
    return sessions, {
        "calendar_valid": valid,
        "decision": "ALLOW_XTKS_SESSION_CALENDAR" if valid else "BLOCK_SESSION_CALENDAR",
        "calendar_id": manifest.get("calendar_id"),
        "generator": manifest.get("generator"),
        "generator_version": manifest.get("generator_version"),
        "session_count": len(sessions),
        "first_session": sessions[0] if sessions else None,
        "last_session": sessions[-1] if sessions else None,
        "calendar_csv_sha256": actual_sha,
        "required_signal_dates_checked": len(set(str(x)[:10] for x in required_signal_dates)),
        "missing_required_signal_dates": sorted(set(missing_required)),
        "insufficient_5bd_horizon_signal_dates": sorted(set(insufficient_horizon)),
        "errors": errors,
        "integrity": {
            "calendar_sha_pinned": True,
            "strictly_sorted_unique_sessions": True,
            "zero_based_contiguous_indices": True,
            "manifest_count_and_bounds_checked": True,
            "required_signal_dates_must_exist": True,
            "five_session_horizon_required": True,
            "does_not_infer_sessions_from_market_data": True,
            "production_modified": False,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate the frozen XTKS session calendar before prospective-shadow 5BD resolution")
    ap.add_argument("--sessions-csv", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--signal-date", action="append", default=[])
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    _, result = validate_xtks_calendar(args.sessions_csv, args.manifest, args.signal_date)
    raw = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    print(raw, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    raise SystemExit(0 if result["calendar_valid"] else 2)


if __name__ == "__main__":
    main()
