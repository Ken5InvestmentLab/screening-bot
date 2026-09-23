"""As-of historical fundamental backfill isolated from the live beta queue."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from .ledger import DEFAULT_LEDGER, read_ledger


ROOT = Path(__file__).resolve().parents[1]
WORKER_OUT = ROOT / "weak_early_beta" / "fundamental_worker" / "out"
DEFAULT_RECEIPTS = WORKER_OUT / "historical_backfill_receipts.json"
DEFAULT_MANIFEST = WORKER_OUT / "historical_backfill_manifest.json"
DEFAULT_BATCH = WORKER_OUT / "historical_backfill_batch.json"
DEFAULT_BATCH_REPORTS = WORKER_OUT / "historical_backfill_reports.json"
FIELD_ORDER = (
    "材料インパクト",
    "事業概要",
    "足元材料",
    "ファンダ要点",
    "注意点",
    "開示リンク",
    "Sources",
)
DETECTION_TIME = "16:15:00+09:00"


def _read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _iso_date(value) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def detection_cutoff(signal_date) -> str:
    """Use the beta runner's 16:15 JST scheduled scan as a fixed historical proxy."""
    return f"{_iso_date(signal_date)}T{DETECTION_TIME}"


def identity(signal_date, symbol: str) -> str:
    return f"{_iso_date(signal_date)}|{str(symbol).strip()}"


def _receipt_map(receipts: Iterable[dict]) -> dict[str, dict]:
    return {
        identity(
            item.get("signal_date", item.get("signalDate")),
            item.get("symbol", item.get("symbolCode", "")),
        ): item
        for item in receipts
    }


def _fields(report: dict) -> dict[str, str]:
    entries = report.get("fields", [])
    values = {
        str(field.get("name", "")).strip(): str(field.get("value", "")).strip()
        for field in entries
        if isinstance(field, dict)
    }
    return values


def validate_historical_report(report: dict) -> str:
    """Reject mismatched, incomplete, or post-detection evidence receipts."""
    signal_date = _iso_date(report["signalDate"])
    symbol = str(report["symbolCode"]).strip()
    if not symbol:
        raise ValueError("symbolCode is required")
    expected_cutoff = detection_cutoff(signal_date)
    if str(report.get("analysisCutoff", "")) != expected_cutoff:
        raise ValueError(
            f"analysisCutoff must equal the scheduled detection cutoff {expected_cutoff}"
        )

    fields = _fields(report)
    missing = [name for name in FIELD_ORDER if not fields.get(name)]
    if missing:
        raise ValueError(f"historical report is missing non-empty fields: {missing}")

    source_checks = report.get("sourceChecks", [])
    roles = {str(row.get("role", "")) for row in source_checks if isinstance(row, dict)}
    required_roles = {"official_ir", "irbank_or_tdnet"}
    if not required_roles.issubset(roles):
        raise ValueError("sourceChecks must cover official_ir and irbank_or_tdnet")
    for row in source_checks:
        if not isinstance(row, dict) or not str(row.get("url", "")).startswith("https://"):
            raise ValueError("every sourceChecks item must have an https URL")

    disclosures = report.get("disclosures", [])
    if not disclosures and not report.get("noMaterialDisclosureReason"):
        raise ValueError("a report with no selected disclosures must explain the verified absence")
    cutoff = pd.Timestamp(expected_cutoff)
    for disclosure in disclosures:
        if not isinstance(disclosure, dict):
            raise ValueError("disclosures must contain objects")
        required = ("title", "publishedAt", "url")
        if any(not str(disclosure.get(key, "")).strip() for key in required):
            raise ValueError(f"disclosure requires title, publishedAt, and url: {disclosure}")
        if not str(disclosure["url"]).startswith("https://"):
            raise ValueError("disclosure links must use https")
        published_at = pd.Timestamp(disclosure["publishedAt"])
        if published_at.tzinfo is None:
            raise ValueError("disclosure publishedAt must include a timezone")
        if published_at > cutoff:
            raise ValueError(
                f"post-detection disclosure rejected: {disclosure['publishedAt']} > {expected_cutoff}"
            )
        if disclosure.get("contentReviewed") is not True:
            raise ValueError("each selected primary disclosure must be marked contentReviewed")

    return identity(signal_date, symbol)


