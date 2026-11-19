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
PRESENTATION = "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-presentation.js"
INITIAL_REVIEW_SCHEMA = "NEW_A_MEMBER_RELEASE_SOURCE_REVIEW_V1"
PRESENTATION_REVIEW_SCHEMA = "NEW_A_MEMBER_PRESENTATION_SUCCESSOR_SOURCE_REVIEW_V1"
COMPLETED_TIMING_REVIEW_SCHEMA = "NEW_A_MEMBER_COMPLETED_TIMING_SUCCESSOR_SOURCE_REVIEW_V1"
FUNDAMENTAL_REVIEW_SCHEMA = "NEW_A_MEMBER_FUNDAMENTAL_SUCCESSOR_SOURCE_REVIEW_V1"
_PURCHASE_LABEL = '<a class="member-purchase" href="/purchase">Premiumのアクセス権を購入する</a>'.encode()
_NEW_PURCHASE_LABEL = '<a class="member-purchase" href="/purchase">Premiumアクセス権を購入する</a>'.encode()
_SUCCESSOR_REVIEW_PATHS = frozenset({
    "weak_early_beta/new_a/member_release_source_review.py",
    "weak_early_beta/new_a/member_ordinary_acceptance.py",
    "tests/test_new_a_member_release_source_review.py",
    "tests/test_new_a_member_ordinary_acceptance.py",
})
_PRESENTATION_SUCCESSOR_PATHS = _SUCCESSOR_REVIEW_PATHS | {PRESENTATION}
_COMPLETED_TIMING_DELTAS = {
    "weak-early-beta-gate/scripts/prepare-new-a-member-projection.cjs": (
        (b"date <= terminal && terminal < asOf", b"date <= terminal && terminal <= asOf"),
        (b"terminal < closed && closed < asOf", b"terminal < closed && closed <= asOf"),
    ),
    "weak-early-beta-gate/src/new-a-member-projection.ts": (
        (b"row.completed_on >= row.date && row.completed_on < through",
         b"row.completed_on >= row.date && row.completed_on <= through"),
    ),
    "weak_early_beta/new_a/member_publisher.py": (
        (b'row["date"] <= row["completed_on"] < as_of', b'row["date"] <= row["completed_on"] <= as_of'),
    ),
}
_TIMING_GUIDE = "weak-early-beta-gate/AGENTS.md"
_TIMING_GUIDE_DELTA = (
    b"Build and paginate that view on the server from verified prior-session monitoring closures and settled virtual "
    b"positions. The current session's activity and active monitoring are Premium only, including their API and pagination metadata.",
    b"Build and paginate that view on the server from verified monitoring closures and settled virtual positions "
    b"completed on or before the latest published session. The current session's action cards and active "
    b"monitoring are Premium only, including their API and pagination metadata.",
)
_MEMBER_DASHBOARD_PATHS = {
    PRESENTATION,
    "weak-early-beta-gate/scripts/build-new-a-member-frame.mjs",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-loader.js",
    "tests/new_a_role_presentation_candidate.test.cjs",
}
_TIMING_SUCCESSOR_PATHS = _SUCCESSOR_REVIEW_PATHS | set(_COMPLETED_TIMING_DELTAS) | _MEMBER_DASHBOARD_PATHS | {
    _TIMING_GUIDE,
    "tests/new_a_member_projection_preparation.test.cjs",
    "tests/new_a_member_projection.test.cjs",
    "tests/test_new_a_member_publisher.py",
}
_FUNDAMENTAL_BASELINE = "161016a13ca09c310fd8d24687743ad90831a8a9"
_FUNDAMENTAL_MIGRATION = "weak-early-beta-gate/member-migrations/0005_new_a_member_fundamental_reports.sql"
_FUNDAMENTAL_PRODUCT_PATHS = frozenset({
    _FUNDAMENTAL_MIGRATION,
    PRESENTATION,
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-loader.js",
    "weak-early-beta-gate/scripts/prepare-new-a-member-projection.cjs",
    "weak-early-beta-gate/src/new-a-member-projection.ts",
    "weak-early-beta-gate/src/new-a-member-services.ts",
    "weak-early-beta-gate/src/new-a-role-facade.ts",
    "weak_early_beta/new_a/fundamentals.py",
    "weak_early_beta/new_a/member_publisher.py",
    "tests/new_a_member_consistency.test.cjs",
    "tests/new_a_member_projection_preparation.test.cjs",
    "tests/new_a_member_worker.test.cjs",
    "tests/new_a_role_presentation_candidate.test.cjs",
    "tests/test_new_a_fundamentals.py",
    "tests/test_new_a_member_publisher.py",
})
# Exact product blobs reviewed from 94d7474 (server), 23dc91c (daily) and ea85b3a (UI).
# Include the full migration bytes; earlier member migrations may not change.
_FUNDAMENTAL_PRODUCT_SHA256 = "0fa5bc7d4f39a024b0031fdb0613d4630c7082d60f718ec82e8b1a2a94cd2800"
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


