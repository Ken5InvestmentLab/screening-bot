"""Stage one verified owner notice slot. No live host or scheduler is installed here."""
from base64 import urlsafe_b64encode
from hashlib import sha256
import json
from pathlib import Path
import re

from .continuing_transition import RUNTIME_RELEASE_SCHEMA
from .files import encode, private_root
from .lifecycle_notice_inputs import valid_morning_advance
from .planned_notice_delivery import (
    HOLDING, JST, MORNING, _assert_window, _clock, _day, _hash, _instant, _require,
    _validate_plan, _verify_recipient, _verify_source,
)


QUEUE_SCHEMA = "NEW_A_OWNER_NOTICE_QUEUE_V2"
MAX_NOTICES = 1000
MAX_PAYLOAD_BYTES = 88 * 1024
MODEL_BASES = {"SAVED_SCOPE", "LATEST_YEAR_STANDALONE"}
ENDPOINTS = ("d5_close", "d5_open", "d6_open", "a20_close")
PUBLICATION_FIELDS = ("schema", "as_of", "dataset_id", "revision", "manifest_sha256", "source_version",
                      "snapshot_sha256", "published", "active_readback_verified",
                      "existing_owner_gate_verified", "local_d1_emulation")


def _read_record(path):
    with path.open("rb") as stream:
        raw = stream.read(4 * 1024 * 1024 + 1)
    _require(len(raw) <= 4 * 1024 * 1024, "notice source receipt exceeds its bounds")
    return json.loads(raw.decode("utf-8-sig")), sha256(raw).hexdigest()


def _read_live_receipts(repo, run_path, basis, target, kind, release, now, advance):
    data_root = private_root(repo)
    runtime = (repo / ".cache/weak_early_beta/daily_runtime").resolve()
    path = Path(run_path)
    _require(runtime.is_relative_to(repo) and path.is_absolute() and path.resolve() == path and
             path.name == "result.json" and path.parent.parent == runtime and path.parent.name.startswith("daily-"),
             "notice source must be the exact ordinary runner receipt")
    publication_path = data_root / "latest-publication.json"
    _require(publication_path.resolve() == publication_path, "unexpected publication receipt location")
    run, run_sha = _read_record(path)
    publication, publication_sha = _read_record(publication_path)
    as_of = publication.get("as_of")
    _day(as_of)
    if advance:
        _require(as_of == now.astimezone(JST).date().isoformat(),
                 "advance preparation requires the current ordinary publication")
    bound = {key: basis[key] for key in ("dataset_id", "revision", "manifest_sha256", "source_version", "snapshot_sha256")}
    _require(publication.get("schema") == "NEW_A_PRIVATE_PUBLICATION_RECEIPT_V1" and
             all(publication.get(key) is True for key in
                 ("published", "active_readback_verified", "existing_owner_gate_verified")) and
             publication.get("local_d1_emulation") is False and
             publication.get("operational_gate_continuity_verified") is not True and
             all(publication.get(key) == value for key, value in bound.items()) and
             (as_of == target if kind == HOLDING else as_of < target),
             "ordinary published notice data differs")
    deployment = run.get("deployment", {})
    verified = deployment.get("approvedWorkerReadback", {})
    new_a = run.get("new_a", {})
    _require(run.get("ok") is True and run.get("completedAt") and _instant(run["completedAt"]) <= now and
             run.get("date") == run.get("latestSession") == as_of and
             run.get("startCommit") == release["source_commit"] and
             run.get("observationKind") != "DELAYED_SCHEDULED_OBSERVATION" and
             new_a.get("owner_publication_verified") is True and
             all(new_a.get(key) == value for key, value in bound.items()
                 if key in ("dataset_id", "source_version", "snapshot_sha256")) and
             deployment.get("reusedApprovedCodeOnly") is True and
             verified.get("versionId") == release["version_id"] and
             verified.get("sourceCommit") == release["source_commit"] and
             verified.get("buildInputSha256") == release["build_input_sha256"],
             "terminal ordinary run and approved deployment differ")
    return (run_sha, publication_sha, {key: publication[key] for key in PUBLICATION_FIELDS})


def _assert_preparation(kind, target, plan, now, scheduled_at, advance):
    _require(type(advance) is bool, "invalid notice preparation mode")
    if not advance:
        _require("preparation_mode" not in plan and "scheduled_for" not in plan,
                 "an advance plan requires its exact preparation mode")
        _assert_window(kind, target, now)
        return
    _require(kind == MORNING and valid_morning_advance(now, scheduled_at) and
             scheduled_at.astimezone(JST).date().isoformat() == target and
             plan.get("preparation_mode") == "AFTER_ORDINARY_PUBLICATION" and
             isinstance(plan.get("scheduled_for"), str) and _instant(plan["scheduled_for"]) == scheduled_at,
             "advance preparation requires the exact next 08:00 JST slot")


def _compact_notice(notice, kind):
    event_id = urlsafe_b64encode(bytes.fromhex(notice["event_id"])).decode("ascii").rstrip("=")
    candidate = int(notice["candidate_date"].replace("-", ""))
    entry = int(notice["simulated_entry_date"].replace("-", ""))
    endpoint = ENDPOINTS.index(notice["evaluation_endpoint"]) if kind == MORNING else None
    return [event_id, notice["symbol"], candidate, entry, endpoint]