def build_manifest(
    ledger: pd.DataFrame,
    receipts: Iterable[dict] = (),
    generated_at: str | None = None,
) -> dict:
    """Build a resumable one-snapshot-per-date/symbol manifest."""
    if ledger.empty:
        records = []
    else:
        grouped = ledger.groupby(["signal_date", "symbol"], sort=True)
        receipt_lookup = _receipt_map(receipts)
        records = []
        for (signal_date, symbol), group in grouped:
            row_id = identity(signal_date, symbol)
            company_name = next(
                (
                    str(value).strip()
                    for value in group["company_name"]
                    if pd.notna(value) and str(value).strip() and str(value).lower() != "nan"
                ),
                "",
            )
            selectors = sorted(set(group["selector_name"].dropna().astype(str)))
            prior = receipt_lookup.get(row_id)
            if prior:
                try:
                    validate_historical_report(prior)
                    status = "complete"
                    receipt_hash = hashlib.sha256(
                        json.dumps(prior, ensure_ascii=False, sort_keys=True).encode("utf-8")
                    ).hexdigest()
                except (KeyError, TypeError, ValueError):
                    status = "needs_receipt_repair"
                    receipt_hash = ""
            elif group["fundamental_status"].astype(str).eq("complete").any():
                status = "legacy_needs_asof_audit"
                receipt_hash = ""
            else:
                status = "pending"
                receipt_hash = ""
            records.append({
                "identity": row_id,
                "signal_date": _iso_date(signal_date),
                "symbol": str(symbol),
                "company_name": company_name,
                "selector_names": selectors,
                "analysis_cutoff": detection_cutoff(signal_date),
                "status": status,
                "receipt_sha256": receipt_hash,
            })

    counts: dict[str, int] = {}
    for record in records:
        counts[record["status"]] = counts.get(record["status"], 0) + 1
    now = generated_at or pd.Timestamp.now(tz="Asia/Tokyo").isoformat()
    return {
        "identity": "WEAK_EARLY_HISTORICAL_FUNDAMENTALS_V1",
        "generated_at": now,
        "source_ledger": "weak_early_beta/state/detections.csv",
        "detection_time_basis": "scheduled daily beta scan at 16:15 JST; deterministic historical proxy",
        "as_of_rule": "only disclosures published at or before analysis_cutoff may be cited or used",
        "discord_policy": "historical analyses are not reposted to Discord",
        "total_identities": len(records),
        "status_counts": counts,
        "records": records,
    }


def select_batch(manifest: dict, limit: int = 4) -> list[dict]:
    if limit < 1:
        raise ValueError("limit must be positive")
    status_priority = {
        "legacy_needs_asof_audit": 0,
        "needs_receipt_repair": 1,
        "pending": 2,
    }
    pending = [
        record
        for record in manifest.get("records", [])
        if record["status"] in status_priority
    ]
    pending.sort(
        key=lambda record: (
            status_priority[record["status"]],
            record["signal_date"],
            record["symbol"],
        )
    )
    return pending[:limit]


def import_historical_reports(
    ledger: pd.DataFrame,
    reports: Iterable[dict],
) -> tuple[pd.DataFrame, list[dict]]:
    """Attach validated historical content without creating Discord receipts."""
    result = ledger.copy()
    for column in ("fundamental_status", "fundamental_html", "updated_at"):
        result[column] = result[column].astype("object")
    accepted = []
    for report in reports:
        row_id = validate_historical_report(report)
        signal_date = _iso_date(report["signalDate"])
        symbol = str(report["symbolCode"]).strip()
        mask = (
            pd.to_datetime(result["signal_date"]).dt.strftime("%Y-%m-%d").eq(signal_date)
            & result["symbol"].astype(str).eq(symbol)
        )
        if not mask.any():
            raise ValueError(f"historical report has no matching detection: {row_id}")
        fields = _fields(report)
        html = "\n\n".join(f"{name}\n{fields[name]}" for name in FIELD_ORDER)
        result.loc[mask, "fundamental_status"] = "complete_historical"
        result.loc[mask, "fundamental_html"] = html
        result.loc[mask, "updated_at"] = pd.Timestamp.now(tz="Asia/Tokyo").isoformat()
        accepted.append(report)
    return result, accepted


def merge_receipts(existing: dict, reports: Iterable[dict]) -> dict:
    """Upsert current snapshots while keeping a durable receipt audit log."""
    saved = {
        identity(item["signalDate"], item["symbolCode"]): item
        for item in existing.get("reports", [])
    }
    audit_log = list(existing.get("audit_log", []))
    imported_at = pd.Timestamp.now(tz="Asia/Tokyo").isoformat()
    for report in reports:
        row_id = validate_historical_report(report)
        previous = saved.get(row_id)
        previous_hash = (
            hashlib.sha256(
                json.dumps(previous, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()
            if previous
            else ""
        )
        current_hash = hashlib.sha256(
            json.dumps(report, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        audit_log.append({
            "identity": row_id,
            "imported_at": imported_at,
            "previous_receipt_sha256": previous_hash,
            "receipt_sha256": current_hash,
        })
        saved[row_id] = report
    return {
        "identity": "WEAK_EARLY_HISTORICAL_FUNDAMENTALS_RECEIPTS_V1",
        "updated_at": imported_at,
        "reports": [saved[key] for key in sorted(saved)],
        "audit_log": audit_log,
    }
