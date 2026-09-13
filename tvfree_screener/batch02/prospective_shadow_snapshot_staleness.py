from __future__ import annotations

import argparse
import json
from pathlib import Path


def evaluate_staleness(snapshot: dict, current_heads: dict[str, str]) -> dict:
    rows = snapshot.get("candidates", [])
    if not isinstance(rows, list):
        raise ValueError("snapshot.candidates must be a list")

    checked = []
    stale_count = 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("candidate row must be an object")
        candidate_id = str(row.get("candidate_id", "")).strip()
        branch = str(row.get("branch", "")).strip()
        observed = str(row.get("observed_head", "")).strip()
        if not candidate_id or not branch or not observed:
            raise ValueError("candidate_id, branch, and observed_head are required")
        current = str(current_heads.get(branch, "")).strip()
        missing_current = not current
        stale = missing_current or current != observed
        stale_count += int(stale)
        checked.append({
            "candidate_id": candidate_id,
            "branch": branch,
            "observed_head": observed,
            "current_head": current or None,
            "stale": stale,
            "reason": (
                "CURRENT_HEAD_UNAVAILABLE" if missing_current else
                "BRANCH_HEAD_ADVANCED" if stale else
                "HEAD_UNCHANGED"
            ),
            "prospective_shadow_start_allowed_from_this_snapshot": bool(
                row.get("ready_for_prospective_shadow", False)
            ) and not stale,
        })

    return {
        "scope": "READINESS_SNAPSHOT_STALENESS_ONLY",
        "opens_strategy_returns": False,
        "selection_or_threshold_tuning_allowed": False,
        "candidate_count": len(checked),
        "stale_count": stale_count,
        "fresh_count": len(checked) - stale_count,
        "decision": "REFRESH_STALE_READINESS" if stale_count else "SNAPSHOT_FRESH",
        "candidates": checked,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Invalidate prospective-shadow readiness snapshots after source branch heads change")
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--current-heads", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    result = evaluate_staleness(
        json.loads(args.snapshot.read_text(encoding="utf-8")),
        json.loads(args.current_heads.read_text(encoding="utf-8")),
    )
    raw = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(raw)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
