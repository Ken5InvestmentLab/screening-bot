"""Apply a reviewed, dormant role-capable release over an ordinary owner release.

This module has no CLI, deployment, observer or promotion adapter. Callbacks
must independently read the actual owner, provider, CI and member D1 evidence.
"""
from copy import deepcopy
from pathlib import Path
import datetime
import hashlib
import json
import os
import re

from . import continuing_acceptance as ca
from . import continuing_transition as transition
from .files import atomic_write, digest, file_sha, private_root, read
from .member_release_source_review import (
    ENTRY_NOTICE_REVIEW_SCHEMA, FIXED_TRIAL_FEE_REVIEW_SCHEMA, LOADING_AND_ZERO_REVIEW_SCHEMA, SHARED_DEFAULTS_REVIEW_SCHEMA,
    APPROVAL_TIMEOUT_REVIEW_SCHEMA, FREE_COMPLETED_ANALYTICS_REVIEW_SCHEMA, SETTLED_PRICE_REVIEW_SCHEMA,
    TIERED_SUCCESSOR_SCHEMAS, PREMIUM_LEGACY_REVIEW_SCHEMA, FUNDAMENTAL_RETENTION_REVIEW_SCHEMA, PREMIUM_RUNTIME_REVIEW_SCHEMA,
    CARD_DISPLAY_REVIEW_SCHEMA, PUBLICATION_RECOVERY_REVIEW_SCHEMA, CARD_EDITORIAL_REVIEW_SCHEMA, SETTLED_HISTORY_REVIEW_SCHEMA,
    CLOUD_OWNER_REFERENCE_REVIEW_SCHEMA, CLOUD_UI_POLISH_REVIEW_SCHEMA, CLOUD_UI_REVIEW_SCHEMA,
    COMPLETED_TIMING_REVIEW_SCHEMA,
    FUNDAMENTAL_IMPACT_REVIEW_SCHEMA, FUNDAMENTAL_INLINE_LINKS_REVIEW_SCHEMA,
    FUNDAMENTAL_POPUP_REVIEW_SCHEMA,
    FUNDAMENTAL_REVIEW_SCHEMA, INITIAL_REVIEW_SCHEMA, JOURNAL_REVIEW_SCHEMA, PRESENTATION_REVIEW_SCHEMA,
    ROLE_ONLY_REVIEW_SCHEMA, UNIFIED_MEMBER_UI_REVIEW_SCHEMA, review_member_release_source,
)
from .operational_admission import ORIGIN, checked_ci
from .release_acceptance import checked_measurements
from .release_maintenance import read_restored_release, verify_restored_release


