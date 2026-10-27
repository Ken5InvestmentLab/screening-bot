"""One byte-pinned Cloud quarantine release, never a provider repair policy.

Return comparison keys and provenance only. Neither input nor canonical trade
economics is changed. The prepared references are retained as reviewed evidence;
this gate does not fetch data or claim new primary-source price corroboration.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .corporate_actions import (
    ACTION_SOURCE, ACTUAL_COLUMNS, OHLC, PRICE_BASIS, REVISION_EVIDENCE,
    REVISION_ISSUE, VERSION, CorporateActionError, _historical_actions,
)


MANIFEST_PATH = Path(__file__).resolve().parent / "state" / "reviewed_repair_releases.json"
MANIFEST_SHA256 = "1f497d13fefb01025a1752570474bae36d98bcff59bbca0a1b123b7cf0387584"
PREVIOUS_SHA256 = "0c4643bb6ea521dc99d9e0a7cab3624bc0e9706ea9796bc26f710af48b278a03"
RELEASE_DATES = ("2026-08-18", "2026-08-19", "2026-08-20", "2026-08-21")
TRANSITION = {
    "identity": "CLOUD_REVIEWED_REPAIR_RELEASE_V1", "manifest_version": 1,
    "previous_source_sha256": PREVIOUS_SHA256, "symbol": "523A",
    "previous_basis": "2026-10-26", "current_basis": "2026-10-27",
    "previous_journal": [], "current_journal": [],
}
COLUMNS = (*OHLC, "volume")


def _reject(detail: str) -> None:
    raise CorporateActionError(f"reviewed repair release mismatch: {detail}")


def _exact(value: Any, expected: Any) -> bool:
    """JSON equality without bool/number coercion or numeric tolerances."""
    if type(expected) in (int, float):
        return type(value) in (int, float) and np.isfinite(value) and value == expected
    if type(value) is not type(expected):
        return False
    if isinstance(expected, dict):
        return value.keys() == expected.keys() and all(_exact(value[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(value) == len(expected) and all(_exact(v, e) for v, e in zip(value, expected))
    return value == expected


def _load_manifest() -> tuple[dict[str, Any], str]:
    try:
        contents = MANIFEST_PATH.read_bytes()
        digest = hashlib.sha256(contents).hexdigest()
        if digest != MANIFEST_SHA256:
            _reject("manifest SHA-256")
        manifest = json.loads(contents.decode("utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise CorporateActionError("cannot load reviewed repair release manifest") from exc
    fields = {*TRANSITION, "primary_sources", "corroborating_sources", "rows"}
    if not isinstance(manifest, dict) or set(manifest) != fields:
        _reject("manifest fields")
    for field, expected in TRANSITION.items():
        if (type(expected) is int and type(manifest[field]) is not int) or not _exact(manifest[field], expected):
            _reject(f"declared {field}")
    sources = manifest["primary_sources"]
    if not isinstance(sources, list) or len(sources) != 3 or any(
        not isinstance(url, str) or not url.startswith("https://") for url in sources
    ):
        _reject("primary references")
    corroboration = manifest["corroborating_sources"]
    if not isinstance(corroboration, list) or len(corroboration) != 1:
        _reject("corroborating references")
    ref = corroboration[0]
    if not isinstance(ref, dict) or set(ref) != {"url", "sha256", "retrieved_at", "rows_verified"} or (
        not isinstance(ref["url"], str) or not ref["url"].startswith("https://")
        or not isinstance(ref["sha256"], str) or len(ref["sha256"]) != 64
        or any(c not in "0123456789abcdef" for c in ref["sha256"])
        or not isinstance(ref["retrieved_at"], str) or not _exact(ref["rows_verified"], 4)
    ):
        _reject("corroborating reference fields")
    rows = manifest["rows"]
    if not isinstance(rows, list) or len(rows) != 4:
        _reject("exactly four reviewed rows required")
    for row, date in zip(rows, RELEASE_DATES):
        if not isinstance(row, dict) or set(row) != {
            "date", "previous_actual", "current_actual", "previous_quarantine_evidence",
        } or row["date"] != date:
            _reject("reviewed row fields/dates")
        for endpoint in ("previous_actual", "current_actual"):
            actual = row[endpoint]
            if not isinstance(actual, dict) or set(actual) != set(COLUMNS) or any(
                type(v) not in (int, float) or not np.isfinite(v) or v <= 0 for v in actual.values()
            ):
                _reject(f"{date} {endpoint}")
        evidence = row["previous_quarantine_evidence"]
        if not isinstance(evidence, dict) or set(evidence) != {
            "identity", "symbol", "date", "previousBasis", "previousProviderRepaired",
            "previousActualVolume", "previousActualOHLC", "historicalActions", "currentActualVolume",
        }:
            _reject(f"{date} evidence fields")
        for field, expected in {
            "identity": "CLOUD_REPAIRED_VOLUME_QUARANTINE_V1", "symbol": "523A", "date": date,
            "previousProviderRepaired": True, "historicalActions": [],
            "previousActualOHLC": {k: row["previous_actual"][k] for k in OHLC},
            "currentActualVolume": row["previous_actual"]["volume"],
        }.items():
            if not _exact(evidence[field], expected):
                _reject(f"{date} evidence {field}")
        if type(evidence["previousActualVolume"]) not in (int, float) or (
            not np.isfinite(evidence["previousActualVolume"]) or evidence["previousActualVolume"] <= 0
        ):
            _reject(f"{date} evidence volume")
        try:
            if not pd.Timestamp(date) < pd.Timestamp(evidence["previousBasis"]) <= pd.Timestamp(TRANSITION["previous_basis"]):
                _reject(f"{date} evidence basis")
        except (TypeError, ValueError) as exc:
            raise CorporateActionError("invalid reviewed repair evidence basis") from exc
    return manifest, digest


def reviewed_repair_release_keys(
    previous: pd.DataFrame, current: pd.DataFrame, *, previous_source_sha256: str | None,
) -> tuple[set[tuple[str, pd.Timestamp]], list[dict[str, Any]]]:
    """Verify all four endpoints atomically; unrelated cache identities opt out.

    Call after normalizing. The quarantine caller additionally checks original
    numeric inputs so reconstruction tolerances cannot conceal a near-match.
    """
    if previous_source_sha256 != PREVIOUS_SHA256:
        return set(), []
    manifest, digest = _load_manifest()
    required = {
        "symbol", "date", *COLUMNS, *ACTUAL_COLUMNS, "basis_asof", "split_ratio", "split_factor",
        "price_basis", "corporate_actions_source", "corporate_actions_version", "provider_repaired",
        "source_usable", "source_issue", "off_session_actions",
    }
    observed: dict[str, dict[str, dict[str, float]]] = {"previous": {}, "current": {}}
    for endpoint, frame in (("previous", previous), ("current", current)):
        if not required.issubset(frame.columns):
            _reject(f"{endpoint} missing metadata")
        group = frame.loc[frame.symbol.eq("523A")]
        basis = pd.Timestamp(manifest[f"{endpoint}_basis"])
        if group.empty or group.basis_asof.isna().any() or not group.basis_asof.eq(basis).all():
            _reject(f"{endpoint} full symbol basis")
        if group.date.duplicated().any():
            _reject(f"{endpoint} duplicate session")
        if _historical_actions(group, basis) != manifest[f"{endpoint}_journal"]:
            _reject(f"{endpoint} complete action journal")
        for field, expected in (
            ("price_basis", PRICE_BASIS), ("corporate_actions_source", ACTION_SOURCE),
            ("corporate_actions_version", VERSION), ("split_factor", 1), ("split_ratio", 0),
        ):
            if group[field].isna().any() or not group[field].eq(expected).all():
                _reject(f"{endpoint} {field}")
        indexed = group.set_index("date")
        for spec in manifest["rows"]:
            date = spec["date"]
            session = pd.Timestamp(date)
            if session not in indexed.index:
                _reject(f"{endpoint} missing {date}")
            row = indexed.loc[session]
            for field, expected in (("provider_repaired", endpoint == "previous"), ("source_usable", endpoint == "current")):
                if not isinstance(row[field], (bool, np.bool_)) or bool(row[field]) is not expected:
                    _reject(f"{endpoint} {date} {field}")
            if not isinstance(row.source_issue, str) or row.source_issue != (REVISION_ISSUE if endpoint == "previous" else ""):
                _reject(f"{endpoint} {date} source issue")
            saved = row.get(REVISION_EVIDENCE, "")
            if endpoint == "previous":
                try:
                    valid = _exact(json.loads(saved), spec["previous_quarantine_evidence"])
                except (TypeError, ValueError):
                    valid = False
                if not valid:
                    _reject(f"{endpoint} {date} original quarantine evidence")
            elif not (isinstance(saved, str) and saved == "") and not (
                pd.api.types.is_scalar(saved) and pd.isna(saved)
            ):
                _reject(f"{endpoint} {date} revision evidence")
            actual = {}
            for column in COLUMNS:
                expected = spec[f"{endpoint}_actual"][column]
                # Factor one: both original and reconstructed values must match
                # exactly. In particular, no price or volume tolerance applies.
                for field in (column, f"actual_{column}"):
                    value = row[field]
                    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.number)) or value != expected:
                        _reject(f"{endpoint} {date} {field}")
                actual[column] = float(row[f"actual_{column}"])
            observed[endpoint][date] = actual
    keys = {("523A", pd.Timestamp(date)) for date in RELEASE_DATES}
    return keys, [{
        "identity": manifest["identity"], "manifestVersion": manifest["manifest_version"],
        "manifestSha256": digest, "previousSourceSha256": previous_source_sha256,
        "symbol": "523A", "previousBasis": manifest["previous_basis"], "currentBasis": manifest["current_basis"],
        "dates": list(RELEASE_DATES), "oldActualValues": observed["previous"], "newActualValues": observed["current"],
        "originalQuarantineEvidence": {r["date"]: copy.deepcopy(r["previous_quarantine_evidence"]) for r in manifest["rows"]},
        "previousHistoricalActions": copy.deepcopy(manifest["previous_journal"]),
        "currentHistoricalActions": copy.deepcopy(manifest["current_journal"]),
        "primarySourceURLs": list(manifest["primary_sources"]),
        "corroboratingSources": copy.deepcopy(manifest["corroborating_sources"]),
    }]
