from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from tvfree_screener.batch02.prospective_shadow_start_readiness import evaluate_start_readiness


FORBIDDEN_EVIDENCE_FIELDS = {
    "ret5bd_gross",
    "ret5bd_net",
    "net_mean",
    "net_median",
    "win_rate",
    "gross_ge10_rate",
    "gross_ge20_rate",
    "top3_removed_net_mean",
}


def _forbidden_keys(payload: dict) -> list[str]:
    found = []
    for key in payload:
        if str(key) in FORBIDDEN_EVIDENCE_FIELDS:
            found.append(str(key))
    return sorted(found)


def build_snapshot(candidates: list[dict]) -> dict:
    rows = []
    seen = set()
    for item in candidates:
        candidate_id = str(item.get("candidate_id", "")).strip()
        lane = str(item.get("lane", "")).strip()
        if not candidate_id:
            raise ValueError("candidate_id is required")
        if candidate_id in seen:
            raise ValueError(f"duplicate candidate_id: {candidate_id}")
        seen.add(candidate_id)
        if not lane:
            raise ValueError(f"{candidate_id}: lane is required")

        forbidden = _forbidden_keys(item)
        readiness_payload = dict(item.get("readiness", {}))
        forbidden += [f"readiness.{k}" for k in _forbidden_keys(readiness_payload)]
        if forbidden:
            raise ValueError(f"{candidate_id}: return/performance fields forbidden in readiness snapshot: {sorted(forbidden)}")

        gate = evaluate_start_readiness(readiness_payload)
        rows.append({
            "candidate_id": candidate_id,
            "lane": lane,
            "source_branch": str(item.get("source_branch", "")),
            "source_commit": str(item.get("source_commit", "")),
            "ready_for_prospective_shadow": gate["ready_for_prospective_shadow"],
            "decision": gate["decision"],
            "missing_requirements": gate["missing_requirements"],
        })

    decision_counts = Counter(r["decision"] for r in rows)
    lane_counts = Counter(r["lane"] for r in rows)
    ready = [r["candidate_id"] for r in rows if r["ready_for_prospective_shadow"]]
    blocked = [r["candidate_id"] for r in rows if not r["ready_for_prospective_shadow"]]
    return {
        "scope": "SUPERVISOR_OUTCOME_FREE_SHADOW_READINESS",
        "candidate_count": len(rows),
        "ready_candidate_ids": ready,
        "blocked_candidate_ids": blocked,
        "decision_counts": dict(sorted(decision_counts.items())),
        "lane_counts": dict(sorted(lane_counts.items())),
        "candidates": rows,
        "integrity": {
            "uses_return_values": False,
            "uses_performance_metrics": False,
            "ranks_candidates": False,
            "selects_best_candidate": False,
            "authorizes_production": False,
            "note": "This snapshot only reports whether frozen prerequisites for prospective evidence collection are complete.",
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Build an outcome-free supervisor snapshot for prospective-shadow readiness")
    ap.add_argument("--inventory-json", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    payload = json.loads(args.inventory_json.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("inventory must be a JSON array")
    out = build_snapshot(payload)
    raw = json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(raw + "\n", encoding="utf-8")
    print(raw)


if __name__ == "__main__":
    main()