APPLICATION_SCHEMA = ca.MEMBER_ORDINARY_APPLICATION_SCHEMA
MEMBER_SUCCESSORS = {
    INITIAL_REVIEW_SCHEMA: PRESENTATION_REVIEW_SCHEMA,
    PRESENTATION_REVIEW_SCHEMA: COMPLETED_TIMING_REVIEW_SCHEMA,
    COMPLETED_TIMING_REVIEW_SCHEMA: FUNDAMENTAL_REVIEW_SCHEMA,
    FUNDAMENTAL_REVIEW_SCHEMA: ROLE_ONLY_REVIEW_SCHEMA,
    ROLE_ONLY_REVIEW_SCHEMA: JOURNAL_REVIEW_SCHEMA,
    JOURNAL_REVIEW_SCHEMA: FUNDAMENTAL_POPUP_REVIEW_SCHEMA,
    FUNDAMENTAL_POPUP_REVIEW_SCHEMA: FUNDAMENTAL_IMPACT_REVIEW_SCHEMA,
    FUNDAMENTAL_IMPACT_REVIEW_SCHEMA: CLOUD_UI_REVIEW_SCHEMA,
    CLOUD_UI_REVIEW_SCHEMA: CLOUD_UI_POLISH_REVIEW_SCHEMA,
    CLOUD_UI_POLISH_REVIEW_SCHEMA: CLOUD_OWNER_REFERENCE_REVIEW_SCHEMA,
    CLOUD_OWNER_REFERENCE_REVIEW_SCHEMA: FUNDAMENTAL_INLINE_LINKS_REVIEW_SCHEMA,
    FUNDAMENTAL_INLINE_LINKS_REVIEW_SCHEMA: UNIFIED_MEMBER_UI_REVIEW_SCHEMA,
    UNIFIED_MEMBER_UI_REVIEW_SCHEMA: LOADING_AND_ZERO_REVIEW_SCHEMA,
    LOADING_AND_ZERO_REVIEW_SCHEMA: SHARED_DEFAULTS_REVIEW_SCHEMA,
    SHARED_DEFAULTS_REVIEW_SCHEMA: FIXED_TRIAL_FEE_REVIEW_SCHEMA,
    FIXED_TRIAL_FEE_REVIEW_SCHEMA: FREE_COMPLETED_ANALYTICS_REVIEW_SCHEMA,
    FREE_COMPLETED_ANALYTICS_REVIEW_SCHEMA: SETTLED_PRICE_REVIEW_SCHEMA,
    SETTLED_PRICE_REVIEW_SCHEMA: APPROVAL_TIMEOUT_REVIEW_SCHEMA,
    APPROVAL_TIMEOUT_REVIEW_SCHEMA: PREMIUM_LEGACY_REVIEW_SCHEMA,
    PREMIUM_LEGACY_REVIEW_SCHEMA: FUNDAMENTAL_RETENTION_REVIEW_SCHEMA,
    FUNDAMENTAL_RETENTION_REVIEW_SCHEMA: PREMIUM_RUNTIME_REVIEW_SCHEMA,
    PREMIUM_RUNTIME_REVIEW_SCHEMA: CARD_DISPLAY_REVIEW_SCHEMA,
    CARD_DISPLAY_REVIEW_SCHEMA: PUBLICATION_RECOVERY_REVIEW_SCHEMA,
    PUBLICATION_RECOVERY_REVIEW_SCHEMA: CARD_EDITORIAL_REVIEW_SCHEMA,
    CARD_EDITORIAL_REVIEW_SCHEMA: SETTLED_HISTORY_REVIEW_SCHEMA,
}
VERSION_BOUND_HANDOVERS = frozenset({
    JOURNAL_REVIEW_SCHEMA, FUNDAMENTAL_POPUP_REVIEW_SCHEMA, FUNDAMENTAL_IMPACT_REVIEW_SCHEMA, CLOUD_UI_REVIEW_SCHEMA,
    CLOUD_UI_POLISH_REVIEW_SCHEMA, CLOUD_OWNER_REFERENCE_REVIEW_SCHEMA, FUNDAMENTAL_INLINE_LINKS_REVIEW_SCHEMA,
    UNIFIED_MEMBER_UI_REVIEW_SCHEMA, LOADING_AND_ZERO_REVIEW_SCHEMA, SHARED_DEFAULTS_REVIEW_SCHEMA,
    ENTRY_NOTICE_REVIEW_SCHEMA, FIXED_TRIAL_FEE_REVIEW_SCHEMA,
}) | TIERED_SUCCESSOR_SCHEMAS
DECISION = "CONTINUING_DAILY_WITH_DORMANT_DESIGNATED_MEMBER_VIEW"
ORDINARY_DECISION = "CONTINUING_DAILY_WITH_NONOWNER_UNMEASURED"
ROUTE = "/api/cloud/new-a-view/history.json"
MAX_OBSERVATION_AGE = datetime.timedelta(minutes=15)
# This is the number of consecutive restorations since the last accepted
# application, not a limit on the ordinary acceptance history.
MAX_CONSECUTIVE_RESTORATIONS = 8
SHA = re.compile(r"[a-f0-9]{64}")
VERSION = re.compile(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}")
RELEASE_KEYS = ("version_id", "build_input_sha256", "policy_sha256", "ci_run_id", "tag")
DEPLOYMENT_KEYS = ("source_commit", "target", "deployment_id", "deployed_at", "active_owner_sha256", *RELEASE_KEYS)
INCUMBENT_POLICY_SCHEMA = "NEW_A_HOST_MEMBER_POLICY_INCUMBENT_V1"
EFFECTIVE_OFF_POLICY_SCHEMA = "NEW_A_HOST_MEMBER_POLICY_EFFECTIVE_OFF_V1"
HANDOVER_POLICY_KEYS = {
    "schema", "database_id", "primary", "source_commit", "worker_version_id", "deployment_id",
    "policy", "observed_at", "raw_receipt_sha256", "synthetic", "platform_signature_claimed",
}
OTHER_LOCKS = (
    ".cache/weak_early_beta/exit-reminder-runner.lock", ".cache/weak_early_beta/exit-reminder.lock",
    "weak_early_beta/state/exit-reminder.lock", "weak_early_beta/state/daily_runtime/daily.lock",
)


def _activation(repo):
    path = private_root(repo) / "activation.json"
    ca.require(path.resolve() == path, "canonical ordinary activation path required")
    return path


def _app_folder(repo, application_id):
    ca.require(isinstance(application_id, str) and SHA.fullmatch(application_id),
               "canonical ordinary application identity required")
    folder = ca.root(repo) / "applications" / application_id
    ca.require(folder.resolve() == folder, "canonical ordinary application path required")
    return folder


def _predecessor(repo, evidence):
    folder = _app_folder(repo, evidence["application_id"])
    completed = read(folder / "completed.json")
    if completed["schema"] == ca.TRANSITION_APPLICATION_SCHEMA:
        return folder / "transition.json", INITIAL_REVIEW_SCHEMA
    ca.require(completed["schema"] == APPLICATION_SCHEMA, "verified ordinary predecessor application required")
    audit = folder / "member-ordinary.json"
    review_schema = MEMBER_SUCCESSORS.get(read(audit)["source_review"]["schema"])
    ca.require(review_schema is not None, "ordinary member predecessor has no reviewed successor")
    return audit, review_schema


