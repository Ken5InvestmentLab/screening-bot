"""Frozen audit runner for the registered Core-3 orderly pullback family."""
from __future__ import annotations

from datetime import datetime, timezone
import gc
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import core_moderate_ridge_audit as shared
from .artifact_store import (
    read_verified_parquet_columns,
    sha256_file,
    write_parquet_artifact,
)
from .core_orderly_pullback import (
    FAMILY_SPEC,
    FAMILY_SPEC_SHA256,
    build_candidate_pool,
    rank_orderly_pool,
)
from .evaluation import cohort_summary, label_summary, return_metrics
from .selection import PolicySpec, apply_selection_policy
from .temporal_policy import validate_period_access


BATCH_DIR = Path(__file__).resolve().parent
REPORT_DIR = BATCH_DIR / "reports"
FROZEN_PATH = REPORT_DIR / "core_orderly_pullback_frozen_spec.json"
DISCOVERY_PATH = REPORT_DIR / "core_orderly_pullback_discovery.json"
POLICY_LOCK_PATH = REPORT_DIR / "core_orderly_pullback_policy_lock.json"
VALIDATION_PATH = REPORT_DIR / "core_orderly_pullback_validation_2024.json"
REPLAY_PATH = REPORT_DIR / "core_orderly_pullback_replay_2025.json"
REPORT_2026_PATH = REPORT_DIR / "core_orderly_pullback_report_2026.json"
ASSUMED_COST = 0.005
TOP_N_VALUES = (1, 2, 3, 5)
PRICE_COLUMNS = ("date", "symbol", "open", "high", "low", "close", "volume")
PANEL_COLUMNS = (
    "date", "symbol", "open", "high", "low", "close", "volume",
    "ret1", "ret5", "ret20", "volume_trend5_20",
)
IMPLEMENTATION_FILES = (
    "core_orderly_pullback.py",
    "core_orderly_pullback_audit.py",
    "core_moderate_ridge_audit.py",
    "core_moderate_ridge.py",
    "feature_panel.py",
    "selection.py",
    "evaluation.py",
    "session_calendar.py",
    "temporal_policy.py",
    "artifact_store.py",
    "test_core_orderly_pullback.py",
)


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def _implementation_hashes() -> dict[str, str]:
    return {name: sha256_file(BATCH_DIR / name) for name in IMPLEMENTATION_FILES}


def _identity_payload(calendar_sha256: str, source_sha256: str, code_hashes: dict[str, str]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "experiment_id": FAMILY_SPEC["experiment_id"],
        "family_spec": FAMILY_SPEC,
        "family_spec_sha256": FAMILY_SPEC_SHA256,
        "source_sha256": source_sha256,
        "calendar_sha256": calendar_sha256,
        "implementation_sha256": code_hashes,
    }


def freeze_spec() -> dict[str, object]:
    """Freeze the complete strategy/data/code identity without reading outcomes."""
    if FROZEN_PATH.exists():
        raise FileExistsError("orderly-pullback spec is already frozen")
    calendar = shared._calendar()
    source_hash = shared._expected_source_hash()
    code_hashes = _implementation_hashes()
    payload = _identity_payload(calendar.sha256, source_hash, code_hashes)
    receipt = {
        **payload,
        "spec_sha256": _canonical_hash(payload),
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "evidence_level": "RETROSPECTIVE_PROVISIONAL",
        "outcome_data_opened_by_freeze": False,
    }
    _write_json(FROZEN_PATH, receipt)
    return receipt


def load_frozen_spec() -> dict[str, object]:
    receipt = json.loads(FROZEN_PATH.read_text(encoding="utf-8"))
    payload = {key: receipt[key] for key in (
        "schema_version", "experiment_id", "family_spec", "family_spec_sha256",
        "source_sha256", "calendar_sha256", "implementation_sha256",
    )}
    if receipt.get("spec_sha256") != _canonical_hash(payload):
        raise ValueError("frozen orderly-pullback spec hash is invalid")
    if receipt.get("family_spec_sha256") != FAMILY_SPEC_SHA256:
        raise ValueError("registered orderly-pullback strategy changed after freeze")
    if receipt.get("implementation_sha256") != _implementation_hashes():
        raise ValueError("orderly-pullback implementation changed after freeze")
    if receipt.get("source_sha256") != shared._expected_source_hash():
        raise ValueError("preserved daily source changed after freeze")
    calendar = shared._calendar()
    if receipt.get("calendar_sha256") != calendar.sha256:
        raise ValueError("XTKS session calendar changed after freeze")
    return receipt


