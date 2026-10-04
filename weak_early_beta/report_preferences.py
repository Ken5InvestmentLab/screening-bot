"""Read-only Cloud presentation views; never mutate the canonical ledger.

Price limits apply to verified nominal signal-day closes, never signal_close.
Endpoint selection creates a temporary metric-compatible view of D6 economics.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import math

import pandas as pd

from .endpoint_receipts import signal_actual_close_verified, sixth_endpoint_verified, sixth_economics_verified
from .reviewed_d5_overlay import actual_d5_economics, actual_forward_entry
from .trade_basis import ECONOMIC_COLUMNS, PRICE_BASIS_VERSION


DEFAULT_PRICE_CAP = 1000
MAX_PRICE_CAP = Decimal("90071992547409.91")  # Number.MAX_SAFE_INTEGER / 100
ENDPOINT_LABELS = {
    "d5_close": "5営業日後 終値",
    "d6_open": "6営業日後 始値",
}


def validate_price_cap(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("価格上限は正の有限値を小数2桁までで指定してください")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("価格上限は正の有限値を小数2桁までで指定してください") from exc
    if not number.is_finite() or number <= 0 or number > MAX_PRICE_CAP or number.normalize().as_tuple().exponent < -2:
        raise ValueError("価格上限は正の有限値を小数2桁までで指定してください")
    result = float(number)
    if not math.isfinite(result):
        raise ValueError("価格上限が大きすぎます")
    return result


def visible_history(ledger: pd.DataFrame) -> pd.DataFrame:
    """2022 is excluded only in the presentation view, with source rows intact."""
    dates = pd.to_datetime(ledger["signal_date"], errors="coerce")
    return ledger.loc[dates.notna() & dates.dt.year.ne(2022)].copy()


def released_history(ledger: pd.DataFrame) -> pd.DataFrame:
    """Return the complete free-page population before any rendering/aggregation.

    Unreleased rows must contribute neither values nor counts, dates, thresholds
    or anonymous aggregates. Require every overlapping selector's D6 receipt so
    a partially migrated identity is not exposed through another mode page.
    """
    result = visible_history(ledger)
    if result.empty:
        return result
    verified = result.apply(sixth_endpoint_verified, axis=1).astype(bool)
    dates = pd.to_datetime(result["signal_date"]).dt.normalize()
    symbols = result["symbol"].astype(str)
    released = verified.groupby([dates, symbols], dropna=False).transform("all")
    return result.loc[released].copy()


def verified_signal_prices(ledger: pd.DataFrame) -> pd.Series:
    if ledger.empty:
        return pd.Series(index=ledger.index, dtype=float)
    verified = ledger.apply(signal_actual_close_verified, axis=1).astype(bool)
    prices = pd.to_numeric(ledger.get("signal_actual_close", pd.Series(index=ledger.index, dtype=float)), errors="coerce")
    return prices.where(verified)


def select_report_view(
    ledger: pd.DataFrame,
    price_cap: object = DEFAULT_PRICE_CAP,
    exit_key: str = "d5_close",
) -> pd.DataFrame:
    cap = validate_price_cap(price_cap)
    if exit_key not in ENDPOINT_LABELS:
        raise ValueError("unknown exit endpoint")
    result = visible_history(ledger)
    if cap is not None:
        result = result.loc[verified_signal_prices(result).le(cap)].copy()
    # Preserve canonical values in this copy only. All presentation consumers
    # use the same independently verified actual D5 acquired lot and receipts.
    for column in ECONOMIC_COLUMNS:
        if column in result and "raw_d5_" + column not in result:
            result["raw_d5_" + column] = result[column]
    verified_d5 = [actual_d5_economics(row) for _, row in result.iterrows()]
    verified_entries = [actual_forward_entry(row) if economics is None else economics
                        for (_, row), economics in zip(result.iterrows(), verified_d5)]
    numeric = ("entry_open", "fifth_xtks_exit_close", "gross_return", "one_hundred_shares_pl_yen",
               "entry_shares", "exit_shares", "holding_action_factor", "entry_cost_yen", "exit_proceeds_yen")
    for column in numeric:
        result[column] = [economics[column] if economics is not None else float("nan") for economics in verified_d5]
    for column in ("entry_open", "entry_shares", "entry_cost_yen"):
        result[column] = [entry[column] if entry is not None else float("nan") for entry in verified_entries]
    for column in ("price_basis_date", "price_basis_source_sha256", "applied_actions_json"):
        values = verified_d5 if column == "applied_actions_json" else verified_entries
        result[column] = [value[column] if value is not None else "" for value in values]
    # Pending exits do not undo a validated purchase. Unknown acquisitions
    # never use legacy economics or prices inferred from another endpoint.
    result["price_basis"] = PRICE_BASIS_VERSION
    result["display_d5_verified"] = [value is not None for value in verified_d5]
    result["status"] = ["mature" if economics is not None else ("entered" if entry is not None else "pending_entry")
                        for economics, entry in zip(verified_d5, verified_entries)]
    for column in ("entry_date", "fifth_xtks_exit_date"):
        original_dates = pd.to_datetime(result.get("raw_d5_" + column, result[column]), errors="coerce")
        values = verified_entries if column == "entry_date" else verified_d5
        result[column] = pd.to_datetime([value[column] if value is not None else original_dates.iloc[index] for index, value in enumerate(values)])
    if exit_key == "d5_close":
        return result
    # Preserve actual D5 values for the detection table. These aliases live
    # only in this temporary view and are never written to the ledger.
    for column in ("fifth_xtks_exit_date", "fifth_xtks_exit_close", "gross_return", "one_hundred_shares_pl_yen"):
        result["display_d5_" + column] = result[column]
    verified = result.apply(sixth_endpoint_verified, axis=1).astype(bool) if not result.empty else pd.Series(index=result.index, dtype=bool)
    returns = pd.to_numeric(result.get("sixth_gross_return", pd.Series(index=result.index, dtype=float)), errors="coerce")
    cash = pd.to_numeric(result.get("sixth_one_hundred_shares_pl_yen", pd.Series(index=result.index, dtype=float)), errors="coerce")
    economic = result.apply(sixth_economics_verified, axis=1).astype(bool) if not result.empty else pd.Series(index=result.index, dtype=bool)
    result["fifth_xtks_exit_date"] = pd.to_datetime(result.get("sixth_xtks_exit_date", pd.Series(index=result.index, dtype=object)), errors="coerce")
    # Older pending records may predate the D6 date column. Use the same
    # deterministic scheduled session as the history UI, while leaving every
    # actual price and receipt unavailable. This also keeps coverage-year
    # denominators identical in native metrics and the browser.
    from .bank_calendar import add_bank_business_days
    scheduled = pd.Series([
        pd.Timestamp(add_bank_business_days(day.date(), 6)) if pd.notna(day) else pd.NaT
        for day in pd.to_datetime(result["signal_date"], errors="coerce")
    ], index=result.index)
    result["fifth_xtks_exit_date"] = result["fifth_xtks_exit_date"].where(result["fifth_xtks_exit_date"].notna(), scheduled)
    result["fifth_xtks_exit_close"] = pd.to_numeric(result.get("sixth_xtks_exit_open", pd.Series(index=result.index, dtype=float)), errors="coerce").where(verified)
    result["gross_return"] = returns.where(economic)
    result["one_hundred_shares_pl_yen"] = cash.where(economic)
    # D6 share-aware economics must never inherit a legacy adjusted entry lot.
    # The receipt writer supplies original actual entry price/cost independently.
    if "sixth_entry_open" in result:
        actual_entry = pd.to_numeric(result["sixth_entry_open"], errors="coerce")
        result["entry_open"] = actual_entry.where(economic, result["entry_open"])
    if "sixth_entry_date" in result:
        result["entry_date"] = pd.to_datetime(result["sixth_entry_date"], errors="coerce").where(economic, result["entry_date"])
    if "sixth_entry_cost_yen" in result:
        result["entry_cost_yen"] = pd.to_numeric(result["sixth_entry_cost_yen"], errors="coerce").where(economic, result["entry_cost_yen"])
    if "sixth_entry_shares" in result:
        result["entry_shares"] = pd.to_numeric(result["sixth_entry_shares"], errors="coerce").where(economic, result["entry_shares"])
    # Do not leave D5 holding quantities/receipts attached to a D6 endpoint.
    # A split or consolidation may occur between those sessions. Missing or
    # quarantined D6 economics must remain unavailable, never inherit D5.
    for column in ("exit_shares", "exit_proceeds_yen", "holding_action_factor"):
        result[column] = pd.to_numeric(
            result.get("sixth_" + column, pd.Series(index=result.index, dtype=float)),
            errors="coerce",
        ).where(economic)
    result["applied_actions_json"] = result.get(
        "sixth_applied_actions_json", pd.Series("", index=result.index, dtype=object)
    ).where(economic, "")
    return result
