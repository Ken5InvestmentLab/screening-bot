"""Private maintainer operation for one exact New A member policy change.

The normal deployment reader and authenticated observation reader are host
capabilities. This module has no CLI, HTTP route or file-based proof adapter.
"""

import hashlib
import hmac
import json
import re
import secrets
from copy import deepcopy
from pathlib import Path

from . import continuing_acceptance as ca
from .continuing_transition import RUNTIME_RELEASE_SCHEMA, checked_normal_deployment, ordinary_runtime_release
from .files import digest, encode, private_root, read
from .member_publication import ready_identity
from .member_publisher import read_member_marker
from .operational_admission import read_active_metadata
from .publisher import LocalD1, WranglerD1


_NORMAL = "https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev"
_STAGE = "https://tentei-kyokuchi-cloud-member-stage.ipo-ken5-5489.workers.dev"
_SCOPE = "EXACT_NEW_A_TIERED_MEMBER_VIEW"
_GUILD = "1479418833352785944"
_ROLE = "1487089073385373828"
_PROTECTED_PATHS = {
    "document": "/weak_early_beta_latest.html",
    "owner_access": "/api/cloud/new-a-finite/access",
    "member_api": "/api/cloud/new-a-view/history.json",
    "premium_dashboard": "/api/cloud/new-a-view/dashboard.json",
    "owner_direct": "/api/cloud/new-a-finite/input/manifest.json",
}
_SUBJECT_DOMAIN = "new-a-member-rollout-subject-v1"
_SHA256 = re.compile(r"[a-f0-9]{64}")
_COMMIT = re.compile(r"[a-f0-9]{40}")
_VERSION = re.compile(r"[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}")
_SUBJECT = re.compile(r"[0-9]{17,20}")
_MODES = {"off", "canary", "enabled"}
_AUDIENCES = {"tiered", "role_only"}
_REVISION_MAX = 2**53 - 1
_PUBLIC_FIELDS = ("revision", "mode", "source_commit", "worker_version_id")
_SUBJECT_FIELDS = ("canary_subject_hmac", "canary_free_subject_hmac")
_CANARY_FIELDS = ("canary_nonce", *_SUBJECT_FIELDS)
_FIELDS = (*_PUBLIC_FIELDS, *_CANARY_FIELDS)
_READ = f"SELECT {','.join(_FIELDS)} FROM new_a_member_release_policy WHERE singleton=1"


def _matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _validate_row(row):
    ca.require(
        isinstance(row, dict) and row.keys() == set(_FIELDS)
        and type(row["revision"]) is int and 1 <= row["revision"] <= _REVISION_MAX
        and isinstance(row["mode"], str) and row["mode"] in _MODES
        and _matches(_COMMIT, row["source_commit"]) and _matches(_VERSION, row["worker_version_id"]),
        "member_rollout_policy_invalid",
    )
    if row["mode"] == "canary":
        ca.require(
            all(_matches(_SHA256, row[key]) for key in _CANARY_FIELDS)
            and row[_SUBJECT_FIELDS[0]] != row[_SUBJECT_FIELDS[1]],
            "member_rollout_canary_binding_invalid",
        )
    else:
        ca.require(all(row[key] is None for key in _CANARY_FIELDS), "member_rollout_canary_binding_invalid")


def _policy(member_db):
    rows = member_db.query(_READ)
    ca.require(len(rows) <= 1, "member_rollout_policy_ambiguous")
    if not rows:
        return None
    _validate_row(rows[0])
    return rows[0]


def _safe(row):
    if row is None:
        return None
    # A null additive field must not invalidate the previous OFF checkpoint.
    fingerprint = row if row["mode"] == "canary" else {key: row[key] for key in _FIELDS[:-1]}
    return {**{key: row[key] for key in _PUBLIC_FIELDS}, "row_sha256": digest(fingerprint)}