def _period(period: str) -> tuple[pd.Timestamp, pd.Timestamp, Path, str]:
    if period == "discovery":
        return shared.DISCOVERY_START, shared.DISCOVERY_END, DISCOVERY_PATH, "select_policy"
    if period == "validation-2024":
        return pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31"), VALIDATION_PATH, "locked_validation"
    if period == "replay-2025":
        return pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31"), REPLAY_PATH, "replay_2025"
    if period == "report-2026":
        return pd.Timestamp("2026-01-01"), pd.Timestamp("2026-12-31"), REPORT_2026_PATH, "report_2026"
    raise ValueError(f"unsupported orderly-pullback period {period}")


def _locked_top_n(spec: dict[str, object], period: str) -> tuple[int, dict[str, object] | None]:
    if period == "discovery":
        return 0, None
    if not POLICY_LOCK_PATH.exists():
        raise ValueError("later period is locked until discovery passes and freezes one Top-N")
    policy_lock = json.loads(POLICY_LOCK_PATH.read_text(encoding="utf-8"))
    if policy_lock.get("spec_sha256") != spec["spec_sha256"]:
        raise ValueError("policy lock does not match the frozen family spec")
    if policy_lock.get("decision") != "PROMOTE_TO_2024_CONFIRMATION":
        raise ValueError("policy lock is not a discovery-passing confirmation lock")
    if int(policy_lock.get("top_n", 0)) not in TOP_N_VALUES:
        raise ValueError("policy lock contains an unregistered Top-N")
    required_status = {
        "validation-2024": (None, "PROMOTE_TO_2025_LOCKED_REPLAY"),
        "replay-2025": ("CONFIRMATION_PASS", "PROMOTE_TO_2025_LOCKED_REPLAY"),
        "report-2026": ("CONFIRMATION_PASS", "PROMOTE_TO_2025_LOCKED_REPLAY"),
    }[period]
    if required_status[0] is not None:
        validation = json.loads(VALIDATION_PATH.read_text(encoding="utf-8"))
        if validation.get("decision") != required_status[0]:
            raise ValueError("2025/2026 access requires unchanged 2024 confirmation pass")
    if period == "report-2026":
        replay = json.loads(REPLAY_PATH.read_text(encoding="utf-8"))
        if replay.get("decision") != "LOCKED_2025_REPLAY_RECORDED":
            raise ValueError("2026 report requires the frozen 2025 replay to be recorded")
    return int(policy_lock["top_n"]), policy_lock


def _load_panel_through(last_session: pd.Timestamp, calendar) -> tuple[pd.DataFrame, dict[str, object], Path]:
    panel_path = shared._feature_panel_path(last_session)
    if not panel_path.exists():
        generated = shared._feature_panel(last_session, calendar)
        del generated
        gc.collect()
    panel, receipt = read_verified_parquet_columns(panel_path, list(PANEL_COLUMNS))
    if (
        receipt.get("source_sha256") != shared._expected_source_hash()
        or receipt.get("calendar_sha256") != calendar.sha256
        or receipt.get("through") != last_session.date().isoformat()
        or receipt.get("labels_included") is not False
    ):
        raise ValueError("decision-only feature panel differs from the frozen data identity")
    return panel, receipt, panel_path


