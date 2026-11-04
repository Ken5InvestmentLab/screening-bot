"""One application-level raw-price restoration backed by reviewed JPX evidence.

Provider packets and previous comparison values remain untouched. The quality
receipt is not signed: lineage relies on a matching computed CSV hash and the
fixed audit contract, as with reviewed off-session journal retention.
"""

from __future__ import annotations

import hashlib
import json
import re
from numbers import Real
from types import MappingProxyType

import numpy as np
import pandas as pd


SEED_SHA256 = "2f5d5a26129bad12d4d8c60398595d0c53b5df3bc0b32fce4e36321015ec5935"
PRIOR_AUDIT_ATTR = "verified_reviewed_provider_restorations"
CATALOG = MappingProxyType({
    "identity": "CLOUD_REVIEWED_PROVIDER_RESTORATION_V1",
    "symbol": "3624",
    "session": "2026-11-02",
    "seedSourceSha256": SEED_SHA256,
    "seedPreviousBasis": "2026-11-02",
    "seedCurrentBasis": "2026-11-04",
    "previousOHLCV": (33, 34, 28, 31, 1917200),
    "incomingOHLCV": (33, 33, 28, 31, 1917200),
    "officialPDFURL": "https://www.jpx.co.jp/automation/markets/statistics-equities/daily/files/202611/stq_20261102.pdf",
    "officialPDFSha256": "dc6cb4fe5b94e59e4551a464bd13270d6f5aaaa656187facb25145d2f4a1ef2b",
    "officialPDFPage": 132,
    "morningOHLC": (33, 34, 28, 31),
    "afternoonOHLC": (31, 31, 30, 31),
    "requests": 47,
    "receiptInventorySha256": "97c4bbb40e8c5a21f1143899c72e27950c94ee3018b8aa888dbf311e243ac055",
    "targetPacket": "00011-ae8f5b4225001403bfb5.pkl",
    "targetPacketSha256": "868553ade2b0739f7667a089cae2b452f4bcd42a9c20b4b2ebc49de3c011893a",
})
CATALOG_SHA256 = hashlib.sha256(
    json.dumps(dict(CATALOG), sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
FIELDS = ("open", "high", "low", "close", "volume")
SESSION = pd.Timestamp(CATALOG["session"])
FIRST_BASIS = pd.Timestamp(CATALOG["seedCurrentBasis"])


def _reject(reason: str) -> None:
    from .corporate_actions import CorporateActionError

    raise CorporateActionError(f"reviewed provider restoration rejected for 3624: {reason}")


def _sha(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _file_sha256(path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_seed_archive(archive) -> None:
    """Read and verify every retained packet; never deserialize or rewrite it."""
    from .acquisition import AcquisitionArchive

    if not isinstance(archive, AcquisitionArchive):
        _reject("seed requires an AcquisitionArchive")
    try:
        manifest = json.loads(archive.manifest_path.read_text(encoding="utf-8"))
        context = archive.context
        if (
            manifest != archive.manifest
            or manifest.get("identity") != "CLOUD_ACQUISITION_V1"
            or manifest.get("context") != context
            or context.get("date") != CATALOG["seedCurrentBasis"]
            or context.get("previousSourceSha256") != SEED_SHA256
            or type(manifest.get("requests")) is not int
            or manifest["requests"] != CATALOG["requests"]
        ):
            _reject("archive context or request count differs")
        receipts = {
            path.name: path for path in archive.directory.glob("*.json")
            if path.name != "manifest.json"
        }
        packets = {path.name: path for path in archive.directory.glob("*.pkl")}
        if len(receipts) != CATALOG["requests"] or len(packets) != CATALOG["requests"]:
            _reject("incomplete archive inventory")
        inventory_sha256 = hashlib.sha256(
            json.dumps(sorted([
                [name, hashlib.sha256(path.read_bytes()).hexdigest()]
                for name, path in receipts.items()
            ]), separators=(",", ":")).encode()
        ).hexdigest()
        if inventory_sha256 != CATALOG["receiptInventorySha256"]:
            _reject("receipt inventory SHA-256 differs")
        numbers = set()
        target_seen = False
        for name, path in sorted(receipts.items()):
            match = re.fullmatch(r"(\d{5})-([0-9a-f]{20})\.json", name)
            if match is None:
                _reject("unexpected receipt filename")
            number = int(match[1])
            if number in numbers:
                _reject("duplicate archive sequence")
            numbers.add(number)
            saved = json.loads(path.read_text(encoding="utf-8"))
            request = saved.get("request")
            if not isinstance(request, dict) or saved.get("error"):
                _reject("archive contains a request error")
            if not isinstance(saved.get("providerErrors", {}), dict):
                _reject("archive providerErrors must be an object")
            # The exact inventory root pins the original inner repair errors
            # as well as all other receipt bytes. Preserve those errors; they
            # do not authorize accepting a top-level request failure.
            key = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()[:20]
            packet_name = f"{number:05d}-{key}.pkl"
            if name != f"{number:05d}-{key}.json" or packet_name not in packets:
                _reject("receipt request identity differs")
            digest = _file_sha256(packets[packet_name])
            if not _sha(saved.get("sha256")) or saved["sha256"] != digest:
                _reject("retained packet SHA-256 differs")
            if packet_name == CATALOG["targetPacket"]:
                tickers = request.get("tickers")
                kwargs = request.get("kwargs")
                if (
                    digest != CATALOG["targetPacketSha256"]
                    or request.get("kind") != "batch"
                    or not isinstance(tickers, list) or "3624.T" not in tickers
                    or not isinstance(kwargs, dict) or kwargs.get("repair") is not True
                ):
                    _reject("reviewed target packet differs")
                target_seen = True
        if numbers != set(range(1, CATALOG["requests"] + 1)) or not target_seen:
            _reject("numbered inventory or reviewed target is missing")
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as exc:
        from .corporate_actions import CorporateActionError

        raise CorporateActionError("invalid reviewed provider acquisition archive") from exc


def _number(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, (bool, np.bool_)) and np.isfinite(value)


def _equals(values, expected: Real) -> bool:
    return all(_number(value) and value == expected for value in values)


def _fingerprint(values) -> str:
    payload = [
        CATALOG["symbol"], CATALOG["session"],
        *[float(value).hex() for value in values],
        float(0).hex(), float(1).hex(), False, [],
    ]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def _audit(previous_sha: str, previous_basis: str, current_basis: str, observed: int) -> dict:
    before = list(CATALOG["incomingOHLCV"])
    before[1] = observed
    after = list(CATALOG["previousOHLCV"])
    return {
        "identity": CATALOG["identity"],
        "catalogSha256": CATALOG_SHA256,
        "symbol": CATALOG["symbol"],
        "session": CATALOG["session"],
        "seedSourceSha256": SEED_SHA256,
        "seedPreviousBasis": CATALOG["seedPreviousBasis"],
        "seedCurrentBasis": CATALOG["seedCurrentBasis"],
        "previousSourceSha256": previous_sha,
        "previousBasis": previous_basis,
        "currentBasis": current_basis,
        "officialPDFURL": CATALOG["officialPDFURL"],
        "officialPDFSha256": CATALOG["officialPDFSha256"],
        "officialPDFPage": CATALOG["officialPDFPage"],
        "targetPacket": CATALOG["targetPacket"],
        "targetPacketSha256": CATALOG["targetPacketSha256"],
        "receiptInventorySha256": CATALOG["receiptInventorySha256"],
        "expectedPreviousOHLCV": after,
        "observedOHLCV": before,
        "restoredOHLCV": after,
        "observedHigh": observed,
        "restoredHigh": 34,
        "targetBeforeSha256": _fingerprint(before),
        "targetAfterSha256": _fingerprint(after),
        "changedCellCount": int(observed != 34),
        "applicationCorrection": True,
        "providerRepaired": False,
    }


def _verify_lineage(previous, source_sha: str, old_basis: pd.Timestamp) -> None:
    from .corporate_actions import _dates

    wrapper = previous.attrs.get(PRIOR_AUDIT_ATTR)
    if (
        not _sha(source_sha) or not isinstance(wrapper, dict)
        or set(wrapper) != {"dailySha256", "restorations"}
        or wrapper["dailySha256"] != source_sha
    ):
        _reject("no matching source-quality lineage")
    audits = wrapper["restorations"]
    if not isinstance(audits, list) or len(audits) != 1 or not isinstance(audits[0], dict):
        _reject("invalid restoration lineage")
    audit = audits[0]
    try:
        prior_sha = audit["previousSourceSha256"]
        prior_basis = _dates([audit["previousBasis"]])[0]
        current_basis = _dates([audit["currentBasis"]])[0]
        observed = audit["observedHigh"]
        if (
            not _sha(prior_sha) or type(observed) is not int or observed not in (33, 34)
            or current_basis != old_basis or current_basis < FIRST_BASIS
            or prior_basis > current_basis
            or (prior_sha == SEED_SHA256 and (
                prior_basis != pd.Timestamp(CATALOG["seedPreviousBasis"])
                or current_basis != FIRST_BASIS
            ))
            or (prior_sha != SEED_SHA256 and prior_basis < FIRST_BASIS)
            or audit != _audit(
                prior_sha, f"{prior_basis:%Y-%m-%d}", f"{current_basis:%Y-%m-%d}", observed,
            )
            or audit["applicationCorrection"] is not True
            or audit["providerRepaired"] is not False
            or type(audit["changedCellCount"]) is not int
        ):
            _reject("catalog, endpoints or restoration proof differs")
    except (KeyError, TypeError, ValueError) as exc:
        from .corporate_actions import CorporateActionError

        raise CorporateActionError("invalid reviewed provider restoration lineage") from exc


def restore_reviewed_provider_values(
    previous: pd.DataFrame | None,
    current: pd.DataFrame,
    *,
    basis_asof: pd.Timestamp,
    archive=None,
) -> tuple[pd.DataFrame, list[dict]]:
    """Restore exactly one current raw high, or audit an already-correct quote.

    Unrelated source hashes remain under ordinary revision validation. No
    tolerance authorizes this operation, and no comparison array is altered.
    """
    from .corporate_actions import (
        ACTION_SOURCE, ACTUAL_COLUMNS, BASIS_COLUMNS, PRICE_BASIS,
        REVISION_EVIDENCE, VERSION, _dates,
    )

    if previous is None:
        return current, []
    source_sha = previous.attrs.get("source_sha256")
    seed = source_sha == SEED_SHA256
    if not seed and PRIOR_AUDIT_ATTR not in previous.attrs:
        return current, []
    if "symbol" not in previous or "symbol" not in current:
        _reject("missing symbol column")
    required_raw = {"symbol", "date", *FIELDS, "split_ratio", "provider_repaired", "off_session_actions"}
    if not required_raw.issubset(current) or not (
        required_raw | set(ACTUAL_COLUMNS) | set(BASIS_COLUMNS)
    ).issubset(previous):
        _reject("incomplete raw or previous basis metadata")
    old_columns = [*dict.fromkeys([
        "symbol", "date", *FIELDS, *ACTUAL_COLUMNS, *BASIS_COLUMNS,
        *([REVISION_EVIDENCE] if REVISION_EVIDENCE in previous else []),
    ])]
    now_columns = [*required_raw, *([REVISION_EVIDENCE] if REVISION_EVIDENCE in current else [])]
    # Only narrow symbol slices are copied for validation.
    old = previous.loc[previous.symbol.eq(CATALOG["symbol"]), old_columns].copy()
    now = current.loc[current.symbol.eq(CATALOG["symbol"]), now_columns].copy()
    if old.empty or now.empty:
        _reject("expected symbol history is missing")
    old["date"], now["date"] = _dates(old.date), _dates(now.date)
    for group in (old, now):
        if group.date.duplicated().any():
            _reject("duplicate reviewed symbol/session")
    old["basis_asof"] = _dates(old.basis_asof)
    current_basis = _dates([basis_asof])[0]
    if old.basis_asof.nunique() != 1:
        _reject("mixed previous basis")
    old_basis = old.basis_asof.iloc[0]
    if seed:
        if old_basis != pd.Timestamp(CATALOG["seedPreviousBasis"]) or current_basis != FIRST_BASIS:
            _reject("seed bases differ")
    else:
        _verify_lineage(previous, source_sha, old_basis)
        if current_basis < FIRST_BASIS or current_basis < old_basis:
            _reject("basis moved backwards")
    # A rolling history can eventually expire the reviewed session altogether.
    if old.date.min() > SESSION and now.date.min() > SESSION:
        return current, []
    if old.date.eq(SESSION).sum() != 1 or now.date.eq(SESSION).sum() != 1:
        _reject("expected reviewed session is missing")
    if old.date.max() > old_basis or now.date.max() > current_basis:
        _reject("session after declared basis")
    reviewed_old = old.loc[old.date.eq(SESSION)]
    reviewed_now = now.loc[now.date.eq(SESSION)]
    for column, expected in (
        ("price_basis", PRICE_BASIS),
        ("corporate_actions_version", VERSION),
        ("corporate_actions_source", ACTION_SOURCE),
    ):
        if not old[column].eq(expected).fillna(False).all():
            _reject(f"unexpected previous {column}")
    if not _equals(old.split_factor, 1):
        _reject("previous split factor differs")
    # Source quality and raw/actual agreement authorize only the reviewed row.
    # Other sessions retain ordinary normalization and revision validation.
    if not reviewed_old.source_usable.astype(str).str.lower().eq("true").all():
        _reject("previous reviewed source is not usable")
    if not reviewed_old.source_issue.fillna("").eq("").all():
        _reject("previous reviewed source issue is not empty")
    for group in (old, now):
        if (
            not _equals(group.split_ratio, 0)
            or not group.provider_repaired.astype(str).str.lower().eq("false").all()
            or not group.off_session_actions.fillna("").eq("").all()
        ):
            _reject("repair flag or action journal differs")
    for group in (reviewed_old, reviewed_now):
        if REVISION_EVIDENCE in group and not group[REVISION_EVIDENCE].fillna("").eq("").all():
            _reject("reviewed revision evidence differs")
    # fetch_daily supplies raw rows. Never leave stale derived columns behind.
    if set(ACTUAL_COLUMNS).intersection(current) or (
        set(BASIS_COLUMNS) - {"split_ratio", "off_session_actions", "provider_repaired"}
    ).intersection(current):
        _reject("current input must precede normalization")
    for field in FIELDS:
        if not all(
            _number(raw) and _number(actual) and raw == actual
            for raw, actual in zip(reviewed_old[field], reviewed_old[f"actual_{field}"])
        ):
            _reject("previous raw/actual units differ")
    before = reviewed_old.iloc[0]
    incoming = reviewed_now.iloc[0]
    if any(not _equals([before[field]], value) for field, value in zip(FIELDS, CATALOG["previousOHLCV"])):
        _reject("previous endpoint differs")
    observed = incoming["high"]
    if not _number(observed) or observed not in (33, 34):
        _reject("unreviewed incoming high")
    for field, value in zip(FIELDS, CATALOG["incomingOHLCV"]):
        if field != "high" and not _equals([incoming[field]], value):
            _reject("incoming OHLCV endpoint differs")
    if seed:
        verify_seed_archive(archive)
    audit = _audit(source_sha, f"{old_basis:%Y-%m-%d}", f"{current_basis:%Y-%m-%d}", int(observed))
    if observed == 34:
        return current, [audit]
    positions = np.flatnonzero(
        current.symbol.eq(CATALOG["symbol"]).to_numpy()
        & (_dates(current.date) == SESSION)
    )
    if len(positions) != 1:
        _reject("ambiguous target position")
    result = current.copy(deep=False)
    high = current["high"].copy(deep=True)
    high.iloc[int(positions[0])] = 34
    result["high"] = high
    return result, [audit]
