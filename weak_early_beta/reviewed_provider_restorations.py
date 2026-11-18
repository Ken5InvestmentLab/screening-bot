"""Raw-price restorations backed by reviewed JPX evidence.

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
# Observed vendor bytes, not an official quote or permission to repair it.
# The Nov 18 retained-source readback proved this exact bar was quarantined.
INVALID_SESSION = pd.Timestamp("2026-11-18")
INVALID_OHLCV = (78., 107., 73., float.fromhex("0x1.b800000000001p+6"), 12506100.)


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


def _retained_invalid_bar(group, current_basis: pd.Timestamp, *, previous: bool) -> bool:
    """Allow only the known unusable bar to reach ordinary OHLC quarantine.

    This is a history exception for later snapshots, never a same-day replay
    authorization. Every raw value and the provider flag remain untouched.
    """
    from .corporate_actions import normalize_daily

    if current_basis <= INVALID_SESSION or len(group) != 1:
        return False
    row = group.iloc[0]
    # Existing CSV loaders decode the persisted close to exactly 110.0.
    # Admit that representation only in the hash-bound previous quality row;
    # fresh vendor input must still retain the original IEEE-754 endpoint.
    expected_values = list(INVALID_OHLCV)
    if previous and _equals([row.close], 110.):
        expected_values[FIELDS.index("close")] = 110.
    if (
        row.date != INVALID_SESSION
        or str(row.provider_repaired).lower() != "true"
        or any(not _equals([row[field]], value) for field, value in zip(FIELDS, expected_values))
    ):
        return False
    if previous and (
        str(row.source_usable).lower() != "false" or row.source_issue != "inconsistent_ohlc"
        or any(not _equals([row[f"actual_{field}"]], value) for field, value in zip(FIELDS, expected_values))
    ):
        return False
    # Exercise the unchanged quality contract on an isolated raw row. Future
    # normalizer changes must not silently make this flagged quote usable.
    checked = normalize_daily(
        group[["symbol", "date", *FIELDS, "split_ratio", "provider_repaired", "off_session_actions"]],
        basis_asof=current_basis,
    )
    return not bool(checked.source_usable.item()) and checked.source_issue.item() == "inconsistent_ohlc"


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
    for is_previous, group in ((True, old), (False, now)):
        flagged = ~group.provider_repaired.astype(str).str.lower().eq("false")
        if (
            not _equals(group.split_ratio, 0)
            or not group.off_session_actions.fillna("").eq("").all()
            or (flagged.any() and not _retained_invalid_bar(
                group.loc[flagged], current_basis, previous=is_previous,
            ))
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


NOVEMBER_AUDIT_ATTR = "verified_november_9_restorations"
NOVEMBER_SEED_SHA = "7d66aba2de7f1568eeaacfc0c19ed4a964aaca8a436f5d8f620fb4e5e9b70122"
NOVEMBER_MANIFEST_SHA = "cacfd93e327a886819f72244a8b3abeb93506bb16a9988a1a8c84ae058e89706"
NOVEMBER_INVENTORY_SHA = "e42ce2d386a19ce23cbbb69e5672a70719dff1ba4e970605f7c9ab3fd2e06d62"
NOVEMBER_SESSION = pd.Timestamp("2026-11-06")
NOVEMBER_FIRST_BASIS = pd.Timestamp("2026-11-09")
NOVEMBER_QUOTES = MappingProxyType({
    "6918": ("open", 2804, (2900, 2953, 2804, 2951, 74600), 86,
             "00031-7fe2903fd0038830eed4.pkl", "8194c1bb3640b4cbf7abd5d90351859b4613dc5ede12a9827f492f37e45f92d1"),
    "7886": ("low", 480, (500, 509, 464, 509, 7000), 161,
             "00037-2e93ce6a4ab3179afcb1.pkl", "2d6d43ed855dad61b05e5ab07c22a58a20f4624efc6dee7b94aa92b032d3319c"),
})


def _november_audit(symbol, previous_sha, basis, observed_value):
    field, _, expected, page, packet, packet_sha = NOVEMBER_QUOTES[symbol]
    observed = list(expected)
    position = FIELDS.index(field)
    observed[position] = observed_value
    return {
        "identity": "CLOUD_REVIEWED_NOVEMBER_9_RESTORATION_V1",
        "symbol": symbol, "session": "2026-11-06", "currentBasis": f"{basis:%Y-%m-%d}",
        "field": field, "seedSourceSha256": NOVEMBER_SEED_SHA, "previousSourceSha256": previous_sha,
        "archiveManifestSha256": NOVEMBER_MANIFEST_SHA,
        "receiptInventorySha256": NOVEMBER_INVENTORY_SHA,
        "targetPacket": packet, "targetPacketSha256": packet_sha,
        "officialPDFURL": "https://www.jpx.co.jp/automation/markets/statistics-equities/daily/files/202611/stq_20261106.pdf",
        "officialPDFSha256": "e571e29926bd76b37724f62d5ac417389e290675d08b5f719c3fa748fb8d0183",
        "officialPDFPage": page, "observedOHLCV": observed,
        "restoredOHLCV": list(expected), "changedCellCount": int(observed_value != expected[position]),
    }


def _verify_november_archive(archive):
    from .corporate_actions import CorporateActionError

    receipts = sorted(
        [file.name, _file_sha256(file)] for file in archive.directory.glob("0*.json")
    )
    inventory_sha = hashlib.sha256(json.dumps(receipts, separators=(",", ":")).encode()).hexdigest()
    if (
        archive.context.get("previousSourceSha256") != NOVEMBER_SEED_SHA
        or archive.manifest.get("requests") != 47 or archive.sequence != 47
        or _file_sha256(archive.manifest_path) != NOVEMBER_MANIFEST_SHA
        or inventory_sha != NOVEMBER_INVENTORY_SHA
        or any(_file_sha256(archive.directory / packet) != packet_sha
               for _, _, _, _, packet, packet_sha in NOVEMBER_QUOTES.values())
    ):
        raise CorporateActionError("reviewed November 9 restoration: retained archive differs")


def _verify_november_audit(symbol, audit, old_basis):
    from .corporate_actions import CorporateActionError

    if not isinstance(audit, dict):
        raise CorporateActionError("reviewed November 9 restoration: prior audit is missing")
    previous_sha = audit.get("previousSourceSha256")
    observed = audit.get("observedOHLCV")
    field, bad_value, expected, *_ = NOVEMBER_QUOTES[symbol]
    position = FIELDS.index(field)
    if (
        not _sha(previous_sha) or not isinstance(observed, list) or len(observed) != len(FIELDS)
        or type(observed[position]) is not int or observed[position] not in (bad_value, expected[position])
        or audit != _november_audit(symbol, previous_sha, old_basis, observed[position])
        or (previous_sha == NOVEMBER_SEED_SHA and old_basis != NOVEMBER_FIRST_BASIS)
    ):
        raise CorporateActionError(f"reviewed {symbol} restoration: prior audit differs")


def _november_quote(previous, current, symbol, basis, prior_audit, seed):
    from .corporate_actions import CorporateActionError, _dates

    before_symbol = previous.loc[previous["symbol"].eq(symbol)]
    incoming_symbol = current.loc[current["symbol"].eq(symbol)]
    before_dates, incoming_dates = _dates(before_symbol["date"]), _dates(incoming_symbol["date"])
    if not seed and incoming_dates.min() > NOVEMBER_SESSION:
        return None
    before_rows = before_symbol.loc[before_dates == NOVEMBER_SESSION]
    incoming_rows = incoming_symbol.loc[incoming_dates == NOVEMBER_SESSION]
    if len(before_rows) != 1 or len(incoming_rows) != 1:
        raise CorporateActionError(f"reviewed {symbol} restoration: ambiguous target")

    before, incoming = before_rows.iloc[0], incoming_rows.iloc[0]
    old_basis = pd.Timestamp(before["basis_asof"])
    if seed:
        if old_basis != NOVEMBER_SESSION or basis != NOVEMBER_FIRST_BASIS:
            raise CorporateActionError(f"reviewed {symbol} restoration: seed basis differs")
    else:
        if not NOVEMBER_FIRST_BASIS <= old_basis <= basis:
            raise CorporateActionError(f"reviewed {symbol} restoration: basis moved backwards")
        _verify_november_audit(symbol, prior_audit, old_basis)

    field, bad_value, expected, *_ = NOVEMBER_QUOTES[symbol]
    official_value = expected[FIELDS.index(field)]
    if (
        str(before["source_usable"]).lower() != "true"
        or not (pd.isna(before["source_issue"]) or before["source_issue"] == "")
        or not _equals([before["split_factor"]], 1)
        or any(not _equals([before[name], before[f"actual_{name}"]], value)
               for name, value in zip(FIELDS, expected))
        or any(not _equals([incoming[name]], value) for name, value in zip(FIELDS, expected) if name != field)
        or not _number(incoming[field]) or incoming[field] not in ((bad_value,) if seed else (bad_value, official_value))
    ):
        raise CorporateActionError(f"reviewed {symbol} restoration: OHLCV differs")
    for row in (before, incoming):
        journal = row["off_session_actions"]
        if (not _equals([row["split_ratio"]], 0)
                or str(row["provider_repaired"]).lower() != "false"
                or not (pd.isna(journal) or journal == "")):
            raise CorporateActionError(f"reviewed {symbol} restoration: unexpected action or repair")

    audit = _november_audit(symbol, previous.attrs["source_sha256"], basis, int(incoming[field]))
    return incoming_rows.index[0], field, official_value, audit


def restore_reviewed_november_quotes(previous, current, *, basis_asof, archive):
    """Restore only the evidenced raw cells, before ordinary source validation."""
    from .acquisition import AcquisitionArchive
    from .corporate_actions import CorporateActionError

    if previous is None:
        return current, {}
    source_sha = previous.attrs.get("source_sha256")
    seed = source_sha == NOVEMBER_SEED_SHA
    lineage = previous.attrs.get(NOVEMBER_AUDIT_ATTR)
    if seed:
        if not isinstance(archive, AcquisitionArchive) or not archive.replay or archive.context.get("date") != "2026-11-09":
            return current, {}
        _verify_november_archive(archive)
        prior = dict.fromkeys(NOVEMBER_QUOTES)
    elif lineage is None:
        return current, {}
    else:
        if not _sha(source_sha) or not isinstance(lineage, dict) or lineage.get("dailySha256") != source_sha:
            raise CorporateActionError("reviewed November 9 restoration: source-quality lineage differs")
        prior = lineage.get("restorations")
        if not isinstance(prior, dict) or not prior or not prior.keys() <= NOVEMBER_QUOTES.keys():
            raise CorporateActionError("reviewed November 9 restoration: unexpected audit identities")
    if not current.index.is_unique:
        raise CorporateActionError("reviewed November 9 restoration: ambiguous raw index")

    result = current.copy(deep=False)
    audits = {}
    basis = pd.Timestamp(basis_asof)
    for symbol, prior_audit in prior.items():
        update = _november_quote(previous, current, symbol, basis, prior_audit, seed)
        if update is None:
            continue
        index, field, official_value, audit = update
        audits[symbol] = audit
        if audit["changedCellCount"]:
            column = result[field].copy()
            column.loc[index] = official_value
            result[field] = column
    return result, audits