def _successor_paths(repo, baseline, candidate, *, allowed_addition=None):
    raw = git(repo, "diff", "--raw", "--no-abbrev", "--no-renames", "-z", baseline, candidate, "--")
    records = raw.split(b"\0")[:-1]
    paths = set()
    for metadata, path in zip(records[::2], records[1::2], strict=True):
        name = path.decode("utf-8")
        fields = metadata.split()
        if len(fields) != 5:
            raise ValueError("Member successor changes an existing file mode or inventory")
        regular_edit = fields[:2] == [b":100644", b"100644"] and fields[-1] == b"M"
        approved_addition = (name == allowed_addition and fields[:2] == [b":000000", b"100644"]
                             and fields[2] == b"0" * 40 and fields[-1] == b"A")
        if not regular_edit and not approved_addition:
            raise ValueError("Member successor changes an existing file mode or inventory")
        paths.add(name)
    return paths


def _check_presentation_successor(repo, baseline, candidate, paths):
    if not paths <= _PRESENTATION_SUCCESSOR_PATHS:
        raise ValueError("Presentation successor changes paths outside the purchase-label scope")

    former = git(repo, "show", f"{baseline}:{PRESENTATION}")
    proposed = git(repo, "show", f"{candidate}:{PRESENTATION}")
    if former.count(_PURCHASE_LABEL) != 1 or proposed != former.replace(_PURCHASE_LABEL, _NEW_PURCHASE_LABEL):
        raise ValueError("Presentation successor changes more than the approved purchase label")


def _check_completed_timing_successor(repo, baseline, candidate, paths):
    if not _COMPLETED_TIMING_DELTAS.keys() <= paths or not paths <= _TIMING_SUCCESSOR_PATHS:
        raise ValueError("Completed-history successor differs from the approved source scope")
    if git(repo, "show", f"{baseline}:{PRESENTATION}").count(_NEW_PURCHASE_LABEL) != 1:
        raise ValueError("Completed-history successor requires the approved member purchase label")
    if PRESENTATION in paths and git(repo, "show", f"{candidate}:{PRESENTATION}").count(_NEW_PURCHASE_LABEL) != 1:
        raise ValueError("Member dashboard changes the approved purchase link or label")
    deltas = dict(_COMPLETED_TIMING_DELTAS)
    if _TIMING_GUIDE in paths:
        deltas[_TIMING_GUIDE] = (_TIMING_GUIDE_DELTA,)
    for path, replacements in deltas.items():
        expected = git(repo, "show", f"{baseline}:{path}")
        for former, inclusive in replacements:
            if expected.count(former) != 1:
                raise ValueError("Approved completed-history cutoff contract differs")
            expected = expected.replace(former, inclusive)
        if git(repo, "show", f"{candidate}:{path}") != expected:
            raise ValueError("Completed-history successor changes more than the inclusive cutoff")


def _check_fundamental_successor(repo, candidate, paths):
    if paths != _FUNDAMENTAL_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS:
        raise ValueError("Fundamental successor differs from the exact reviewed source scope")
    checked = hashlib.sha256()
    for path in sorted(_FUNDAMENTAL_PRODUCT_PATHS):
        checked.update(path.encode() + b"\0")
        checked.update(hashlib.sha256(git(repo, "show", f"{candidate}:{path}")).digest())
    if checked.hexdigest() != _FUNDAMENTAL_PRODUCT_SHA256:
        raise ValueError("Fundamental successor differs from the reviewed product or migration bytes")