def _validate_expected(expected):
    if expected is None:
        return
    ca.require(
        isinstance(expected, dict) and expected.keys() == {*_PUBLIC_FIELDS, "row_sha256"}
        and type(expected["revision"]) is int and 1 <= expected["revision"] <= _REVISION_MAX
        and isinstance(expected["mode"], str) and expected["mode"] in _MODES
        and _matches(_COMMIT, expected["source_commit"]) and _matches(_VERSION, expected["worker_version_id"])
        and _matches(_SHA256, expected["row_sha256"]),
        "member_rollout_expected_snapshot_invalid",
    )


def read_member_policy(member_db):
    """Primary state for compare-and-swap; callers never receive canary material."""
    return _safe(_policy(member_db))


def _same_version(row, release):
    return bool(row and row["source_commit"] == release["source_commit"]
                and row["worker_version_id"] == release["version_id"])


def _mode(row, release):
    return row["mode"] if _same_version(row, release) else "off"


def _subject_hmac(nonce, release, subject):
    ca.require(_matches(_SUBJECT, subject), "member_rollout_verified_subject_required")
    payload = encode([_SUBJECT_DOMAIN, release["source_commit"], release["version_id"], subject]).encode()
    return hmac.new(bytes.fromhex(nonce), payload, hashlib.sha256).hexdigest()


def _databases(repo, owner_db, member_db):
    ca.require(owner_db is not member_db, "member_rollout_independent_databases_required")
    if isinstance(owner_db, LocalD1) and isinstance(member_db, LocalD1):
        return
    for db, binding in ((owner_db, "CLOUD_DB"), (member_db, "CLOUD_MEMBER_DB")):
        ca.require(
            isinstance(db, WranglerD1) and db.repo == repo and db.binding == binding and db.require_primary is True,
            "member_rollout_verified_primary_required",
        )


def _deployment(repo, release, reader):
    ca.require(callable(reader) and release and release.get("schema") == RUNTIME_RELEASE_SCHEMA,
               "member_rollout_exact_approved_release_required")
    observation = checked_normal_deployment(release["source_commit"], ca.target(repo), lambda: reader(release))
    ca.require(
        observation.get("normal_origin") == _NORMAL and observation.get("live_traffic_percent") == 100
        and _matches(_VERSION, observation.get("deployment_id"))
        and _matches(_SHA256, observation.get("active_owner_sha256"))
        and all(observation[key] == release[key] for key in
                ("version_id", "build_input_sha256", "policy_sha256", "ci_run_id", "tag")),
        "member_rollout_normal_release_differs",
    )
    return observation


def _exact_deployment(value):
    return {key: value[key] for key in ("deployment_id", "version_id", "deployed_at")}


def _projection(repo, owner_db, member_db, live):
    row, manifest, active = read_active_metadata(owner_db)
    ca.require(active == live["active_owner_sha256"], "member_rollout_owner_primary_changed")
    current = ready_identity(row, manifest)
    marker = read_member_marker(member_db)
    path = private_root(repo) / "latest-member-publication.json"
    ca.require(path.is_file() and path.resolve() == path, "member_rollout_projection_receipt_unavailable")
    receipt = read(path)
    ca.require(isinstance(marker, dict), "member_rollout_projection_marker_unavailable")
    ca.require(
        json.loads(marker["identity"]) == current and receipt.get("schema") == "NEW_A_MEMBER_PUBLICATION_V1"
        and receipt.get("published") is True and receipt.get("active_readback_verified") is True
        and receipt.get("worker_version_id") == live["version_id"] and receipt.get("source") == current
        and receipt.get("projection_sha256") == marker["digest"],
        "member_rollout_projection_differs",
    )
    return {"owner_ready_sha256": active, "projection_sha256": marker["digest"]}


def configured_member_audience(repo):
    """Read the audience from the exact reviewed Worker source configuration."""
    config = read(Path(repo) / "weak-early-beta-gate/wrangler.jsonc")
    audience = config.get("vars", {}).get("CLOUD_MEMBER_AUDIENCE", "tiered")
    ca.require(isinstance(audience, str) and audience in _AUDIENCES, "member_rollout_invalid_audience")
    return audience


