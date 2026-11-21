"""Local release hold around one independently authorized Cloud CI handoff.

The maintainer performs any Git/CI/Worker operations separately, after admission.
This module cannot publish, reset a Git ref, launch a task, or infer terminal
provider state from a checkout. An unresolved operation retains the local hold.
"""

import datetime
import os
import re
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from . import continuing_acceptance as ca
from .continuing_transition import RUNTIME_RELEASE_SCHEMA, checked_normal_deployment, ordinary_runtime_release
from .files import atomic_write, digest, file_sha, private_root, read


_BRANCH = "research/weak-early-beta"
_ORIGIN = "https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev"
_SCOPE = "EXACT_NEW_A_CLOUD_RELEASE_WINDOW"
_COMMIT = re.compile(r"[a-f0-9]{40}")
_SHA = re.compile(r"[a-f0-9]{64}")
_VERSION = re.compile(r"[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}")
_RELEASE = ("source_commit", "activation_sha256", "version_id", "build_input_sha256", "policy_sha256", "ci_run_id", "tag")
_PAIR = (*_RELEASE, "acceptance_sha256", "deployment_id", "target")


def _matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def observe_release_pair(repo, *, git_reader, deployment_reader):
    """Assemble local approval/Git and native provider proof via trusted readers.

    git_reader(repo) independently verifies the clean canonical branch and exact
    origin ref. deployment_reader(repo, release) provides a real normal provider
    observation including the native 100% deployment and primary/nonce readback.
    """
    repo = Path(repo).resolve()
    ca.require(callable(git_reader) and callable(deployment_reader), "release_pair_readers_required")
    release = ordinary_runtime_release(repo)
    ca.require(release and release.get("schema") == RUNTIME_RELEASE_SCHEMA, "release_ordinary_approval_required")
    activation = private_root(repo) / "activation.json"
    value = read(activation)
    acceptance = value.get("owner_acceptance", {}).get("continuing_acceptance", {})
    ca.require(file_sha(activation) == release["activation_sha256"] and _matches(_SHA, acceptance.get("sha256")),
               "release_approval_changed")
    git = git_reader(repo)
    _check_git(repo, git, release["source_commit"])
    target = ca.target(repo)
    provider = checked_normal_deployment(release["source_commit"], target, lambda: deployment_reader(repo, release))
    ca.require(provider.get("normal_origin") == _ORIGIN and provider.get("live_traffic_percent") == 100
               and _matches(_SHA, provider.get("active_owner_sha256"))
               and all(provider[key] == release[key] for key in _RELEASE[2:]),
               "release_normal_provider_differs")
    _check_git(repo, git_reader(repo), release["source_commit"])
    ca.require(file_sha(activation) == release["activation_sha256"] and ordinary_runtime_release(repo) == release,
               "release_approval_changed")
    return {
        "schema": "NEW_A_HOST_OBSERVED_RELEASE_PAIR_V1", "repository": str(repo),
        "git": git, **{key: release[key] for key in _RELEASE}, "acceptance_sha256": acceptance["sha256"],
        "deployment_id": provider["deployment_id"], "target": target,
        "provider_sha256": provider["raw_receipt_sha256"], "observed_at": provider["observed_at"],
    }


def _check_git(repo, git, source):
    ca.require(isinstance(git, dict) and git.get("repository") == str(repo) and git.get("branch") == _BRANCH
               and git.get("clean") is True and git.get("local_head") == source and git.get("remote_head") == source,
               "release_git_pair_differs")


def _observe(repo, pair_reader):
    ca.require(callable(pair_reader), "release_pair_reader_required")
    observation = pair_reader(repo)
    ca.require(isinstance(observation, dict) and observation.get("schema") == "NEW_A_HOST_OBSERVED_RELEASE_PAIR_V1"
               and observation.get("repository") == str(repo) and _matches(_COMMIT, observation.get("source_commit"))
               and _matches(_VERSION, observation.get("version_id")) and _matches(_VERSION, observation.get("deployment_id"))
               and all(_matches(_SHA, observation.get(key)) for key in
                       ("activation_sha256", "acceptance_sha256", "build_input_sha256", "policy_sha256", "provider_sha256"))
               and observation.get("target") == ca.target(repo)
               and type(observation.get("ci_run_id")) is int and observation["ci_run_id"] > 0
               and isinstance(observation.get("tag"), str) and observation["tag"].startswith("cloud-deploy-")
               and ca.timestamp(observation["observed_at"]) <= ca.now(),
               "release_verified_pair_required")
    _check_git(repo, observation.get("git"), observation["source_commit"])
    return {key: observation[key] for key in _PAIR}, observation["provider_sha256"]


