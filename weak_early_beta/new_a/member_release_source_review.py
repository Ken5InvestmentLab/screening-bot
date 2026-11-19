"""Read-only review of the exact Git-tree delta for the member-only rollout."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from . import continuing_acceptance as acceptance


CONFIG = "weak-early-beta-gate/wrangler.jsonc"
ENTRY = "weak-early-beta-gate/src/index.ts"
MEMBER_BINDING = {
    "binding": "CLOUD_MEMBER_DB",
    "database_name": "tentei-cloud-member-view",
    "database_id": "72edf9bf-b033-463b-a053-ff259db17cb5",
    "remote": False,
    "migrations_dir": "member-migrations",
}


def git(repo, *args):
    return subprocess.check_output(["git", "--no-optional-locks", *args], cwd=repo)


def unique_replace(data, old, new):
    if data.count(old) != 1:
        raise ValueError("Accepted owner entrypoint contract differs")
    return data.replace(old, new)


def review_member_release_source(repo, baseline, candidate):
    """Review a proposed tree against the actual approved owner-only source."""
    repo = Path(repo).resolve()
    if not all(re.fullmatch(r"[a-f0-9]{40}", value) for value in (baseline, candidate)) or baseline == candidate:
        raise ValueError("Distinct full commits required for member source review")
    if git(repo, "merge-base", baseline, candidate).decode().strip() != baseline:
        raise ValueError("Member source is not a descendant of the accepted owner source")

    before = {name: git(repo, "show", f"{baseline}:{name}") for name in sorted(acceptance.AUTH_FILES)}
    after = {name: git(repo, "show", f"{candidate}:{name}") for name in sorted(acceptance.AUTH_FILES)}
    changed = [name for name in before if before[name] != after[name]]
    if changed != [ENTRY]:
        raise ValueError("Existing Discord or owner authorization code changed beyond the member fallback")
    expected = unique_replace(before[ENTRY], b"import { passiveObservationSink", (
        b"import {memberRouteCandidate} from './new-a-role-integration';\n"
        b"import { passiveObservationSink"
    ))
    expected = unique_replace(expected, b"    if (denied) return denied;", (
        b"    if (denied) return (await memberRouteCandidate(request, env, denied, operationalBuild)) ?? denied;"
    ))
    with_observer = unique_replace(expected, b"env, denied, operationalBuild))", b"env, denied, operationalBuild, ctx))")
    if after[ENTRY] not in (expected, with_observer):
        raise ValueError("Member fallback changes more than the existing owner-denial branch")

    common_config = json.loads(git(repo, "show", f"{baseline}:{CONFIG}"))
    candidate_config = json.loads(git(repo, "show", f"{candidate}:{CONFIG}"))
    mode = candidate_config["vars"].pop("CLOUD_MEMBER_VIEW_ENABLED", None)
    databases = candidate_config["d1_databases"]
    member = [database for database in databases if database.get("binding") == "CLOUD_MEMBER_DB"]
    if mode not in ("true", "false") or member != [MEMBER_BINDING]:
        raise ValueError("Member mode or dedicated production D1 binding differs")
    candidate_config["d1_databases"] = [database for database in databases if database not in member]
    if candidate_config != common_config:
        raise ValueError("Candidate changes an existing production or preview binding or setting")

    paths = [*sorted(acceptance.AUTH_FILES), CONFIG, "weak-early-beta-gate/src/new-a-member-release.ts",
             "weak-early-beta-gate/src/new-a-role-facade.ts", "weak-early-beta-gate/src/new-a-role-integration.ts",
             "weak-early-beta-gate/src/new-a-member-observation.ts",
             "weak-early-beta-gate/member-migrations/0003_new_a_member_response_observations.sql"]
    delta = git(repo, "diff", "--binary", baseline, candidate, "--", *paths)
    return {
        "schema": "NEW_A_MEMBER_RELEASE_SOURCE_REVIEW_V1",
        "accepted_owner_source": baseline,
        "candidate_source": candidate,
        "reviewed_diff_sha256": hashlib.sha256(delta).hexdigest(),
        "member_database_id": member[0]["database_id"],
        "member_support_configured": mode == "true",
        "owner_only_gate_preserved": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    print(json.dumps(review_member_release_source(Path.cwd(), args.baseline, args.candidate)))
