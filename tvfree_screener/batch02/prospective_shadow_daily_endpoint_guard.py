from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Mapping

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PLACEHOLDERS = {"", "TODO", "TBD", "UNKNOWN", "PLACEHOLDER", "N/A"}
PURPOSE = "PROSPECTIVE_SHADOW_5BD_ENDPOINTS"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_aware_iso(value: object, field: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return dt


def _normalize_symbol(value: object) -> str:
    return str(value or "").strip().replace(".0", "").upper()


def _scan_daily_csv(path: Path) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    dates: list[str] = []

    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = set(reader.fieldnames or [])
        required = {"symbol", "date", "open", "close"}
        missing = sorted(required - fields)
        if missing:
            return [], {
                "row_count": 0,
                "first_date": None,
                "last_date": None,
                "symbol_count": 0,
                "duplicate_key_count": 0,
                "invalid_row_count": 0,
                "errors": [f"required_columns_missing:{','.join(missing)}"],
            }

        for row_number, row in enumerate(reader, start=2):
            symbol = _normalize_symbol(row.get("symbol"))
            date_text = str(row.get("date", ""))[:10]
            invalid = False
            if not symbol:
                errors.append(f"row_{row_number}:empty_symbol")
                invalid = True
            try:
                datetime.strptime(date_text, "%Y-%m-%d")
            except ValueError:
                errors.append(f"row_{row_number}:invalid_date")
                invalid = True

            key = (symbol, date_text)
            if key in seen:
                errors.append(f"row_{row_number}:duplicate_symbol_date:{symbol}|{date_text}")
            else:
                seen.add(key)

            normalized = {
                "symbol": symbol,
                "date": date_text,
                "open": row.get("open"),
                "close": row.get("close"),
            }

            for field in ("open", "close"):
                raw = row.get(field)
                if raw in (None, ""):
                    continue
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    errors.append(f"row_{row_number}:{field}_not_numeric")
                    invalid = True
                    continue
                if not math.isfinite(value) or value <= 0:
                    errors.append(f"row_{row_number}:{field}_not_finite_positive")
                    invalid = True

            if not invalid:
                rows.append(normalized)
                dates.append(date_text)

    duplicate_count = sum(1 for error in errors if "duplicate_symbol_date" in error)
    invalid_count = sum(1 for error in errors if "duplicate_symbol_date" not in error)
    return rows, {
        "row_count": len(rows),
        "first_date": min(dates) if dates else None,
        "last_date": max(dates) if dates else None,
        "symbol_count": len({r["symbol"] for r in rows}),
        "duplicate_key_count": duplicate_count,
        "invalid_row_count": invalid_count,
        "errors": errors,
    }


def build_daily_endpoint_manifest(
    csv_path: Path,
    *,
    dataset_id: str,
    source_name: str,
    source_kind: str,
    acquired_at: str,
    price_adjustment_semantics: str,
) -> dict:
    for field, value in {
        "dataset_id": dataset_id,
        "source_name": source_name,
        "source_kind": source_kind,
        "price_adjustment_semantics": price_adjustment_semantics,
    }.items():
        text = str(value or "").strip()
        if text.upper() in PLACEHOLDERS:
            raise ValueError(f"{field} must be explicit and non-placeholder")
    _parse_aware_iso(acquired_at, "acquired_at")
    _, stats = _scan_daily_csv(csv_path)
    if stats["errors"]:
        raise ValueError("daily endpoint CSV is not structurally valid: " + ";".join(stats["errors"][:10]))

    return {
        "manifest_version": 1,
        "purpose": PURPOSE,
        "dataset_id": str(dataset_id).strip(),
        "source_name": str(source_name).strip(),
        "source_kind": str(source_kind).strip(),
        "acquired_at": str(acquired_at),
        "price_adjustment_semantics": str(price_adjustment_semantics).strip(),
        "csv_sha256": _sha256_file(csv_path),
        "row_count": stats["row_count"],
        "symbol_count": stats["symbol_count"],
        "first_date": stats["first_date"],
        "last_date": stats["last_date"],
        "immutable_input": True,
        "production_authorized": False,
    }


def validate_daily_endpoint_dataset(csv_path: Path, manifest: Mapping) -> dict:
    errors: list[str] = []

    if manifest.get("manifest_version") != 1:
        errors.append("manifest_version_must_be_1")
    if manifest.get("purpose") != PURPOSE:
        errors.append("purpose_mismatch")
    for field in ("dataset_id", "source_name", "source_kind", "price_adjustment_semantics"):
        value = str(manifest.get(field, "")).strip()
        if value.upper() in PLACEHOLDERS:
            errors.append(f"{field}_missing_or_placeholder")

    try:
        _parse_aware_iso(manifest.get("acquired_at"), "acquired_at")
    except ValueError as exc:
        errors.append(str(exc))

    expected_sha = str(manifest.get("csv_sha256", "")).strip().lower()
    if not SHA256_RE.fullmatch(expected_sha):
        errors.append("manifest_csv_sha256_invalid")
    actual_sha = _sha256_file(csv_path)
    if expected_sha and expected_sha != actual_sha:
        errors.append("daily_csv_sha256_mismatch")

    rows, stats = _scan_daily_csv(csv_path)
    errors.extend(stats["errors"])

    expected = {
        "row_count": stats["row_count"],
        "symbol_count": stats["symbol_count"],
        "first_date": stats["first_date"],
        "last_date": stats["last_date"],
    }
    for field, actual in expected.items():
        if manifest.get(field) != actual:
            errors.append(f"{field}_mismatch")

    if manifest.get("immutable_input") is not True:
        errors.append("immutable_input_must_be_true")
    if manifest.get("production_authorized") is not False:
        errors.append("production_authorized_must_be_false")

    valid = not errors
    return {
        "endpoint_dataset_valid": valid,
        "decision": "ALLOW_DAILY_ENDPOINT_DATASET" if valid else "BLOCK_DAILY_ENDPOINT_DATASET",
        "dataset_id": manifest.get("dataset_id"),
        "source_name": manifest.get("source_name"),
        "source_kind": manifest.get("source_kind"),
        "acquired_at": manifest.get("acquired_at"),
        "price_adjustment_semantics": manifest.get("price_adjustment_semantics"),
        "csv_sha256": actual_sha,
        "row_count": stats["row_count"],
        "symbol_count": stats["symbol_count"],
        "first_date": stats["first_date"],
        "last_date": stats["last_date"],
        "errors": errors,
        "integrity": {
            "exact_csv_sha_pinned": True,
            "dataset_provenance_required": True,
            "acquisition_time_timezone_aware": True,
            "symbol_date_uniqueness_required": True,
            "positive_finite_present_prices_required": True,
            "price_adjustment_semantics_declared": True,
            "production_modified": False,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Create or verify prospective-shadow daily endpoint provenance manifests")
    sub = ap.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("--daily", type=Path, required=True)
    create.add_argument("--dataset-id", required=True)
    create.add_argument("--source-name", required=True)
    create.add_argument("--source-kind", required=True)
    create.add_argument("--acquired-at", required=True)
    create.add_argument("--price-adjustment-semantics", required=True)
    create.add_argument("--output", type=Path, required=True)

    verify = sub.add_parser("verify")
    verify.add_argument("--daily", type=Path, required=True)
    verify.add_argument("--manifest", type=Path, required=True)

    args = ap.parse_args()
    if args.command == "create":
        manifest = build_daily_endpoint_manifest(
            args.daily,
            dataset_id=args.dataset_id,
            source_name=args.source_name,
            source_kind=args.source_kind,
            acquired_at=args.acquired_at,
            price_adjustment_semantics=args.price_adjustment_semantics,
        )
        raw = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
        print(raw, end="")
        return

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = validate_daily_endpoint_dataset(args.daily, manifest)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if result["endpoint_dataset_valid"] else 2)


if __name__ == "__main__":
    main()