def stage_notice_queue(db, repo, run_path, plan, *, kind, owner, read_source, read_release,
                       read_recipient, now=_clock, scheduled_at=None, advance=False, holding_trigger=None):
    """Prepare by CAS, retain existing rows, and verify the exact staged payload."""
    repo = Path(repo).resolve(strict=True)
    target, notices = _validate_plan(plan, kind)
    _assert_preparation(kind, target, plan, now(), scheduled_at, advance)
    _require(plan.get("model_basis") in MODEL_BASES, "notice calculation basis is unverified")
    _require(len(notices) <= MAX_NOTICES, "notice slot exceeds the Worker delivery budget")
    if not notices:
        return {"status": "no-notices", "kind": kind, "target_date": target, "staged": 0}
    _require(_hash(owner), "owner binding required")
    basis = plan["basis"]
    release = read_release()
    _require(release.get("schema") == RUNTIME_RELEASE_SCHEMA and release.get("worker") == "tentei-kyokuchi-cloud" and
             release.get("database") == "tentei-cloud-settings" and
             re.fullmatch(r"[a-f0-9]{40}", str(release.get("source_commit", ""))) and
             re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", str(release.get("version_id", ""))) and
             _hash(release.get("activation_sha256")) and _hash(release.get("build_input_sha256")),
             "live ordinary release verification required")
    run_sha, publication_sha, publication = _read_live_receipts(repo, run_path, basis, target, kind, release, now(), advance)
    recipient_proof = read_recipient()
    recipient = recipient_proof.get("recipient_binding_sha256")
    _verify_recipient(recipient_proof, owner, recipient, now())
    _verify_source(read_source(), plan, owner, now())
    _require(read_release() == release, "live approved release changed during notice preparation")
    _require(_read_live_receipts(repo, run_path, basis, target, kind, release, now(), advance)[:2] == (run_sha, publication_sha),
             "notice source receipts changed during preparation")
    _assert_preparation(kind, target, plan, now(), scheduled_at, advance)
    value = {
        "schema": QUEUE_SCHEMA, "kind": kind, "target_date": target,
        "source_commit": release["source_commit"], "worker_version_id": release["version_id"],
        "build_input_sha256": release["build_input_sha256"], "source_run_sha256": run_sha,
        "publication_receipt_sha256": publication_sha, "owner_binding_sha256": owner,
        "recipient_binding_sha256": recipient, "model_basis": plan["model_basis"],
        "basis": basis, "publication": publication, "notices": [_compact_notice(notice, kind) for notice in notices],
    }
    if holding_trigger is not None:
        _require(kind == HOLDING and _hash(holding_trigger), "invalid holding dispatch token")
        value["holding_trigger"] = {
            "sha256": sha256(holding_trigger.encode("ascii")).hexdigest(),
            "expires_at_ms": int(now().timestamp() * 1000) + 120_000,
        }
    raw = encode(value)
    _require(len(raw.encode("utf-8")) <= MAX_PAYLOAD_BYTES, "notice payload exceeds the Worker input budget")
    payload_sha = sha256(raw.encode("utf-8")).hexdigest()
    db.query("""
        INSERT INTO new_a_owner_notice_queue(target_date,kind,payload_json,payload_sha256)
        SELECT ?,?,?,? FROM new_a_active_pointer p
        JOIN new_a_private_datasets d ON d.dataset_id=p.dataset_id
        JOIN new_a_finite_trial_preferences f ON f.member_id=?
        WHERE p.pointer_key='owner' AND d.status='READY' AND p.dataset_id=? AND p.revision=?
          AND d.manifest_sha256=? AND d.source_version=? AND f.revision=?
        ON CONFLICT(target_date,kind) DO NOTHING
    """, (target, kind, raw, payload_sha, "cloud_" + owner, basis["dataset_id"], basis["revision"],
          basis["manifest_sha256"], basis["source_version"], basis["preferences_revision"]))
    rows = db.query("""
        SELECT q.payload_json,q.payload_sha256 FROM new_a_owner_notice_queue q
        JOIN new_a_active_pointer p ON p.pointer_key='owner'
        JOIN new_a_private_datasets d ON d.dataset_id=p.dataset_id
        JOIN new_a_finite_trial_preferences f ON f.member_id=?
        WHERE q.target_date=? AND q.kind=? AND d.status='READY' AND p.dataset_id=?
          AND p.revision=? AND d.manifest_sha256=? AND d.source_version=? AND f.revision=?
    """, ("cloud_" + owner, target, kind, basis["dataset_id"], basis["revision"],
          basis["manifest_sha256"], basis["source_version"], basis["preferences_revision"]))
    exact = rows == [{"payload_json": raw, "payload_sha256": payload_sha}]
    if not exact and holding_trigger is not None and len(rows) == 1:
        # A later attempt may recover the same queue without receiving the
        # original one-time dispatch token. Leave that row and its receipt intact.
        previous_raw = rows[0]["payload_json"]
        previous_sha = rows[0]["payload_sha256"]
        _require(sha256(previous_raw.encode("utf-8")).hexdigest() == previous_sha,
                 "notice staging digest mismatch")
        previous = json.loads(previous_raw)
        previous.pop("holding_trigger", None)
        value.pop("holding_trigger")
        _require(encode(previous) == encode(value), "notice staging conflict or source race")
        payload_sha = previous_sha
    else:
        _require(exact, "notice staging conflict, source race or incomplete readback")
    result = {"status": "staged", "kind": kind, "target_date": target,
              "staged": len(notices), "payload_sha256": payload_sha}
    if holding_trigger is not None:
        result["ready_to_dispatch_holding"] = exact
    return result
