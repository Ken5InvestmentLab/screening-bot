"""Receipts for the explicitly reviewed, pinned Cloud research price artifacts.

These artifacts contain already reconstructed nominal quotes and action-aware
trade records, not raw Yahoo bars. Never invent adjusted OHLC or split factors
to make them look like a fresh market-data download.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from functools import lru_cache
from typing import Any

import pandas as pd

from .bank_calendar import add_bank_business_days
from .trade_basis import PRICE_BASIS_VERSION, build_trade_economics


KIND = "REVIEWED_RESEARCH_NOMINAL_V1"
SOURCE_BASIS = "reviewed_research_nominal_actual"
ACTION_VERSION = "RESEARCH_EXPLICIT_HOLDING_ACTIONS_V1"
ACTION_SOURCE = "pinned_research_inputs.applied_actions"
PRICE_PACKAGE_SHA256 = "481a688c76f6d86c3741b016de510ca2deb5f52a4c61ba4ccd91977ed55be37d"
MODE_PACKAGE_SHA256 = "370e9c266319115b035808949b9fc5df3b2fe50f2f64b1dc9ce3f236714578d7"
PRICE_INPUT_SHA256 = "a388021bdc008975cbc442db38d2e3f319ac70baf6b27389180a3f070029ecae"
MODE_INPUT_SHA256 = "618cc3b0b5a71d6d60fa67cfa645bf6ae59aaac42cc5ebe01590c4c3ea91e849"
VERIFICATION_SCOPE = "pinned_research_receipt_replay_not_raw_market_refetch"


def record_digest(record: Any) -> str:
    return hashlib.sha256(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _positive(value: Any) -> bool:
    return not isinstance(value, bool) and math.isfinite(float(value)) and float(value) > 0


def _same(left: Any, right: Any) -> bool:
    return math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-7)


def verify_research_trade(record: Mapping[str, Any], *, endpoint: str = "OPEN6") -> dict[str, Any]:
    """Recompute dates, original shares/cost, all actions, proceeds and returns."""
    encoded = json.dumps(dict(record), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return dict(_verified_trade_cached(encoded, endpoint))


@lru_cache(maxsize=2048)
def _verified_trade_cached(encoded: str, endpoint: str) -> dict[str, Any]:
    record = json.loads(encoded)
    signal = pd.Timestamp(record["signal_date"]).normalize()
    entry = pd.Timestamp(add_bank_business_days(signal.date(), 1))
    exit = pd.Timestamp(add_bank_business_days(signal.date(), 6 if endpoint == "OPEN6" else 5))
    if (
        endpoint not in {"OPEN6", "BASE5"} or record["rule"] != endpoint
        or record["status"] != "resolved" or int(record["signal_year"]) != signal.year
        or record["entry_date"] != f"{entry:%Y-%m-%d}"
        or record["exit_date"] != f"{exit:%Y-%m-%d}"
        or record["scheduled_exit_date"] != f"{exit:%Y-%m-%d}"
        or record["reason"] != ("sixth_open_control" if endpoint == "OPEN6" else "fixed_session_close")
        or record["entry_shares"] != 100
        or record["holding_sessions"] != (6 if endpoint == "OPEN6" else 5)
        or not isinstance(record["applied_actions"], list)
    ):
        raise ValueError("research trade identity, schedule or endpoint is not verified")
    actions = pd.DataFrame(record["applied_actions"], columns=["effective_date", "ratio"])
    economics = build_trade_economics(
        entry, exit, record["entry_price"], record["exit_price"], actions,
        symbol=str(record["symbol"]), entry_shares=100, basis_date=exit,
        source_sha256=PRICE_INPUT_SHA256,
    )
    if json.loads(economics["applied_actions_json"]) != record["applied_actions"]:
        raise ValueError("research trade action coverage contains extra, repeated or unordered events")
    for stored, calculated in (("entry_cost_yen", "entry_cost_yen"), ("exit_shares", "exit_shares"),
                               ("exit_proceeds_yen", "exit_proceeds_yen"), ("gross_return", "gross_return"),
                               ("price_pl_yen", "one_hundred_shares_pl_yen")):
        if not _same(record[stored], economics[calculated]):
            raise ValueError(f"research trade arithmetic mismatch: {stored}")
    return economics


def research_price_evidence_verified(evidence: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    try:
        record = evidence["research_record"]
        if (
            evidence.get("provenance_kind") != KIND
            or evidence.get("source_price_basis") != SOURCE_BASIS
            or evidence.get("corporate_actions_version") != ACTION_VERSION
            or evidence.get("corporate_actions_source") != ACTION_SOURCE
            or evidence.get("source_sha256") != PRICE_INPUT_SHA256
            or evidence.get("source_package_sha256") != PRICE_PACKAGE_SHA256
            or evidence.get("source_member") != "inputs.json"
            or evidence.get("research_record_sha256") != record_digest(record)
            or evidence.get("verification_scope") != VERIFICATION_SCOPE
            or evidence.get("raw_market_refetched") is not False
            or evidence.get("basis_semantics") != "nominal_session_not_vendor_adjustment_snapshot"
            or record["signal_date"] != f"{pd.Timestamp(row['signal_date']):%Y-%m-%d}"
            or str(record["symbol"]) != str(row["symbol"])
            or evidence["basis_asof"] != evidence["session"]
            or "adjusted_price" in evidence or "split_factor" in evidence
        ):
            return False
        if evidence["field"] == "actual_close":
            return bool(
                evidence["source_record_path"] == f"prices/{evidence['source_record_index']}"
                and record["signal_usable"] is True and _positive(record["signal_close"])
                and _same(record["signal_close"], evidence["actual_price"])
                and evidence["peer_source_sha256"] == MODE_INPUT_SHA256
                and evidence["peer_package_sha256"] == MODE_PACKAGE_SHA256
                and evidence["peer_signal_identity"] == f"{record['signal_date']}|{record['symbol']}"
                and _same(evidence["peer_nominal_close"], record["signal_close"])
            )
        if evidence["field"] != "actual_open":
            return False
        verify_research_trade(record)
        stage = "DEV" if pd.Timestamp(record["signal_date"]).year <= 2025 else "EVAL"
        return bool(
            evidence["source_record_path"] == f"controls/{stage}/OPEN6/{evidence['source_record_index']}"
            and _same(record["exit_price"], evidence["actual_price"])
            and evidence["entry_session"] == record["entry_date"]
            and evidence["holding_actions"] == record["applied_actions"]
        )
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def research_entry_evidence_verified(entry: Mapping[str, Any], exit_evidence: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    try:
        record = exit_evidence["research_record"]
        return bool(
            research_price_evidence_verified(exit_evidence, row)
            and entry["source_sha256"] == PRICE_INPUT_SHA256
            and entry["research_record_sha256"] == exit_evidence["research_record_sha256"]
            and entry["source_field"] == "entry_price"
            and _same(entry["actual_open"], record["entry_price"])
            and _same(entry["actual_open"], row["sixth_entry_open"])
            and "adjusted_open" not in entry and "split_factor" not in entry
        )
    except (KeyError, TypeError, ValueError):
        return False


def _evidence(record: dict, *, field: str, record_index: int, observed_at: str) -> dict:
    signal = pd.Timestamp(record["signal_date"])
    session = signal if field == "actual_close" else pd.Timestamp(record["exit_date"])
    stage = "DEV" if signal.year <= 2025 else "EVAL"
    return {
        "provenance_kind": KIND, "session": f"{session:%Y-%m-%d}", "symbol": str(record["symbol"]),
        "field": field, "actual_price": float(record["signal_close"] if field == "actual_close" else record["exit_price"]),
        "basis_asof": f"{session:%Y-%m-%d}", "basis_semantics": "nominal_session_not_vendor_adjustment_snapshot",
        "price_basis": PRICE_BASIS_VERSION, "source_price_basis": SOURCE_BASIS,
        "corporate_actions_version": ACTION_VERSION, "corporate_actions_source": ACTION_SOURCE,
        "source_usable": True, "source_sha256": PRICE_INPUT_SHA256, "source_package_sha256": PRICE_PACKAGE_SHA256,
        "source_member": "inputs.json", "source_record_index": record_index,
        "source_record_path": f"prices/{record_index}" if field == "actual_close" else f"controls/{stage}/OPEN6/{record_index}",
        "research_record": record, "research_record_sha256": record_digest(record),
        "verification_scope": VERIFICATION_SCOPE, "raw_market_refetched": False,
    }


def build_research_receipts(row: Mapping[str, Any], price_record: dict, trade: dict, *,
                            price_index: int, trade_index: int, peer_close: float,
                            observed_at: str) -> dict[str, Any]:
    """Import only after the caller verifies both exact packages and manifests."""
    from .endpoint_receipts import SIXTH_PRICE_COLUMNS, signal_actual_close_verified, sixth_endpoint_verified, sixth_economics_verified

    observed = pd.Timestamp(observed_at)
    if pd.isna(observed) or observed.tzinfo is None or observed > pd.Timestamp.now(tz="UTC"):
        raise ValueError("research ingestion time must be timezone-aware and non-future")
    economics = verify_research_trade(trade)
    signal_evidence = _evidence(price_record, field="actual_close", record_index=price_index, observed_at=observed_at)
    signal_evidence.update({"peer_source_sha256": MODE_INPUT_SHA256, "peer_package_sha256": MODE_PACKAGE_SHA256,
                            "peer_signal_identity": f"{price_record['signal_date']}|{price_record['symbol']}",
                            "peer_nominal_close": float(peer_close)})
    exit_evidence = _evidence(trade, field="actual_open", record_index=trade_index, observed_at=observed_at)
    exit_evidence.update({"entry_session": trade["entry_date"], "holding_actions": trade["applied_actions"]})
    result = {"sixth_xtks_exit_date": pd.Timestamp(trade["exit_date"])}
    for prefix, price_column, evidence in (("signal_actual_close", "signal_actual_close", signal_evidence),
                                           ("sixth_xtks_exit", "sixth_xtks_exit_open", exit_evidence)):
        result.update({price_column: evidence["actual_price"], f"{prefix}_status": "verified",
                       f"{prefix}_observed_at": observed_at, f"{prefix}_source_sha256": PRICE_INPUT_SHA256,
                       f"{prefix}_price_basis": PRICE_BASIS_VERSION,
                       f"{prefix}_provenance_json": json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)})
    result.update({f"sixth_{column}": economics[column] for column in (
        "entry_date", "entry_open", "entry_shares", "entry_cost_yen", "gross_return", "one_hundred_shares_pl_yen",
        "exit_shares", "exit_proceeds_yen", "holding_action_factor", "applied_actions_json", "price_basis_date", "price_basis_source_sha256",
    )})
    result.update({"sixth_economics_status": "verified", "sixth_economics_issue": "", "sixth_economics_observed_at": observed_at})
    exit_receipt = {key: result[key].isoformat() if isinstance(result[key], pd.Timestamp) else result[key] for key in SIXTH_PRICE_COLUMNS}
    result["sixth_economics_provenance_json"] = json.dumps({
        "version": KIND, "source_sha256": PRICE_INPUT_SHA256,
        "entry": {"session": trade["entry_date"], "actual_open": float(trade["entry_price"]),
                  "basis_asof": trade["exit_date"], "source_sha256": PRICE_INPUT_SHA256,
                  "research_record_sha256": exit_evidence["research_record_sha256"], "source_field": "entry_price"},
        "exit_receipt": exit_receipt, "holding_actions": trade["applied_actions"],
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    merged = {**dict(row), **result}
    if not (signal_actual_close_verified(merged) and sixth_endpoint_verified(merged) and sixth_economics_verified(merged)):
        raise ValueError("research receipt does not match the target identity or verified endpoint contract")
    return result