def _check_successor_policy(source_review, baseline, deployment):
    if source_review["schema"] in MEMBER_SUCCESSORS.values():
        ca.require(deployment["policy_sha256"] == baseline["policy_sha256"],
                   "member successor changes the approved live owner policy")


def _header(operating_repo, candidate_repo, plan):
    previous, repo = Path(operating_repo).resolve(), Path(candidate_repo).resolve()
    ca.require(not (repo.is_relative_to(previous) or previous.is_relative_to(repo)),
               "distinct non-overlapping operating and candidate checkouts required")
    baseline = transition.ordinary_runtime_release(previous)
    ca.require(baseline is not None, "verified operating ordinary predecessor required")
    previous_activation = read(_activation(previous))
    owner = previous_activation["owner_acceptance"]
    previous_audit, review_schema = _predecessor(previous, owner)
    source = ca.head(repo)
    target = ca.target(repo)
    ca.require(plan.get("decision") == DECISION and plan.get("scope") == ca.SCOPE
               and plan.get("strategy") == "A_BASE" and plan.get("virtual_only") is True
               and plan.get("nonowner_evidence_mode") == "OWNER_DECISION_UNMEASURED"
               and "run_date" not in plan and "expires_at" not in plan
               and plan.get("source_commit") == source and plan.get("target") == target == ca.target(previous)
               and plan.get("prior_acceptance") == owner["continuing_acceptance"]
               and plan.get("expected_activation_sha256") == baseline["activation_sha256"] == file_sha(_activation(repo)),
               "member ordinary plan, predecessor, target or activation differs")
    until = ca.timestamp(plan["management_not_after"])
    ca.require(ca.now() < until <= ca.now() + datetime.timedelta(hours=1),
               "member ordinary management authority expired or too broad")
    ca.verify_sources(repo, plan["auth_source_hashes"])
    _, old = ca.load_reference(previous, owner["continuing_acceptance"], "records")
    source_review = review_member_release_source(repo, baseline["source_commit"], source)
    ca.require(source_review["member_support_configured"] is True
               and source_review["schema"] == review_schema and source_review == plan.get("source_review"),
               "reviewed member capability must match the exact candidate source")
    predecessor_deployment = read(previous_audit)["deployment"] if review_schema in VERSION_BOUND_HANDOVERS else None
    return repo, baseline, old, source_review, predecessor_deployment


def _restoration_sequence(value):
    if isinstance(value, list):
        ca.require(2 <= len(value) <= MAX_CONSECUTIVE_RESTORATIONS, "restoration chain length differs")
        return value
    return [value]


def _read_restoration(repo, reference):
    records = [read_restored_release(repo, item) for item in _restoration_sequence(reference)]
    return records if isinstance(reference, list) else records[0]


def _restoration_reference(restoration):
    refs = [item["reference"] for item in _restoration_sequence(restoration)]
    return refs if isinstance(restoration, list) else refs[0]


def _restored_predecessor(restoration, baseline, prior_acceptance, old_deployment):
    if restoration is None:
        return None
    restored, admitted_at = None, None
    deployment_ids = set()
    for proof in _restoration_sequence(restoration):
        old, next_pair, next_admitted = verify_restored_release(proof)
        if restored is None:
            ca.require(old_deployment is not None
                       and all(old[key] == old_deployment[key] for key in
                               ("source_commit", "target", "deployment_id", *RELEASE_KEYS))
                       and old["activation_sha256"] == baseline["activation_sha256"]
                       and old["acceptance_sha256"] == prior_acceptance["sha256"],
                       "restoration does not match the archived ordinary predecessor")
            deployment_ids.add(old["deployment_id"])
        else:
            ca.require(old == restored and admitted_at < next_admitted, "consecutive restoration pairs differ")
        ca.require(next_pair["deployment_id"] not in deployment_ids, "restoration deployment was repeated")
        deployment_ids.add(next_pair["deployment_id"])
        restored, admitted_at = next_pair, next_admitted
    return restored["deployment_id"], admitted_at


