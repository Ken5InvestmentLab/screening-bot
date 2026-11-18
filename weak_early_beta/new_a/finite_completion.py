"""Read verified Nov17 recovery history without contacting D1 or Discord."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re

from .files import digest

JST = timezone(timedelta(hours=9))
HEX = re.compile(r"[0-9a-f]{64}")
MESSAGE_ID = re.compile(r"[1-9][0-9]{16,19}")


def _require(condition, message):
    if not condition:
        raise ValueError("Finite completion: " + message)


def _read(path):
    raw = Path(path).read_bytes()
    _require(len(raw) <= 2_000_000, "receipt exceeds expected size")
    return json.loads(raw.decode("utf-8-sig")), hashlib.sha256(raw).hexdigest()


def _timestamp(string):
    result = datetime.fromisoformat(string)
    _require(result.tzinfo is not None, "receipt is missing a timezone")
    return result


def verified_completion(repo, finite_ref, finite_record, independent_receipt):
    """Reconcile the immutable run and a trusted operator's independent readback.

    The supplied independent receipt must come from the trusted host's audited
    storage. This function checks consistency, not provider signatures.
    """
    repo = Path(repo).resolve()
    evidence, evidence_hash = _read(independent_receipt)
    _require(
        evidence["schema"] == "NEW_A_NOV17_INDEPENDENT_FINAL_READBACK_V1"
        and evidence["passed"] is True
        and evidence["stage"] == "external_readback"
        and evidence["read_only"] is True
        and evidence["production_changes"] is False
        and evidence["posts_performed"] is False,
        "independent readback is not successful and read-only",
    )
    local, d1, discord = (evidence[key] for key in ("local", "d1", "discord"))
    start = _timestamp(local["run_started_at_jst"])
    end = _timestamp(local["run_completed_at_jst"])
    observed = _timestamp(evidence["observed_at_jst"])
    target, execution = finite_record["target_date"], finite_record["execution_date"]
    _require(
        local["target_date"] == target
        and local["actual_execution_date"] == execution
        and start.astimezone(JST).date().isoformat() == execution
        and _timestamp(finite_record["issued_at"]) <= start < end <= observed
        < _timestamp(finite_record["not_after"]),
        "target, execution date or observation order differs",
    )
    name = start.astimezone(timezone.utc).isoformat(timespec="milliseconds")
    name = name.replace("+00:00", "Z").replace(":", "-").replace(".", "-")
    runtime = (repo / ".cache/weak_early_beta/daily_runtime").resolve()
    _require(runtime.is_relative_to(repo), "runtime escapes the checkout")
    result_path = (runtime / ("daily-" + name) / "result.json").resolve()
    _require(result_path.is_relative_to(runtime), "result escapes canonical runtime")
    run, result_hash = _read(result_path)
    proof, deployment = run["new_a"], run["deployment"]
    source = finite_record["source_commit"]
    ci = finite_record["ci"]
    _require(
        run["identity"] == "WEAK_EARLY_CLOUD_DAILY_V1"
        and run["ok"] is True
        and run["stage"] == "notification"
        and run["observationKind"] == "DELAYED_SCHEDULED_OBSERVATION"
        and run["date"] == run["latestSession"] == target
        and run["executionDate"] == execution
        and run["startCommit"] == local["source_commit"] == deployment["headSha"] == source
        and _timestamp(run["startedAt"]) == start
        and _timestamp(run["completedAt"]) == end
        and run["pid"] == local["root_pid"]
        and deployment["versionId"] == local["worker_version"] == ci["version_id"]
        and deployment["run"]["databaseId"] == local["ci_run_id"] == ci["run_id"]
        and deployment["reusedPredeployedCodeOnly"] is True
        and run["nativeAdmissionContinuation"]["original_run_id"] == run["originalRunId"],
        "terminal runner identity differs from the admitted run",
    )
    _require(
        proof["strategy"] == "A_BASE"
        and proof["operational_publication_verified"] is True
        and proof["owner_publication_verified"] is False
        and proof["owner_http_observed"] is False
        and proof["dataset_id"] == local["dataset_id"]
        and proof["snapshot_sha256"] == local["daily_snapshot_sha256"]
        and proof["source_version"] == local["source_version"]
        and all(
            HEX.fullmatch(local[key])
            for key in ("daily_snapshot_sha256", "source_version", "manifest_sha256")
        )
        and local["operational_gate_continuity_verified"] is True
        and local["existing_owner_gate_verified"] is False
        and local["owner_http_observed"] is False
        and d1["passed"] is True
        and d1["select_only"] is True
        and d1["ready"] is True
        and d1["as_of"] == target
        and d1["same_target_dataset_count"] == 1
        and d1["current_display_snapshot_matches"] is True
        and d1["current_d1_challenge_matches_public_worker"] is True,
        "publication or independent D1 readback differs",
    )
    sent, final = (run[key] for key in ("notifications", "notificationReconciliation"))
    messages = discord["messages"]
    signal_count, summary_count = sent["signal_notifications"], sent["completion_notifications"]
    _require(
        sent["dry_run"] is False
        and final["dry_run"] is True
        and sent["date"] == final["date"] == target
        and sent["snapshot_sha256"] == final["snapshot_sha256"] == proof["snapshot_sha256"]
        and final["signal_notifications"] == final["completion_notifications"] == final["external_sends"]
        == local["outbox_remaining_signal"] == local["outbox_remaining_summary"] == 0
        and discord["passed"] is True
        and discord["get_only"] is True
        and len(messages) == discord["expected_delivery_count"] == sent["external_sends"]
        == signal_count + summary_count
        and sum(row["kind"] == "signal" for row in messages) == signal_count
        and sum(row["kind"] == "summary" for row in messages) == summary_count
        and len({row["message_id"] for row in messages}) == len(messages)
        and len({row["event_id"] for row in messages}) == len(messages)
        and all(
            MESSAGE_ID.fullmatch(row["message_id"])
            and row["payload_footer_and_delayed_run_verified"] is True
            and start <= _timestamp(row["arrived_at_jst"]) <= observed
            for row in messages
        ),
        "notification is pending or its independent readback differs",
    )
    receipts = {"terminal_runner": result_hash, "independent_readback": evidence_hash}
    return {
        "schema": "NEW_A_VERIFIED_FINITE_COMPLETION_V1",
        "finite_admission": finite_ref,
        "source_commit": source,
        "target_date": target,
        "execution_date": execution,
        "publication_verified": True,
        "notification_reconciled": True,
        "receipt_hashes": receipts,
        "completion_sha256": digest(receipts),
    }
