from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_CHECKS = (
    "representation_gate_passed",
    "supervised_evaluation_preregistered",
    "h1_policy_frozen",
    "model_freeze_manifest_valid",
    "model_spec_sha_pinned",
    "candidate_export_contract_satisfied",
    "causal_preflight_passed",
    "append_only_integrity_enabled",
    "production_isolation_confirmed",
    "historical_2026_tuning_forbidden",
)


def evaluate_start_readiness(payload: dict) -> dict:
    checks = {name: bool(payload.get(name, False)) for name in REQUIRED_CHECKS}
    missing = [name for name, ok in checks.items() if not ok]
    ready = not missing
    return {
        "ready_for_prospective_shadow": ready,
        "decision": "ALLOW_PROSPECTIVE_SHADOW_START" if ready else "BLOCK_PROSPECTIVE_SHADOW_START",
        "checks": checks,
        "missing_requirements": missing,
        "integrity": {
            "opens_strategy_returns": False,
            "changes_model": False,
            "changes_thresholds": False,
            "changes_ranking": False,
            "changes_cooldown": False,
            "changes_eligibility": False,
            "production_modified": False,
            "note": "This gate only authorizes evidence collection. It never promotes a model.",
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Outcome-free prospective-shadow start-readiness gate")
    ap.add_argument("--readiness-json", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    payload = json.loads(args.readiness_json.read_text(encoding="utf-8"))
    result = evaluate_start_readiness(payload)
    raw = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(raw)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
