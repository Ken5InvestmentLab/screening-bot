from __future__ import annotations

import argparse
import json
from pathlib import Path


VALID_RELATIONS = {"IDENTICAL", "AHEAD", "BEHIND", "DIVERGED", "UNKNOWN"}


def classify_relation(compare_status: str | None, ahead_by: int | None = None, behind_by: int | None = None) -> str:
    status = str(compare_status or "").lower()
    if status == "identical":
        return "IDENTICAL"
    if status == "ahead":
        return "AHEAD"
    if status == "behind":
        return "BEHIND"
    if status == "diverged":
        return "DIVERGED"
    if ahead_by == 0 and behind_by == 0:
        return "IDENTICAL"
    if isinstance(ahead_by, int) and isinstance(behind_by, int):
        if ahead_by > 0 and behind_by == 0:
            return "AHEAD"
        if behind_by > 0 and ahead_by == 0:
            return "BEHIND"
        if ahead_by > 0 and behind_by > 0:
            return "DIVERGED"
    return "UNKNOWN"


def evaluate_branch_ancestry(snapshot: dict, current: dict) -> dict:
    snap_branch = str(snapshot.get("branch", ""))
    cur_branch = str(current.get("branch", ""))
    snap_sha = str(snapshot.get("observed_head", ""))
    cur_sha = str(current.get("current_head", ""))
    relation = classify_relation(
        current.get("compare_status"),
        current.get("ahead_by"),
        current.get("behind_by"),
    )

    errors: list[str] = []
    if not snap_branch or not cur_branch or snap_branch != cur_branch:
        errors.append("BRANCH_IDENTITY_MISMATCH")
    if not snap_sha or not cur_sha:
        errors.append("MISSING_HEAD_SHA")
    if relation == "BEHIND":
        errors.append("BRANCH_REWIND_DETECTED")
    elif relation == "DIVERGED":
        errors.append("BRANCH_HISTORY_DIVERGED")
    elif relation == "UNKNOWN":
        errors.append("ANCESTRY_UNVERIFIED")

    unchanged = relation == "IDENTICAL" and snap_sha == cur_sha
    fast_forward_only = relation in {"IDENTICAL", "AHEAD"} and not errors
    readiness_snapshot_still_current = unchanged

    if not fast_forward_only:
        decision = "BLOCK_AND_RECONCILE_BRANCH_HISTORY"
    elif not unchanged:
        decision = "REFRESH_READINESS_AFTER_FAST_FORWARD"
    else:
        decision = "ALLOW_EXISTING_READINESS_SNAPSHOT"

    return {
        "branch": snap_branch or cur_branch,
        "snapshot_head": snap_sha,
        "current_head": cur_sha,
        "relation": relation,
        "fast_forward_only": fast_forward_only,
        "readiness_snapshot_still_current": readiness_snapshot_still_current,
        "decision": decision,
        "errors": errors,
        "integrity": {
            "opens_strategy_returns": False,
            "changes_model": False,
            "changes_thresholds": False,
            "changes_ranking": False,
            "changes_cooldown": False,
            "changes_eligibility": False,
            "production_modified": False,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Classify branch ancestry before prospective-shadow authorization")
    ap.add_argument("--snapshot-json", type=Path, required=True)
    ap.add_argument("--current-json", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    snapshot = json.loads(args.snapshot_json.read_text(encoding="utf-8"))
    current = json.loads(args.current_json.read_text(encoding="utf-8"))
    result = evaluate_branch_ancestry(snapshot, current)
    raw = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(raw)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw + "\n", encoding="utf-8")
    if result["decision"] == "BLOCK_AND_RECONCILE_BRANCH_HISTORY":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