def _role(value, allowed, audience):
    shared_status = 200 if allowed or audience == "tiered" else 403
    ca.require(
        isinstance(value, dict) and value.get("session_verified") is True
        and value.get("owner") is False and value.get("fresh_designated_role_checked") is True
        and value.get("guild_id") == _GUILD and value.get("designated_role_id") == _ROLE
        and value.get("has_designated_role") is allowed and _matches(_SUBJECT, value.get("subject"))
        and value.get("document_status") == shared_status and value.get("member_api_status") == shared_status
        and value.get("premium_dashboard_status") == (200 if allowed else 403)
        and value.get("owner_direct_status") == 403,
        "member_rollout_actual_role_observation_required",
    )
    return value["subject"]


def _observe(reader, context, *, live, stage=False, observed_after=None, canary=None):
    ca.require(callable(reader), "member_rollout_authenticated_observer_required")
    request = {
        **context, "schema": "NEW_A_MEMBER_ROLLOUT_OBSERVATION_REQUEST_V2",
        "paths": _PROTECTED_PATHS, "guild_id": _GUILD, "designated_role_id": _ROLE,
    }
    audience = request.get("audience", "tiered")
    request_sha256 = digest(request)
    value = reader(deepcopy(request))
    ca.require(
        isinstance(value, dict) and value.get("schema") == "NEW_A_HOST_MEMBER_ROLLOUT_OBSERVATION_V2"
        and value.get("request_sha256") == request_sha256 and value.get("audience", "tiered") == audience
        and value.get("synthetic") is False and value.get("platform_signature_claimed") is False
        and value.get("origin") == (_STAGE if stage else _NORMAL)
        and value.get("source_commit") == live["source_commit"]
        and _matches(_VERSION, value.get("worker_version_id"))
        and (value["worker_version_id"] != live["version_id"] if stage else value["worker_version_id"] == live["version_id"])
        and _matches(_SHA256, value.get("raw_receipt_sha256")),
        "member_rollout_observation_provenance",
    )
    observed = ca.timestamp(value["observed_at"])
    earliest = ca.timestamp(live["deployed_at"]) if not stage else ca.timestamp(value["deployed_at"])
    if observed_after is not None:
        earliest = max(earliest, ca.timestamp(observed_after))
    ca.require(earliest <= observed <= ca.now(), "member_rollout_observation_time")
    if not stage:
        owner = value.get("owner", {})
        anonymous = value.get("anonymous", {})
        ca.require(
            owner.get("session_verified") is True and owner.get("owner") is True
            and owner.get("document_status") == 200 and owner.get("access_api_status") == 200
            and owner.get("access") == {"authorized": True, "strategy": "A_BASE"}
            and anonymous.get("cookies_sent") is False and anonymous.get("authorization_sent") is False
            and anonymous.get("document_status") in (302, 303, 307, 401, 403)
            and anonymous.get("member_api_status") in (401, 403)
            and anonymous.get("premium_dashboard_status") in (401, 403)
            and anonymous.get("owner_direct_status") in (401, 403),
            "member_rollout_owner_or_private_boundary_unverified",
        )
    subjects = None
    if stage or context["effective_mode"] != "off":
        premium = _role(value.get("role_allowed"), True, audience)
        free = _role(value.get("role_denied"), False, audience)
        ca.require(premium != free, "member_rollout_distinct_accounts_required")
        subjects = (premium, free)
    if canary is not None:
        ca.require(
            subjects is not None and all(hmac.compare_digest(
                _subject_hmac(canary["canary_nonce"], live, subject), canary[key],
            ) for key, subject in zip(_SUBJECT_FIELDS, subjects, strict=True)),
            "member_rollout_canary_subject_differs",
        )
    return subjects, value["raw_receipt_sha256"]


