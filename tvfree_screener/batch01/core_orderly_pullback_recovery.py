"""Hash-locked report recovery for orderly-pullback attempt01.

The strategy and 2022H2-2023 labels were already exposed by attempt01. This
module only reconstructs the preregistered family gate from those exact,
persisted artifacts. It never changes or evaluates Top-N policies.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pandas as pd

from . import core_moderate_ridge_audit as shared
from . import core_orderly_pullback_audit as original
from .artifact_store import read_verified_parquet, sha256_file
from .core_orderly_pullback import FAMILY_SPEC, FAMILY_SPEC_SHA256
from .evaluation import cohort_summary, label_summary


BATCH_DIR = Path(__file__).resolve().parent
REPORT_DIR = BATCH_DIR / "reports"
CACHE_DIR = BATCH_DIR / ".cache"
ATTEMPT_ID = "CORE-ORDERLY-PULLBACK-20260913-02-REPORT-RECOVERY"
PARENT_STATUS_PATH = REPORT_DIR / "core_orderly_pullback_attempt01_status.json"
PARENT_FROZEN_PATH = REPORT_DIR / "core_orderly_pullback_frozen_spec.json"
FROZEN_PATH = REPORT_DIR / "core_orderly_pullback_attempt02_recovery_frozen.json"
REPORT_PATH = REPORT_DIR / "core_orderly_pullback_attempt02_recovery_report.json"
RECOVERY_FILES = (
    "core_orderly_pullback_recovery.py",
    "core_orderly_pullback_audit.py",
    "core_orderly_pullback.py",
    "core_moderate_ridge_audit.py",
    "artifact_store.py",
    "evaluation.py",
    "session_calendar.py",
    "selection.py",
)
ARTIFACT_FILES = {
    "candidate_pool": "core_orderly_pullback_discovery_candidate_pool.parquet",
    "ranked_pool": "core_orderly_pullback_discovery_ranked_pool.parquet",
    "outcome_labels": "core_orderly_pullback_discovery_labels.parquet",
}


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _code_hashes() -> dict[str, str]:
    return {name: sha256_file(BATCH_DIR / name) for name in RECOVERY_FILES}


def _load_parent() -> tuple[dict[str, object], dict[str, object]]:
    status = json.loads(PARENT_STATUS_PATH.read_text(encoding="utf-8"))
    parent = original.load_frozen_spec()
    if status.get("decision") != "IMPLEMENTATION_ABORT_NOT_A_MODEL_PERFORMANCE_DECISION":
        raise ValueError("attempt01 status is not the recorded implementation abort")
    if status.get("frozen_spec_sha256") != parent.get("spec_sha256"):
        raise ValueError("attempt01 status and frozen spec do not match")
    if status.get("frozen_runner_sha256") != parent["implementation_sha256"]["core_orderly_pullback_audit.py"]:
        raise ValueError("attempt01 status and frozen runner do not match")
    if "family gate therefore was not KEEP" not in str(status.get("control_flow_evidence", "")):
        raise ValueError("attempt01 trace does not establish the non-KEEP discovery branch")
    return status, parent


def freeze_recovery() -> dict[str, object]:
    """Freeze recovery code and expected input hashes before loading label values."""
    if FROZEN_PATH.exists():
        raise FileExistsError("attempt02 recovery spec already exists; do not overwrite it")
    status, parent = _load_parent()
    expected_artifacts = {
        key: {
            "path": str((CACHE_DIR / filename).relative_to(BATCH_DIR)),
            "sha256": status["artifacts"][key]["sha256"],
            "rows": int(status["artifacts"][key]["rows"]),
        }
        for key, filename in ARTIFACT_FILES.items()
    }
    payload = {
        "schema_version": 1,
        "attempt_id": ATTEMPT_ID,
        "parent_experiment_id": parent["experiment_id"],
        "parent_spec_sha256": parent["spec_sha256"],
        "parent_runner_sha256": parent["implementation_sha256"]["core_orderly_pullback_audit.py"],
        "family_spec_sha256": FAMILY_SPEC_SHA256,
        "source_sha256": parent["source_sha256"],
        "calendar_sha256": parent["calendar_sha256"],
        "recovery_implementation_sha256": _code_hashes(),
        "expected_parent_artifacts": expected_artifacts,
        "prior_discovery_outcomes_already_opened": True,
        "discovery_evidence_class": "RETROSPECTIVE_PROVISIONAL_ENGINEERING_REPLAY",
        "policy_outcomes_permitted": False,
        "later_periods_permitted": False,
    }
    receipt = {
        **payload,
        "spec_sha256": _canonical_hash(payload),
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "freeze_reads_label_values": False,
    }
    _write_json(FROZEN_PATH, receipt)
    return receipt


def _load_frozen_recovery() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    receipt = json.loads(FROZEN_PATH.read_text(encoding="utf-8"))
    payload = {key: value for key, value in receipt.items() if key not in {
        "spec_sha256", "frozen_at_utc", "freeze_reads_label_values",
    }}
    if receipt.get("spec_sha256") != _canonical_hash(payload):
        raise ValueError("attempt02 recovery spec hash is invalid")
    if receipt.get("recovery_implementation_sha256") != _code_hashes():
        raise ValueError("recovery implementation changed after freeze")
    status, parent = _load_parent()
    if receipt.get("parent_spec_sha256") != parent.get("spec_sha256"):
        raise ValueError("recovery receipt points to a different attempt01 spec")
    if receipt.get("parent_runner_sha256") != parent["implementation_sha256"]["core_orderly_pullback_audit.py"]:
        raise ValueError("recovery receipt points to a different attempt01 runner")
    if receipt.get("source_sha256") != shared._expected_source_hash():
        raise ValueError("preserved source hash changed")
    calendar = shared._calendar()
    if receipt.get("calendar_sha256") != calendar.sha256:
        raise ValueError("XTKS calendar hash changed")
    return receipt, status, parent


def _verify_artifacts(status: dict[str, object]) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for key, filename in ARTIFACT_FILES.items():
        frame, manifest = read_verified_parquet(CACHE_DIR / filename)
        expected = status["artifacts"][key]
        if len(frame) != int(expected["rows"]) or manifest.get("sha256") != expected["sha256"]:
            raise ValueError(f"{key} differs from the attempt01 status receipt")
        if manifest.get("spec_sha256") != status["frozen_spec_sha256"]:
            raise ValueError(f"{key} was created from a different strategy spec")
        if manifest.get("source_sha256") != shared._expected_source_hash():
            raise ValueError(f"{key} was created from a different preserved source")
        if manifest.get("calendar_sha256") != shared._calendar().sha256:
            raise ValueError(f"{key} was created from a different XTKS calendar")
        frames[key] = frame
    return frames


def _recovery_decision(family_decision: str) -> tuple[str, str]:
    """Fail closed against attempt01's persisted trace; never unlock policy evaluation."""
    if family_decision not in {"KEEP", "REJECT", "INCONCLUSIVE_INCOMPLETE_POOL_COHORT_COVERAGE"}:
        raise ValueError(f"unknown registered family decision: {family_decision}")
    if family_decision == "KEEP":
        return "RECOVERY_ABORT_PRIOR_TRACE_DISAGREEMENT", "NOT_EVALUATED_RECOVERY_FAIL_CLOSED"
    return family_decision, "NOT_EVALUATED_FAMILY_NOT_KEEP"


