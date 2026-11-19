"""Private host side of the opt-in, exact-version member response observation."""

from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
import secrets

from .files import digest
from .member_rollout import _GUILD, _NORMAL, _PROTECTED_PATHS, _ROLE, _STAGE

SHA = re.compile(r"[a-f0-9]{64}")
COMMIT = re.compile(r"[a-f0-9]{40}")
VERSION = re.compile(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}")
SUBJECT = re.compile(r"\d{17,20}")
WINDOW_FIELDS = (
    "window_id", "origin", "source_commit", "build_input_sha256", "worker_version_id",
    "opens_at_ms", "closes_at_ms", "subject_key", "allowed_subject_hmac", "denied_subject_hmac",
)
OBSERVATION_FIELDS = (*WINDOW_FIELDS[:5], "subject_hmac", "route", "status", "role_result", "observed_at_ms")


def matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def now_ms():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def iso_ms(value):
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()


def checked_deployment(reader, origin):
    value = reader()
    if (value.get("origin", value.get("normal_origin")) != origin or value.get("synthetic") is True
            or value.get("platform_signature_claimed") is not False
            or value.get("live_traffic_percent") != 100
            or not matches(SHA, value.get("raw_receipt_sha256"))
            or not matches(COMMIT, value.get("source_commit"))
            or not matches(SHA, value.get("build_input_sha256"))
            or not matches(VERSION, value.get("version_id"))):
        raise ValueError("Exact live member observation deployment unavailable")
    timestamp = datetime.fromisoformat(value["deployed_at"].replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp.timestamp() * 1000 > now_ms():
        raise ValueError("Member observation deployment time is unavailable")
    return value


def subject_tag(window, subject):
    payload = ["new-a-member-observation-subject-v1", *(window[key] for key in WINDOW_FIELDS[:5]), subject]
    message = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode()
    return hmac.new(bytes.fromhex(window["subject_key"]), message, hashlib.sha256).hexdigest()


def checked_subjects(allowed, denied):
    if allowed == denied or not all(matches(SUBJECT, value) for value in (allowed, denied)):
        raise ValueError("Two distinct trusted Discord account selectors required")


def read_window(member_db):
    rows = member_db.query(f"SELECT {','.join(WINDOW_FIELDS)} FROM new_a_member_observation_window_v1 WHERE singleton=1")
    if len(rows) > 1:
        raise ValueError("More than one member observation window exists")
    return rows[0] if rows else None


def open_member_window(member_db, *, origin, deployment_reader, allowed, denied, duration_ms=600_000):
    """Caller supplies verified account selections and the authorized primary Member D1."""
    checked_subjects(allowed, denied)
    if origin not in (_NORMAL, _STAGE) or type(duration_ms) is not int or not 1 <= duration_ms <= 900_000:
        raise ValueError("Invalid member observation scope or duration")
    live = checked_deployment(deployment_reader, origin)
    opened = now_ms()
    window = {
        "window_id": secrets.token_hex(32), "origin": origin, "source_commit": live["source_commit"],
        "build_input_sha256": live["build_input_sha256"], "worker_version_id": live["version_id"],
        "opens_at_ms": opened, "closes_at_ms": opened + duration_ms, "subject_key": secrets.token_hex(32),
    }
    window.update(allowed_subject_hmac=subject_tag(window, allowed), denied_subject_hmac=subject_tag(window, denied))
    slots = ",".join("?" for _ in WINDOW_FIELDS)
    assignments = ",".join(f"{key}=excluded.{key}" for key in WINDOW_FIELDS)
    sql = (
        f"INSERT INTO new_a_member_observation_window_v1 (singleton,{','.join(WINDOW_FIELDS)}) VALUES(1,{slots}) "
        f"ON CONFLICT(singleton) DO UPDATE SET {assignments} "
        "WHERE new_a_member_observation_window_v1.closes_at_ms <= ?"
    )
    try:
        member_db.query(sql, (*[window[key] for key in WINDOW_FIELDS], opened))
    except Exception as error:
        if read_window(member_db) != window:
            raise RuntimeError("Member observation window write unconfirmed") from error
    else:
        if read_window(member_db) != window:
            raise ValueError("An active member observation window already exists")
    return window["window_id"]


def read_member_window(member_db, *, origin, deployment_reader, window_id, allowed, denied):
    """Read only authenticated results for exactly these two accounts and three routes."""
    checked_subjects(allowed, denied)
    if origin not in (_NORMAL, _STAGE) or not matches(SHA, window_id):
        raise ValueError("Invalid member observation window selection")
    live = checked_deployment(deployment_reader, origin)
    window = read_window(member_db)
    expected_identity = (window_id, origin, live["source_commit"], live["build_input_sha256"], live["version_id"])
    if not window or tuple(window.get(key) for key in WINDOW_FIELDS[:5]) != expected_identity:
        raise ValueError("Member observation window identity changed")
    if not matches(SHA, window.get("subject_key")):
        raise ValueError("Member observation window verifier unavailable")
    subjects = (("allowed", allowed), ("denied", denied))
    tags = {role: subject_tag(window, subject) for role, subject in subjects}
    if any(not hmac.compare_digest(value, window[f"{role}_subject_hmac"]) for role, value in tags.items()):
        raise ValueError("Member observation account differs from the authorized selection")
    opened, closed = window["opens_at_ms"], window["closes_at_ms"]
    observed_before = now_ms()
    if type(opened) is not int or type(closed) is not int or not 0 < opened <= observed_before or not 0 < closed - opened <= 900_000:
        raise ValueError("Member observation window time is invalid")
    routes = {key: _PROTECTED_PATHS[key] for key in ("document", "member_api", "owner_direct")}
    rows = member_db.query(
        f"SELECT {','.join(OBSERVATION_FIELDS)} FROM new_a_member_response_observation_v1 "
        "WHERE window_id=? ORDER BY subject_hmac, route", (window_id,),
    )
    if len(rows) != len(routes) * len(subjects):
        raise ValueError("Member route observations are incomplete")
    indexed = {}
    for row in rows:
        route, tag, when = row["route"], row["subject_hmac"], row["observed_at_ms"]
        if (tuple(row.get(key) for key in WINDOW_FIELDS[:5]) != expected_identity
                or route not in routes.values() or tag not in tags.values()
                or type(when) is not int or not opened <= when < closed or when > observed_before
                or (tag, route) in indexed):
            raise ValueError("Member route observation provenance differs")
        indexed[tag, route] = row

    role_receipts = {}
    for role, subject in subjects:
        has_role = role == "allowed"
        values = {}
        for key, route in routes.items():
            row = indexed.get((tags[role], route))
            result = "not_checked" if key == "owner_direct" else role
            status = 403 if key == "owner_direct" or not has_role else 200
            if not row or row["role_result"] != result or row["status"] != status:
                raise ValueError("Member route or Discord role outcome differs")
            values[key + "_status"] = status
        role_receipts["role_" + role] = {
            "subject": subject, "session_verified": True, "owner": False,
            "fresh_designated_role_checked": True, "guild_id": _GUILD,
            "designated_role_id": _ROLE, "has_designated_role": has_role, **values,
        }
    if read_window(member_db) != window:
        raise ValueError("Member observation window changed during readback")
    return {
        "observed_at": iso_ms(min(row["observed_at_ms"] for row in rows)),
        "raw_receipt_sha256": digest([live["raw_receipt_sha256"], rows]),
        **role_receipts,
    }


def member_rollout_observation(request, *, deployment_reader, member_db=None,
                               window_id=None, accounts=None, boundary_reader=None):
    """Trusted callback for member_rollout; keep the returned subjects in memory."""
    phase = request.get("phase")
    stage = phase == "stage"
    origin = _STAGE if stage else _NORMAL
    if (phase not in ("stage", "before", "after") or request.get("paths") != _PROTECTED_PATHS
            or request.get("guild_id") != _GUILD or request.get("designated_role_id") != _ROLE):
        raise ValueError("Member rollout observation request differs")
    live = checked_deployment(deployment_reader, origin)
    if (request.get("source_commit") != live["source_commit"]
            or (request.get("worker_version_id") == live["version_id"]) == stage):
        raise ValueError("Member observation differs from the exact rollout release")

    result = {}
    report_times = []
    raw_receipts = [live["raw_receipt_sha256"]]
    if not stage:
        if not callable(boundary_reader):
            raise ValueError("Actual owner and anonymous boundary observations required")
        raw = boundary_reader(request)
        if (raw.get("origin") != origin or raw.get("source_commit") != live["source_commit"]
                or raw.get("worker_version_id") != live["version_id"] or raw.get("synthetic") is not False
                or not matches(SHA, raw.get("raw_receipt_sha256"))):
            raise ValueError("Owner boundary observation provenance differs")
        observed_at = datetime.fromisoformat(raw["observed_at"].replace("Z", "+00:00"))
        if observed_at.tzinfo is None or observed_at > datetime.now(timezone.utc):
            raise ValueError("Owner boundary observation time differs")
        result.update(owner=raw["owner"], anonymous=raw["anonymous"])
        report_times.append(observed_at)
        raw_receipts.append(raw["raw_receipt_sha256"])
    if stage or request.get("effective_mode") != "off":
        if member_db is None or not isinstance(accounts, (tuple, list)) or len(accounts) != 2:
            raise ValueError("Authorized Member D1 observations are required")

        def same_deployment():
            fresh = checked_deployment(deployment_reader, origin)
            fields = ("source_commit", "build_input_sha256", "version_id", "deployed_at", "deployment_id")
            if any(fresh.get(field) != live.get(field) for field in fields):
                raise ValueError("Live member deployment changed during observation")
            return fresh

        members = read_member_window(
            member_db, origin=origin, deployment_reader=same_deployment, window_id=window_id,
            allowed=accounts[0], denied=accounts[1],
        )
        result.update(role_allowed=members["role_allowed"], role_denied=members["role_denied"])
        report_times.append(datetime.fromisoformat(members["observed_at"]))
        raw_receipts.append(members["raw_receipt_sha256"])
    return {
        "schema": "NEW_A_HOST_MEMBER_ROLLOUT_OBSERVATION_V1", "request_sha256": digest(request),
        "synthetic": False, "platform_signature_claimed": False, "origin": origin,
        "source_commit": live["source_commit"], "worker_version_id": live["version_id"],
        "deployed_at": live["deployed_at"], "observed_at": min(report_times).isoformat(),
        "raw_receipt_sha256": digest(raw_receipts), **result,
    }