def _lock_paths(repo):
    base = repo / ".cache/weak_early_beta"
    runtime = base / "daily_runtime"
    config_path = base / "daily-runner.config.json"
    ca.require(config_path.resolve() == config_path, "release_runtime_config_path")
    config = read(config_path)
    ca.require(Path(config["repoPath"]) == repo and Path(config["runtimeDir"]) == runtime,
               "release_unexpected_operating_runtime")
    active = (runtime / "task-entry.lock", runtime / "daily.lock", base / "exit-reminder-runner.lock")
    legacy = (base / "exit-reminder.lock", repo / "weak_early_beta/state/exit-reminder.lock",
              repo / "weak_early_beta/state/daily_runtime/daily.lock")
    ca.require(all(path.resolve() == path for path in (*active, *legacy)), "release_lock_path_escape")
    return active, legacy


def _claim(path, owner):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(owner)
        stream.flush()
        os.fsync(stream.fileno())


def _owns(path, owner):
    return path.is_file() and not path.is_symlink() and path.read_text(encoding="utf-8") == owner


def _drop_own(paths, owner):
    for path in reversed(paths):
        if _owns(path, owner):
            path.unlink()


def _idle(repo, idle_reader, legacy):
    ca.require(callable(idle_reader) and idle_reader(repo) is True and not any(path.exists() for path in legacy),
               "release_runner_not_verified_idle")


def _directory(repo, operation):
    ca.require(_matches(_SHA, operation), "release_operation_id_invalid")
    root = private_root(repo) / "release-maintenance" / operation
    ca.require(root.resolve() == root, "release_private_operation_path")
    return root


def _file(root, name):
    path = root / name
    ca.require(path.resolve() == path, "release_private_operation_path")
    return path


def _plan(repo, operation):
    root = _directory(repo, operation)
    plan = read(_file(root, "intent.json"))
    ca.require(plan.get("schema") == "NEW_A_RELEASE_MAINTENANCE_INTENT_V1" and digest(plan) == operation
               and plan.get("repository") == str(repo), "release_intent_changed")
    return root, plan, "new-a-release:" + operation


