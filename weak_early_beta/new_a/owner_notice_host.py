"""Canonical host connection for staging owner notices after an ordinary run.

Enable only with the exact opted-in device binding and an already-applied ordinary
approval. This entrypoint uses existing readbacks and the existing D1 writer.
After staging, it asks the Worker to dispatch the same-day holding notice.
"""
import argparse
from datetime import timedelta
from http.client import HTTPSConnection, HTTPException
import json
from pathlib import Path
import re
import subprocess
import sys

from .continuing_acceptance import target
from .continuing_transition import RUNTIME_RELEASE_SCHEMA, ordinary_runtime_release
from .files import digest, private_root, read
from .lifecycle_notice_inputs import OWNER_PROOF, LifecycleNoticeInputs
from .owner_notice_producer import OwnerNoticeProducer, _terminal_result
from .planned_notice_delivery import AUDIENCE, _clock, _hash, _instant, _require
from .publisher import WranglerD1

HOST_SCHEMA = "NEW_A_OWNER_NOTICE_HOST_V1"
RUNTIME_SCHEMA = "NEW_A_OWNER_NOTICE_RUNTIME_V1"
DEVICE_ID = re.compile(r"[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}")
NOTICE_HOST = "tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev"
HOLDING_NOTICE_PATH = "/api/cloud/new-a-finite/holding-notice-dispatch"
DEVICE_READ = """
SELECT subscription.subscription_id, metadata.endpoint_hash
FROM cloud_push_subscriptions AS subscription
JOIN cloud_push_subscription_metadata AS metadata ON metadata.subscription_id=subscription.subscription_id
JOIN cloud_member_preferences AS preferences ON preferences.member_id=subscription.member_id
WHERE subscription.member_id=? AND subscription.revoked_at IS NULL AND metadata.vapid_public_key=?
  AND (metadata.expires_at_ms IS NULL OR metadata.expires_at_ms>?)
  AND (json_type(preferences.preferences_json,'$.notifications.new_detection')='true'
       OR json_type(preferences.preferences_json,'$.notifications.reminder')='true')
LIMIT 9
"""


def _binding_file(repo):
    file = private_root(repo) / "owner-notice-host.json"
    _require(file.resolve() == file and file.is_file(), "owner notice host is not enabled")
    with file.open("rb") as stream:
        raw = stream.read(2049)
    _require(0 < len(raw) <= 2048, "owner notice host setting exceeds its bounds")
    value = json.loads(raw.decode("utf-8-sig"))
    _require(isinstance(value, dict) and set(value) == {"schema", "enabled", "recipient_binding_sha256"} and
             value["schema"] == HOST_SCHEMA and value["enabled"] is True and
             _hash(value["recipient_binding_sha256"]), "the fixed owner notice device is not approved")
    return value["recipient_binding_sha256"]


def _runtime_subprocess(repo, config, node, release):
    result = subprocess.run(
        [str(node), str(repo / "scripts/windows/new-a-owner-notice-host.mjs"), str(config)],
        cwd=repo, input=json.dumps(release), encoding="utf-8", capture_output=True, timeout=140,
    )
    _require(result.returncode == 0 and len(result.stdout.encode("utf-8")) <= 4096,
             "live owner notice identity observation failed")
    return json.loads(result.stdout)


def _dispatch_holding(token):
    connection = HTTPSConnection(NOTICE_HOST, timeout=8)
    try:
        connection.request("POST", HOLDING_NOTICE_PATH, headers={"Authorization": "Bearer " + token})
        return "accepted" if connection.getresponse().status == 204 else "unconfirmed"
    except (OSError, HTTPException):
        return "unconfirmed"
    finally:
        connection.close()


