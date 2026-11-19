"""Private, read-only proof of the known production Worker and its owner D1."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from . import continuing_acceptance as acceptance
from .continuing_transition import RUNTIME_RELEASE_SCHEMA, checked_normal_deployment
from .files import digest, private_root, read
from .operational_admission import ORIGIN, now, observe_normal_response, read_active_metadata, stamp
from .publisher import WranglerD1


def deployment_metadata(raw, expected_version):
    """JSON returned by the installed Wrangler deployments status command."""
    try:
        deployment = json.loads(raw)
        routes = deployment["versions"]
        if (not isinstance(routes, list) or len(routes) != 1
                or routes[0]["version_id"] != expected_version
                or type(routes[0]["percentage"]) not in (int, float)
                or routes[0]["percentage"] != 100):
            raise ValueError("Approved Cloud Worker is not the single active version at 100 percent")
        timestamp = stamp(deployment["created_on"])
        identity = deployment["id"]
        if (not re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", identity)
                or deployment.get("strategy") != "percentage" or timestamp > now()):
            raise ValueError("Cloudflare deployment identity differs")
    except (TypeError, KeyError, AttributeError) as error:
        raise ValueError("Cloudflare deployment response is incomplete") from error
    return {"id": identity, "created_on": deployment["created_on"], "version_id": expected_version}


def deployment_status(repo, node):
    gate = repo / "weak-early-beta-gate"
    config = gate / "wrangler.jsonc"
    cli = gate / "node_modules/wrangler/bin/wrangler.js"
    if config.resolve() != config or cli.resolve() != cli or not cli.is_file():
        raise ValueError("Canonical Wrangler deployment command unavailable")
    process = subprocess.run(
        [node, str(cli), "deployments", "status", "--config", str(config),
         "--env=", "--name", acceptance.SERVICE, "--json"],
        cwd=gate, env={**os.environ, "CLOUDFLARE_API_BASE_URL": "https://api.cloudflare.com/client/v4"},
        capture_output=True, timeout=45,
    )
    if process.returncode != 0:
        if b"No access to the specified resource" in process.stderr:
            raise PermissionError("Cloudflare refused production deployment readback")
        raise ValueError("Production deployment readback failed")
    if not 0 < len(process.stdout) <= 65536:
        raise ValueError("Cloudflare deployment response size differs")
    return process.stdout


def read_active_production_release(repo, approved_release):
    """Combine two provider status reads with a live nonce and primary D1 proof."""
    repo = Path(repo).resolve()
    target = acceptance.target(repo)
    if (approved_release.get("schema") != RUNTIME_RELEASE_SCHEMA
            or approved_release.get("source_commit") != acceptance.head(repo)
            or approved_release.get("worker") != target["service"]
            or approved_release.get("database") != target["database_name"]
            or target["database_id"] != "e0cdb3a7-b682-4db8-96ac-f2afcc9c23cb"):
        raise ValueError("Approved production Worker runtime identity required")

    node = read(repo / ".cache/weak_early_beta/daily-runner.config.json")["nodePath"]
    version_id = approved_release["version_id"]
    before_raw = deployment_status(repo, node)
    before = deployment_metadata(before_raw, version_id)
    owner = WranglerD1(repo, private_root(repo) / "sql", execute=True, node=node, require_primary=True)
    try:
        initial_owner = read_active_metadata(owner)
        response_sha = observe_normal_response(
            source=approved_release["source_commit"], version_id=version_id,
            build_input_sha256=approved_release["build_input_sha256"],
            policy_sha256=approved_release["policy_sha256"], active=initial_owner[2],
        )
        if read_active_metadata(owner) != initial_owner:
            raise ValueError("Owner READY generation changed during Worker readback")
    finally:
        owner.close()

    after_raw = deployment_status(repo, node)
    if deployment_metadata(after_raw, version_id) != before:
        raise ValueError("Active Cloudflare deployment changed during Worker readback")
    if acceptance.head(repo) != approved_release["source_commit"] or acceptance.target(repo) != target:
        raise ValueError("Local approved source or target changed during Worker readback")

    raw_hash = digest([hashlib.sha256(raw).hexdigest() for raw in (before_raw, after_raw)] + [response_sha])
    evidence = {
        "schema": "NEW_A_HOST_VERIFIED_DEPLOYMENT_V1",
        "source_commit": approved_release["source_commit"],
        "target": target,
        "version_id": version_id,
        "deployment_id": before["id"],
        "deployed_at": before["created_on"],
        "observed_at": now().isoformat(),
        "raw_receipt_sha256": raw_hash,
        "deployment_succeeded": True,
        "platform_signature_claimed": False,
        "live_traffic_percent": 100,
        "normal_origin": ORIGIN,
        "active_owner_sha256": initial_owner[2],
        **{key: approved_release[key] for key in ("build_input_sha256", "policy_sha256", "ci_run_id", "tag")},
    }
    return checked_normal_deployment(evidence["source_commit"], target, lambda: evidence)
