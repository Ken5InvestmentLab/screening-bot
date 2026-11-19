"""Import one verified owner READY generation into the dedicated member store."""

import datetime
import hashlib
import json
import re
import stat
from pathlib import Path

from .publisher import literal


_SOURCE_KEYS = ("status", "dataset_id", "revision", "as_of", "source_version")
_ROW_LIMITS = {"history": 100, "analytics": 3, "chart": 3000}
_PRESETS = ("defensive", "medium", "return_priority")
_WATCH_STATES = {
    "WATCHING", "TRIGGERED", "EXPIRED", "UP_ESCAPED", "DOWN_INVALIDATED", "REFERENCE_ONLY",
}
_MAX_SAFE_INT = 2**53 - 1
_MAX_MANIFEST = 65_536
_MAX_PART = 196_608
_BATCH_SIZE = 8
_SQL_STATEMENT_LIMIT = 90_000  # WranglerD1 serializes parameters into SQL.
_MANIFEST = "SELECT digest,json FROM private_projection_manifest WHERE identity=?"
_MARKER = "SELECT identity,digest FROM private_projection_ready WHERE singleton=1"
_INSERT_MANIFEST = """
    INSERT INTO private_projection_manifest (identity,digest,json) VALUES (?,?,?)
    ON CONFLICT(identity) DO NOTHING
"""
_INSERT_PART = """
    INSERT INTO private_projection_part (identity,kind,idx,json) VALUES (?,?,?,?)
    ON CONFLICT(identity,kind,idx) DO NOTHING
"""
_STAGED = """
    EXISTS (SELECT 1 FROM private_projection_manifest WHERE identity=? AND digest=?)
    AND (SELECT COUNT(*) FROM private_projection_part WHERE identity=?)=?
"""


def _require(condition, code):
    if not condition:
        raise ValueError(code)


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _keys(value, keys):
    return isinstance(value, dict) and value.keys() == set(keys)


def _int(value, minimum=0, maximum=_MAX_SAFE_INT):
    return type(value) is int and minimum <= value <= maximum


def _day(value):
    if not isinstance(value, str):
        return False
    try:
        return datetime.date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _identity(source):
    _require(
        _keys(source, _SOURCE_KEYS) and source["status"] == "READY"
        and isinstance(source["dataset_id"], str)
        and re.fullmatch(r"a-[0-9a-f]{20,64}", source["dataset_id"])
        and _int(source["revision"], 1) and _day(source["as_of"])
        and _hash(source["source_version"]),
        "member_owner_ready_invalid",
    )
    # The Worker uses this same ordered JSON text as the D1 key.
    return json.dumps({key: source[key] for key in _SOURCE_KEYS}, separators=(",", ":"))


def _json(text):
    def unique(items):
        result = dict(items)
        _require(len(result) == len(items), "member_projection_duplicate_json_key")
        return result

    def unsupported(_):
        raise ValueError("member_projection_invalid_json_constant")

    try:
        return json.loads(text, object_pairs_hook=unique, parse_constant=unsupported)
    except (ValueError, RecursionError):
        raise ValueError("member_projection_invalid_json") from None


def _read(path, limit):
    try:
        info = path.lstat()
        _require(
            stat.S_ISREG(info.st_mode) and not path.is_symlink() and 0 < info.st_size <= limit,
            "member_projection_file_invalid",
        )
        with path.open("rb") as stream:
            raw = stream.read(limit + 1)
        _require(len(raw) == info.st_size, "member_projection_file_changed")
        return raw, raw.decode("utf-8")
    except (OSError, UnicodeError):
        raise ValueError("member_projection_file_unavailable") from None


def _amount(value):
    return type(value) in (int, float) and abs(value) < 1e12


def _public_part_shape(part, kind, index, rows, as_of):
    # The pinned builder and Worker validate the actual analytic values.
    # Reject any data outside the builder's public field and container shapes.
    _require(
        _keys(part, ("kind", "index", "rows")) and part["kind"] == kind
        and _int(part["index"], index, index) and isinstance(part["rows"], list)
        and len(part["rows"]) == rows,
        "member_projection_part_shape",
    )
    for position, row in enumerate(part["rows"]):
        if kind == "history":
            allowed = (
                _keys(row, ("date", "symbol", "state")) and _day(row["date"]) and row["date"] <= as_of
                and isinstance(row["symbol"], str) and re.fullmatch(r"[0-9A-Z]{4}", row["symbol"])
                and isinstance(row["state"], str) and row["state"] in _WATCH_STATES
            )
        elif kind == "chart":
            allowed = (
                _keys(row, ("date", "equity_yen", "holding_count")) and _day(row["date"]) and row["date"] <= as_of
                and (
                    row["equity_yen"] is None and row["holding_count"] is None
                    or _amount(row["equity_yen"]) and _int(row["holding_count"])
                )
            )
        else:
            allowed = (
                _keys(row, ("preset", "from", "through", "resolved", "metrics"))
                and row["preset"] == _PRESETS[position]
                and _day(row["from"]) and row["from"] <= as_of and row["through"] == as_of
                and type(row["resolved"]) is bool
                and (
                    not row["resolved"] and row["metrics"] is None
                    or row["resolved"] and _metrics_shape(row["metrics"])
                )
            )
        _require(allowed, "member_projection_public_row_shape")


