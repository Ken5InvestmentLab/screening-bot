"""Reference-only performance annotations for hard-to-fill Cloud entries.

The historical trade ledger remains intact.  These annotations describe a
conservative performance policy, not proof that a particular order did not
execute.  They must not be used as a signal-date tradability gate.

``jpx_session_one_price`` means a JPX session report shows no morning trade
and one afternoon price.  ``user_designated_one_price`` means the user elected
reference-only treatment based on a one-price daily record; it does not claim
that JPX verified the stop-high price or intraday trade timing.
"""

from __future__ import annotations

import csv
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd


DEFAULT_EXCLUSIONS = Path(__file__).resolve().parent / "state" / "entry_feasibility_exclusions.csv"
REFERENCE_ONLY_COLUMN = "performance_reference_only"
REASON_COLUMN = "performance_reference_reason"
EVIDENCE_URL_COLUMN = "performance_reference_evidence_url"
VERIFICATION_NOTE_COLUMN = "performance_reference_verification_note"
_REQUIRED_COLUMNS = ("symbol", "entry_date", "reason", "evidence_url", "verification_note")
_SYMBOL_PATTERN = re.compile(r"[0-9A-Z]{4}\Z")
_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_REASON_CODES = {"stop_high_one_price"}
_VERIFICATION_NOTES = {"jpx_session_one_price", "user_designated_one_price"}


def _valid_iso_date(value: str, *, location: str) -> str:
    if not _DATE_PATTERN.fullmatch(value):
        raise ValueError(f"{location}: expected YYYY-MM-DD, got {value!r}")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError(f"{location}: invalid calendar date {value!r}") from exc


def load_entry_feasibility_exclusions(
    path: Path = DEFAULT_EXCLUSIONS,
) -> dict[tuple[str, str], dict[str, str]]:
    """Read the reviewed symbol/entry-date policy, rejecting ambiguous input."""
    path = Path(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        if len(header) != len(set(header)):
            raise ValueError(f"duplicate columns in {path}")
        if set(header) != set(_REQUIRED_COLUMNS):
            raise ValueError(
                f"{path}: expected columns {', '.join(_REQUIRED_COLUMNS)}; got {header}"
            )
        exclusions: dict[tuple[str, str], dict[str, str]] = {}
        for line_number, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{path}:{line_number}: malformed CSV row")
            symbol = row["symbol"].strip().upper()
            if not _SYMBOL_PATTERN.fullmatch(symbol):
                raise ValueError(f"{path}:{line_number}: invalid symbol {symbol!r}")
            entry_date = _valid_iso_date(
                row["entry_date"].strip(), location=f"{path}:{line_number}:entry_date"
            )
            reason = row["reason"].strip()
            if reason not in _REASON_CODES:
                raise ValueError(f"{path}:{line_number}: unknown reason code {reason!r}")
            evidence_url = row["evidence_url"].strip()
            parsed = urlparse(evidence_url)
            if (
                parsed.scheme != "https"
                or parsed.hostname != "www.jpx.co.jp"
                or "/markets/statistics-equities/daily/" not in parsed.path
                or not parsed.path.endswith(".pdf")
            ):
                raise ValueError(f"{path}:{line_number}: expected a JPX daily-report PDF URL")
            verification_note = row["verification_note"].strip()
            if verification_note not in _VERIFICATION_NOTES:
                raise ValueError(f"{path}:{line_number}: unknown verification note {verification_note!r}")
            key = (symbol, entry_date)
            if key in exclusions:
                raise ValueError(f"{path}:{line_number}: duplicate symbol/entry_date {key}")
            exclusions[key] = {
                "reason": reason,
                "evidence_url": evidence_url,
                "verification_note": verification_note,
            }
    if not exclusions:
        raise ValueError(f"{path}: exclusion policy is empty")
    return exclusions


def _ledger_entry_dates(ledger: pd.DataFrame) -> pd.Series:
    """Normalize dates only for the lookup, preserving the source column."""
    raw = ledger["entry_date"]
    dates = pd.to_datetime(raw, errors="coerce")
    invalid = raw.notna() & raw.astype(str).str.strip().ne("") & dates.isna()
    if invalid.any():
        raise ValueError(f"ledger contains invalid entry_date at index {raw.index[invalid][0]!r}")
    return dates.dt.strftime("%Y-%m-%d").fillna("")


def annotate_entry_feasibility(
    ledger: pd.DataFrame,
    exclusions_path: Path = DEFAULT_EXCLUSIONS,
) -> pd.DataFrame:
    """Return a ledger copy with reference-only flags for reviewed entries.

    All selectors sharing the same symbol and entry date receive the same
    annotation.  Historical returns, cash P/L, status and source_scope are
    deliberately left untouched so the rows remain visible in history.
    """
    missing = {"symbol", "entry_date"}.difference(ledger.columns)
    if missing:
        raise ValueError(f"ledger missing columns: {', '.join(sorted(missing))}")
    exclusions = load_entry_feasibility_exclusions(exclusions_path)
    result = ledger.copy()
    symbols = result["symbol"].astype(str).str.strip().str.upper()
    entry_dates = _ledger_entry_dates(result)
    keys = list(zip(symbols, entry_dates))
    matches = [exclusions.get(key) for key in keys]
    result[REFERENCE_ONLY_COLUMN] = pd.Series(
        [match is not None for match in matches], index=result.index, dtype=bool
    )
    result[REASON_COLUMN] = [match["reason"] if match else "" for match in matches]
    result[EVIDENCE_URL_COLUMN] = [
        match["evidence_url"] if match else "" for match in matches
    ]
    result[VERIFICATION_NOTE_COLUMN] = [
        match["verification_note"] if match else "" for match in matches
    ]
    return result


def performance_eligible(
    ledger: pd.DataFrame,
    exclusions_path: Path = DEFAULT_EXCLUSIONS,
) -> pd.DataFrame:
    """Return rows eligible for metrics, leaving the source ledger unchanged."""
    annotated = annotate_entry_feasibility(ledger, exclusions_path)
    return annotated.loc[~annotated[REFERENCE_ONLY_COLUMN]].copy()