def _cas(member_db, previous, proposed):
    values = tuple(proposed[key] for key in _FIELDS)
    if previous is None:
        placeholders = ",".join("?" for _ in _FIELDS)
        sql = (
            f"INSERT INTO new_a_member_release_policy (singleton,{','.join(_FIELDS)}) "
            f"VALUES (1,{placeholders}) ON CONFLICT(singleton) DO NOTHING"
        )
    else:
        setters = ",".join(f"{key}=?" for key in _FIELDS)
        predicates = " AND ".join(f"{key} IS ?" for key in _FIELDS)
        sql = f"UPDATE new_a_member_release_policy SET {setters} WHERE singleton=1 AND {predicates}"
        values += tuple(previous[key] for key in _FIELDS)
    try:
        member_db.query(sql, values)
    except Exception as error:
        if read_member_policy(member_db) != _safe(proposed):
            raise RuntimeError("member_rollout_write_unconfirmed") from error
    else:
        ca.require(read_member_policy(member_db) == _safe(proposed), "member_rollout_cas_conflict")


def change_member_rollout(
    repo, owner_db, member_db, *, mode, expected, owner_message, primary_reader, owner_authority,
    decision_reader, observation_reader, deployment_reader=None,
):
    """Change role access only under a live pin and real, independently read host evidence.

    A pending intent precludes repeating an ambiguous write. Reconcile the desired
    row through the same call with the original expected snapshot and owner intent.
    Use an independently authorized OFF operation as the rollback.
    """
    repo = Path(repo).resolve()
    _databases(repo, owner_db, member_db)
    ca.require(isinstance(mode, str) and mode in _MODES, "member_rollout_mode_invalid")
    _validate_expected(expected)
    expected = dict(expected) if expected is not None else None
    if deployment_reader is None:
        from .cloud_worker_release_readback import read_active_production_release

        def deployment_reader(approved):
            return read_active_production_release(repo, approved)

    release = ordinary_runtime_release(repo)
    live = _deployment(repo, release, deployment_reader)
    owner = ca.primary_message(owner_message, primary_reader, owner_authority)
    ca.require(callable(decision_reader), "member_rollout_maintainer_review_required")
    intent = {
        "scope": _SCOPE, "mode": mode, "previous": expected, "source_commit": release["source_commit"],
        "worker_version_id": release["version_id"], "deployment_id": live["deployment_id"],
        "message_id": owner["message_id"], "message_sha256": owner["text_sha256"],
        "owner_only_routes_preserved": True,
    }
    action_sha256 = digest(intent)
    review = decision_reader(deepcopy(owner), deepcopy(intent))
    ca.require(
        isinstance(review, dict) and review.get("schema") == "NEW_A_HOST_MEMBER_ROLLOUT_REVIEW_V1"
        and review.get("decision") == "APPLY_EXACT_MEMBER_ROLLOUT"
        and review.get("action_sha256") == action_sha256 and review.get("platform_signature_claimed") is False,
        "member_rollout_maintainer_review_required",
    )
    current = _policy(member_db)
    before = _safe(current)
    audit = private_root(repo) / "member-rollout"
    ca.require(audit.resolve() == audit, "member_rollout_private_audit_path")
    pending_path = audit / f"{action_sha256}-intent.json"
    complete_path = audit / f"{action_sha256}-complete.json"
    for path in (pending_path, complete_path):
        ca.require(path.resolve() == path, "member_rollout_private_audit_path")

    projection = _projection(repo, owner_db, member_db, live) if mode != "off" else None
    context = {
        "action_sha256": action_sha256, "source_commit": live["source_commit"],
        "worker_version_id": live["version_id"], "projection": projection,
    }
    audience = configured_member_audience(repo) if mode != "off" else "tiered"
    if audience == "role_only":
        context["audience"] = audience
    if pending_path.exists():
        pending = read(pending_path)
        ca.require(pending.get("schema") == "NEW_A_MEMBER_ROLLOUT_INTENT_V1"
                   and pending.get("intent") == intent and pending.get("after") == before
                   and pending.get("projection") == projection, "member_rollout_pending_reconcile")
    else:
        ca.require(before == expected, "member_rollout_cas_conflict")
        existing_mode = _mode(current, release)
        ca.require(
            (existing_mode, mode) in {("off", "canary"), ("canary", "enabled"), ("canary", "off"), ("enabled", "off")},
            "member_rollout_transition_denied",
        )
        source_observations = {}
        subjects = None
        if mode != "off":
            _, source_observations["normal"] = _observe(
                observation_reader, {**context, "phase": "before", "policy": before, "effective_mode": existing_mode},
                live=live, canary=current if existing_mode == "canary" else None,
            )
            if mode == "canary":
                subjects, source_observations["stage"] = _observe(
                    observation_reader, {**context, "phase": "stage", "effective_mode": "enabled"}, live=live, stage=True,
                )
        nonce = secrets.token_hex(32) if subjects is not None else None
        subject_hashes = dict.fromkeys(_SUBJECT_FIELDS)
        if nonce is not None:
            subject_hashes = {
                key: _subject_hmac(nonce, release, subject)
                for key, subject in zip(_SUBJECT_FIELDS, subjects, strict=True)
            }
        proposed = {
            "revision": current["revision"] + 1 if current else 1,
            "mode": mode, "source_commit": release["source_commit"], "worker_version_id": release["version_id"],
            "canary_nonce": nonce, **subject_hashes,
        }
        _validate_row(proposed)
        ca.require(ordinary_runtime_release(repo) == release, "member_rollout_approved_release_changed")
        confirmed = _deployment(repo, release, deployment_reader)
        ca.require(_exact_deployment(confirmed) == _exact_deployment(live), "member_rollout_worker_changed")
        if projection is not None:
            ca.require(_projection(repo, owner_db, member_db, confirmed) == projection, "member_rollout_projection_changed")
        pending = {
            "schema": "NEW_A_MEMBER_ROLLOUT_INTENT_V1", "intent": intent, "after": _safe(proposed),
            "projection": projection, "prepared_at": ca.now().isoformat(), "before_observations": source_observations,
        }
        ca.immutable(pending_path, pending)
        _cas(member_db, current, proposed)

    latest = _deployment(repo, release, deployment_reader)
    ca.require(_exact_deployment(latest) == _exact_deployment(live) and ordinary_runtime_release(repo) == release,
               "member_rollout_worker_changed")
    if projection is not None:
        ca.require(_projection(repo, owner_db, member_db, latest) == projection, "member_rollout_projection_changed")
    actual = _policy(member_db)
    after = _safe(actual)
    ca.require(after == pending["after"], "member_rollout_cas_conflict")
    final_observation = None
    if mode != "off":
        _, final_observation = _observe(
            observation_reader, {**context, "phase": "after", "policy": after, "effective_mode": mode},
            live=latest, observed_after=pending["prepared_at"], canary=actual if mode == "canary" else None,
        )
    final = _deployment(repo, release, deployment_reader)
    if projection is not None:
        ca.require(_projection(repo, owner_db, member_db, final) == projection, "member_rollout_projection_changed")
    ca.require(_exact_deployment(final) == _exact_deployment(live)
               and read_member_policy(member_db) == after and ordinary_runtime_release(repo) == release,
               "member_rollout_final_readback_changed")
    if complete_path.exists():
        receipt = read(complete_path)
        ca.require(receipt.get("action_sha256") == action_sha256 and receipt.get("after") == after,
                   "member_rollout_receipt_differs")
        return receipt
    receipt = {
        "schema": "NEW_A_MEMBER_ROLLOUT_APPLICATION_V1", "action_sha256": action_sha256,
        "before": expected, "after": after, "projection": projection, "rollback_mode": "off",
        "deployment_id": live["deployment_id"], "provider_sha256": final["raw_receipt_sha256"],
        "protected_observation_sha256": final_observation,
    }
    ca.immutable(complete_path, receipt)
    return receipt