def _metrics_shape(metrics):
    return (
        _keys(metrics, ("net_profit", "max_drawdown_pct", "win_rate_pct", "trade_count"))
        and _amount(metrics["net_profit"]) and _amount(metrics["max_drawdown_pct"])
        and (metrics["win_rate_pct"] is None or _amount(metrics["win_rate_pct"]))
        and _int(metrics["trade_count"])
    )


def _prepared(folder, receipt_sha256):
    folder = Path(folder).resolve()
    receipt_bytes, receipt_text = _read(folder / "receipt.json", _MAX_MANIFEST)
    _require(_hash(receipt_sha256) and _sha(receipt_bytes) == receipt_sha256, "member_projection_receipt_pin")
    receipt = _json(receipt_text)
    _require(
        _keys(receipt, (
            "schema", "source", "source_manifest_sha256", "owner_readback_sha256",
            "projection_manifest_sha256", "history_rows", "parts", "activated",
        )) and receipt["schema"] == "NEW_A_MEMBER_PROJECTION_OFFLINE_V1"
        and receipt["activated"] is False and _hash(receipt["source_manifest_sha256"])
        and _hash(receipt["owner_readback_sha256"]) and _hash(receipt["projection_manifest_sha256"])
        and _int(receipt["history_rows"]) and _int(receipt["parts"], 4, 204),
        "member_projection_receipt_invalid",
    )
    identity = _identity(receipt["source"])
    raw, manifest_text = _read(folder / "manifest.json", _MAX_MANIFEST)
    digest = _sha(raw)
    _require(digest == receipt["projection_manifest_sha256"], "member_projection_manifest_pin")
    manifest = _json(manifest_text)
    _require(
        _keys(manifest, ("schema", "audience", "basis", "source", "parts"))
        and manifest["schema"] == "NEW_A_SHARED_READONLY_VIEW_V1"
        and manifest["audience"] == "EXISTING_DESIGNATED_DISCORD_ROLE"
        and manifest["basis"] == "SHARED_SIMULATION_DEFAULTS_NOT_OWNER_SETTINGS"
        and _identity(manifest["source"]) == identity and isinstance(manifest["parts"], list)
        and len(manifest["parts"]) == receipt["parts"],
        "member_projection_manifest_invalid",
    )
    counts = dict.fromkeys(_ROW_LIMITS, 0)
    parts = {}
    history_rows = 0
    for descriptor in manifest["parts"]:
        _require(_keys(descriptor, ("kind", "index", "rows", "bytes", "sha256")), "member_projection_descriptor")
        kind, index, rows, size, sha = (descriptor[key] for key in ("kind", "index", "rows", "bytes", "sha256"))
        _require(
            isinstance(kind, str) and kind in counts and _int(index, counts[kind], counts[kind])
            and _int(rows, 1, _ROW_LIMITS[kind]) and _int(size, 1, _MAX_PART) and _hash(sha)
            and (kind != "analytics" or rows == len(_PRESETS)),
            "member_projection_descriptor",
        )
        raw, text = _read(folder / f"{kind}-{index}.json", size)
        _require(len(raw) == size and _sha(raw) == sha, "member_projection_part_pin")
        _public_part_shape(_json(text), kind, index, rows, receipt["source"]["as_of"])
        parts[kind, index] = text
        counts[kind] += 1
        if kind == "history":
            history_rows += rows
    _require(
        counts["analytics"] == 1 and counts["chart"] == 3 and history_rows == receipt["history_rows"],
        "member_projection_inventory",
    )
    return identity, digest, manifest_text, parts


def _checked_marker(marker):
    if marker is not None:
        _require(
            _keys(marker, ("identity", "digest")) and isinstance(marker["identity"], str)
            and len(marker["identity"]) <= 512 and _hash(marker["digest"])
            and _identity(_json(marker["identity"])) == marker["identity"],
            "member_projection_marker_invalid",
        )
    return marker


