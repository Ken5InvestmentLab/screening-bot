"""Explicit, read-only report overlay; never imported by daily ledger loading.

The private artifact contains one receipt per signal and an immutable-baseline
hash per eligible mode. A changed historical baseline requires a new review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import pandas as pd

from .endpoint_receipts import (
    ENDPOINT_COLUMNS, ENDPOINT_DATE_COLUMNS, ENDPOINT_NUMBER_COLUMNS, ENDPOINT_TEXT_COLUMNS,
    preserve_verified_endpoints, signal_actual_close_verified, sixth_endpoint_verified,
    sixth_economics_verified,
)
from .ledger import EXIT_REMINDER_COLUMNS, LEDGER_COLUMNS
from .research_price_receipts import VERIFICATION_SCOPE
from .research_price_receipts import PRICE_PACKAGE_SHA256, MODE_PACKAGE_SHA256
from .trade_basis import LEGACY_PRICE_BASIS_VERSION


SCHEMA = "CLOUD_REVIEWED_ENDPOINT_OVERLAY_V1"
DEFAULT_OVERLAY = Path(__file__).resolve().parent / "state" / "reviewed_endpoint_receipts.v1.json"
# Pinned after replaying the two approved research packages. This is private
# server/build input; neither this artifact nor its manifest is a public asset.
DEFAULT_OVERLAY_SHA256 = "a4af8311918ab34ab0ebf7346b3f75a44f3d00e303be81d2e6fc1c88c6824411"
_MUTABLE_COLUMNS = {
    "company_name", "selector_name", "signal_discord_url", "notified_at", "fundamental_status",
    "fundamental_discord_url", "fundamental_html", "created_at", "updated_at",
    *EXIT_REMINDER_COLUMNS, "d5_price_observed_at",
}
BASELINE_COLUMNS = [column for column in LEDGER_COLUMNS if column not in {*ENDPOINT_COLUMNS, *_MUTABLE_COLUMNS}]
_BASELINE_DATES = {"signal_date", "entry_date", "fifth_xtks_exit_date"}
_BASELINE_TEXT = {
    "detection_id", "symbol", "selector_id", "model_period", "status", "source_scope", "source_sha256",
    "price_basis", "price_basis_date", "price_basis_source_sha256", "applied_actions_json",
}


def _blank(value) -> bool:
    return value is None or pd.isna(value) or value == ""


def _plain(value):
    if _blank(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if hasattr(value, "item"):
        return value.item()
    return value


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def baseline_digest(row) -> str:
    values = {}
    for column in BASELINE_COLUMNS:
        value = row.get(column)
        if column == "price_basis" and _blank(value) and str(row.get("source_scope", "")).startswith("EXACT_CANONICAL"):
            value = LEGACY_PRICE_BASIS_VERSION
        if _blank(value):
            values[column] = None
        elif column in _BASELINE_DATES:
            values[column] = pd.Timestamp(value).strftime("%Y-%m-%d")
        elif column in _BASELINE_TEXT:
            values[column] = str(value)
        else:
            number = float(value)
            if not math.isfinite(number):
                raise ValueError(f"nonfinite immutable baseline: {column}")
            values[column] = number
    return hashlib.sha256(_json_bytes(values)).hexdigest()


def _identity(row) -> str:
    return f"{pd.Timestamp(row['signal_date']):%Y-%m-%d}|{row['symbol']}"


def build_reviewed_endpoint_overlay(original: pd.DataFrame, reviewed: pd.DataFrame, *, audit: dict) -> tuple[bytes, dict]:
    """Build a deduplicated sidecar only after the explicit backfill succeeded."""
    if original.detection_id.duplicated().any() or reviewed.detection_id.duplicated().any():
        raise ValueError("duplicate detection identity in overlay input")
    source = original.set_index("detection_id", drop=False)
    if set(source.index) != set(reviewed.detection_id):
        raise ValueError("overlay backfill changed the detection identity set")
    records = {}
    for _, row in reviewed.iterrows():
        prior = source.loc[row["detection_id"]]
        if baseline_digest(prior) != baseline_digest(row):
            raise ValueError("overlay backfill changed an immutable original column")
        if not all(check(row) for check in (signal_actual_close_verified, sixth_endpoint_verified, sixth_economics_verified)):
            continue
        if not str(prior.get("source_scope", "")).startswith("EXACT_CANONICAL"):
            raise ValueError("research overlay cannot adopt a forward observation")
        identity = _identity(row)
        receipts = {column: _plain(row.get(column)) for column in ENDPOINT_COLUMNS}
        if identity not in records:
            records[identity] = {"identity": identity, "receipts": receipts, "target_modes": {}}
        elif records[identity]["receipts"] != receipts:
            raise ValueError(f"mode receipts disagree for one research identity: {identity}")
        records[identity]["target_modes"][str(row["detection_id"])] = baseline_digest(prior)
    package = {
        "schema": SCHEMA, "verification_scope": VERIFICATION_SCOPE, "raw_market_refetched": False,
        "baseline_columns": BASELINE_COLUMNS, "input_ledger_sha256": audit["input_ledger_sha256"],
        "source_packages": [{key: receipt[key] for key in ("bytes", "sha256", "manifest_sha256", "members_verified")}
                            for receipt in audit["source_packages"]],
        "observed_at": audit["observed_at"], "records": records,
    }
    encoded = _json_bytes(package)
    manifest = {
        "schema": SCHEMA, "artifact": DEFAULT_OVERLAY.name, "bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(), "signal_identities": len(records),
        "mode_rows": sum(len(record["target_modes"]) for record in records.values()),
        "input_ledger_sha256": audit["input_ledger_sha256"], "source_packages": package["source_packages"],
        "verification_scope": VERIFICATION_SCOPE, "raw_market_refetched": False,
        "known_2026_is_historical_reuse": True, "d5_economics_modified": False,
        "original_ledger_modified": False, "notifications_sent": 0,
    }
    return encoded, manifest


def load_reviewed_endpoint_overlay(path: Path = DEFAULT_OVERLAY, *, expected_sha256: str = DEFAULT_OVERLAY_SHA256) -> dict:
    """Read and verify exactly once per report generation; a missing file fails closed."""
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("reviewed endpoint overlay SHA-256 mismatch")
    package = json.loads(raw)
    if package.get("schema") != SCHEMA or package.get("baseline_columns") != BASELINE_COLUMNS:
        raise ValueError("unsupported reviewed endpoint overlay schema/baseline")
    if package.get("verification_scope") != VERIFICATION_SCOPE or package.get("raw_market_refetched") is not False:
        raise ValueError("incorrect reviewed endpoint overlay verification scope")
    return package


def apply_reviewed_endpoint_overlay(frame: pd.DataFrame, overlay: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """Explicit report-only join. Never mutates its input or writes a ledger.

    Pass a loaded overlay to reuse one file read for full/free/mode reports.
    Missing/unlisted/new modes are untouched. An altered reviewed baseline or
    conflicting verified receipt aborts adoption. Quarantines stay untouched.
    """
    package = load_reviewed_endpoint_overlay() if overlay is None else overlay
    if package.get("schema") != SCHEMA or package.get("baseline_columns") != BASELINE_COLUMNS:
        raise ValueError("unsupported reviewed endpoint overlay")
    if frame.detection_id.duplicated().any():
        raise ValueError("duplicate detection identities in report ledger")
    result = frame.copy(deep=True)
    for column in ENDPOINT_COLUMNS:
        if column not in result:
            result[column] = pd.NaT if column in ENDPOINT_DATE_COLUMNS else (float("nan") if column in ENDPOINT_NUMBER_COLUMNS else "")
        elif column in [*ENDPOINT_TEXT_COLUMNS, *ENDPOINT_DATE_COLUMNS]:
            result[column] = result[column].astype(object)
    counts = Counter()
    for index, row in result.iterrows():
        record = package["records"].get(_identity(row))
        if record is None or str(row["detection_id"]) not in record["target_modes"]:
            counts["unmatched_untouched"] += 1
            continue
        if not str(row.get("source_scope", "")).startswith("EXACT_CANONICAL") or baseline_digest(row) != record["target_modes"][str(row["detection_id"])]:
            raise ValueError(f"reviewed endpoint baseline changed: {row['detection_id']}")
        if any(row.get(column) in ("quarantined", "review_required") for column in
               ("signal_actual_close_status", "sixth_xtks_exit_status", "sixth_economics_status")):
            counts["review_untouched"] += 1
            continue
        receipts = record["receipts"]
        if set(receipts) != set(ENDPOINT_COLUMNS):
            raise ValueError("overlay attempts to write outside independent endpoint columns")
        candidate = {**dict(row), **receipts}
        if not all(check(candidate) for check in (signal_actual_close_verified, sixth_endpoint_verified, sixth_economics_verified)):
            raise ValueError(f"invalid reviewed endpoint receipt: {row['detection_id']}")
        if signal_actual_close_verified(row) and not math.isclose(float(row["signal_actual_close"]), float(candidate["signal_actual_close"]), rel_tol=1e-12, abs_tol=1e-10):
            raise ValueError(f"conflicting reviewed signal close: {row['detection_id']}")
        if sixth_economics_verified(row):
            economic_numbers = [column for column in ENDPOINT_NUMBER_COLUMNS if column.startswith("sixth_")]
            if any(not math.isclose(float(row[column]), float(candidate[column]), rel_tol=1e-12, abs_tol=1e-8)
                   for column in economic_numbers):
                raise ValueError(f"conflicting reviewed D6 economics: {row['detection_id']}")
        preserved = preserve_verified_endpoints(row, candidate)
        if preserved.get("sixth_xtks_exit_status") == "quarantined":
            raise ValueError(f"conflicting reviewed D6 receipt: {row['detection_id']}")
        for column in ENDPOINT_COLUMNS:
            value = preserved.get(column)
            result.at[index, column] = pd.to_datetime(value) if column in ENDPOINT_DATE_COLUMNS else value
        counts["applied"] += 1
    old_columns = [column for column in frame if column not in ENDPOINT_COLUMNS]
    pd.testing.assert_frame_equal(frame[old_columns], result[old_columns])
    return result, {"schema": SCHEMA, "counts": dict(counts), "d5_economics_modified": False,
                    "original_ledger_modified": False, "verification_scope": VERIFICATION_SCOPE}


def main() -> None:
    """Create a new private overlay from an already audited, separate CSV."""
    from .ledger import read_ledger

    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("ledger", "reviewed-ledger", "audit", "output", "manifest"):
        parser.add_argument(f"--{flag}", required=True)
    args = parser.parse_args()
    inputs = [Path(value).resolve(strict=True) for value in (args.ledger, args.reviewed_ledger, args.audit)]
    outputs = [Path(value).resolve() for value in (args.output, args.manifest)]
    if len(set(inputs + outputs)) != 5 or any(path.exists() for path in outputs):
        raise ValueError("overlay creation requires distinct inputs and new output files")
    input_bytes = [path.read_bytes() for path in inputs]
    audit = json.loads(input_bytes[2])
    if audit.get("schema") != "CLOUD_PINNED_RESEARCH_ENDPOINT_BACKFILL_V1" or audit.get("csv_readback_all_receipts_verified") is not True:
        raise ValueError("overlay requires a successful research backfill with CSV readback")
    if (hashlib.sha256(input_bytes[0]).hexdigest() != audit.get("input_ledger_sha256") or
            hashlib.sha256(input_bytes[1]).hexdigest() != audit.get("output_ledger_sha256")):
        raise ValueError("overlay input ledger does not match its reviewed audit")
    if {receipt["sha256"] for receipt in audit["source_packages"]} != {PRICE_PACKAGE_SHA256, MODE_PACKAGE_SHA256}:
        raise ValueError("overlay source packages differ from reviewed research")
    raw, reviewed = read_ledger(inputs[0]), read_ledger(inputs[1])
    encoded, manifest = build_reviewed_endpoint_overlay(raw, reviewed, audit=audit)
    restored, applied = apply_reviewed_endpoint_overlay(raw, json.loads(encoded))
    for verifier in (signal_actual_close_verified, sixth_endpoint_verified, sixth_economics_verified):
        if restored.apply(verifier, axis=1).tolist() != reviewed.apply(verifier, axis=1).tolist():
            raise ValueError("overlay replay changed receipt verification coverage")
    manifest["replay"] = applied
    created = []
    try:
        for path, content in zip(outputs, (encoded, _json_bytes(manifest))):
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as handle:
                created.append(path)
                handle.write(content)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    if any(path.read_bytes() != original for path, original in zip(inputs, input_bytes)):
        raise RuntimeError("overlay input changed concurrently; do not adopt output")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