def _member_successor(repo, baseline, candidate):
    if baseline == _FUNDAMENTAL_BASELINE:
        paths = _successor_paths(repo, baseline, candidate, allowed_addition=_FUNDAMENTAL_MIGRATION)
        _check_fundamental_successor(repo, candidate, paths)
        schema = FUNDAMENTAL_REVIEW_SCHEMA
    else:
        paths = _successor_paths(repo, baseline, candidate)
        if PRESENTATION in paths and not _COMPLETED_TIMING_DELTAS.keys() & paths:
            _check_presentation_successor(repo, baseline, candidate, paths)
            schema = PRESENTATION_REVIEW_SCHEMA
        else:
            _check_completed_timing_successor(repo, baseline, candidate, paths)
            schema = COMPLETED_TIMING_REVIEW_SCHEMA
    # Keep the full-index diff format of the already-issued presentation approval.
    delta = git(repo, "diff", "--binary", "--full-index", "--no-renames", "--no-ext-diff", "--no-textconv",
                "--no-color", "--src-prefix=a/", "--dst-prefix=b/", "--unified=3", "--diff-algorithm=myers",
                "--no-indent-heuristic", baseline, candidate, "--")
    return {
        "schema": schema,
        "accepted_owner_source": baseline,
        "candidate_source": candidate,
        "reviewed_diff_sha256": hashlib.sha256(delta).hexdigest(),
        "member_database_id": MEMBER_BINDING["database_id"],
        "member_support_configured": True,
        "owner_only_gate_preserved": True,
    }


def review_member_release_source(repo, baseline, candidate):
    """Review initial member support or one exact successor."""
    repo = Path(repo).resolve()
    if not all(re.fullmatch(r"[a-f0-9]{40}", value) for value in (baseline, candidate)) or baseline == candidate:
        raise ValueError("Distinct full commits required for member source review")
    if git(repo, "merge-base", baseline, candidate).decode().strip() != baseline:
        raise ValueError("Member source is not a descendant of the accepted owner source")

    before = {name: git(repo, "show", f"{baseline}:{name}") for name in sorted(acceptance.AUTH_FILES)}
    after = {name: git(repo, "show", f"{candidate}:{name}") for name in sorted(acceptance.AUTH_FILES)}
    changed = [name for name in before if before[name] != after[name]]
    baseline_config_bytes = git(repo, "show", f"{baseline}:{CONFIG}")
    candidate_config_bytes = git(repo, "show", f"{candidate}:{CONFIG}")
    common_config = json.loads(baseline_config_bytes)
    prior_members = [db for db in common_config["d1_databases"] if db.get("binding") == "CLOUD_MEMBER_DB"]
    if prior_members or "CLOUD_MEMBER_VIEW_ENABLED" in common_config["vars"]:
        if changed:
            raise ValueError("Member successor changes existing Discord or owner authorization source")
        if (baseline_config_bytes != candidate_config_bytes or common_config.get("name") != acceptance.SERVICE
                or common_config["vars"].get("CLOUD_MEMBER_VIEW_ENABLED") != "true" or prior_members != [MEMBER_BINDING]):
            raise ValueError("Member successor changes the approved Worker configuration or member D1")
        return _member_successor(repo, baseline, candidate)

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
    purchase_anchor = (
        b"    const denied = await ownerOnlyGate(request, env);\n"
        b"    if (denied) return (await memberRouteCandidate(request, env, denied, operationalBuild, ctx)) ?? denied;\n"
        b"    const pathname = new URL(request.url).pathname;"
    )
    variants = [expected, with_observer]
    if with_observer.count(purchase_anchor) == 1:
        variants.append(unique_replace(with_observer, purchase_anchor, (
            b"    const pathname = new URL(request.url).pathname;\n"
            b"    if (env.CLOUD_MEMBER_VIEW_ENABLED === 'true' && pathname === '/purchase' && ['GET', 'HEAD'].includes(request.method)) return sharedGate.fetch(request, env);\n"
            b"    const denied = await ownerOnlyGate(request, env);\n"
            b"    if (denied) return (await memberRouteCandidate(request, env, denied, operationalBuild, ctx)) ?? denied;"
        )))
    if after[ENTRY] not in variants:
        raise ValueError("Member fallback changes more than the existing owner-denial branch")

    candidate_config = json.loads(candidate_config_bytes)
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
             "weak-early-beta-gate/src/new-a-member-services.ts", "weak-early-beta-gate/src/new-a-member-projection.ts",
             "weak-early-beta-gate/scripts/prepare-new-a-member-projection.cjs", "weak_early_beta/new_a/member_publisher.py",
             "weak-early-beta-gate/src/new-a-member-observation.ts",
             "weak-early-beta-gate/member-migrations/0003_new_a_member_response_observations.sql",
             "weak-early-beta-gate/member-migrations/0004_new_a_member_access_tiers.sql"]
    delta = git(repo, "diff", "--binary", baseline, candidate, "--", *paths)
    return {
        "schema": INITIAL_REVIEW_SCHEMA,
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