def read_member_marker(member_db):
    """Read the member activation marker from the authoritative DB adapter."""
    rows = member_db.query(_MARKER)
    _require(len(rows) <= 1, "member_projection_marker_ambiguous")
    return _checked_marker(rows[0] if rows else None)


def _batches(values):
    for offset in range(0, len(values), _BATCH_SIZE):
        yield values[offset:offset + _BATCH_SIZE]


def _check_sql_size(sql, values):
    size = len(sql.encode()) - sql.count("?") + sum(len(literal(value).encode()) for value in values)
    _require(size <= _SQL_STATEMENT_LIMIT, "member_projection_sql_statement_budget")


def _verify_manifest(member_db, identity, digest, text):
    _require(
        member_db.query(_MANIFEST, (identity,)) == [{"digest": digest, "json": text}],
        "member_projection_readback_manifest_conflict",
    )


def _verify_staged(member_db, identity, digest, text, parts):
    _verify_manifest(member_db, identity, digest, text)
    count = member_db.query("SELECT COUNT(*) AS total FROM private_projection_part WHERE identity=?", (identity,))
    _require(count == [{"total": len(parts)}], "member_projection_readback_inventory")
    for group in _batches(list(parts)):
        filters = " OR ".join("(kind=? AND idx=?)" for _ in group)
        values = (identity, *(value for key in group for value in key))
        rows = member_db.query(
            "SELECT kind,idx,json FROM private_projection_part WHERE identity=? AND (" + filters + ")", values,
        )
        _require(
            len(rows) == len(group) and all(_keys(row, ("kind", "idx", "json")) for row in rows)
            and {(row["kind"], row["idx"]): row["json"] for row in rows} == {key: parts[key] for key in group},
            "member_projection_readback_part_conflict",
        )


def import_member_projection(
    member_db, projection_directory, *, read_official_ready, receipt_sha256, expected_previous, activate=True,
):
    """Stage immutable data and optionally CAS-select it. Both adapters must read primary state.

    The receipt hash and expected marker are supplied by the trusted publication host.
    A failure can leave immutable staged rows. A changed owner after successful CAS
    leaves an out-of-generation marker, which the Worker will never serve.
    """
    _require(type(activate) is bool and callable(read_official_ready), "member_projection_import_context")
    baseline = _checked_marker(expected_previous)
    baseline = dict(baseline) if baseline else None
    identity, digest, text, parts = _prepared(projection_directory, receipt_sha256)
    source = _json(identity)
    target = {"identity": identity, "digest": digest}

    def check_owner():
        _require(_identity(read_official_ready()) == identity, "member_owner_ready_changed")

    stage = (_INSERT_MANIFEST, (identity, digest, text))
    statements = [(_INSERT_PART, (identity, *key, part)) for key, part in parts.items()]
    _check_sql_size(*stage)
    for statement in statements:
        _check_sql_size(*statement)
    check_owner()
    current = read_member_marker(member_db)
    replay = current == target
    if not replay:
        _require(current == baseline, "member_projection_marker_compare_and_swap")
        if current:
            _require(_json(current["identity"])["revision"] < source["revision"], "member_projection_revision_conflict")
        member_db.query(*stage)
        _verify_manifest(member_db, identity, digest, text)
        for group in _batches(statements):
            member_db.batch(group)
    _verify_staged(member_db, identity, digest, text, parts)
    check_owner()
    if not activate or replay:
        _require(read_member_marker(member_db) == current, "member_projection_marker_changed")
        check_owner()
        status = "already_active" if replay else "staged"
    else:
        staged = (identity, digest, identity, len(parts))
        if current is None:
            sql = """
                INSERT INTO private_projection_ready (singleton,identity,digest)
                SELECT 1,?,? WHERE """ + _STAGED + " ON CONFLICT(singleton) DO NOTHING"
            values = (identity, digest, *staged)
        else:
            sql = """
                UPDATE private_projection_ready SET identity=?,digest=?
                WHERE singleton=1 AND identity=? AND digest=? AND """ + _STAGED
            values = (identity, digest, current["identity"], current["digest"], *staged)
        # Unknown write outcomes are read back exactly once, without writing again.
        try:
            member_db.query(sql, values)
        except Exception as error:
            if read_member_marker(member_db) != target:
                raise RuntimeError("member_projection_marker_unconfirmed") from error
        else:
            _require(read_member_marker(member_db) == target, "member_projection_marker_compare_and_swap")
        check_owner()
        status = "activated"
    return {
        "status": status, "source": source, **target, "parts": len(parts),
        "activated": status in ("activated", "already_active"),
    }