def _effective_off(policy, database_id, deployment, handover, *, source_review_schema=JOURNAL_REVIEW_SCHEMA,
                   restored=None):
    prior_deployment, incumbent = handover
    prior_id = prior_deployment["deployment_id"] if restored is None else restored[0]
    for receipt, pins, deployment_id, schema in (
        (incumbent, prior_deployment, prior_id, INCUMBENT_POLICY_SCHEMA),
        (policy, deployment, deployment["deployment_id"], EFFECTIVE_OFF_POLICY_SCHEMA),
    ):
        ca.require(isinstance(receipt, dict) and set(receipt) == HANDOVER_POLICY_KEYS
                   and receipt["schema"] == schema and receipt["database_id"] == database_id
                   and receipt["source_commit"] == pins["source_commit"]
                   and receipt["worker_version_id"] == pins["version_id"]
                   and receipt["deployment_id"] == deployment_id
                   and receipt["primary"] is True and receipt["synthetic"] is False
                   and receipt["platform_signature_claimed"] is False
                   and SHA.fullmatch(str(receipt["raw_receipt_sha256"])),
                   "exact primary incumbent and effective-OFF member evidence required")
    changed_at = ca.timestamp(deployment["deployed_at"])
    observed = ca.timestamp(incumbent["observed_at"])
    ca.require(source_review_schema in VERSION_BOUND_HANDOVERS, "version-bound member handover review required")
    # Runner-only changes are outside the Worker inputs and require the same build.
    same_build_input = prior_deployment["build_input_sha256"] == deployment["build_input_sha256"]
    oldest_observation = max(ca.timestamp(prior_deployment["deployed_at"]), changed_at - datetime.timedelta(hours=1))
    if restored is not None:
        oldest_observation = max(oldest_observation, restored[1])
    ca.require(prior_deployment["source_commit"] != deployment["source_commit"]
               and prior_deployment["version_id"] != deployment["version_id"]
               and prior_deployment["deployment_id"] != deployment["deployment_id"]
               and prior_id != deployment["deployment_id"]
               and same_build_input == (source_review_schema in {JOURNAL_REVIEW_SCHEMA, APPROVAL_TIMEOUT_REVIEW_SCHEMA,
                                                                 PREMIUM_LEGACY_REVIEW_SCHEMA, PREMIUM_RUNTIME_REVIEW_SCHEMA})
               and oldest_observation <= observed <= changed_at,
               "successor deployment or incumbent observation differs")
    row = policy["policy"]
    ca.require(isinstance(row, dict) and set(row) == {"mode", "source_commit", "worker_version_id", "revision"}
               and row == incumbent["policy"] and row["mode"] == "enabled"
               and row["source_commit"] == prior_deployment["source_commit"]
               and row["worker_version_id"] == prior_deployment["version_id"]
               and type(row["revision"]) is int and 1 <= row["revision"] <= 2**53 - 1,
               "member policy differs from the pinned enabled predecessor")
    return row


def _normal_evidence(source, target, member_database_id, ci, deployment, policy, as_of, *, live, handover=None,
                     source_review_schema=JOURNAL_REVIEW_SCHEMA, restored=None):
    checked_ci(ci, source)
    transition.checked_normal_deployment(source, target, lambda: deployment)
    ca.require(ci.get("synthetic") is not True and deployment.get("normal_origin") == ORIGIN
               and type(deployment.get("live_traffic_percent")) in (int, float)
               and deployment["live_traffic_percent"] == 100
               and VERSION.fullmatch(str(deployment.get("deployment_id", "")))
               and SHA.fullmatch(str(deployment.get("active_owner_sha256", "")))
               and deployment["ci_run_id"] == ci["run_id"]
               and all(deployment[key] == ci[key] for key in ("tag", "version_id", "build_input_sha256")),
               "exact normal CI, production deployment or owner generation differs")
    if handover is not None:
        row = _effective_off(policy, member_database_id, deployment, handover, source_review_schema=source_review_schema,
                             restored=restored)
    else:
        ca.require(isinstance(policy, dict) and policy.get("schema") == "NEW_A_HOST_MEMBER_POLICY_OFF_V1"
                   and policy.get("database_id") == member_database_id and policy.get("source_commit") == source
                   and policy.get("worker_version_id") == deployment["version_id"] and policy.get("primary") is True
                   and "policy" in policy and policy.get("synthetic") is not True
                   and policy.get("platform_signature_claimed") is False
                   and SHA.fullmatch(str(policy.get("raw_receipt_sha256", ""))),
                   "primary member rollout OFF readback required")
        row = policy["policy"]
        ca.require(row is None or (
            isinstance(row, dict) and set(row) == {"mode", "source_commit", "worker_version_id", "revision"}
            and row.get("mode") == "off" and row.get("source_commit") == source
            and row.get("worker_version_id") == deployment["version_id"]
            and type(row.get("revision")) is int and 1 <= row["revision"] <= 2**53 - 1
        ), "member rollout must remain OFF")
    earliest = ca.timestamp(deployment["deployed_at"])
    if live:
        earliest = max(earliest, as_of - MAX_OBSERVATION_AGE)
    ca.require(all(earliest <= ca.timestamp(item["observed_at"]) <= as_of for item in (deployment, policy)),
               "normal deployment or member OFF observation is stale or premature")
    return {key: deployment[key] for key in DEPLOYMENT_KEYS}, row


