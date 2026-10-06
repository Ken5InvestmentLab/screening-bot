"""Reviewed comparison overrides for one explicitly fingerprinted transition.

This module never repairs a provider frame or rewrites a cache. Its overrides
apply only to the previous actual-value arrays inside source revision validation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .corporate_actions import (
    ACTION_SOURCE,
    ACTUAL_COLUMNS,
    OHLC,
    PRICE_BASIS,
    VERSION,
    CorporateActionError,
    REVISION_EVIDENCE,
    _historical_actions,
)


DEFAULT_MANIFEST = Path(__file__).resolve().parent / "state" / "reviewed_source_corrections.json"
PREVIOUS_SHA256 = "87896f4954b5e4d3a441578ac5a240a92ab50aeab1c371cc1d6023551c04798a"
CORRECTION_DATES = ("2026-09-24", "2026-09-25", "2026-09-28")
PRIMARY_SOURCE_URLS = (
    "https://www.hokuhoku-fg.co.jp/stocks/docs/kabushiki20260724.pdf",
    "https://www.hokuhoku-fg.co.jp/stocks/benefit/",
    "https://www.jpx.co.jp/markets/equities/rights/archives-01.html",
    "https://finance.yahoo.co.jp/quote/8377.T/history",
)
TRANSITION = {
    "identity": "CLOUD_REVIEWED_SOURCE_CORRECTIONS_V1",
    "manifest_version": 1,
    "previous_source_sha256": PREVIOUS_SHA256,
    "previous_basis": "2026-10-05",
    "current_basis": "2026-10-06",
    "symbol": "8377",
    "previous_journal": [],
    "current_journal": [{"effective_date": "2026-09-29", "ratio": 10.0}],
    "previous_split_factor": 1.0,
    "current_split_factor": 10.0,
    "previous_provider_repaired": False,
    "current_provider_repaired": False,
    "previous_source_usable": True,
    "current_source_usable": True,
    "previous_action_ratio": 0.0,
    "current_action_ratio": 10.0,
}


def _reject(detail: str) -> None:
    raise CorporateActionError(f"reviewed source correction mismatch: {detail}")


def _load_manifest(manifest: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    try:
        if manifest is None:
            contents = DEFAULT_MANIFEST.read_bytes()
            loaded = json.loads(contents.decode("utf-8"))
        else:
            # Tests may supply an explicit independent manifest. There is no
            # environment variable, CLI path, or provider-controlled registry.
            contents = json.dumps(
                manifest, sort_keys=True, separators=(",", ":"), allow_nan=False,
            ).encode("utf-8")
            loaded = json.loads(contents)
    except (OSError, UnicodeError, TypeError, ValueError) as exc:
        raise CorporateActionError("cannot load reviewed source correction manifest") from exc
    if not isinstance(loaded, dict):
        _reject("manifest must be an object")
    return loaded, hashlib.sha256(contents).hexdigest()


def _validate_manifest(manifest: dict[str, Any]) -> None:
    if set(manifest) != set(TRANSITION).union({"primary_sources", "rows"}):
        _reject("manifest fields")
    for field, expected in TRANSITION.items():
        value = manifest[field]
        # JSON equality alone would accept true as a version or numeric factor.
        if type(value) is not type(expected) or value != expected:
            _reject(f"declared {field}")
    if manifest["primary_sources"] != list(PRIMARY_SOURCE_URLS):
        _reject("primary sources")
    rows = manifest["rows"]
    if not isinstance(rows, list) or len(rows) != len(CORRECTION_DATES):
        _reject("exactly three reviewed rows are required")
    for row, date in zip(rows, CORRECTION_DATES):
        if not isinstance(row, dict) or set(row) != {"date", "previous_actual", "current_actual"}:
            _reject("row fields")
        if row["date"] != date:
            _reject("correction dates")
        for endpoint in ("previous_actual", "current_actual"):
            values = row[endpoint]
            if not isinstance(values, dict) or set(values) != {*OHLC, "volume"}:
                _reject(f"{date} {endpoint} fields")
            for column, value in values.items():
                if type(value) not in (int, float) or not np.isfinite(value):
                    _reject(f"{date} {endpoint} {column}")
                if value < 0 or (column != "volume" and value == 0):
                    _reject(f"{date} {endpoint} non-positive price/negative volume")


def reviewed_comparison_overrides(
    previous: pd.DataFrame,
    current: pd.DataFrame,
    *,
    previous_source_sha256: str | None,
    manifest: dict[str, Any] | None = None,
) -> tuple[dict[tuple[str, pd.Timestamp], dict[str, float]], list[dict[str, Any]]]:
    """Verify normalized endpoints and return comparison-only actual overrides.

    An unrelated full-file hash leaves ordinary validation in charge. Once the
    pinned hash matches, any transition or endpoint mismatch fails closed before
    an override is returned.
    """
    if previous_source_sha256 != PREVIOUS_SHA256:
        return {}, []
    reviewed, manifest_hash = _load_manifest(manifest)
    _validate_manifest(reviewed)
    required = {
        "symbol", "date", *OHLC, "volume", *ACTUAL_COLUMNS,
        "split_ratio", "split_factor", "basis_asof", "price_basis",
        "corporate_actions_version", "corporate_actions_source",
        "provider_repaired", "source_usable", "source_issue",
        "off_session_actions",
    }
    for endpoint, frame in (("previous", previous), ("current", current)):
        if not required.issubset(frame.columns):
            _reject(f"{endpoint} requires verified basis metadata")

    symbol = reviewed["symbol"]
    groups = {
        "previous": previous.loc[previous["symbol"].eq(symbol)],
        "current": current.loc[current["symbol"].eq(symbol)],
    }
    for endpoint, group in groups.items():
        basis = pd.Timestamp(reviewed[f"{endpoint}_basis"])
        if group.empty or not group["basis_asof"].eq(basis).all():
            _reject(f"{endpoint} basis/symbol")
        if _historical_actions(group, basis) != reviewed[f"{endpoint}_journal"]:
            _reject(f"{endpoint} complete action journal")
        for field, expected in (
            ("price_basis", PRICE_BASIS),
            ("corporate_actions_version", VERSION),
            ("corporate_actions_source", ACTION_SOURCE),
        ):
            if not group[field].eq(expected).all():
                _reject(f"{endpoint} {field}")
        event_rows = group.loc[group["date"].eq(pd.Timestamp("2026-09-29"))]
        if len(event_rows) != 1 or float(event_rows.iloc[0]["split_ratio"]) != reviewed[f"{endpoint}_action_ratio"]:
            _reject(f"{endpoint} September 29 action row")

    indexed = {endpoint: group.set_index("date") for endpoint, group in groups.items()}
    overrides: dict[tuple[str, pd.Timestamp], dict[str, float]] = {}
    observed: dict[str, dict[str, dict[str, float]]] = {"previous": {}, "current": {}}
    corrected: dict[str, dict[str, float]] = {}
    for specification in reviewed["rows"]:
        date_text = specification["date"]
        date = pd.Timestamp(date_text)
        for endpoint, rows in indexed.items():
            if date not in rows.index or not rows.index.is_unique:
                _reject(f"{endpoint} missing/duplicate {date_text}")
            row = rows.loc[date]
            factor = reviewed[f"{endpoint}_split_factor"]
            if float(row["split_factor"]) != factor or float(row["split_ratio"]) != 0.0:
                _reject(f"{endpoint} {date_text} factor/action")
            for field in ("provider_repaired", "source_usable"):
                if bool(row[field]) is not reviewed[f"{endpoint}_{field}"]:
                    _reject(f"{endpoint} {date_text} {field}")
            if str(row["source_issue"]) != "":
                _reject(f"{endpoint} {date_text} source issue")
            evidence = row.get(REVISION_EVIDENCE, "")
            if pd.notna(evidence) and str(evidence).strip():
                _reject(f"{endpoint} {date_text} unexpected revision evidence")
            actual_values = {}
            for column in (*OHLC, "volume"):
                expected = float(specification[f"{endpoint}_actual"][column])
                actual = float(row[f"actual_{column}"])
                raw = float(row[column])
                expected_raw = expected * factor if column == "volume" else expected / factor
                reconstructed = raw / factor if column == "volume" else raw * factor
                exact_volume = endpoint == "current" and column == "volume"
                if exact_volume:
                    valid = actual == expected and raw == expected_raw and reconstructed == actual
                else:
                    # Absolute endpoint fingerprints only: percentage tolerance
                    # or an inferred tenfold ratio cannot authorize this repair.
                    valid = (
                        np.isclose(actual, expected, rtol=0, atol=1e-3)
                        and np.isclose(raw, expected_raw, rtol=0, atol=1e-3)
                        and np.isclose(reconstructed, actual, rtol=0, atol=1e-3)
                    )
                if not valid:
                    _reject(f"{endpoint} {date_text} {column} endpoint")
                actual_values[column] = actual
            observed[endpoint][date_text] = actual_values
        corrected[date_text] = {
            column: float(specification["current_actual"][column])
            for column in (*OHLC, "volume")
        }
        overrides[(symbol, date)] = {
            f"actual_{column}": value for column, value in corrected[date_text].items()
        }

    return overrides, [{
        "identity": reviewed["identity"],
        "manifestVersion": reviewed["manifest_version"],
        "manifestSha256": manifest_hash,
        "previousSourceSha256": previous_source_sha256,
        "symbol": symbol,
        "previousBasis": reviewed["previous_basis"],
        "currentBasis": reviewed["current_basis"],
        "dates": list(CORRECTION_DATES),
        "oldActualValues": observed["previous"],
        "newActualValues": observed["current"],
        "correctedBaselineActualValues": corrected,
        "primarySourceURLs": list(reviewed["primary_sources"]),
    }]