@contextmanager
def _serialize(root):
    lock = _file(root, "transition.lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    # The stable file has an OS-owned lock. A dead maintainer process cannot
    # prevent later reconciliation or authorize clearing the independent hold.
    with lock.open("a+b") as stream:
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ValueError("release_transition_already_held") from None
        yield


def _save(path, value):
    # Every write is under the operation's OS lock. Existing records never get
    # overwritten. A reader observes the whole record or no record.
    ca.require(not path.exists(), "release_receipt_already_exists")
    atomic_write(path, value)
    ca.require(read(path) == value, "release_receipt_readback_differs")


def begin_release(
    repo, candidate_source, *, not_after, owner_message, primary_reader, owner_authority,
    decision_reader, pair_reader, idle_reader,
):
    """Exclusively hold the exact operating paths. This does not admit a deploy."""
    repo = Path(repo).resolve()
    deadline = ca.timestamp(not_after)
    ca.require(ca.now() < deadline <= ca.now() + datetime.timedelta(hours=1)
               and _matches(_COMMIT, candidate_source), "release_finite_window_invalid")
    old, provider_sha = _observe(repo, pair_reader)
    ca.require(candidate_source != old["source_commit"], "release_candidate_must_differ")
    owner = ca.primary_message(owner_message, primary_reader, owner_authority)
    ca.require(callable(decision_reader), "release_exact_maintainer_review_required")
    intent = {
        "schema": "NEW_A_RELEASE_MAINTENANCE_INTENT_V1", "scope": _SCOPE, "repository": str(repo),
        "old": old, "candidate_source": candidate_source, "not_after": not_after,
        "owner_message_sha256": owner["text_sha256"], "owner_message_id": owner["message_id"],
    }
    operation = digest(intent)
    decision = decision_reader(deepcopy(owner), deepcopy(intent))
    ca.require(isinstance(decision, dict) and decision.get("schema") == "NEW_A_HOST_RELEASE_MAINTENANCE_REVIEW_V1"
               and decision.get("operation_sha256") == operation and decision.get("authorized") is True
               and decision.get("platform_signature_claimed") is False, "release_exact_maintainer_review_required")
    paths, legacy = _lock_paths(repo)
    _idle(repo, idle_reader, legacy)
    root = _directory(repo, operation)
    token = "new-a-release:" + operation
    with _serialize(root):
        _save(_file(root, "intent.json"), intent)
        claimed = []
        try:
            for path in paths:
                _claim(path, token)
                claimed.append(path)
            _idle(repo, idle_reader, legacy)
            confirmed, confirmed_sha = _observe(repo, pair_reader)
            ca.require(confirmed == old and all(_owns(path, token) for path in paths) and ca.now() < deadline,
                       "release_old_pair_changed_before_hold")
            receipt = {
                "schema": "NEW_A_RELEASE_MAINTENANCE_HELD_V1", "operation_sha256": operation,
                "old_sha256": digest(old), "provider_before_sha256": provider_sha,
                "provider_held_sha256": confirmed_sha, "not_after": not_after,
            }
            _save(_file(root, "held.json"), receipt)
        except BaseException:
            _drop_own(claimed, token)
            raise
    return receipt


def verify_release_hold(repo, operation, *, admitted=True):
    """Return the existing lock-owner token for an approval applied inside the hold."""
    repo = Path(repo).resolve()
    root, plan, token = _plan(repo, operation)
    held = read(_file(root, "held.json"))
    ca.require(held.get("schema") == "NEW_A_RELEASE_MAINTENANCE_HELD_V1"
               and held.get("operation_sha256") == operation and held.get("old_sha256") == digest(plan["old"])
               and ca.now() < ca.timestamp(plan["not_after"]) and not _file(root, "terminal.json").exists(),
               "release_active_hold_required")
    paths, legacy = _lock_paths(repo)
    ca.require(all(_owns(path, token) for path in paths) and not any(path.exists() for path in legacy),
               "release_lock_ownership_changed")
    if admitted:
        recorded = read(_file(root, "admitted.json"))
        ca.require(recorded.get("schema") == "NEW_A_RELEASE_MAINTENANCE_ADMISSION_V1"
                   and recorded.get("operation_sha256") == operation
                   and recorded.get("candidate_source") == plan["candidate_source"], "release_admission_required")
    return token


@contextmanager
def admitted_release_hold(repo, operation):
    """Serialize local approval work against finishing an admitted operation."""
    repo = Path(repo).resolve()
    root, _, _ = _plan(repo, operation)
    with _serialize(root):
        yield verify_release_hold(repo, operation)


def admit_release(repo, operation, *, pair_reader, idle_reader):
    """One-time boundary prior to externally managed, separately authorized CI."""
    repo = Path(repo).resolve()
    root, plan, token = _plan(repo, operation)
    with _serialize(root):
        path = _file(root, "admitted.json")
        ca.require(not path.exists(), "release_admission_already_consumed_reconcile")
        verify_release_hold(repo, operation, admitted=False)
        _, legacy = _lock_paths(repo)
        _idle(repo, idle_reader, legacy)
        old, provider_sha = _observe(repo, pair_reader)
        ca.require(old == plan["old"] and verify_release_hold(repo, operation, admitted=False) == token,
                   "release_old_pair_changed_before_admission")
        receipt = {
            "schema": "NEW_A_RELEASE_MAINTENANCE_ADMISSION_V1", "operation_sha256": operation,
            "candidate_source": plan["candidate_source"], "provider_sha256": provider_sha,
            "admitted_at": ca.now().isoformat(), "not_after": plan["not_after"],
        }
        _save(path, receipt)
    return receipt


def _resolve_terminal(plan, operation, pair, admitted, terminal_reader):
    old = plan["old"]
    if not admitted:
        ca.require(pair == old, "release_unadmitted_old_pair_changed")
        return "old-unchanged", None
    ca.require(callable(terminal_reader), "release_terminal_host_reader_required")
    receipt = terminal_reader(operation, deepcopy(pair))
    ca.require(isinstance(receipt, dict) and receipt.get("schema") == "NEW_A_HOST_RELEASE_TERMINAL_V1"
               and receipt.get("operation_sha256") == operation and receipt.get("observed_pair_sha256") == digest(pair)
               and receipt.get("synthetic") is False and receipt.get("platform_signature_claimed") is False
               and _matches(_SHA, receipt.get("raw_receipt_sha256")), "release_terminal_unconfirmed")
    status = receipt.get("outcome")
    if status == "old-restored":
        ca.require(all(pair[key] == old[key] for key in _PAIR if key != "deployment_id"),
                   "release_old_pair_not_restored")
    elif status == "old-unchanged":
        ca.require(pair == old, "release_old_pair_changed")
    elif status == "candidate-selected":
        ca.require(pair["source_commit"] == plan["candidate_source"] and pair["target"] == old["target"]
                   and all(pair[key] != old[key] for key in ("version_id", "acceptance_sha256", "activation_sha256")),
                   "release_candidate_pair_not_approved")
    else:
        raise ValueError("release_terminal_unconfirmed")
    return status, receipt["raw_receipt_sha256"]


def verify_restored_release(evidence):
    """Verify a closed rollback's original and restored pair receipts offline."""
    ca.require(isinstance(evidence, dict) and set(evidence) == {"reference", "receipts"},
               "release_restoration_evidence_invalid")
    reference, receipts = evidence["reference"], evidence["receipts"]
    ca.require(isinstance(reference, dict) and set(reference) == {"operation_sha256", "released_sha256"}
               and all(_matches(_SHA, value) for value in reference.values())
               and isinstance(receipts, dict) and set(receipts) == {"intent", "admitted", "terminal", "released"}
               and all(isinstance(value, str) and 0 < len(value.encode("utf-8")) <= 16_384
                       for value in receipts.values()), "release_restoration_evidence_invalid")
    operation = reference["operation_sha256"]
    plan, admitted, terminal, released = (json.loads(receipts[key]) for key in
                                         ("intent", "admitted", "terminal", "released"))
    ca.require(all(isinstance(value, dict) for value in (plan, admitted, terminal, released))
               and sha256(receipts["released"].encode()).hexdigest() == reference["released_sha256"]
               and digest(plan) == operation and plan.get("schema") == "NEW_A_RELEASE_MAINTENANCE_INTENT_V1"
               and plan.get("scope") == _SCOPE and _matches(_COMMIT, plan.get("candidate_source"))
               and admitted.get("schema") == "NEW_A_RELEASE_MAINTENANCE_ADMISSION_V1"
               and admitted.get("operation_sha256") == operation
               and admitted.get("candidate_source") == plan["candidate_source"]
               and admitted.get("not_after") == plan.get("not_after")
               and ca.timestamp(admitted["admitted_at"]) < ca.timestamp(plan["not_after"])
               and _matches(_SHA, admitted.get("provider_sha256"))
               and terminal.get("schema") == "NEW_A_RELEASE_MAINTENANCE_TERMINAL_V1"
               and terminal.get("operation_sha256") == operation and terminal.get("outcome") == "old-restored"
               and all(_matches(_SHA, terminal.get(key)) for key in
                       ("terminal_proof_sha256", "provider_before_sha256", "provider_after_sha256"))
               and released == {"schema": "NEW_A_RELEASE_MAINTENANCE_RELEASED_V1", "operation_sha256": operation,
                                "outcome": "old-restored", "starts": 0,
                                "terminal_sha256": sha256(receipts["terminal"].encode()).hexdigest()},
               "release_restoration_receipts_differ")
    old, restored = plan.get("old"), terminal.get("pair")
    ca.require(isinstance(old, dict) and isinstance(restored, dict) and set(old) == set(restored) == set(_PAIR)
               and _matches(_COMMIT, old.get("source_commit")) and plan["candidate_source"] != old["source_commit"]
               and _matches(_VERSION, old.get("version_id"))
               and all(_matches(_VERSION, pair.get("deployment_id")) for pair in (old, restored))
               and old["deployment_id"] != restored["deployment_id"]
               and all(old[key] == restored[key] for key in _PAIR if key != "deployment_id"),
               "release_restoration_pairs_differ")
    return old, restored, ca.timestamp(admitted["admitted_at"])


def read_restored_release(repo, reference):
    """Read only the canonical operation named by the maintainer's exact reference."""
    ca.require(isinstance(reference, dict) and set(reference) == {"operation_sha256", "released_sha256"},
               "release_restoration_reference_invalid")
    repo = Path(repo).resolve()
    root, plan, _ = _plan(repo, reference["operation_sha256"])
    receipts = {}
    for key in ("intent", "admitted", "terminal", "released"):
        path = _file(root, key + ".json")
        ca.require(path.is_file() and 0 < path.stat().st_size <= 16_384,
                   "release_restoration_receipt_unavailable")
        receipts[key] = path.read_bytes().decode("utf-8")
    ca.require(json.loads(receipts["intent"]) == plan, "release_restoration_intent_changed")
    evidence = {"reference": deepcopy(reference), "receipts": receipts}
    verify_restored_release(evidence)
    return evidence


def finish_release(repo, operation, *, pair_reader, idle_reader, terminal_reader=None):
    """Clear only owned locks after independent terminal and pair readback.

    This remains permitted after the finite mutation window. Expiry never
    assumes an outcome, drops a hold, or reissues a deploy automatically.
    """
    repo = Path(repo).resolve()
    root, plan, token = _plan(repo, operation)
    with _serialize(root):
        released = _file(root, "released.json")
        terminal_path = _file(root, "terminal.json")
        if released.exists():
            receipt = read(released)
            ca.require(receipt.get("operation_sha256") == operation
                       and receipt.get("terminal_sha256") == file_sha(terminal_path), "release_completion_changed")
            return receipt
        paths, legacy = _lock_paths(repo)
        _idle(repo, idle_reader, legacy)
        ca.require(all(not path.exists() or _owns(path, token) for path in paths), "release_lock_ownership_changed")
        if _file(root, "held.json").exists() and not terminal_path.exists():
            ca.require(all(_owns(path, token) for path in paths), "release_lock_ownership_changed")
        pair, provider_sha = _observe(repo, pair_reader)
        status, resolution_sha = _resolve_terminal(
            plan, operation, pair, _file(root, "admitted.json").exists(), terminal_reader,
        )
        confirmed, confirmed_sha = _observe(repo, pair_reader)
        ca.require(confirmed == pair and all(not path.exists() or _owns(path, token) for path in paths),
                   "release_final_pair_or_lock_changed")
        terminal = {
            "schema": "NEW_A_RELEASE_MAINTENANCE_TERMINAL_V1", "operation_sha256": operation,
            "pair": pair, "outcome": status, "terminal_proof_sha256": resolution_sha,
            "provider_before_sha256": provider_sha, "provider_after_sha256": confirmed_sha,
        }
        if terminal_path.exists():
            saved = read(terminal_path)
            ca.require(all(saved.get(key) == terminal[key] for key in ("operation_sha256", "pair", "outcome")),
                       "release_terminal_receipt_changed")
        else:
            _save(terminal_path, terminal)
        _drop_own(paths, token)
        ca.require(not any(_owns(path, token) for path in paths), "release_owned_lock_remains")
        result = {
            "schema": "NEW_A_RELEASE_MAINTENANCE_RELEASED_V1", "operation_sha256": operation,
            "outcome": status, "terminal_sha256": file_sha(terminal_path), "starts": 0,
        }
        _save(released, result)
    return result