class OwnerNoticeHost:
    def __init__(self, repo, recipient, public_key, database, *, observe, approval, clock=_clock):
        _require(_hash(recipient) and isinstance(public_key, str) and bool(public_key) and
                 callable(observe) and callable(approval) and callable(clock),
                 "owner notice host has no bound readers or device")
        self.repo = repo
        self.recipient = recipient
        self.public_key = public_key
        self.database = database
        self.observe = observe
        self.approval = approval
        self.clock = clock
        self.cached = None

    def _verify(self):
        _require(_binding_file(self.repo) == self.recipient, "approved owner device binding changed")
        approved = self.approval()
        _require(isinstance(approved, dict) and approved.get("schema") == RUNTIME_RELEASE_SCHEMA,
                 "ordinary approved Worker is unavailable for notices")
        now = self.clock()
        if self.cached and self.cached[0] == approved and now < _instant(self.cached[1]["expires_at"]):
            return self.cached
        runtime = self.observe(approved)
        now = self.clock()
        observed, expires = _instant(runtime["observed_at"]), _instant(runtime["expires_at"])
        _require(runtime.get("schema") == RUNTIME_SCHEMA and
                 runtime.get("source_commit") == approved["source_commit"] and
                 runtime.get("worker_version_id") == approved["version_id"] and
                 runtime.get("normal_owner_policy_verified") is True and
                 type(runtime.get("fresh_paid_role")) is bool and
                 _hash(runtime.get("owner_binding_sha256")) and _hash(runtime.get("d1_active_sha256")) and
                 observed <= now < expires <= observed + timedelta(seconds=30),
                 "exact live Worker or owner input proof differs")
        self.cached = (approved, runtime)
        return self.cached

    def read_release(self):
        return self._verify()[0]

    def read_owner_policy(self, expected_target):
        _require(expected_target == target(self.repo), "owner notice D1 target differs")
        _, runtime = self._verify()
        return {
            "schema": OWNER_PROOF, "normal_owner_policy_verified": True,
            **{key: runtime[key] for key in ("owner_binding_sha256", "d1_active_sha256", "observed_at", "expires_at")},
        }

    def read_recipient(self):
        _, runtime = self._verify()
        _require(runtime.get("fresh_paid_role") is True, "fresh entitled owner role is unavailable")
        owner = runtime["owner_binding_sha256"]
        member = "cloud_" + owner
        now = self.clock()
        registrations = self.database.query(DEVICE_READ, (member, self.public_key, int(now.timestamp() * 1000)))
        _require(len(registrations) <= 8, "fixed recipient selection is ambiguous")
        matches = [
            device for device in registrations
            if DEVICE_ID.fullmatch(str(device.get("subscription_id", ""))) and _hash(device.get("endpoint_hash"))
            and digest(["NEW_A_OWNER_WEB_PUSH_DEVICE_V1", member, device["subscription_id"], device["endpoint_hash"]])
            == self.recipient
        ]
        _require(len(matches) == 1 and _binding_file(self.repo) == self.recipient and
                 self.clock() < _instant(runtime["expires_at"]), "approved and opted-in owner device unavailable")
        return {"schema": "NEW_A_OWNER_NOTICE_RECIPIENT_V1", "audience": AUDIENCE,
                "owner_binding_sha256": owner, "recipient_binding_sha256": self.recipient,
                "enabled": True, "owner_verified": True, "fresh_paid_role": True,
                "observed_at": runtime["observed_at"], "expires_at": runtime["expires_at"]}


def after_publication(repo, run_path):
    repo = Path(repo).resolve(strict=True)
    _require(repo == Path(__file__).resolve().parents[2], "use the intended canonical daily checkout")
    _terminal_result(repo, run_path, _clock())
    recipient = _binding_file(repo)
    config = repo / ".cache/weak_early_beta/daily-runner.config.json"
    _require(config.resolve() == config and config.is_file(), "canonical notice runner configuration differs")
    settings = read(config)
    node = Path(settings["nodePath"])
    _require(Path(settings["repoPath"]).resolve() == repo and
             Path(settings["runtimeDir"]).resolve() == repo / ".cache/weak_early_beta/daily_runtime" and
             node.is_absolute() and node.is_file(), "canonical notice runner configuration differs")
    worker_vars = read(repo / "weak-early-beta-gate/wrangler.jsonc")["vars"]
    _require(worker_vars.get("CLOUD_PUSH_MEMBERSHIP_POLICY") == "whop_managed_discord_role",
             "approved managed-role policy is unavailable")
    public_key = worker_vars.get("CLOUD_VAPID_PUBLIC_KEY")
    dispatch_holding = None
    if (worker_vars.get("CLOUD_PUSH_MODE") == "new_a_owner_scheduled" and
            worker_vars.get("CLOUD_NEW_A_OWNER_PUSH_ENABLED") == "true" and
            worker_vars.get("CLOUD_PUSH_SCHEDULER_ENABLED") == "false"):
        dispatch_holding = _dispatch_holding
    official_target = target(repo)
    _require(official_target["service"] == "tentei-kyokuchi-cloud", "unexpected owner notice target")
    database = WranglerD1(repo, private_root(repo) / "sql", execute=True, node=str(node))
    try:
        host = OwnerNoticeHost(repo, recipient, public_key, database,
                               observe=lambda release: _runtime_subprocess(repo, config, node, release),
                               approval=lambda: ordinary_runtime_release(repo))
        inputs = LifecycleNoticeInputs(repo, database, lambda: host.read_owner_policy(official_target), node=str(node))
        producer = OwnerNoticeProducer(repo, inputs, database, read_release=host.read_release,
                                       read_recipient=host.read_recipient, dispatch_holding=dispatch_holding)
        return producer.after_publication(run_path)
    finally:
        database.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--after-publication", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(after_publication(Path.cwd(), args.after_publication), ensure_ascii=True))
    except Exception:
        print("owner_notice_host_unavailable", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