def _save_decision_artifacts(
    *, period: str, spec: dict[str, object], panel_receipt: dict[str, object],
    pool: pd.DataFrame, ranked: pd.DataFrame, sessions: pd.DatetimeIndex, top_n_values: tuple[int, ...],
) -> tuple[dict[str, object], dict[int, pd.DataFrame]]:
    metadata = {
        "experiment_id": FAMILY_SPEC["experiment_id"],
        "spec_sha256": spec["spec_sha256"],
        "source_sha256": spec["source_sha256"],
        "calendar_sha256": spec["calendar_sha256"],
        "feature_panel_sha256": panel_receipt["sha256"],
        "period": period,
        "future_columns_included": False,
    }
    pool_path = BATCH_DIR / ".cache" / f"core_orderly_pullback_{period}_candidate_pool.parquet"
    pool_receipt = write_parquet_artifact(
        pool.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True),
        pool_path,
        metadata={**metadata, "ranking_fields_included": False},
    )
    ranked_path = BATCH_DIR / ".cache" / f"core_orderly_pullback_{period}_ranked_pool.parquet"
    ranked_receipt = write_parquet_artifact(
        ranked.sort_values(["date", "raw_rank"], kind="mergesort").reset_index(drop=True),
        ranked_path,
        metadata={**metadata, "ranking_fields_included": True},
    )
    selected_by_n: dict[int, pd.DataFrame] = {}
    selected_hashes: dict[str, str] = {}
    selection_hashes: dict[str, str] = {}
    policy_hashes: dict[str, str] = {}
    for top_n in top_n_values:
        policy = PolicySpec("core", top_n, f"{FAMILY_SPEC['family']}-top{top_n}")
        selection = apply_selection_policy(ranked, sessions=sessions, policy=policy)
        selected_by_n[top_n] = selection.selected
        path = BATCH_DIR / ".cache" / f"core_orderly_pullback_{period}_selected_top{top_n}.parquet"
        receipt = write_parquet_artifact(
            selection.selected.sort_values(["date", "policy_rank"], kind="mergesort").reset_index(drop=True),
            path,
            metadata={
                **metadata,
                "top_n": top_n,
                "policy_sha256": selection.policy_sha256,
                "selection_sha256": selection.selection_sha256,
                "future_columns_included": False,
            },
        )
        selected_hashes[str(top_n)] = str(receipt["sha256"])
        selection_hashes[str(top_n)] = selection.selection_sha256
        policy_hashes[str(top_n)] = selection.policy_sha256
    return {
        "candidate_pool_sha256": pool_receipt["sha256"],
        "ranked_pool_sha256": ranked_receipt["sha256"],
        "selected_policy_sha256_by_top_n": selected_hashes,
        "selection_sha256_by_top_n": selection_hashes,
        "policy_sha256_by_top_n": policy_hashes,
    }, selected_by_n


def _rank_band_metrics(ranked: pd.DataFrame, labels: pd.DataFrame) -> dict[str, object]:
    joined = ranked.loc[:, ["date", "symbol", "raw_rank"]].merge(
        labels.loc[:, ["date", "symbol", "gross_return", "label_status", "label_resolved"]],
        on=["date", "symbol"], how="left", validate="one_to_one",
    )
    joined["rank_band"] = np.where(joined["raw_rank"].le(5), joined["raw_rank"].astype(str), "6+")
    output: dict[str, object] = {}
    for band in ("1", "2", "3", "4", "5", "6+"):
        group = joined.loc[joined["rank_band"].eq(band)].copy()
        if group.empty:
            output[band] = {"selected_count": 0, "metrics": None}
            continue
        metrics = label_summary(group, costs=(0.0, 0.005, 0.01))
        output[band] = {"selected_count": int(len(group)), "metrics": metrics}
    return output


def _family_gate(signal: dict[str, object], cohort: dict[str, object]) -> tuple[str, dict[str, object]]:
    net_signal = signal["round_trip_cost_scenarios"]["0.005"]
    checks = {
        "pool_signal_mean_positive": net_signal.get("mean") is not None and net_signal["mean"] > 0,
        "pool_signal_median_positive": net_signal.get("median") is not None and net_signal["median"] > 0,
        "pool_signal_mean_ex_top3_positive": net_signal.get("mean_excluding_top3_winners") is not None and net_signal["mean_excluding_top3_winners"] > 0,
        "pool_complete_cohort_mean_positive": cohort.get("mean") is not None and cohort["mean"] > 0,
        "pool_complete_cohort_median_positive": cohort.get("median") is not None and cohort["median"] > 0,
        "pool_complete_cohort_mean_ex_top3_positive": cohort.get("mean_excluding_top3_winners") is not None and cohort["mean_excluding_top3_winners"] > 0,
    }
    values = [
        net_signal.get("mean"), net_signal.get("median"), net_signal.get("mean_excluding_top3_winners"),
        cohort.get("mean"), cohort.get("median"), cohort.get("mean_excluding_top3_winners"),
    ]
    if any(value is None for value in values):
        decision = "INCONCLUSIVE_INCOMPLETE_POOL_COHORT_COVERAGE"
    elif all(checks.values()):
        decision = "KEEP"
    else:
        decision = "REJECT"
    return decision, checks