def recover_report() -> dict[str, object]:
    """Reconstruct only the frozen family gate from attempt01's exact artifacts."""
    frozen, status, parent = _load_frozen_recovery()
    frames = _verify_artifacts(status)
    pool = frames["candidate_pool"]
    ranked = frames["ranked_pool"]
    labels = frames["outcome_labels"]

    identity = ("date", "symbol")
    for name, frame in frames.items():
        if not set(identity).issubset(frame.columns) or frame.duplicated(list(identity)).any():
            raise ValueError(f"{name} has invalid candidate keys")
    pool_keys = pool.loc[:, list(identity)].copy()
    ranked_keys = ranked.loc[:, list(identity)].copy()
    label_keys = labels.loc[:, list(identity)].copy()
    for frame in (pool_keys, ranked_keys, label_keys):
        frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
        frame["symbol"] = frame["symbol"].astype("string")
    expected_keys = pool_keys.sort_values(list(identity), kind="mergesort").reset_index(drop=True)
    for name, keys in (("ranked_pool", ranked_keys), ("outcome_labels", label_keys)):
        actual = keys.sort_values(list(identity), kind="mergesort").reset_index(drop=True)
        if not expected_keys.equals(actual):
            raise ValueError(f"{name} key universe differs from the frozen candidate pool")
    if not labels["family"].astype("string").eq(str(FAMILY_SPEC["family"])).all():
        raise ValueError("outcome labels include a different family")
    if not labels["spec_hash"].astype("string").eq(str(parent["spec_sha256"])).all():
        raise ValueError("outcome labels include a different strategy spec")
    if not pool["spec_hash"].astype("string").eq(str(parent["spec_sha256"])).all():
        raise ValueError("candidate pool includes a different strategy spec")
    if not ranked["spec_hash"].astype("string").eq(str(parent["spec_sha256"])).all():
        raise ValueError("ranked pool includes a different strategy spec")

    calendar = shared._calendar()
    sessions = calendar.slice(shared.DISCOVERY_START, shared.DISCOVERY_END)
    pool_labels = pool_keys.merge(
        labels,
        on=list(identity),
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    if not pool_labels["_merge"].eq("both").all():
        raise ValueError("some frozen candidates do not have exactly one label row")
    pool_labels.drop(columns=["_merge"], inplace=True)

    signal_metrics = label_summary(pool_labels, costs=(0.0, 0.005, 0.01))
    pool_daily = shared._pool_daily(pool_labels, sessions)
    cohort_metrics = cohort_summary(pool_daily, repetitions=2000)
    family_decision, family_checks = original._family_gate(signal_metrics, cohort_metrics)
    decision, policy_decision = _recovery_decision(family_decision)

    daily_counts = pool.groupby("date", sort=True).size()
    coverage = {
        "complete_days": int(pool_daily["cohort_status"].eq("COMPLETE").sum()),
        "partial_unresolved_days": int(pool_daily["cohort_status"].eq("PARTIAL_UNRESOLVED").sum()),
        "abstain_days": int(pool_daily["cohort_status"].eq("ABSTAIN").sum()),
    }
    report = {
        "schema_version": 1,
        "attempt_id": ATTEMPT_ID,
        "parent_experiment_id": parent["experiment_id"],
        "family": FAMILY_SPEC["family"],
        "parent_spec_sha256": parent["spec_sha256"],
        "recovery_spec_sha256": frozen["spec_sha256"],
        "source_sha256": frozen["source_sha256"],
        "calendar_sha256": frozen["calendar_sha256"],
        "recovery_code_sha256": frozen["recovery_implementation_sha256"],
        "period": "2022H2-2023 discovery family-gate recovery",
        "evidence_level": "RETROSPECTIVE_PROVISIONAL_ENGINEERING_REPLAY",
        "prior_discovery_outcomes_already_opened": True,
        "input_artifacts": {
            key: {
                "path": value["path"],
                "rows": value["rows"],
                "sha256": value["sha256"],
            }
            for key, value in frozen["expected_parent_artifacts"].items()
        },
        "candidate_pool_rows": int(len(pool)),
        "candidate_pool_unique_symbols": int(pool["symbol"].nunique()),
        "candidate_pool_active_dates": int(pool["date"].nunique()),
        "candidate_pool_max_names_per_day": int(daily_counts.max()),
        "candidate_pool_mean_names_per_active_day": float(daily_counts.mean()),
        "candidate_pool_signal_metrics": signal_metrics,
        "candidate_pool_complete_daily_cohorts": cohort_metrics,
        "candidate_pool_daily_coverage": coverage,
        "family_gate_checks": family_checks,
        "family_decision": family_decision,
        "selection_policy_decision": policy_decision,
        "selection_policy_reports": [],
        "selection_policy_metrics_opened_by_recovery": False,
        "2024_2025_2026_opened": False,
        "prior_attempt_trace": status["control_flow_evidence"],
        "policy_permission": "No Top-N outcomes may be evaluated from this recovery. A KEEP result would contradict the prior trace and fail closed.",
        "production_boundary": "Research-only Python CLI; no production runtime, Codex, LLM, or external model is called.",
        "decision": decision,
        "execution_cost_note": "0.5% round-trip is a sensitivity assumption, not observed slippage, commissions, tax, or fill quality.",
    }
    _write_json(REPORT_PATH, report)
    return report


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("freeze", "audit"))
    phase = parser.parse_args().phase
    if phase == "freeze":
        receipt = freeze_recovery()
        print(json.dumps({
            "attempt_id": ATTEMPT_ID,
            "recovery_spec_sha256": receipt["spec_sha256"],
            "frozen_at_utc": receipt["frozen_at_utc"],
            "outcomes_previously_opened": receipt["prior_discovery_outcomes_already_opened"],
        }, indent=2, ensure_ascii=False))
        return
    report = recover_report()
    print(json.dumps({
        "attempt_id": report["attempt_id"],
        "family_decision": report["family_decision"],
        "decision": report["decision"],
        "candidate_pool_rows": report["candidate_pool_rows"],
        "selection_policy_decision": report["selection_policy_decision"],
        "2024_2025_2026_opened": report["2024_2025_2026_opened"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()