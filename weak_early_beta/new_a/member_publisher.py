"""Import one verified owner READY generation into the dedicated member store."""

import datetime
import hashlib
import json
import re
import stat
from pathlib import Path

from .publisher import RemoteD1Error, literal


_SOURCE_KEYS = ("status", "dataset_id", "revision", "as_of", "source_version")
_ROW_LIMITS = {"history": 100, "analytics": 3, "chart": 3000}
_PRESETS = ("defensive", "medium", "return_priority")
_WATCH_STATES = {
    "WATCHING", "TRIGGERED", "EXPIRED", "UP_ESCAPED", "DOWN_INVALIDATED", "REFERENCE_ONLY",
    "DATA_GAP", "BASIS_CHANGED", "IDENTITY_CHANGED",
}
_COMPLETED_STATES = {"EXPIRED", "UP_ESCAPED", "DOWN_INVALIDATED", "HOLD_ENDED"}
_TODAY_STATES = {"WATCH_STARTED", "ENTRY_CANDIDATE", "WATCH_TERMINAL", "HOLD_STARTED", "HOLD_ENDED"}
_MAX_HISTORY_PAGES = 200
_MAX_DASHBOARD_ROWS = 1000
_MAX_SAFE_INT = 2**53 - 1
_MAX_MANIFEST = 65_536
_MAX_PART = 196_608
_MAX_FUNDAMENTAL = 16_384
_FUNDAMENTAL_FIELDS = ("材料インパクト", "事業概要", "足元材料", "ファンダ要点", "注意点", "開示リンク", "Sources")
_ANALYSIS_TIMESTAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?(?:Z|[+-]\d\d:\d\d)")
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
_INSERT_FUNDAMENTAL = """
    INSERT INTO private_projection_fundamental (identity,sha256,json) VALUES (?,?,?)
    ON CONFLICT(identity,sha256) DO NOTHING
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


def _public_part_shape(part, kind, index, rows, as_of, view, with_reports):
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
            keys = ("date", "symbol", "state")
            if view == "dashboard":
                keys += ("lane",)
            elif view == "completed":
                keys += ("completed_on",)
            valid_shape = _keys(row, keys) or (
                view == "history" and with_reports and _keys(row, (*keys, "fundamental_sha256"))
                and _hash(row["fundamental_sha256"])
            )
            allowed = (
                valid_shape and _day(row["date"]) and row["date"] <= as_of
                and isinstance(row["symbol"], str) and re.fullmatch(r"[0-9A-Z]{4}", row["symbol"])
                and isinstance(row["state"], str)
            )
            if allowed and view == "dashboard":
                allowed = (row["lane"] == "today" and row["date"] == as_of and row["state"] in _TODAY_STATES
                           or row["lane"] == "watching" and row["state"] == "WATCHING")
            elif allowed and view == "completed":
                allowed = (row["state"] in _COMPLETED_STATES and _day(row["completed_on"])
                           and row["date"] <= row["completed_on"] <= as_of)
            elif allowed:
                allowed = row["state"] in _WATCH_STATES
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


def _fundamental_text(value, limit):
    return isinstance(value, str) and bool(value.strip()) and len(value.encode("utf-8", errors="surrogatepass")) <= limit \
        and not any(0xD800 <= ord(char) <= 0xDFFF for char in value)


def _fundamental_shape(report, expected):
    _require(
        _keys(report, ("date", "symbol", "company_name", "analysis_cutoff", "fields"))
        and (report["date"], report["symbol"]) == expected
        and (report["company_name"] is None or _fundamental_text(report["company_name"], 256))
        and isinstance(report["analysis_cutoff"], str) and _ANALYSIS_TIMESTAMP.fullmatch(report["analysis_cutoff"])
        and isinstance(report["fields"], list) and len(report["fields"]) == len(_FUNDAMENTAL_FIELDS)
        and all(_keys(field, ("label", "text")) and field["label"] == label
                and _fundamental_text(field["text"], 8192) for label, field in zip(_FUNDAMENTAL_FIELDS, report["fields"])),
        "member_projection_fundamental_shape",
    )
    try:
        datetime.datetime.fromisoformat(report["analysis_cutoff"].replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("member_projection_fundamental_cutoff") from None


def _prepared(folder, receipt_sha256):
    folder = Path(folder).resolve()
    receipt_bytes, receipt_text = _read(folder / "receipt.json", _MAX_MANIFEST)
    _require(_hash(receipt_sha256) and _sha(receipt_bytes) == receipt_sha256, "member_projection_receipt_pin")
    receipt = _json(receipt_text)
    version = receipt.get("schema") if isinstance(receipt, dict) else None
    with_reports = version == "NEW_A_MEMBER_PROJECTION_OFFLINE_V3"
    tiered = with_reports or version == "NEW_A_MEMBER_PROJECTION_OFFLINE_V2"
    receipt_keys = (
        "schema", "source", "source_manifest_sha256", "owner_readback_sha256",
        "projection_manifest_sha256", "history_rows", "parts", "activated",
    )
    _require(
        _keys(receipt, (*receipt_keys, "fundamental_reports") if with_reports else receipt_keys)
        and (tiered or version == "NEW_A_MEMBER_PROJECTION_OFFLINE_V1")
        and receipt["activated"] is False and _hash(receipt["source_manifest_sha256"])
        and _hash(receipt["owner_readback_sha256"]) and _hash(receipt["projection_manifest_sha256"])
        and _int(receipt["history_rows"])
        and _int(receipt["parts"], 5 if tiered else 4,
                 2 * _MAX_HISTORY_PAGES + 5 if tiered else _MAX_HISTORY_PAGES + 4)
        and (not with_reports or _int(receipt["fundamental_reports"], 1, min(100 * _MAX_HISTORY_PAGES, receipt["history_rows"]))),
        "member_projection_receipt_invalid",
    )
    identity = _identity(receipt["source"])
    raw, manifest_text = _read(folder / "manifest.json", _MAX_MANIFEST)
    digest = _sha(raw)
    _require(digest == receipt["projection_manifest_sha256"], "member_projection_manifest_pin")
    manifest = _json(manifest_text)
    keys = ("schema", "audience", "basis", "source", "parts")
    if tiered:
        keys += ("history_layout",)
    if with_reports:
        keys += ("fundamental_reports",)
    schema = "NEW_A_SHARED_READONLY_VIEW_V" + ("3" if with_reports else "2" if tiered else "1")
    _require(
        _keys(manifest, keys) and manifest["schema"] == schema
        and (not with_reports or _int(manifest["fundamental_reports"], receipt["fundamental_reports"], receipt["fundamental_reports"]))
        and manifest["audience"] == ("AUTHENTICATED_TIERED_DISCORD_VIEW" if tiered else "EXISTING_DESIGNATED_DISCORD_ROLE")
        and manifest["basis"] == "SHARED_SIMULATION_DEFAULTS_NOT_OWNER_SETTINGS"
        and _identity(manifest["source"]) == identity and isinstance(manifest["parts"], list)
        and len(manifest["parts"]) == receipt["parts"],
        "member_projection_manifest_invalid",
    )
    premium_pages = dashboard_index = None
    if tiered:
        layout = manifest["history_layout"]
        _require(_keys(layout, ("premium_pages", "completed_pages"))
                 and _int(layout["premium_pages"], 0, _MAX_HISTORY_PAGES)
                 and _int(layout["completed_pages"], 0, layout["premium_pages"]),
                 "member_projection_history_layout")
        premium_pages = layout["premium_pages"]
        dashboard_index = premium_pages + layout["completed_pages"]
    counts = dict.fromkeys(_ROW_LIMITS, 0)
    parts = {}
    history_rows = 0
    premium = {}
    completed = set()
    report_refs = {}
    for descriptor in manifest["parts"]:
        _require(_keys(descriptor, ("kind", "index", "rows", "bytes", "sha256")), "member_projection_descriptor")
        kind, index, rows, size, sha = (descriptor[key] for key in ("kind", "index", "rows", "bytes", "sha256"))
        _require(isinstance(kind, str) and kind in counts and _int(index, counts[kind], counts[kind]),
                 "member_projection_descriptor")
        view = kind
        if kind == "history" and tiered:
            _require(index <= dashboard_index, "member_projection_history_layout")
            if index == dashboard_index:
                view = "dashboard"
            elif index >= premium_pages:
                view = "completed"
        _require(
            _int(rows, 0, _MAX_DASHBOARD_ROWS) if view == "dashboard" else _int(rows, 1, _ROW_LIMITS[kind]),
            "member_projection_descriptor",
        )
        _require(_int(size, 1, _MAX_PART) and _hash(sha) and (kind != "analytics" or rows == len(_PRESETS)),
                 "member_projection_descriptor")
        raw, text = _read(folder / f"{kind}-{index}.json", size)
        _require(len(raw) == size and _sha(raw) == sha, "member_projection_part_pin")
        part = _json(text)
        _public_part_shape(part, kind, index, rows, receipt["source"]["as_of"], view, with_reports)
        parts[kind, index] = text
        counts[kind] += 1
        if view == "history":
            history_rows += rows
            if tiered:
                for row in part["rows"]:
                    key = (row["date"], row["symbol"])
                    _require(key not in premium, "member_projection_history_duplicate")
                    premium[key] = row["state"]
                    report_digest = row.get("fundamental_sha256")
                    if report_digest is not None:
                        _require(report_digest not in report_refs, "member_projection_fundamental_duplicate")
                        report_refs[report_digest] = key
        elif view == "completed":
            for row in part["rows"]:
                key = (row["date"], row["symbol"])
                original = "TRIGGERED" if row["state"] == "HOLD_ENDED" else row["state"]
                _require(key not in completed and premium.get(key) == original,
                         "member_projection_unmatched_completed_history")
                completed.add(key)
    _require(
        counts["analytics"] == 1 and counts["chart"] == 3 and history_rows == receipt["history_rows"]
        and (not tiered or counts["history"] == dashboard_index + 1),
        "member_projection_inventory",
    )
    _require(len(report_refs) == receipt.get("fundamental_reports", 0), "member_projection_fundamental_inventory")
    reports = {}
    for report_digest, expected in report_refs.items():
        raw, text = _read(folder / f"fundamental-{report_digest}.json", _MAX_FUNDAMENTAL)
        _require(_sha(raw) == report_digest, "member_projection_fundamental_pin")
        _fundamental_shape(_json(text), expected)
        reports[report_digest] = text
    return identity, digest, manifest_text, parts, reports


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


def _verify_staged(member_db, identity, digest, text, parts, reports):
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

    if reports:
        count = member_db.query(
            "SELECT COUNT(*) AS total FROM private_projection_fundamental WHERE identity=?", (identity,),
        )
        _require(count == [{"total": len(reports)}], "member_projection_readback_fundamental_inventory")
        for group in _batches(list(reports)):
            placeholders = ",".join("?" for _ in group)
            rows = member_db.query(
                f"SELECT sha256,json FROM private_projection_fundamental WHERE identity=? AND sha256 IN ({placeholders})",
                (identity, *group),
            )
            _require(
                len(rows) == len(group) and all(_keys(row, ("sha256", "json")) for row in rows)
                and {row["sha256"]: row["json"] for row in rows} == {sha: reports[sha] for sha in group},
                "member_projection_readback_fundamental_conflict",
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
    identity, digest, text, parts, reports = _prepared(projection_directory, receipt_sha256)
    source = _json(identity)
    target = {"identity": identity, "digest": digest}

    def check_owner():
        _require(_identity(read_official_ready()) == identity, "member_owner_ready_changed")

    stage = (_INSERT_MANIFEST, (identity, digest, text))
    statements = [(_INSERT_PART, (identity, *key, part)) for key, part in parts.items()]
    statements.extend((_INSERT_FUNDAMENTAL, (identity, sha, report)) for sha, report in reports.items())
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
            try:
                member_db.batch(group)
            except RemoteD1Error as error:
                if str(error) != 'remote_d1_upload_internal_error_reconcile_before_retry':
                    raise
                # The installed Wrangler raises this before beginning ingestion.
                # Reconcile both primaries, then retry only this immutable group once.
                check_owner()
                _require(read_member_marker(member_db) == current, 'member_projection_marker_changed')
                _verify_manifest(member_db, identity, digest, text)
                member_db.batch(group)
    _verify_staged(member_db, identity, digest, text, parts, reports)
    check_owner()
    if not activate or replay:
        _require(read_member_marker(member_db) == current, "member_projection_marker_changed")
        check_owner()
        status = "already_active" if replay else "staged"
    else:
        staged_checks = _STAGED
        staged = (identity, digest, identity, len(parts))
        if reports:
            staged_checks += " AND (SELECT COUNT(*) FROM private_projection_fundamental WHERE identity=?)=?"
            staged += (identity, len(reports))
        if current is None:
            sql = """
                INSERT INTO private_projection_ready (singleton,identity,digest)
                SELECT 1,?,? WHERE """ + staged_checks + " ON CONFLICT(singleton) DO NOTHING"
            values = (identity, digest, *staged)
        else:
            sql = """
                UPDATE private_projection_ready SET identity=?,digest=?
                WHERE singleton=1 AND identity=? AND digest=? AND """ + staged_checks
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
