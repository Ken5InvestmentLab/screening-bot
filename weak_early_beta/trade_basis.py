"""Actual-session economics for an original lot across splits/consolidations.

The caller must verify the action coverage and reconstruct actual-session
prices before calling this module. Vendor-adjusted prices must not be passed
as actual prices. Historical canonical rows are never migrated here.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from datetime import date
from typing import Any

import pandas as pd


PRICE_BASIS_VERSION = "ACTUAL_SESSION_SHARE_AWARE_V1"
LEGACY_PRICE_BASIS_VERSION = "LEGACY_VENDOR_ADJUSTED_REFERENCE_V1"
TRADE_BASIS_COLUMNS = [
    "price_basis", "price_basis_date", "price_basis_source_sha256",
    "entry_shares", "exit_shares", "holding_action_factor",
    "entry_cost_yen", "exit_proceeds_yen", "applied_actions_json",
]
ECONOMIC_COLUMNS = [
    "status", "entry_date", "entry_open", "fifth_xtks_exit_date",
    "fifth_xtks_exit_close", "gross_return", "one_hundred_shares_pl_yen",
    *TRADE_BASIS_COLUMNS,
]


class UnsupportedFractionalShares(ValueError):
    """A corporate action needs an unmodeled cash-in-lieu/rounding policy."""


def _receipt_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate frozen action JSON key: {key}")
        result[key] = value
    return result


def _invalid_json_constant(value: str) -> None:
    raise ValueError(f"non-standard frozen action JSON constant: {value}")


def _session(value: Any) -> pd.Timestamp:
    session = pd.Timestamp(value)
    if pd.isna(session):
        raise ValueError("trade/action session is missing")
    if session.tzinfo is not None:
        session = session.tz_convert("Asia/Tokyo").tz_localize(None)
    return session.normalize()


def _price(value: Any) -> float:
    if value is None or pd.isna(value):
        return float("nan")
    price = float(value)
    if not math.isfinite(price) or price <= 0:
        raise ValueError(f"actual-session price must be positive and finite: {value}")
    return price


def _whole_shares(value: Any, *, location: str) -> float:
    shares = float(value)
    if not math.isfinite(shares) or shares <= 0:
        raise ValueError(f"{location}: shares must be positive and finite")
    nearest = round(shares)
    if nearest <= 0 or not math.isclose(shares, nearest, rel_tol=0, abs_tol=1e-8):
        raise UnsupportedFractionalShares(
            f"{location}: fractional shares {shares}; cash-in-lieu is not modeled"
        )
    return float(nearest)


def _holding_actions(
    actions: pd.DataFrame | None,
    entry: pd.Timestamp,
    exit: pd.Timestamp,
    symbol: str | None,
) -> list[dict[str, Any]]:
    if actions is None or actions.empty:
        return []
    if not {"effective_date", "ratio"}.issubset(actions.columns):
        raise ValueError("action table requires effective_date and ratio")
    table = actions.copy()
    if "symbol" in table:
        table["symbol"] = table["symbol"].astype(str)
        if symbol is None and table["symbol"].nunique() > 1:
            raise ValueError("symbol is required for a multi-symbol action table")
        if symbol is not None:
            table = table[table["symbol"].eq(str(symbol))].copy()
    table["effective_date"] = table["effective_date"].map(_session)
    table["ratio"] = pd.to_numeric(table["ratio"], errors="raise")
    if any(not math.isfinite(float(ratio)) or ratio <= 0 for ratio in table["ratio"]):
        raise ValueError("action ratios must be positive and finite")
    selected = table[
        table["effective_date"].gt(entry) & table["effective_date"].le(exit)
    ].sort_values("effective_date")
    result = []
    for effective_date, group in selected.groupby("effective_date", sort=True):
        ratios = group["ratio"].unique()
        if len(ratios) != 1:
            raise ValueError(f"conflicting action ratios for {effective_date:%Y-%m-%d}")
        result.append({"effective_date": f"{effective_date:%Y-%m-%d}", "ratio": float(ratios[0])})
    return result


def build_trade_economics(
    entry_date: Any,
    exit_date: Any,
    actual_entry_open: Any,
    actual_exit_close: Any,
    actions: pd.DataFrame | None,
    *,
    symbol: str | None = None,
    entry_shares: float = 100,
    basis_date: Any = None,
    source_sha256: str = "",
) -> dict[str, Any]:
    """Return actual prices and economics, keeping the original acquired lot.

    Actions effective on the entry session are already reflected in its actual
    price. Only ``entry < effective_date <= exit`` changes the held quantity.
    Each quantity must remain integral; no fractional liquidation is invented.
    Missing endpoints remain pending and may be filled by a later invocation.
    """
    entry = _session(entry_date) if pd.notna(entry_date) else pd.NaT
    exit = _session(exit_date) if pd.notna(exit_date) else pd.NaT
    if pd.notna(entry) and pd.notna(exit) and exit < entry:
        raise ValueError("exit session precedes entry session")
    entry_price = _price(actual_entry_open)
    exit_price = _price(actual_exit_close)
    if math.isfinite(entry_price) and pd.isna(entry):
        raise ValueError("entry price requires an entry session")
    if math.isfinite(exit_price) and pd.isna(exit):
        raise ValueError("exit price requires an exit session")
    original_shares = _whole_shares(entry_shares, location="entry")
    events = (
        _holding_actions(actions, entry, exit, symbol)
        if pd.notna(entry) and pd.notna(exit) else []
    )
    exit_shares = original_shares
    for action in events:
        exit_shares = _whole_shares(
            exit_shares * action["ratio"], location=action["effective_date"]
        )
    factor = exit_shares / original_shares
    mature = math.isfinite(entry_price) and math.isfinite(exit_price)
    cost = entry_price * original_shares if math.isfinite(entry_price) else float("nan")
    proceeds = exit_price * exit_shares if mature else float("nan")
    basis = _session(basis_date) if pd.notna(basis_date) else (exit if mature else entry)
    if mature and basis < exit:
        raise ValueError("verified basis date precedes the completed exit session")
    return {
        "status": "mature" if mature else ("entered" if math.isfinite(entry_price) else "pending_entry"),
        "entry_date": entry,
        "entry_open": entry_price,
        "fifth_xtks_exit_date": exit,
        "fifth_xtks_exit_close": exit_price,
        "gross_return": proceeds / cost - 1 if mature else float("nan"),
        "one_hundred_shares_pl_yen": proceeds - cost if mature else float("nan"),
        "price_basis": PRICE_BASIS_VERSION,
        "price_basis_date": f"{basis:%Y-%m-%d}" if pd.notna(basis) else "",
        "price_basis_source_sha256": str(source_sha256 or ""),
        "entry_shares": original_shares,
        "exit_shares": exit_shares,
        "holding_action_factor": factor,
        "entry_cost_yen": cost,
        "exit_proceeds_yen": proceeds,
        "applied_actions_json": json.dumps(events, ensure_ascii=False, separators=(",", ":")),
    }


def is_frozen_trade(row: Mapping[str, Any]) -> bool:
    """Recognize a complete forward snapshot, rejecting corrupt marked rows."""
    if str(row.get("source_scope", "")) != "FORWARD_CAUSAL":
        return False
    if str(row.get("price_basis", "")) != PRICE_BASIS_VERSION or str(row.get("status", "")) != "mature":
        return False
    try:
        entry = _session(row["entry_date"])
        exit = _session(row["fifth_xtks_exit_date"])
        entry_price = _price(row["entry_open"])
        exit_price = _price(row["fifth_xtks_exit_close"])
        if not math.isfinite(entry_price) or not math.isfinite(exit_price):
            raise ValueError("frozen endpoints must be positive and finite")
        entry_shares = _whole_shares(row["entry_shares"], location="frozen entry")
        exit_shares = _whole_shares(row["exit_shares"], location="frozen exit")
        expected = {
            "entry_cost_yen": entry_price * entry_shares,
            "exit_proceeds_yen": exit_price * exit_shares,
            "holding_action_factor": exit_shares / entry_shares,
            "gross_return": exit_price * exit_shares / (entry_price * entry_shares) - 1,
            "one_hundred_shares_pl_yen": exit_price * exit_shares - entry_price * entry_shares,
        }
        basis_value = row["price_basis_date"]
        if not isinstance(basis_value, (str, date, pd.Timestamp)) or pd.isna(basis_value):
            raise ValueError("missing or invalid frozen basis date")
        basis = _session(basis_value)
        if exit < entry or basis < exit:
            raise ValueError("invalid frozen basis dates")
        actions = json.loads(
            str(row["applied_actions_json"]), object_pairs_hook=_receipt_object,
            parse_constant=_invalid_json_constant,
        )
        if not isinstance(actions, list):
            raise ValueError("frozen applied actions are not a list")
        held_shares = entry_shares
        last_action = entry
        for action in actions:
            if not isinstance(action, dict):
                raise ValueError("frozen action receipt is not an object")
            effective = _session(action["effective_date"])
            if action["effective_date"] != f"{effective:%Y-%m-%d}":
                raise ValueError("frozen action effective date is not an ISO session date")
            ratio_value = action["ratio"]
            if isinstance(ratio_value, bool) or not isinstance(ratio_value, (int, float)):
                raise ValueError("frozen action ratio is not numeric")
            ratio = float(ratio_value)
            if not last_action < effective <= exit or not math.isfinite(ratio) or ratio <= 0:
                raise ValueError("invalid frozen holding action")
            held_shares = _whole_shares(held_shares * ratio, location="frozen action")
            last_action = effective
        if held_shares != exit_shares:
            raise ValueError("frozen quantity does not match its action receipts")
        for column, value in expected.items():
            if not math.isfinite(value) or not math.isclose(float(row[column]), value, rel_tol=1e-9, abs_tol=1e-7):
                raise ValueError(f"inconsistent {column}")
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"corrupt frozen trade economics: {exc}") from exc
    return True


def preserve_completed_economics(
    existing: Mapping[str, Any], incoming: Mapping[str, Any]
) -> dict[str, Any]:
    """Retain completed economics and the original cost of an entered trade."""
    result = dict(incoming)
    if is_frozen_trade(existing):
        for column in ECONOMIC_COLUMNS:
            result[column] = existing[column]
        # An old completed row has no reconstructable acquisition timestamp.
        # A later replay must not invent one for result-notification eligibility.
        result["d5_price_observed_at"] = existing.get("d5_price_observed_at", "")
        return result
    if (
        str(existing.get("source_scope", "")) == "FORWARD_CAUSAL"
        and str(existing.get("price_basis", "")) == PRICE_BASIS_VERSION
        and str(existing.get("status", "")) == "entered"
    ):
        entry = _session(existing["entry_date"])
        price = _price(existing["entry_open"])
        shares = _whole_shares(existing["entry_shares"], location="recorded entry")
        cost = float(existing["entry_cost_yen"])
        if not math.isfinite(price) or not math.isfinite(cost) or not math.isclose(cost, price * shares, rel_tol=1e-9, abs_tol=1e-7):
            raise ValueError("corrupt recorded entry economics")
        for column in ("entry_date", "fifth_xtks_exit_date"):
            if pd.notna(incoming.get(column)) and _session(incoming[column]) != _session(existing[column]):
                raise ValueError(f"{column} revision requires review")
        if str(incoming.get("price_basis", "")) != PRICE_BASIS_VERSION:
            raise ValueError("recorded entry price basis revision requires review")
        current_price = _price(incoming.get("entry_open"))
        if math.isfinite(current_price) and abs(current_price - price) > max(0.01, abs(price) * 1e-6):
            raise ValueError("entry price revision requires review")
        if pd.notna(incoming.get("entry_shares")) and _whole_shares(incoming["entry_shares"], location="incoming entry") != shares:
            raise ValueError("entry shares revision requires review")
        if not math.isfinite(current_price):
            # A source gap/quality quarantine cannot undo a recorded purchase.
            # Endpoint refresh can fill its exit separately from this replay.
            for column in ECONOMIC_COLUMNS:
                result[column] = existing[column]
            return result
        if str(incoming.get("status", "")) == "mature":
            is_frozen_trade(incoming)
        for column in ("entry_date", "entry_open", "entry_shares", "entry_cost_yen"):
            result[column] = existing[column]
        if str(result.get("status", "")) == "mature":
            proceeds = float(result["exit_proceeds_yen"])
            result["gross_return"] = proceeds / cost - 1
            result["one_hundred_shares_pl_yen"] = proceeds - cost
            is_frozen_trade(result)
    return result