def run_period(period: str) -> dict[str, object]:
    spec = load_frozen_spec()
    if period == "discovery" and DISCOVERY_PATH.exists():
        raise FileExistsError("discovery report already exists; do not reopen or overwrite it")
    if period == "validation-2024" and VALIDATION_PATH.exists():
        raise FileExistsError("2024 report already exists; do not reopen or overwrite it")
    if period == "replay-2025" and REPLAY_PATH.exists():
        raise FileExistsError("2025 replay already exists; do not reopen or overwrite it")
    if period == "report-2026" and REPORT_2026_PATH.exists():
        raise FileExistsError("2026 report already exists; do not reopen or overwrite it")

    start, period_end, report_path, intent = _period(period)
    locked_top_n, policy_lock = _locked_top_n(spec, period)
    calendar = shared._calendar()
    last_session = calendar.sessions[calendar.sessions <= period_end][-1]
    eval_sessions = calendar.sessions[(calendar.sessions >= start) & (calendar.sessions <= last_session)]
    phase_opened_at = datetime.now(timezone.utc).isoformat()
    if period == "discovery":
        access = validate_period_access(
            intent=intent, start=start, end=period_end, spec_sha256=str(spec["spec_sha256"]),
        )
        top_n_values = TOP_N_VALUES
    else:
        access = validate_period_access(
            intent=intent,
            start=start,
            end=period_end,
            spec_sha256=str(spec["spec_sha256"]),
            frozen_spec_sha256=str(spec["spec_sha256"]),
            spec_frozen_at=spec["frozen_at_utc"],
            phase_opened_at=phase_opened_at,
            model_fit_through="2025-12-31" if period == "report-2026" else None,
        )
        top_n_values = (locked_top_n,)

    panel, panel_receipt, panel_path = _load_panel_through(last_session, calendar)
    source_panel_rows = int(len(panel))
    pool = build_candidate_pool(panel, spec_hash=str(spec["spec_sha256"]))
    date_pos = {pd.Timestamp(day): index for index, day in enumerate(calendar.sessions)}
    final_pos = date_pos[pd.Timestamp(last_session)]
    pool["session_index"] = pool["date"].map(date_pos).astype("int32")
    pool = pool.loc[
        pool["date"].between(start, period_end)
        & pool["session_index"].add(5).le(final_pos)
    ].copy()
    if pool.empty:
        raise ValueError("registered orderly-pullback family produced no eligible candidates")

    # Candidate membership and all policy selections are written before the
    # outcome-only OHLCV projection is opened below.
    ranked = rank_orderly_pool(pool, sessions=eval_sessions)
    decision_columns = [
        "date", "symbol", "family", "spec_hash", "identity_key", "candidate_id",
        "feature_timestamp", "inclusion_reason", "close", "ret5", "ret20",
        "path_abs_sum20", "path_efficiency20", "volume_trend5_20",
    ]
    raw_pool = pool.loc[:, decision_columns].copy()
    rank_columns = [
        "date", "symbol", "family", "spec_hash", "identity_key", "candidate_id",
        "feature_timestamp", "score", "raw_rank", "daily_candidate_count",
        "ret5", "ret20", "path_abs_sum20", "path_efficiency20",
        "volume_trend5_20", "path_efficiency_pct", "volume_contraction_pct", "quality_score", "close",
    ]
    ranked = ranked.loc[:, rank_columns].copy()
    label_signals = raw_pool.loc[:, ["date", "symbol", "close"]].copy()
    artifact_hashes, selected_by_n = _save_decision_artifacts(
        period=period,
        spec=spec,
        panel_receipt=panel_receipt,
        pool=raw_pool,
        ranked=ranked,
        sessions=eval_sessions,
        top_n_values=top_n_values,
    )
    candidate_rows = int(len(raw_pool))
    candidate_dates = int(raw_pool["date"].nunique())
    max_candidates_per_day = int(raw_pool.groupby("date").size().max())
    mean_candidates_per_day = float(raw_pool.groupby("date").size().mean())
    del pool, raw_pool, ranked, panel
    gc.collect()

    prices, price_receipt = read_verified_parquet_columns(panel_path, list(PRICE_COLUMNS))
    if price_receipt.get("sha256") != panel_receipt.get("sha256"):
        raise ValueError("outcome price projection does not match the decision-only panel receipt")
    labels = shared.build_labels_for_eligible_signals(prices, label_signals, calendar)
    del prices
    gc.collect()
    labels["family"] = str(FAMILY_SPEC["family"])
    labels["spec_hash"] = str(spec["spec_sha256"])
    label_path = BATCH_DIR / ".cache" / f"core_orderly_pullback_{period}_labels.parquet"
    label_receipt = write_parquet_artifact(
        labels.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True),
        label_path,
        metadata={
            "experiment_id": FAMILY_SPEC["experiment_id"],
            "spec_sha256": spec["spec_sha256"],
            "source_sha256": spec["source_sha256"],
            "calendar_sha256": spec["calendar_sha256"],
            "outcome_table_separate_from_decision_artifacts": True,
            "period": period,
        },
    )
    pool_labels = label_signals.merge(
        labels,
        on=["date", "symbol"], how="left", validate="one_to_one",
    )
    if pool_labels["label_resolved"].isna().any():
        pool_labels["label_resolved"] = pool_labels["label_resolved"].fillna(False)
        pool_labels["label_status"] = pool_labels["label_status"].fillna("LABEL_ROW_MISSING")
    pool_signal_metrics = label_summary(pool_labels, costs=(0.0, 0.005, 0.01))
    pool_daily = shared._pool_daily(pool_labels, eval_sessions)
    pool_cohort_metrics = cohort_summary(pool_daily, repetitions=2000)
    family_decision, family_gates = _family_gate(pool_signal_metrics, pool_cohort_metrics)

    # Load the saved pre-outcome ranking only after pool outcomes have been
    # summarized. It is never rebuilt or changed using any label information.
    from .artifact_store import read_verified_parquet
    ranked, ranked_receipt = read_verified_parquet(
        BATCH_DIR / ".cache" / f"core_orderly_pullback_{period}_ranked_pool.parquet"
    )
    if ranked_receipt.get("sha256") != artifact_hashes["ranked_pool_sha256"]:
        raise ValueError("saved ranking artifact changed before outcome evaluation")
    rank_metrics = _rank_band_metrics(ranked, pool_labels)

    policy_reports: list[dict[str, object]] = []
    decision = "NOT_EVALUATED_FAMILY_NOT_KEEP"
    frozen_top_n = None
    if period == "discovery" and family_decision == "KEEP":
        for top_n in top_n_values:
            report, _ = shared._selection_report(
                ranked=ranked,
                labels=pool_labels,
                sessions=eval_sessions,
                top_n=top_n,
                family=str(FAMILY_SPEC["family"]),
                spec_hash=str(spec["spec_sha256"]),
                pool_metrics=pool_signal_metrics,
                pool_daily=pool_daily,
                phase_name=period,
            )
            if report["selection_sha256"] != artifact_hashes["selection_sha256_by_top_n"][str(top_n)]:
                raise RuntimeError("policy selections changed between pre-outcome save and post-outcome evaluation")
            policy_reports.append(report)
        passed = [report for report in policy_reports if report["passes_all_gates"]]
        if passed:
            passed.sort(key=lambda item: (-float(item["daily_cohort_net_metrics"]["mean"]), int(item["top_n"])))
            frozen_top_n = int(passed[0]["top_n"])
            decision = "PROMOTE_TO_2024_CONFIRMATION"
            _write_json(POLICY_LOCK_PATH, {
                "schema_version": 1,
                "experiment_id": FAMILY_SPEC["experiment_id"],
                "spec_sha256": spec["spec_sha256"],
                "decision": decision,
                "top_n": frozen_top_n,
                "policy_sha256": passed[0]["policy_sha256"],
                "selection_sha256": passed[0]["selection_sha256"],
                "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
                "selection_rule": "highest discovery complete-daily-cohort mean among passing policies; exact ties choose smaller N",
                "multiple_names_per_day": True,
            })
        else:
            decision = "SELECTION_COUNT_UNRESOLVED"
    elif period == "validation-2024":
        policy_reports = [
            shared._selection_report(
                ranked=ranked, labels=pool_labels, sessions=eval_sessions,
                top_n=locked_top_n, family=str(FAMILY_SPEC["family"]),
                spec_hash=str(spec["spec_sha256"]), pool_metrics=pool_signal_metrics,
                pool_daily=pool_daily, phase_name=period,
            )[0]
        ]
        if policy_reports[0]["policy_sha256"] != policy_lock["policy_sha256"]:
            raise ValueError("2024 policy hash differs from the discovery lock")
        decision = "CONFIRMATION_PASS" if policy_reports[0]["passes_all_gates"] else "REJECT_AFTER_2024_CONFIRMATION"
    elif period == "replay-2025":
        policy_reports = [
            shared._selection_report(
                ranked=ranked, labels=pool_labels, sessions=eval_sessions,
                top_n=locked_top_n, family=str(FAMILY_SPEC["family"]),
                spec_hash=str(spec["spec_sha256"]), pool_metrics=pool_signal_metrics,
                pool_daily=pool_daily, phase_name=period,
            )[0]
        ]
        if policy_reports[0]["policy_sha256"] != policy_lock["policy_sha256"]:
            raise ValueError("2025 policy hash differs from the discovery lock")
        decision = "LOCKED_2025_REPLAY_RECORDED"
    else:
        policy_reports = [
            shared._selection_report(
                ranked=ranked, labels=pool_labels, sessions=eval_sessions,
                top_n=locked_top_n, family=str(FAMILY_SPEC["family"]),
                spec_hash=str(spec["spec_sha256"]), pool_metrics=pool_signal_metrics,
                pool_daily=pool_daily, phase_name=period,
            )[0]
        ]
        if policy_reports[0]["policy_sha256"] != policy_lock["policy_sha256"]:
            raise ValueError("2026 frozen reporting policy hash differs from the discovery lock")
        decision = "FROZEN_2026_REPORT_ONLY"

    if period == "validation-2024" and decision == "REJECT_AFTER_2024_CONFIRMATION":
        # The registered protocol does not open 2025 or 2026 after this result.
        pass
    report = {
        "schema_version": 1,
        "experiment_id": FAMILY_SPEC["experiment_id"],
        "family": FAMILY_SPEC["family"],
        "family_spec_sha256": FAMILY_SPEC_SHA256,
        "spec_sha256": spec["spec_sha256"],
        "period": period,
        "period_access": access,
        "spec_frozen_at_utc": spec["frozen_at_utc"],
        "phase_opened_at_utc": phase_opened_at,
        "source_sha256": spec["source_sha256"],
        "calendar_sha256": spec["calendar_sha256"],
        "feature_panel_sha256": panel_receipt["sha256"],
        "source_panel_rows": source_panel_rows,
        "candidate_pool_rows": candidate_rows,
        "candidate_pool_unique_symbols": int(label_signals["symbol"].nunique()),
        "candidate_pool_active_dates": candidate_dates,
        "candidate_pool_max_names_per_day": max_candidates_per_day,
        "candidate_pool_mean_names_per_active_day": mean_candidates_per_day,
        "candidate_pool_signal_metrics": pool_signal_metrics,
        "candidate_pool_complete_daily_cohorts": pool_cohort_metrics,
        "candidate_pool_daily_coverage": {
            "complete_days": int(pool_daily["cohort_status"].eq("COMPLETE").sum()),
            "partial_unresolved_days": int(pool_daily["cohort_status"].eq("PARTIAL_UNRESOLVED").sum()),
            "abstain_days": int(pool_daily["cohort_status"].eq("ABSTAIN").sum()),
        },
        "family_decision": family_decision if period == "discovery" else None,
        "family_gate_checks": family_gates if period == "discovery" else None,
        "raw_rank_band_metrics": rank_metrics,
        "selection_policy_reports": policy_reports,
        "selection_policy_decision": decision,
        "locked_top_n": frozen_top_n if period == "discovery" else locked_top_n,
        "multiple_names_per_day": True,
        "unresolved_candidates_retained": int((~pool_labels["label_resolved"].astype(bool)).sum()),
        "artifacts": {
            **artifact_hashes,
            "outcome_labels_sha256": label_receipt["sha256"],
        },
        "evidence_level": "RETROSPECTIVE_PROVISIONAL",
        "prior_partial_discovery_exposure": "Attempt03 may have partially accessed discovery OHLCV; attempt04 is an engineering replay of a frozen Ridge strategy. No outcomes were used to tune this registered family; this remains historical provisional evidence, not untouched OOS.",
        "execution_cost_note": "0.5% round-trip is a sensitivity assumption, not observed slippage, commissions, tax, or fill quality.",
    }
    _write_json(report_path, report)
    del ranked, labels, pool_labels, label_signals, selected_by_n
    gc.collect()
    return report


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("freeze", "discovery", "validation-2024", "replay-2025", "report-2026"))
    args = parser.parse_args()
    if args.phase == "freeze":
        result = freeze_spec()
        print(json.dumps({"experiment_id": result["experiment_id"], "spec_sha256": result["spec_sha256"], "frozen_at_utc": result["frozen_at_utc"]}, indent=2))
        return
    result = run_period(args.phase)
    print(json.dumps({
        "experiment_id": result["experiment_id"],
        "period": result["period"],
        "family_decision": result["family_decision"],
        "selection_policy_decision": result["selection_policy_decision"],
        "locked_top_n": result["locked_top_n"],
        "candidate_pool_rows": result["candidate_pool_rows"],
        "complete_daily_cohort_days": result["candidate_pool_daily_coverage"]["complete_days"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
