from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping, Sequence


REQUIRED_SOURCE_BRANCHES = (
    "research/tvfree-canonical-batch02",
    "research/tentei-cloud-mtf",
    "research/consensus-atr-regime-gate",
)


def evaluate_authorization(payload: Mapping) -> dict:
    sources = list(payload.get("sources", []))
    by_branch = {str(x.get("branch", "")): x for x in sources if isinstance(x, Mapping)}

    missing_branches = [b for b in REQUIRED_SOURCE_BRANCHES if b not in by_branch]
    source_checks = {}
    blockers = []

    for branch in REQUIRED_SOURCE_BRANCHES:
        row = by_branch.get(branch)
        if row is None:
            source_checks[branch] = {"present": False}
            blockers.append(f"missing_source_branch:{branch}")
            continue

        readiness_ok = bool(row.get("readiness_ok", False))
        staleness_ok = bool(row.get("staleness_ok", False))
        ancestry_ok = bool(row.get("ancestry_ok", False))
        current_head = str(row.get("current_head", ""))
        observed_head = str(row.get("observed_head", ""))
        head_pinned = bool(current_head and observed_head and current_head == observed_head)

        source_checks[branch] = {
            "present": True,
            "readiness_ok": readiness_ok,
            "staleness_ok": staleness_ok,
            "ancestry_ok": ancestry_ok,
            "current_head": current_head,
            "observed_head": observed_head,
            "head_pinned": head_pinned,
        }
        if not readiness_ok:
            blockers.append(f"readiness_blocked:{branch}")
        if not staleness_ok:
            blockers.append(f"stale_snapshot:{branch}")
        if not ancestry_ok:
            blockers.append(f"ancestry_blocked:{branch}")
        if not head_pinned:
            blockers.append(f"head_not_pinned:{branch}")

    supervisor_contract_sha256 = str(payload.get("supervisor_contract_sha256", ""))
    expected_supervisor_contract_sha256 = str(payload.get("expected_supervisor_contract_sha256", ""))
    supervisor_contract_ok = bool(
        supervisor_contract_sha256
        and expected_supervisor_contract_sha256
        and supervisor_contract_sha256 == expected_supervisor_contract_sha256
    )
    if not supervisor_contract_ok:
        blockers.append("supervisor_contract_mismatch")

    all_heads_refetched_immediately_before_authorization = bool(
        payload.get("all_heads_refetched_immediately_before_authorization", False)
    )
    if not all_heads_refetched_immediately_before_authorization:
        blockers.append("source_heads_not_refetched_immediately_before_authorization")

    production_isolation_confirmed = bool(payload.get("production_isolation_confirmed", False))
    if not production_isolation_confirmed:
        blockers.append("production_isolation_not_confirmed")

    historical_2026_tuning_forbidden = bool(payload.get("historical_2026_tuning_forbidden", False))
    if not historical_2026_tuning_forbidden:
        blockers.append("historical_2026_tuning_not_forbidden")

    blockers = sorted(set(blockers))
    authorized = not blockers
    return {
        "authorized_for_prospective_shadow_start": authorized,
        "decision": "AUTHORIZE_PROSPECTIVE_SHADOW_START" if authorized else "BLOCK_PROSPECTIVE_SHADOW_START",
        "missing_source_branches": missing_branches,
        "source_checks": source_checks,
        "supervisor_contract_ok": supervisor_contract_ok,
        "all_heads_refetched_immediately_before_authorization": all_heads_refetched_immediately_before_authorization,
        "production_isolation_confirmed": production_isolation_confirmed,
        "historical_2026_tuning_forbidden": historical_2026_tuning_forbidden,
        "blockers": blockers,
        "integrity": {
            "uses_strategy_returns": False,
            "ranks_candidates": False,
            "changes_models": False,
            "changes_thresholds": False,
            "changes_cooldowns": False,
            "changes_eligibility": False,
            "production_modified": False,
            "note": "Authorization permits evidence collection only; it never promotes a model to production.",
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Final outcome-free authorization gate for prospective shadow start")
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    report = evaluate_authorization(payload)
    raw = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(raw)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