def _review(plan, old, source_review, deployment, policy, room_transfer):
    review = dict(
        previous_acceptance=plan["prior_acceptance"], expected_activation_sha256=plan["expected_activation_sha256"],
        prior_source_commit=old["source_commit"], reviewed_diff_sha256=source_review["reviewed_diff_sha256"],
        historical_auth_source_hashes=old["auth_source_hashes"], current_auth_source_hashes=plan["auth_source_hashes"],
        management_not_after=plan["management_not_after"], normal_deployment_sha256=digest(deployment),
        member_policy_sha256=digest(policy), member_access_off=True,
        existing_access_policy_preserved=True, owner_room_transfer=room_transfer,
    )
    if source_review["schema"] in VERSION_BOUND_HANDOVERS | {ROLE_ONLY_REVIEW_SCHEMA}:
        audience = "tiered" if source_review["schema"] in TIERED_SUCCESSOR_SCHEMAS else "role_only"
        ca.require(source_review.get("member_audience") == audience, "verified member audience required")
        review["member_audience"] = audience
    if source_review["schema"] in VERSION_BOUND_HANDOVERS:
        review["predecessor_member_policy_sha256"] = digest(plan["predecessor_member_policy"])
    if "prior_release_restoration" in plan:
        review["prior_release_restoration_sha256"] = digest(plan["prior_release_restoration"])
    return review


def _readers(*, ci_reader, deployment_reader, member_policy_reader):
    ca.require(all(callable(reader) for reader in (ci_reader, deployment_reader, member_policy_reader)),
               "independent CI, production deployment and member D1 readers required")
    return tuple(deepcopy(reader()) for reader in (ci_reader, deployment_reader, member_policy_reader))


def _private_http_observations(raw):
    shared = ("receipt_sha256", "source_commit", "target", "version_id", "observed_at",
              "origin", "deployment_id", "synthetic")
    return {
        kind: {key: deepcopy(item[key]) for key in (
            *shared, *(("owner_identity_verified", "source_kind", "document", "api") if kind == "owner" else ()),
        ) if key in item}
        for kind, item in raw.items()
    }


def _check_http_boundary(measurements, raw, deployment, as_of):
    ca.require(set(raw) == set(ca.PATHS)
               and all(value.get("origin") == ORIGIN and value.get("deployment_id") == deployment["deployment_id"]
                       and as_of - MAX_OBSERVATION_AGE <= ca.timestamp(value["observed_at"]) <= as_of
                       for value in raw.values()), "fresh exact normal-origin HTTP evidence required")
    direct = {r["path"]: r for r in measurements["direct"]["observations"]}
    ca.require(direct.get(ROUTE, {}).get("status") in (401, 403)
               and direct[ROUTE].get("private_gate") is True, "member endpoint denial not observed while OFF")


def _prepare(operating_repo, candidate_repo, plan, *, primary_reader, ordinary_decision_reader,
             role_decision_reader, measurement_reader, raw_reader, authority, room_transfer_reader=None,
             ci_reader, deployment_reader, member_policy_reader):
    repo, baseline, old, source_review, predecessor_deployment = _header(operating_repo, candidate_repo, plan)
    restoration = (_read_restoration(operating_repo, plan["prior_release_restoration"])
                   if "prior_release_restoration" in plan else None)
    restored = _restored_predecessor(restoration, baseline, plan["prior_acceptance"], predecessor_deployment)
    owner = ca.primary_message(plan["owner_message"], primary_reader, authority)
    room = None
    if old["owner_message"]["room_id"] != owner["room_id"]:
        ca.require(callable(room_transfer_reader), "independent same-account room transfer reader required")
        room = room_transfer_reader(old["owner_message"], owner)
    transition.check_owner_continuity(old["owner_message"], owner, room, as_of=ca.now(), live=True)
    ca.require(callable(ordinary_decision_reader) and callable(role_decision_reader) and callable(raw_reader),
               "independent ordinary and member intent reviews and raw observations required")
    ci, deployment, policy = _readers(ci_reader=ci_reader, deployment_reader=deployment_reader,
                                     member_policy_reader=member_policy_reader)
    source, target = plan["source_commit"], plan["target"]
    incumbent = deepcopy(plan.get("predecessor_member_policy"))
    handover = (predecessor_deployment, incumbent) if predecessor_deployment is not None else None
    pins, row = _normal_evidence(source, target, source_review["member_database_id"],
                                 ci, deployment, policy, ca.now(), live=True, handover=handover,
                                 source_review_schema=source_review["schema"], restored=restored)
    _check_successor_policy(source_review, baseline, pins)
    raw = _private_http_observations({kind: raw_reader(kind) for kind in ca.PATHS})
    measurements = checked_measurements(plan, measurement_reader, raw.__getitem__, deployment)
    _check_http_boundary(measurements, raw, pins, ca.now())
    ordinary_review = ca.checked_decision(ordinary_decision_reader(owner["message_id"]), owner, source, target,
                                          ORDINARY_DECISION)
    review = ca.checked_decision(role_decision_reader(owner["message_id"]), owner, source, target, DECISION)
    expected = _review(plan, old, source_review, pins, row, room)
    ca.require(all(review.get(key, object()) == value for key, value in expected.items()),
               "member role review does not bind the exact predecessor, deployment and OFF policy")
    ca.require(_header(operating_repo, repo, plan)[1] == baseline
               and (restoration is None or _read_restoration(operating_repo, _restoration_reference(restoration)) == restoration),
               "operating ordinary predecessor changed during observation")
    return owner, ordinary_review, measurements, dict(review=review, source_review=source_review,
        predecessor=baseline, ci=ci, deployment=deployment, member_policy=policy, http_observations=raw,
        **({"prior_release_restoration": restoration} if restoration is not None else {}),
        **({"predecessor_member_policy": incumbent} if handover is not None else {}))


