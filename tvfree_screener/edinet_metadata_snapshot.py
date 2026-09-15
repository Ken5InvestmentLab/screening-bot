"""Freeze a complete, outcome-blind EDINET metadata snapshot from daily JSON files.

This module deliberately does not call the EDINET API. Acquisition credentials and
network retry policy stay outside the research audit layer. The input is one raw
JSON response per calendar date; this tool verifies full preregistered coverage,
hashes every raw response, normalizes only the metadata fields required by the
frozen sample selector, and emits an immutable manifest/CSV pair.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd

DEFAULT_START = date(2023, 1, 1)
DEFAULT_END = date(2025, 12, 31)


def _optional_text(value: object) -> str:
    """Normalize nullable EDINET scalar text without turning JSON null into 'None'."""
    return "" if value is None else str(value).strip()


def _is_edinet_null_tombstone(item: dict[str, object]) -> bool:
    """Recognize the documented withdrawn/unavailable placeholder row shape.

    EDINET document-list history can retain a docID while nulling filing metadata
    and setting all downloadable-content/legal flags to 0. These rows cannot be
    part of the preregistered docType 120/130 sample. Any other malformed shape
    still fails closed.
    """
    zero_flags = ("xbrlFlag", "pdfFlag", "attachDocFlag", "englishDocFlag", "csvFlag", "legalStatus")
    return (
        item.get("docTypeCode") is None
        and item.get("submitDateTime") is None
        and str(item.get("disclosureStatus", "")) == "0"
        and all(str(item.get(name, "")) == "0" for name in zero_flags)
    )



def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: str | Path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


def _dates(start: date, end: date) -> Iterable[date]:
    if start > end:
        raise ValueError("start date must be <= end date")
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _parse_date(value: object, *, name: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{name} must be YYYY-MM-DD") from exc


def _extract_results(payload: object, *, source_date: date) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        raise ValueError(f"{source_date}: top-level EDINET response must be an object")

    metadata = payload.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            raise ValueError(f"{source_date}: metadata must be an object")
        status = metadata.get("status")
        # EDINET successful metadata responses use status 200. Accept numeric or
        # textual representation, but never silently accept a different status.
        if status is not None and str(status) != "200":
            raise ValueError(f"{source_date}: EDINET metadata status is not 200: {status!r}")

    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError(f"{source_date}: EDINET response results must be a list")
    return results


def freeze_metadata_snapshot(
    input_dir: str | Path,
    *,
    start: object = DEFAULT_START.isoformat(),
    end: object = DEFAULT_END.isoformat(),
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Validate and normalize an exact daily EDINET metadata snapshot.

    Expected file naming is ``YYYY-MM-DD.json`` for every calendar day in the
    requested interval. Missing days, malformed JSON, non-success metadata status,
    malformed result rows, and duplicate doc IDs fail closed.
    """

    start_date = _parse_date(start, name="start")
    end_date = _parse_date(end, name="end")
    root = Path(input_dir)
    if not root.is_dir():
        raise ValueError(f"input_dir does not exist or is not a directory: {root}")

    expected_dates = list(_dates(start_date, end_date))
    expected_names = {f"{d.isoformat()}.json" for d in expected_dates}
    available_names = {p.name for p in root.glob("*.json") if p.is_file()}
    missing = sorted(expected_names - available_names)
    if missing:
        preview = ", ".join(missing[:5])
        suffix = " ..." if len(missing) > 5 else ""
        raise ValueError(f"incomplete EDINET metadata date coverage; missing {len(missing)} day(s): {preview}{suffix}")

    rows: list[dict[str, object]] = []
    daily_files: list[dict[str, object]] = []
    excluded_tombstones: list[str] = []
    for source_date in expected_dates:
        path = root / f"{source_date.isoformat()}.json"
        raw = path.read_bytes()
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{source_date}: invalid JSON") from exc

        results = _extract_results(payload, source_date=source_date)
        daily_files.append(
            {
                "date": source_date.isoformat(),
                "file": path.name,
                "sha256": _sha256_bytes(raw),
                "result_rows": len(results),
            }
        )

        for idx, item in enumerate(results):
            if not isinstance(item, dict):
                raise ValueError(f"{source_date}: result row {idx} must be an object")
            doc_id = _optional_text(item.get("docID"))
            doc_type_code = _optional_text(item.get("docTypeCode"))
            submit_datetime = _optional_text(item.get("submitDateTime"))
            if not doc_id:
                raise ValueError(f"{source_date}: result row {idx} missing docID")
            if not doc_type_code or not submit_datetime:
                if _is_edinet_null_tombstone(item):
                    excluded_tombstones.append(
                        "|".join(
                            [
                                source_date.isoformat(),
                                doc_id,
                                _optional_text(item.get("withdrawalStatus")),
                                _optional_text(item.get("parentDocID")),
                            ]
                        )
                    )
                    continue
                raise ValueError(
                    f"{source_date}: result row {idx} missing docID/docTypeCode/submitDateTime"
                )
            try:
                submit_ts = pd.Timestamp(submit_datetime)
            except Exception as exc:  # pandas exposes several parser exception classes
                raise ValueError(f"{source_date}: invalid submitDateTime {submit_datetime!r}") from exc
            if submit_ts.tzinfo is None:
                # EDINET submitDateTime is Japan local time. Make the normalization
                # explicit so downstream selector input is timezone-aware.
                submit_ts = submit_ts.tz_localize("Asia/Tokyo")
            else:
                submit_ts = submit_ts.tz_convert("Asia/Tokyo")

            rows.append(
                {
                    "doc_id": doc_id,
                    "doc_type_code": doc_type_code,
                    "submit_datetime": submit_ts.isoformat(),
                    "source_date": source_date.isoformat(),
                }
            )

    frame = pd.DataFrame(rows, columns=["doc_id", "doc_type_code", "submit_datetime", "source_date"])
    if not frame.empty and frame["doc_id"].duplicated().any():
        duplicates = sorted(frame.loc[frame["doc_id"].duplicated(keep=False), "doc_id"].unique().tolist())
        raise ValueError(f"duplicate doc_id across daily EDINET metadata snapshot: {duplicates[:5]}")

    # Stable row order makes the emitted CSV hash reproducible independently of
    # filesystem enumeration order.
    frame = frame.sort_values(
        ["submit_datetime", "doc_id", "doc_type_code", "source_date"], kind="stable"
    ).reset_index(drop=True)

    aggregate_material = "\n".join(
        f"{entry['date']} {entry['sha256']}" for entry in daily_files
    ).encode("utf-8")
    manifest: dict[str, object] = {
        "status": "EDINET_METADATA_SNAPSHOT_COMPLETE_OUTCOME_BLIND",
        "coverage": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "expected_calendar_days": len(expected_dates),
            "observed_calendar_days": len(daily_files),
            "full_period_pass": True,
        },
        "raw_daily_files": daily_files,
        "raw_daily_hash_chain_sha256": _sha256_bytes(aggregate_material),
        "normalized_rows": int(len(frame)),
        "normalized_columns": ["doc_id", "doc_type_code", "submit_datetime", "source_date"],
        "excluded_document_list_rows": {
            "edinet_null_tombstone_count": len(excluded_tombstones),
            "edinet_null_tombstone_sha256": _sha256_bytes("\n".join(excluded_tombstones).encode("utf-8")),
            "policy": "skip only documented null-metadata rows with disclosureStatus=0 and all content/legal flags=0; all other malformed rows fail closed",
        },
        "strategy_outcomes_opened": False,
        "parser_outputs_used_for_selection": False,
    }
    return frame, manifest


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", required=True)
    p.add_argument("--start", default=DEFAULT_START.isoformat())
    p.add_argument("--end", default=DEFAULT_END.isoformat())
    p.add_argument("--metadata-output", required=True)
    p.add_argument("--manifest-output", required=True)
    a = p.parse_args()

    frame, manifest = freeze_metadata_snapshot(a.input_dir, start=a.start, end=a.end)

    metadata_path = Path(a.metadata_output)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(metadata_path, index=False)
    manifest["normalized_csv"] = {
        "path": str(metadata_path),
        "sha256": _sha256(metadata_path),
    }

    manifest_path = Path(a.manifest_output)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
