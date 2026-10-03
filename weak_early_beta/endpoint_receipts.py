"""Independent, verified detection-close and sixth-session-open receipts.

The legacy signal_close and D5 economics are deliberately never migrated here.
An observed D6 open can unlock a row even when its trade economics need review.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from typing import Any

import pandas as pd

from .bank_calendar import add_bank_business_days
from .corporate_actions import ACTION_SOURCE, PRICE_BASIS as SOURCE_PRICE_BASIS, VERSION as ACTION_VERSION
from .trade_basis import PRICE_BASIS_VERSION, UnsupportedFractionalShares, build_trade_economics, is_frozen_trade


SIGNAL_ACTUAL_COLUMNS = [
    "signal_actual_close", "signal_actual_close_status", "signal_actual_close_observed_at",
    "signal_actual_close_source_sha256", "signal_actual_close_price_basis",
    "signal_actual_close_provenance_json",
]
SIXTH_PRICE_COLUMNS = [
    "sixth_xtks_exit_date", "sixth_xtks_exit_open", "sixth_xtks_exit_status",
    "sixth_xtks_exit_observed_at", "sixth_xtks_exit_source_sha256",
    "sixth_xtks_exit_price_basis", "sixth_xtks_exit_provenance_json",
]
SIXTH_ECONOMIC_COLUMNS = [
    "sixth_economics_status", "sixth_entry_date", "sixth_entry_open",
    "sixth_entry_shares", "sixth_entry_cost_yen", "sixth_gross_return",
    "sixth_one_hundred_shares_pl_yen", "sixth_exit_shares",
    "sixth_exit_proceeds_yen", "sixth_holding_action_factor",
    "sixth_applied_actions_json", "sixth_price_basis_date",
    "sixth_price_basis_source_sha256", "sixth_economics_observed_at",
    "sixth_economics_issue",
]
ENDPOINT_COLUMNS = [*SIGNAL_ACTUAL_COLUMNS, *SIXTH_PRICE_COLUMNS, *SIXTH_ECONOMIC_COLUMNS]
ENDPOINT_DATE_COLUMNS = ["sixth_xtks_exit_date", "sixth_entry_date"]
ENDPOINT_NUMBER_COLUMNS = [
    "signal_actual_close", "sixth_xtks_exit_open", "sixth_entry_open", "sixth_entry_shares",
    "sixth_entry_cost_yen", "sixth_gross_return", "sixth_one_hundred_shares_pl_yen",
    "sixth_exit_shares", "sixth_exit_proceeds_yen", "sixth_holding_action_factor",
]
ENDPOINT_TEXT_COLUMNS = [
    column for column in ENDPOINT_COLUMNS
    if column not in ENDPOINT_DATE_COLUMNS and column not in ENDPOINT_NUMBER_COLUMNS
]


def _positive(value: Any) -> bool:
    try:
        return not isinstance(value, bool) and math.isfinite(float(value)) and float(value) > 0
    except (TypeError, ValueError):
        return False


def _earliest_observation(session: pd.Timestamp, field: str) -> pd.Timestamp:
    # A reminder before the opening auction cannot be a result receipt.
    minutes = 9 * 60 if field == "actual_open" else (15 * 60 + (30 if session >= pd.Timestamp("2024-11-05") else 0))
    return pd.Timestamp(year=session.year, month=session.month, day=session.day,
                        hour=minutes // 60, minute=minutes % 60, tz="Asia/Tokyo")


def _price_verified(row: Mapping[str, Any], prefix: str, price_column: str) -> bool:
    """Fail closed for old, missing, malformed or merely scheduled endpoints."""
    try:
        observed = pd.Timestamp(row.get(f"{prefix}_observed_at"))
        evidence = json.loads(str(row.get(f"{prefix}_provenance_json", "")))
        endpoint_date = pd.Timestamp(
            row.get("signal_date" if prefix == "signal_actual_close" else "sixth_xtks_exit_date")
        ).normalize()
        field = "actual_close" if prefix == "signal_actual_close" else "actual_open"
        signal = pd.Timestamp(row.get("signal_date")).normalize()
        expected_date = signal if field == "actual_close" else pd.Timestamp(add_bank_business_days(signal.date(), 6))
        return bool(
            row.get(f"{prefix}_status") == "verified"
            and _positive(row.get(price_column))
            and row.get(f"{prefix}_price_basis") == PRICE_BASIS_VERSION
            and re.fullmatch(r"[0-9a-f]{64}", str(row.get(f"{prefix}_source_sha256", "")))
            and pd.notna(observed) and observed.tzinfo is not None
            and observed <= pd.Timestamp.now(tz="UTC")
            and pd.notna(endpoint_date)
            and endpoint_date == expected_date
            and observed >= _earliest_observation(endpoint_date, field)
            and evidence.get("symbol") == str(row.get("symbol"))
            and evidence.get("session") == f"{endpoint_date:%Y-%m-%d}"
            and evidence.get("field") == ("actual_close" if prefix == "signal_actual_close" else "actual_open")
            and evidence.get("source_sha256") == row.get(f"{prefix}_source_sha256")
            and evidence.get("price_basis") == PRICE_BASIS_VERSION
            and evidence.get("source_price_basis") == SOURCE_PRICE_BASIS
            and evidence.get("corporate_actions_version") == ACTION_VERSION
            and evidence.get("corporate_actions_source") == ACTION_SOURCE
            and evidence.get("source_usable") is True
            and pd.Timestamp(evidence["basis_asof"]) >= endpoint_date
            and pd.Timestamp(evidence["basis_asof"]).date() <= observed.tz_convert("Asia/Tokyo").date()
            and _positive(evidence.get("adjusted_price")) and _positive(evidence.get("split_factor"))
            and math.isclose(float(evidence["adjusted_price"]) * float(evidence["split_factor"]), float(row[price_column]), rel_tol=1e-9)
            and math.isclose(float(evidence["actual_price"]), float(row[price_column]), rel_tol=1e-9)
        )
    except (TypeError, ValueError, KeyError, AttributeError):
        return False


def signal_actual_close_verified(row: Mapping[str, Any]) -> bool:
    return _price_verified(row, "signal_actual_close", "signal_actual_close")


def sixth_endpoint_verified(row: Mapping[str, Any]) -> bool:
    return _price_verified(row, "sixth_xtks_exit", "sixth_xtks_exit_open")


def sixth_economics_verified(row: Mapping[str, Any]) -> bool:
    if row.get("sixth_economics_status") != "verified" or not sixth_endpoint_verified(row):
        return False
    view = {column.removeprefix("sixth_"): row.get(column) for column in SIXTH_ECONOMIC_COLUMNS}
    view.update({"source_scope": "FORWARD_CAUSAL", "price_basis": PRICE_BASIS_VERSION,
                 "status": "mature", "fifth_xtks_exit_date": row.get("sixth_xtks_exit_date"),
                 "fifth_xtks_exit_close": row.get("sixth_xtks_exit_open")})
    try:
        expected_entry = pd.Timestamp(add_bank_business_days(pd.Timestamp(row["signal_date"]).date(), 1))
        observed = pd.Timestamp(row.get("sixth_economics_observed_at"))
        return bool(
            pd.Timestamp(row.get("sixth_entry_date")).normalize() == expected_entry
            and pd.notna(observed) and observed.tzinfo is not None
            and observed <= pd.Timestamp.now(tz="UTC")
            and observed >= pd.Timestamp(row["sixth_xtks_exit_observed_at"])
            and pd.Timestamp(row["sixth_price_basis_date"]).date() <= observed.tz_convert("Asia/Tokyo").date()
            and re.fullmatch(r"[0-9a-f]{64}", str(row.get("sixth_price_basis_source_sha256", "")))
            and is_frozen_trade(view) and _consistent_with_frozen_d5(row, view)
        )
    except (KeyError, TypeError, ValueError):
        return False


def _consistent_with_frozen_d5(row: Mapping[str, Any], sixth_economics: Mapping[str, Any]) -> bool:
    """A later source must retain the already verified D5 holding-action prefix."""
    if not is_frozen_trade(row):
        return True
    if pd.Timestamp(row["entry_date"]).normalize() != pd.Timestamp(sixth_economics["entry_date"]).normalize():
        return False
    for column in ("entry_open", "entry_shares", "entry_cost_yen"):
        if not math.isclose(float(row[column]), float(sixth_economics[column]), rel_tol=1e-9, abs_tol=1e-7):
            return False
    fifth = pd.Timestamp(row["fifth_xtks_exit_date"]).normalize()
    if fifth != pd.Timestamp(add_bank_business_days(pd.Timestamp(row["signal_date"]).date(), 5)):
        return False
    prefix = [action for action in json.loads(str(sixth_economics["applied_actions_json"]))
              if pd.Timestamp(action["effective_date"]) <= fifth]
    return prefix == json.loads(str(row["applied_actions_json"]))


def source_digest(raw: pd.DataFrame, declared_sha256: str = "") -> str:
    """Use the serialized source hash, or hash the normalized supplied evidence."""
    if re.fullmatch(r"[0-9a-f]{64}", str(declared_sha256)):
        return declared_sha256
    return hashlib.sha256(raw.to_csv(index=False, lineterminator="\n").encode("utf-8")).hexdigest()


def _capture_price(
    prices: pd.DataFrame, symbol: str, session: pd.Timestamp, field: str,
    prefix: str, price_column: str, digest: str, observed_at: str,
) -> dict[str, Any]:
    result = {
        price_column: float("nan"), f"{prefix}_status": "missing",
        f"{prefix}_observed_at": "", f"{prefix}_source_sha256": "",
        f"{prefix}_price_basis": "", f"{prefix}_provenance_json": "",
    }
    if pd.Timestamp(observed_at) < _earliest_observation(session, field):
        result[f"{prefix}_status"] = "pending"
        return result
    if (symbol, session) not in prices.index:
        if not prices.empty and session > prices.index.get_level_values("date").max():
            result[f"{prefix}_status"] = "pending"
        return result
    quote = prices.loc[(symbol, session)]
    if not bool(quote["source_usable"]):
        result[f"{prefix}_status"] = "quarantined"
        return result
    if not _positive(quote[field]):
        return result
    provenance = {
        "session": f"{session:%Y-%m-%d}", "symbol": symbol, "field": field,
        "actual_price": float(quote[field]), "adjusted_price": float(quote[field.removeprefix("actual_")]),
        "split_factor": float(quote["split_factor"]),
        "basis_asof": f"{pd.Timestamp(quote['basis_asof']):%Y-%m-%d}",
        "price_basis": PRICE_BASIS_VERSION, "source_price_basis": str(quote["price_basis"]),
        "corporate_actions_version": str(quote["corporate_actions_version"]),
        "corporate_actions_source": str(quote["corporate_actions_source"]),
        "source_usable": True, "source_sha256": digest,
    }
    return {
        price_column: float(quote[field]), f"{prefix}_status": "verified",
        f"{prefix}_observed_at": observed_at, f"{prefix}_source_sha256": digest,
        f"{prefix}_price_basis": PRICE_BASIS_VERSION,
        f"{prefix}_provenance_json": json.dumps(provenance, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    }


def build_endpoint_receipts(
    row: Mapping[str, Any], prices: pd.DataFrame, actions: pd.DataFrame, *,
    digest: str, observed_at: str,
) -> dict[str, Any]:
    """Add verified endpoints without changing a previously captured endpoint.

    Callers supply normalized action-aware daily evidence. A D5-frozen trade is
    intentionally supported. Canonical rows are accepted only by the explicit
    ledger backfill API; normal model refresh never calls this for those rows.
    """
    signal = pd.Timestamp(row["signal_date"]).normalize()
    symbol = str(row["symbol"])
    entry = pd.Timestamp(add_bank_business_days(signal.date(), 1))
    sixth = pd.Timestamp(add_bank_business_days(signal.date(), 6))
    observed = pd.Timestamp(observed_at)
    if pd.isna(observed) or observed.tzinfo is None or observed > pd.Timestamp.now(tz="UTC"):
        raise ValueError("endpoint observation time must be timezone-aware and non-future")
    result = {"sixth_xtks_exit_date": sixth}
    for prefix, price_column, session, field, columns, verifier in (
        ("signal_actual_close", "signal_actual_close", signal, "actual_close", SIGNAL_ACTUAL_COLUMNS, signal_actual_close_verified),
        ("sixth_xtks_exit", "sixth_xtks_exit_open", sixth, "actual_open", SIXTH_PRICE_COLUMNS, sixth_endpoint_verified),
    ):
        if row.get(f"{prefix}_status") == "verified":
            if not verifier(row):
                raise ValueError(f"corrupt verified endpoint receipt: {prefix}")
            result.update({column: row.get(column) for column in columns})
            if prefix == "sixth_xtks_exit" and pd.Timestamp(row["sixth_xtks_exit_date"]).normalize() != sixth:
                raise ValueError("sixth session revision requires review")
        else:
            result.update(_capture_price(prices, symbol, session, field, prefix, price_column, digest, observed_at))
            if result.get(f"{prefix}_status") == "verified" and not verifier({**dict(row), **result}):
                raise ValueError(f"invalid new endpoint receipt: {prefix}; review source basis and observation time")
    # Keep verified D6 economics just as D5 economics are frozen.
    if row.get("sixth_economics_status") == "verified":
        if not sixth_economics_verified(row):
            raise ValueError("corrupt verified sixth economics")
        result.update({column: row.get(column) for column in SIXTH_ECONOMIC_COLUMNS})
        return result
    result.update({column: float("nan") for column in SIXTH_ECONOMIC_COLUMNS})
    result.update({"sixth_economics_status": "pending", "sixth_entry_date": entry,
                   "sixth_applied_actions_json": "", "sixth_price_basis_date": "",
                   "sixth_price_basis_source_sha256": "", "sixth_economics_observed_at": "",
                   "sixth_economics_issue": ""})
    if not sixth_endpoint_verified({**dict(row), **result}) or (symbol, entry) not in prices.index:
        return result
    quote = prices.loc[(symbol, entry)]
    if not bool(quote["source_usable"]):
        result["sixth_economics_status"] = "review_required"
        result["sixth_economics_issue"] = "quarantined_entry"
        return result
    actual_entry = float(quote["actual_open"])
    shares = 100.0
    if str(row.get("source_scope", "")) == "FORWARD_CAUSAL" and row.get("price_basis") == PRICE_BASIS_VERSION and _positive(row.get("entry_open")):
        if pd.Timestamp(row["entry_date"]).normalize() != entry:
            raise ValueError("entry session revision requires review for sixth economics")
        if abs(actual_entry - float(row["entry_open"])) > max(.01, abs(float(row["entry_open"])) * 1e-6):
            raise ValueError("entry price revision requires review for sixth economics")
        actual_entry = float(row["entry_open"])
        shares = float(row.get("entry_shares", 100))
    try:
        economics = build_trade_economics(
            entry, sixth, actual_entry, result["sixth_xtks_exit_open"], actions,
            symbol=symbol, entry_shares=shares, basis_date=quote["basis_asof"], source_sha256=digest,
        )
    except UnsupportedFractionalShares:
        result["sixth_economics_status"] = "review_required"
        result["sixth_economics_issue"] = "fractional_shares_requires_review"
        return result
    if not _consistent_with_frozen_d5(row, economics):
        result["sixth_economics_status"] = "review_required"
        result["sixth_economics_issue"] = "frozen_d5_action_revision"
        return result
    result.update({f"sixth_{column}": economics[column] for column in (
        "entry_date", "entry_open", "entry_shares", "entry_cost_yen", "gross_return",
        "one_hundred_shares_pl_yen", "exit_shares", "exit_proceeds_yen",
        "holding_action_factor", "applied_actions_json", "price_basis_date",
        "price_basis_source_sha256",
    )})
    result["sixth_economics_status"] = "verified"
    result["sixth_economics_observed_at"] = observed_at
    if not sixth_economics_verified({**dict(row), **result}):
        raise ValueError("invalid new sixth economics; review source basis and observation time")
    return result


def preserve_verified_endpoints(existing: Mapping[str, Any], incoming: Mapping[str, Any]) -> dict[str, Any]:
    """Replay must not erase or revise independently verified receipts."""
    result = dict(incoming)
    for status, columns, verifier in (
        ("signal_actual_close_status", SIGNAL_ACTUAL_COLUMNS, signal_actual_close_verified),
        ("sixth_xtks_exit_status", SIXTH_PRICE_COLUMNS, sixth_endpoint_verified),
    ):
        if existing.get(status) == "verified":
            if not verifier(existing):
                raise ValueError(f"corrupt verified endpoint receipt: {status}")
            result.update({column: existing.get(column) for column in columns})
    if existing.get("sixth_economics_status") == "verified":
        if not sixth_economics_verified(existing):
            raise ValueError("corrupt verified sixth economics")
        result.update({column: existing.get(column) for column in SIXTH_ECONOMIC_COLUMNS})
    if result.get("sixth_economics_status") == "verified" and not sixth_economics_verified(result):
        raise ValueError("sixth endpoint/economics revision requires review")
    return result