def prepare(operating_repo, candidate_repo, plan, **readers):
    """Check current real host evidence without writing an application or grant.

    The independent CI and deployment readers return the existing exact
    normal-CI and production-deployment evidence. The member policy reader
    returns a primary OFF observation for the same candidate Worker and
    dedicated D1. A version-bound handover uses primary effective-OFF evidence
    that matches the admitted enabled predecessor receipt in the plan.
    Ordinary HTTP measurements use the existing owner boundary,
    with the actual normal origin, deployment ID and denied member API added.
    """
    _, _, measurements, audit = _prepare(operating_repo, candidate_repo, plan, **readers)
    return dict(status="prepared-not-applied", source_commit=plan["source_commit"],
                deployment_version_id=audit["deployment"]["version_id"], review_sha256=digest(audit["review"]),
                measurement_sha256={kind: digest(value) for kind, value in measurements.items()},
                apply_authorized=False)


def issue(operating_repo, candidate_repo, plan, **readers):
    """Use the existing finite management grant issuer, not a reusable flag."""
    owner, review, measurements, _ = _prepare(operating_repo, candidate_repo, plan, **readers)
    by_id = {binding["id"]: measurements[kind] for kind, binding in plan["measurements"].items()}
    ca.require(len(by_id) == len(ca.PATHS), "distinct host measurement identities required")
    return ca.issue(candidate_repo, {**plan, "decision": "CONTINUE_UNTIL_REVOKED_OR_BOUND_SOURCE_CHANGED"},
                    primary_reader=readers["primary_reader"], authority=readers["authority"],
                    measurement_reader=by_id.__getitem__,
                    decision_reader=lambda message_id: review if message_id == owner["message_id"] else {})


def verify_application(repo, record, grant, current_path, folder, completed, claim, seen):
    """Verify the completed operation without requiring any online approval reader."""
    path = folder / "member-ordinary.json"
    ca.require(path.resolve() == path and file_sha(path) == completed.get("member_ordinary_sha256")
               == claim.get("member_ordinary_sha256"), "completed member ordinary audit differs")
    audit = read(path)
    archived = folder / "original.json"
    before, current = read(archived), read(current_path)
    old_evidence = before["owner_acceptance"]
    baseline = audit["predecessor"]
    ca.require(before.get("operational_admission") is None and baseline["activation_sha256"] == file_sha(archived)
               and completed["previous_acceptance"] == old_evidence["continuing_acceptance"],
               "completed member ordinary predecessor differs")
    old = ca.validate_evidence(old_evidence, repo, _activation_path=archived,
                               _historical_source=baseline["source_commit"], _historical_git_sources=True,
                               _seen=seen)
    previous_audit, review_schema = _predecessor(repo, old_evidence)
    old_deployment = read(previous_audit)["deployment"]
    ca.require(baseline["source_commit"] == old["source_commit"] and baseline["worker"] == record["target"]["service"]
               and baseline["database"] == record["target"]["database_name"] and old["target"] == record["target"]
               and all(baseline[key] == old_deployment[key] for key in RELEASE_KEYS),
               "archived ordinary Worker release differs")
    source_review = review_member_release_source(repo, old["source_commit"], record["source_commit"])
    ca.require(source_review["member_support_configured"] is True
               and source_review["schema"] == review_schema and source_review == audit["source_review"],
               "completed member source review differs")
    applied_at = ca.timestamp(completed["applied_at"])
    incumbent = audit.get("predecessor_member_policy")
    restoration = audit.get("prior_release_restoration")
    restored = _restored_predecessor(restoration, baseline, completed["previous_acceptance"],
                                     old_deployment if review_schema in VERSION_BOUND_HANDOVERS else None)
    handover = (old_deployment, incumbent) if review_schema in VERSION_BOUND_HANDOVERS else None
    pins, row = _normal_evidence(record["source_commit"], record["target"], source_review["member_database_id"],
                                 audit["ci"], audit["deployment"], audit["member_policy"], applied_at,
                                 live=False, handover=handover, source_review_schema=review_schema, restored=restored)
    _check_successor_policy(source_review, baseline, pins)
    raw = audit["http_observations"]
    measurements = record["measurements"]
    measurement_check = {**record, "measurements": {
        kind: {"id": kind, "sha256": digest(value)} for kind, value in measurements.items()
    }}
    checked_measurements(measurement_check, measurements.__getitem__, raw.__getitem__, audit["deployment"])
    _check_http_boundary(measurements, raw, pins, applied_at)
    review = ca.checked_decision(audit["review"], record["owner_message"], record["source_commit"],
                                 record["target"], DECISION)
    room = review.get("owner_room_transfer")
    transition.check_owner_continuity(old["owner_message"], record["owner_message"], room,
                                      as_of=applied_at, live=False)
    expected = _review({
        "auth_source_hashes": record["auth_source_hashes"],
        "prior_acceptance": completed["previous_acceptance"],
        "expected_activation_sha256": grant["expected_activation_sha256"],
        "management_not_after": review["management_not_after"],
        "predecessor_member_policy": incumbent,
        **({"prior_release_restoration": _restoration_reference(restoration)} if restoration is not None else {}),
    }, old, source_review, pins, row, room)
    ca.require(all(review.get(key, object()) == value for key, value in expected.items())
               and applied_at <= ca.timestamp(review["management_not_after"])
               and all(item["deployment_version_id"] == pins["version_id"] for item in record["measurements"].values())
               and current == {**before, "owner_acceptance": current["owner_acceptance"]},
               "completed member ordinary application widened runtime or access scope")
    return audit["deployment"]


