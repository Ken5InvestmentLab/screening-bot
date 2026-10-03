"""Pinned, report-only actual D5 economics; canonical D5 is never rewritten."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path

import pandas as pd

from .research_price_receipts import (
    PRICE_INPUT_SHA256, PRICE_PACKAGE_SHA256, MODE_PACKAGE_SHA256,
    VERIFICATION_SCOPE, record_digest, verify_research_trade,
)
from .reviewed_endpoint_overlay import baseline_digest, BASELINE_COLUMNS
from .trade_basis import ECONOMIC_COLUMNS, PRICE_BASIS_VERSION, is_frozen_trade, preserve_completed_economics

SCHEMA = "CLOUD_REVIEWED_ACTUAL_D5_OVERLAY_V1"
RECEIPT_COLUMN = "reviewed_d5_receipt_json"
DEFAULT_OVERLAY = Path(__file__).resolve().parent / "state" / "reviewed_actual_d5.v1.json"
DEFAULT_OVERLAY_SHA256 = "e1ad97ad0c97c23967af88af3d6b38d1250b268a72f75a1f8beede6fa03be29f"


def _identity(row) -> str:
    return f"{pd.Timestamp(row['signal_date']):%Y-%m-%d}|{row['symbol']}"


def _encoded(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf8")


@lru_cache(maxsize=2048)
def _checked_receipt(encoded: str, identity: str) -> dict:
    receipt = json.loads(encoded)
    record = receipt["record"]
    if (receipt.get("schema") != SCHEMA or receipt.get("identity") != identity
            or _identity(record) != identity
            or receipt.get("source_input_sha256") != PRICE_INPUT_SHA256
            or receipt.get("source_package_sha256") != PRICE_PACKAGE_SHA256
            or receipt.get("peer_package_sha256") != MODE_PACKAGE_SHA256
            or receipt.get("record_sha256") != record_digest(record)
            or receipt.get("verification_scope") != VERIFICATION_SCOPE
            or receipt.get("raw_market_refetched") is not False
            or receipt.get("cost_yen") != 0
            or receipt.get("source_record_path") != f"controls/{'DEV' if int(record['signal_year']) <= 2025 else 'EVAL'}/BASE5/{receipt['source_record_index']}"):
        raise ValueError("invalid actual D5 presentation receipt")
    observed = pd.Timestamp(receipt["observed_at"])
    exit_day = pd.Timestamp(record["exit_date"])
    earliest = pd.Timestamp(year=exit_day.year, month=exit_day.month, day=exit_day.day,
                            hour=15, minute=30 if exit_day >= pd.Timestamp("2024-11-05") else 0, tz="Asia/Tokyo")
    if observed.tzinfo is None or observed < earliest or observed > pd.Timestamp.now(tz="UTC"):
        raise ValueError("D5 receipt predates its actual close or has a future import time")
    return verify_research_trade(record, endpoint="BASE5")


def actual_d5_economics(row) -> dict | None:
    """Require verified nominal evidence, or an existing actual forward snapshot."""
    receipt = row.get(RECEIPT_COLUMN)
    if isinstance(receipt, str) and receipt:
        try:
            return dict(_checked_receipt(receipt, _identity(row)))
        except (ValueError, TypeError, KeyError, OverflowError):
            return None
    original = dict(row)
    for column in ECONOMIC_COLUMNS:
        if "raw_d5_" + column in row:
            original[column] = row["raw_d5_" + column]
    try:
        if is_frozen_trade(original):
            return {column: original[column] for column in ECONOMIC_COLUMNS}
    except (ValueError, TypeError, KeyError):
        # A malformed marked snapshot is unavailable in this read-only view;
        # the canonical loader/updater retains its strict corruption checks.
        return None
    return None


def actual_forward_entry(row) -> dict | None:
    """Keep a validated acquired lot while its D5 endpoint is still pending."""
    receipt = row.get(RECEIPT_COLUMN)
    if isinstance(receipt, str) and receipt:
        return None  # A rejected historical receipt cannot become a forward lot.
    original = dict(row)
    for column in ECONOMIC_COLUMNS:
        if "raw_d5_" + column in row:
            original[column] = row["raw_d5_" + column]
    if (str(original.get("source_scope", "")) != "FORWARD_CAUSAL"
            or original.get("price_basis") != PRICE_BASIS_VERSION
            or original.get("status") != "entered"):
        return None
    try:
        # Use the canonical acquired-lot validation without changing the source.
        checked = preserve_completed_economics(original, original)
        return {column: checked[column] for column in (
            "entry_date", "entry_open", "entry_shares", "entry_cost_yen",
            "price_basis_date", "price_basis_source_sha256",
        )}
    except (ValueError, TypeError, KeyError):
        return None


def apply_reviewed_d5_overlay(frame: pd.DataFrame, package: dict | None = None) -> tuple[pd.DataFrame, dict]:
    if package is None:
        raw = DEFAULT_OVERLAY.read_bytes()
        if hashlib.sha256(raw).hexdigest() != DEFAULT_OVERLAY_SHA256:
            raise ValueError("actual D5 sidecar SHA-256 mismatch")
        package = json.loads(raw)
    if package.get("schema") != SCHEMA or package.get("baseline_columns") != BASELINE_COLUMNS:
        raise ValueError("unsupported actual D5 sidecar schema")
    if frame.detection_id.duplicated().any():
        raise ValueError("duplicate detection identity in D5 presentation input")
    result = frame.copy(deep=True)
    result[RECEIPT_COLUMN] = ""
    applied = 0
    for index, row in frame.iterrows():
        record = package["records"].get(_identity(row))
        if record is None or str(row["detection_id"]) not in record["target_modes"]:
            continue
        if not str(row.get("source_scope", "")).startswith("EXACT_CANONICAL") or baseline_digest(row) != record["target_modes"][str(row["detection_id"])]:
            raise ValueError(f"actual D5 immutable baseline changed: {row['detection_id']}")
        if any(row.get(column) in ("quarantined", "review_required") for column in ("signal_actual_close_status", "sixth_xtks_exit_status", "sixth_economics_status")):
            continue
        receipt = _encoded(record["receipt"]).decode("utf8")
        economics = _checked_receipt(receipt, _identity(row))
        # A verified D6 must start from exactly the same acquired lot; only
        # actions through the fifth session belong to the D5 holding period.
        from .endpoint_receipts import sixth_economics_verified
        if sixth_economics_verified(row):
            for field in ("entry_open", "entry_shares", "entry_cost_yen"):
                if not math.isclose(float(economics[field]), float(row['sixth_' + field]), rel_tol=1e-9, abs_tol=1e-7):
                    raise ValueError("D5/D6 actual acquired lots disagree")
            prefix = [a for a in json.loads(row["sixth_applied_actions_json"]) if a["effective_date"] <= f"{economics['fifth_xtks_exit_date']:%Y-%m-%d}"]
            if prefix != json.loads(economics["applied_actions_json"]):
                raise ValueError("D5/D6 actual holding-action prefix disagrees")
        result.at[index, RECEIPT_COLUMN] = receipt
        applied += 1
    pd.testing.assert_frame_equal(result[frame.columns], frame)
    return result, {"schema": SCHEMA, "applied_mode_rows": applied, "canonical_d5_modified": False, "cost_yen": 0}


def build_sidecar(frame, evidence, *, observed_at, source_packages, input_ledger_sha256):
    records = {}
    for _, row in frame.iterrows():
        identity = _identity(row)
        if not str(row.get("source_scope", "")).startswith("EXACT_CANONICAL") or identity not in evidence["trades"]["BASE5"]:
            continue
        index, trade = evidence["trades"]["BASE5"][identity]
        receipt = {"schema": SCHEMA, "identity": identity, "record": trade, "record_sha256": record_digest(trade),
                   "source_input_sha256": PRICE_INPUT_SHA256, "source_package_sha256": PRICE_PACKAGE_SHA256,
                   "peer_package_sha256": MODE_PACKAGE_SHA256, "source_record_index": index,
                   "source_record_path": f"controls/{'DEV' if int(trade['signal_year']) <= 2025 else 'EVAL'}/BASE5/{index}",
                   "verification_scope": VERIFICATION_SCOPE, "raw_market_refetched": False,
                   "observed_at": observed_at, "cost_yen": 0}
        _checked_receipt(_encoded(receipt).decode("utf8"), identity)
        records.setdefault(identity, {"receipt": receipt, "target_modes": {}})["target_modes"][str(row["detection_id"])] = baseline_digest(row)
    package = {"schema": SCHEMA, "baseline_columns": BASELINE_COLUMNS, "records": records,
               "source_packages": source_packages, "input_ledger_sha256": input_ledger_sha256,
               "canonical_d5_modified": False, "cost_yen": 0, "raw_market_refetched": False}
    return _encoded(package)


def main():
    from .ledger import read_ledger
    from .research_endpoint_backfill import verified_zip, validate_research_inputs
    from .research_price_receipts import MODE_INPUT_SHA256
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("ledger", "price-comparison-zip", "mode-research-zip", "output"):
        parser.add_argument('--' + flag, type=Path, required=True)
    args = parser.parse_args()
    inputs = [p.resolve(strict=True) for p in (args.ledger, args.price_comparison_zip, args.mode_research_zip)]
    output = args.output.resolve()
    if output.exists() or output in inputs:
        raise ValueError("D5 sidecar requires a new output distinct from its preserved inputs")
    comparison, price_receipt = verified_zip(inputs[1], PRICE_PACKAGE_SHA256, "manifest.json")
    mode, mode_receipt = verified_zip(inputs[2], MODE_PACKAGE_SHA256, "MANIFEST.json")
    compact = mode["legacy_mode_sizing_v1/compact_inputs.json"]
    if hashlib.sha256(comparison["inputs.json"]).hexdigest() != PRICE_INPUT_SHA256 or hashlib.sha256(compact).hexdigest() != MODE_INPUT_SHA256:
        raise ValueError("pinned D5 source member changed")
    evidence = validate_research_inputs(json.loads(comparison["inputs.json"]), json.loads(compact), json.loads(comparison["results.json"]))
    before = [p.read_bytes() for p in inputs]
    frame = read_ledger(inputs[0])
    # Reuse the reviewed mode set rather than extending historical eligibility.
    from .reviewed_endpoint_overlay import load_reviewed_endpoint_overlay
    mode_ids = {key for r in load_reviewed_endpoint_overlay()["records"].values() for key in r["target_modes"]}
    eligible = frame[frame.detection_id.isin(mode_ids)]
    raw = build_sidecar(eligible, evidence, observed_at=pd.Timestamp.now(tz="UTC").isoformat(), source_packages=[price_receipt,mode_receipt], input_ledger_sha256=hashlib.sha256(before[0]).hexdigest())
    apply_reviewed_d5_overlay(frame, json.loads(raw))
    if before != [p.read_bytes() for p in inputs]:
        raise ValueError("D5 source changed concurrently")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as handle:
        handle.write(raw)
    print(json.dumps({"path":str(output),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"signals":len(json.loads(raw)["records"]),"mode_rows":len(eligible),"canonical_d5_modified":False}))


if __name__ == '__main__':
    main()