def apply(operating_repo, candidate_repo, plan, issued, *, preflight, arbitration_owner=None,
          operating_arbitration_owner=None, **readers):
    """Apply once to the candidate. An ambiguous application must be reconciled."""
    repo = Path(candidate_repo).resolve()
    activation = _activation(repo)
    record = ca.validate_record(repo, issued["acceptance"])
    grant_path, grant = ca.load_reference(repo, issued["application_grant"], "grants")
    grant_id = grant_path.stem
    ca.require(record["schema"] == ca.SCHEMA and grant_id == digest(grant)
               and grant.get("schema") == "NEW_A_FINITE_ACCEPTANCE_APPLICATION_V1"
               and grant.get("scope") == ca.SCOPE and grant.get("acceptance") == issued["acceptance"]
               and grant.get("source_commit") == record["source_commit"] == plan["source_commit"]
               and grant.get("target") == record["target"] == plan["target"]
               and grant.get("owner_message") == record["owner_message"]
               and grant.get("expected_activation_sha256") == plan["expected_activation_sha256"]
               and grant.get("platform_signature_claimed") is False,
               "exact member ordinary management grant required")
    folder = _app_folder(repo, grant_id)
    completed_path = folder / "completed.json"
    if completed_path.exists():
        completed = read(completed_path)
        ca.require(completed["schema"] == APPLICATION_SCHEMA and completed["grant"] == issued["application_grant"]
                   and completed["acceptance"] == issued["acceptance"]
                   and completed["after_sha256"] == file_sha(activation),
                   "completed member ordinary activation changed")
        ca.validate_evidence(read(activation)["owner_acceptance"], repo)
        return {**completed, "same_operation_replay": True}

    def within_grant():
        start, end = (ca.timestamp(grant[key]) for key in ("issued_at", "not_after"))
        current = ca.now()
        return start <= current < end <= start + datetime.timedelta(hours=1)             and current < ca.timestamp(plan["management_not_after"])

    previous_repo = Path(operating_repo).resolve()
    config = repo / ".cache/weak_early_beta/daily-runner.config.json"
    runtime = config.parent / "daily_runtime"
    old_runtime = previous_repo / ".cache/weak_early_beta/daily_runtime"
    config_bytes = config.read_bytes()
    configured = json.loads(config_bytes.decode("utf-8-sig"))
    ca.require(config.resolve() == config and runtime.resolve() == runtime and runtime.is_dir()
               and old_runtime.resolve() == old_runtime and old_runtime.is_dir()
               and not (repo.is_relative_to(previous_repo) or previous_repo.is_relative_to(repo))
               and (repo / configured["repoPath"]).resolve() == repo
               and (repo / configured["runtimeDir"]).resolve() == runtime
               and within_grant() and callable(preflight), "canonical runtime and unexpired member grant required")
    held = []

    def hold(path, delegated):
        if delegated is None:
            transition._acquire(path, grant_id, held)
        else:
            ca.require(isinstance(delegated, str) and delegated and path.resolve() == path
                       and path.read_text() == delegated, "delegated launch arbitration changed")

    def other_locks_clear():
        for base in (repo, previous_repo):
            for name in OTHER_LOCKS:
                lock = base / name
                if not lock.exists():
                    continue
                if (base == previous_repo and name == OTHER_LOCKS[0]
                        and operating_arbitration_owner is not None and lock.resolve() == lock
                        and lock.read_text() == operating_arbitration_owner):
                    continue
                return False
        return True

    try:
        hold(old_runtime / "task-entry.lock", operating_arbitration_owner)
        hold(runtime / "task-entry.lock", arbitration_owner)
        ready = preflight()
        ca.require(ready.get("ok") is True and ready.get("sideEffects") is False
                   and ready.get("head") == record["source_commit"]
                   and Path(ready.get("repository", "")).resolve() == repo,
                   "formal candidate launch preflight not ready")
        hold(old_runtime / "daily.lock", operating_arbitration_owner)
        hold(runtime / "daily.lock", None)
        ca.require(other_locks_clear(),
                   "another Cloud owner lock exists before member approval")
        owner, ordinary_review, measurements, audit = _prepare(previous_repo, repo, plan, **readers)
        ca.require(owner == record["owner_message"] and ordinary_review == record["host_decision"]
                   and measurements == record["measurements"], "issued member ordinary observations differ")

        original = activation.read_bytes()
        expected_sha = plan["expected_activation_sha256"]
        ca.require(hashlib.sha256(original).hexdigest() == expected_sha, "member ordinary activation changed")
        value = json.loads(original.decode("utf-8-sig"))
        evidence = {**value["owner_acceptance"], "auth_source_hashes": record["auth_source_hashes"],
                    "continuing_acceptance": issued["acceptance"], "application_id": grant_id}
        value["owner_acceptance"] = evidence
        folder.mkdir(parents=True, exist_ok=False)
        audit_ref = ca.immutable(folder / "member-ordinary.json", audit)
        # Persist the application intent before replacing activation.
        pending = folder / "candidate.json"
        atomic_write(pending, value)
        claim = dict(grant=issued["application_grant"], before_sha256=expected_sha,
                     after_sha256=file_sha(pending), member_ordinary_sha256=audit_ref["sha256"])
        ca.immutable(folder / "claim.json", claim)
        with (folder / "original.json").open("xb") as archive:
            archive.write(original)
            archive.flush()
            os.fsync(archive.fileno())
        completed = dict(schema=APPLICATION_SCHEMA, **claim, acceptance=issued["acceptance"],
                         previous_acceptance=plan["prior_acceptance"], source_commit=record["source_commit"],
                         applied_at=ca.now().isoformat(), same_operation_replay=False)
        # The pending application is the first link during post-write
        # validation. Reserve that exact link before replacing activation.
        verify_application(repo, record, grant, pending, folder, completed, claim, {issued["acceptance"]["sha256"]})
        ca.require(within_grant() and ca.validate_record(repo, issued["acceptance"]) == record
                   and config.read_bytes() == config_bytes and file_sha(activation) == expected_sha
                   and transition.ordinary_runtime_release(previous_repo) == audit["predecessor"]
                   and other_locks_clear(),
                   "member ordinary runtime, predecessor or authority changed before replace")
        handover = None
        restored = None
        review_schema = audit["source_review"]["schema"]
        if review_schema in VERSION_BOUND_HANDOVERS:
            predecessor_audit, _ = _predecessor(previous_repo, read(_activation(previous_repo))["owner_acceptance"])
            predecessor_deployment = read(predecessor_audit)["deployment"]
            handover = (predecessor_deployment, audit["predecessor_member_policy"])
            restoration = audit.get("prior_release_restoration")
            if restoration is not None:
                ca.require(_read_restoration(previous_repo, _restoration_reference(restoration)) == restoration,
                           "restored ordinary predecessor changed before apply")
                restored = _restored_predecessor(restoration, audit["predecessor"], plan["prior_acceptance"],
                                                 predecessor_deployment)
        stored_pins, stored_policy = _normal_evidence(record["source_commit"], record["target"],
            audit["source_review"]["member_database_id"], audit["ci"], audit["deployment"], audit["member_policy"],
            ca.now(), live=True, handover=handover, source_review_schema=review_schema, restored=restored)
        live_proofs = _readers(**{key: readers[key] for key in ("ci_reader", "deployment_reader", "member_policy_reader")})
        fresh_pins, fresh_policy = _normal_evidence(record["source_commit"], record["target"],
            audit["source_review"]["member_database_id"], *live_proofs, ca.now(), live=True, handover=handover,
            source_review_schema=review_schema, restored=restored)
        ca.require(fresh_pins == stored_pins and fresh_policy == stored_policy and live_proofs[0] == audit["ci"],
                   "production Worker or member OFF policy changed before apply")
        ca.require(within_grant() and config.read_bytes() == config_bytes
                   and file_sha(activation) == expected_sha and other_locks_clear()
                   and ca.head(repo) == record["source_commit"]
                   and ca.head(previous_repo) == audit["predecessor"]["source_commit"]
                   and file_sha(_activation(previous_repo)) == expected_sha,
                   "member ordinary inputs changed before replace")
        ca.verify_sources(repo, record["auth_source_hashes"])
        for base, delegated, daily in ((old_runtime, operating_arbitration_owner, operating_arbitration_owner),
                                       (runtime, arbitration_owner, None)):
            ca.require((base / "task-entry.lock").read_text() == (delegated or grant_id)
                       and (base / "daily.lock").read_text() == (daily or grant_id),
                       "member ordinary launch locks changed before replace")
        completed["applied_at"] = ca.now().isoformat()
        os.replace(pending, activation)
        ca.require(file_sha(activation) == completed["after_sha256"], "member ordinary replace ambiguous")
        ca.immutable(completed_path, completed)
        ca.validate_evidence(evidence, repo)
        return completed
    finally:
        for lock in reversed(held):
            if lock.exists() and lock.read_text() == grant_id:
                lock.unlink()
