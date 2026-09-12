"""Run a purged First Reversal winner/loser feature audit in sealed phases."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from .artifact_store import sha256_file
from .evaluation import build_five_session_labels, cohort_summary, daily_cohorts, label_summary
from .feature_separation import (
    EXPLORATORY_FEATURES,
    discovery_tercile_edges,
    directional_confirmation,
    feature_band_metrics,
    feature_class_separation,
    select_directionally_stable_features,
)
from .first_reversal import FIRST_REVERSAL_SPEC, FIRST_REVERSAL_SPEC_SHA256
from .session_calendar import SessionCalendar
from .temporal_policy import validate_period_access


BATCH_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE = BATCH_DIR / ".cache" / "artifacts" / "tse_daily.csv"
DEFAULT_POOL = BATCH_DIR / ".cache" / "first_reversal_candidate_pool.parquet"
DEFAULT_FREEZE = BATCH_DIR / "reports" / "first_reversal_feature_freeze.json"
DEFAULT_QUALIFIED_FREEZE = BATCH_DIR / "reports" / "first_reversal_feature_freeze_qualified.json"
DEFAULT_QUALITY_REPORT = BATCH_DIR / "reports" / "first_reversal_feature_quality_review.json"
DEFAULT_REPORT_DIR = BATCH_DIR / "reports"
DEFAULT_CALENDAR = BATCH_DIR / "reference" / "xtks_sessions.csv"
DEFAULT_CALENDAR_MANIFEST = BATCH_DIR / "reference" / "xtks_sessions.manifest.json"
DEFAULT_PRESERVATION_MANIFEST = BATCH_DIR / "PRESERVATION_MANIFEST.json"

FEATURE_AUDIT_SPEC: dict[str, Any] = {
    "spec_id": "first_reversal_winner_loser_feature_audit_v1",
    "target": "next XTKS session open to fifth XTKS session close",
    "winner": "gross 5-session return >= +10%",
    "loser": "gross 5-session return <= -10%",
    "discovery": {
        "2022H2": "signal dates 2022-07-01 through final 2022 XTKS session; exit must remain in 2022",
        "2023": "signal dates 2023-01-01 through final 2023 XTKS session; exit must remain in 2023",
        "pooled": "union of the two separately purged discovery splits",
    },
    "feature_set": list(EXPLORATORY_FEATURES),
    "excluded_reconstruction_only_features": ["volr5_inclusive", "volr20_inclusive"],
    "selection_rule": {
        "minimum_winners_and_losers_per_split": 50,
        "require_same_nonzero_cliffs_delta_and_median_delta_direction_in_2022H2_2023_and_pooled": True,
        "maximum_selected_features": 2,
        "sort": "absolute pooled Cliffs delta descending, feature name ascending",
        "minimum_effect_threshold": None,
        "p_values": "not used; rows have cross-sectional and repeated-symbol dependence",
    },
    "confirmation_rule": {
        "freeze_tercile_cutpoints": "33.333% and 66.667% quantiles of all finite discovery candidate feature values, without labels",
        "require_2024_and_2025": "selected feature class-effect direction and outer-band extreme-winner share both match discovery",
        "minimum_winners_and_losers_in_each_outer_band": 50,
    },
    "evidence_level": "RETROSPECTIVE_PROVISIONAL; historical years and aggregate strategy results have been previously observed",
}
FEATURE_AUDIT_SPEC_SHA256 = hashlib.sha256(
    json.dumps(FEATURE_AUDIT_SPEC, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
).hexdigest()
FEATURE_QUALITY_SPEC: dict[str, Any] = {
    "spec_id": "first_reversal_feature_coverage_semantics_review_v1",
    "minimum_finite_feature_rate_each_discovery_split": 0.95,
    "missingness_must_have_one_unambiguous_signal_time_interpretation": True,
    "dropped_feature_replacement": "none within this batch; no discovery re-search",
    "outcome_access": "forbidden; this phase may read only the frozen discovery report and signal-time candidate features",
}
FEATURE_QUALITY_SPEC_SHA256 = hashlib.sha256(
    json.dumps(FEATURE_QUALITY_SPEC, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
).hexdigest()

PRICE_COLUMNS = ["date", "symbol", "open", "high", "low", "close", "volume"]
POOL_METADATA_COLUMNS = ["date", "symbol", "family", "spec_hash", "candidate_id"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _manifest_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".manifest.json")


def _verified_pool_period(
    pool_path: Path,
    *,
    start: str,
    through: str,
    features: list[str],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    manifest_path = _manifest_path(pool_path)
    receipt = json.loads(manifest_path.read_text(encoding="utf-8"))
    actual = sha256_file(pool_path)
    if actual != receipt.get("sha256"):
        raise ValueError("candidate-pool bytes differ from their manifest")
    parquet = pq.ParquetFile(pool_path)
    if parquet.metadata.num_rows != int(receipt.get("rows", -1)):
        raise ValueError("candidate-pool row count differs from its manifest")
    if parquet.schema_arrow.names != receipt.get("columns"):
        raise ValueError("candidate-pool columns differ from its manifest")
    required = [*POOL_METADATA_COLUMNS, *features]
    if not set(required).issubset(parquet.schema_arrow.names):
        raise ValueError("candidate pool does not contain the registered feature schema")
    frame = pd.read_parquet(
        pool_path,
        engine="pyarrow",
        columns=list(dict.fromkeys(required)),
        filters=[("date", ">=", pd.Timestamp(start)), ("date", "<=", pd.Timestamp(through))],
    )
    if frame.empty:
        raise ValueError(f"candidate pool has no signal rows for {start} through {through}")
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    frame["symbol"] = frame["symbol"].astype("string")
    if not frame["family"].eq(FIRST_REVERSAL_SPEC["spec_id"]).all():
        raise ValueError("candidate pool contains an unexpected family")
    if not frame["spec_hash"].eq(FIRST_REVERSAL_SPEC_SHA256).all():
        raise ValueError("candidate pool contains an unexpected First Reversal spec hash")
    if frame.duplicated(["date", "symbol"]).any():
        raise ValueError("candidate pool contains duplicate symbol/date rows")
    return frame, {**receipt, "sha256": actual, "rows_in_period_filter": int(len(frame))}


def _read_prices_through(source_path: Path, *, through: pd.Timestamp) -> pd.DataFrame:
    """Read only the OHLCV prefix allowed for the currently opened phase."""
    chunks: list[pd.DataFrame] = []
    for chunk in pd.read_csv(
        source_path,
        usecols=PRICE_COLUMNS,
        dtype={
            "symbol": "string", "open": "float64", "high": "float64", "low": "float64",
            "close": "float64", "volume": "float64",
        },
        parse_dates=["date"],
        chunksize=500_000,
    ):
        chunk["date"] = pd.to_datetime(chunk["date"], errors="raise").dt.normalize()
        allowed = chunk.loc[chunk["date"].le(through)].copy()
        if not allowed.empty:
            chunks.append(allowed)
    if not chunks:
        raise ValueError("no OHLCV rows fall within the opened phase")
    prices = pd.concat(chunks, ignore_index=True)
    if prices["date"].max() > through:
        raise RuntimeError("phase price reader included data after its cutoff")
    return prices


def _session_end(calendar: SessionCalendar, year: int) -> pd.Timestamp:
    end = pd.Timestamp(f"{year}-12-31")
    available = calendar.sessions[calendar.sessions <= end]
    if available.empty or available[-1].year != year:
        raise ValueError(f"frozen XTKS calendar lacks the final session in {year}")
    return pd.Timestamp(available[-1])


def _purge_to_period_end(
    pool: pd.DataFrame,
    *,
    calendar: SessionCalendar,
    period_start: str,
    period_end: pd.Timestamp,
) -> tuple[pd.DataFrame, int]:
    date_positions = calendar.sessions.get_indexer(pd.DatetimeIndex(pool["date"]))
    if (date_positions < 0).any():
        raise ValueError("candidate pool includes a non-session signal date")
    end_position = calendar.position(period_end)
    eligible = date_positions + 5 <= end_position
    return pool.loc[eligible].copy(), int((~eligible).sum())


def _period_feature_effects(frame: pd.DataFrame) -> dict[str, dict[str, object]]:
    periods = {
        "2022H2": frame.loc[frame["date"].between("2022-07-01", "2022-12-31")],
        "2023": frame.loc[frame["date"].between("2023-01-01", "2023-12-31")],
        "discovery_pooled": frame,
    }
    effects: dict[str, dict[str, object]] = {}
    for feature in EXPLORATORY_FEATURES:
        effects[feature] = {
            period: feature_class_separation(rows, feature)
            for period, rows in periods.items()
        }
    return effects


def _outcome_summary(frame: pd.DataFrame, calendar: SessionCalendar) -> dict[str, object]:
    daily = daily_cohorts(
        frame.loc[:, ["date", "symbol", "family", "spec_hash"]],
        frame,
        sessions=calendar.sessions,
    )
    return {
        "signal_level": label_summary(frame),
        "equal_weight_daily_candidate_cohort": cohort_summary(daily, repetitions=2000),
        "daily_cohort_status_counts": {
            str(key): int(value) for key, value in daily["cohort_status"].value_counts().items()
        },
    }


def _discovery(
    *,
    source_path: Path,
    pool_path: Path,
    calendar_path: Path,
    calendar_manifest_path: Path,
    preservation_manifest_path: Path,
    freeze_path: Path,
    report_dir: Path,
) -> dict[str, object]:
    phase_opened_at = _utc_now()
    access = validate_period_access(
        intent="select_features",
        start="2022-07-01",
        end="2023-12-31",
        spec_sha256=FEATURE_AUDIT_SPEC_SHA256,
    )
    calendar_receipt = json.loads(calendar_manifest_path.read_text(encoding="utf-8"))
    calendar = SessionCalendar.from_csv(calendar_path, expected_sha256=calendar_receipt["csv_sha256"])
    preserved = json.loads(preservation_manifest_path.read_text(encoding="utf-8"))
    source_receipt = next(item for item in preserved["artifacts"] if item["member"] == source_path.name)
    source_sha = sha256_file(source_path)
    if source_sha != source_receipt["member_sha256"]:
        raise ValueError("OHLCV source hash differs from the preservation manifest")
    pool, pool_receipt = _verified_pool_period(
        pool_path, start="2022-07-01", through="2023-12-31", features=list(EXPLORATORY_FEATURES),
    )

    half_2022_end = _session_end(calendar, 2022)
    year_2023_end = _session_end(calendar, 2023)
    h2_2022, purged_2022 = _purge_to_period_end(
        pool.loc[pool["date"].between("2022-07-01", "2022-12-31")],
        calendar=calendar, period_start="2022-07-01", period_end=half_2022_end,
    )
    year_2023, purged_2023 = _purge_to_period_end(
        pool.loc[pool["date"].between("2023-01-01", "2023-12-31")],
        calendar=calendar, period_start="2023-01-01", period_end=year_2023_end,
    )
    discovery_pool = pd.concat([h2_2022, year_2023], ignore_index=True)
    if discovery_pool.empty:
        raise ValueError("purged discovery pool is empty")
    prices = _read_prices_through(source_path, through=year_2023_end)
    labels = build_five_session_labels(prices, discovery_pool, calendar)
    if labels["exit_date"].gt(labels["date"].map(
        lambda day: half_2022_end if day.year == 2022 else year_2023_end
    )).any():
        raise RuntimeError("discovery target crossed its split-end purge boundary")

    effects = _period_feature_effects(labels)
    selected = select_directionally_stable_features(effects)
    frozen_features = []
    for item in selected:
        edges = discovery_tercile_edges(discovery_pool[item["feature"]])
        frozen_features.append({**item, "tercile_edges": list(edges)})

    split_summaries = {
        "2022H2": _outcome_summary(labels.loc[labels["date"].between("2022-07-01", "2022-12-31")], calendar),
        "2023": _outcome_summary(labels.loc[labels["date"].between("2023-01-01", "2023-12-31")], calendar),
        "discovery_pooled": _outcome_summary(labels, calendar),
    }
    freeze_spec = {
        "candidate_pool_spec_sha256": FIRST_REVERSAL_SPEC_SHA256,
        "feature_audit_spec_sha256": FEATURE_AUDIT_SPEC_SHA256,
        "features": frozen_features,
    }
    freeze_spec_sha = hashlib.sha256(
        json.dumps(freeze_spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    frozen_at = _utc_now()
    freeze = {
        "schema_version": 1,
        "experiment_id": "TVF-FR-FEATURE-20260913-01",
        "spec_id": "first_reversal_discovery_feature_freeze_v1",
        "spec_sha256": freeze_spec_sha,
        "created_at_utc": frozen_at,
        "discovery_phase_opened_at_utc": phase_opened_at,
        "access": access,
        "candidate_pool_sha256": pool_receipt["sha256"],
        "source_sha256": source_sha,
        "calendar_sha256": calendar.sha256,
        "first_reversal_spec_sha256": FIRST_REVERSAL_SPEC_SHA256,
        "feature_audit_spec_sha256": FEATURE_AUDIT_SPEC_SHA256,
        "features": frozen_features,
        "feature_audit_spec": FEATURE_AUDIT_SPEC,
        "evidence_level": "RETROSPECTIVE_PROVISIONAL",
        "caveat": "2024 aggregate First Reversal results were already present in the handoff; later feature-specific confirmation is historical and is not independent OOS evidence.",
    }
    _json_write(freeze_path, freeze)
    freeze_sha = sha256_file(freeze_path)
    report = {
        "schema_version": 1,
        "experiment_id": freeze["experiment_id"],
        "phase": "discovery_2022H2_2023",
        "phase_opened_at_utc": phase_opened_at,
        "created_at_utc": _utc_now(),
        "access": access,
        "spec_sha256": freeze_spec_sha,
        "candidate_pool_sha256": pool_receipt["sha256"],
        "candidate_pool_spec_sha256": FIRST_REVERSAL_SPEC_SHA256,
        "source_sha256": source_sha,
        "calendar_sha256": calendar.sha256,
        "periods": {
            "2022H2": {"signals_before_purge": int(pool["date"].between("2022-07-01", "2022-12-31").sum()), "purged_signals": purged_2022, "period_end": str(half_2022_end.date())},
            "2023": {"signals_before_purge": int(pool["date"].between("2023-01-01", "2023-12-31").sum()), "purged_signals": purged_2023, "period_end": str(year_2023_end.date())},
        },
        "labeled_signal_count": int(len(labels)),
        "outcomes": split_summaries,
        "feature_effects": effects,
        "selected_features": frozen_features,
        "decision": "LOCK_FEATURES_FOR_2024_DIRECTIONAL_CONFIRMATION" if frozen_features else "REJECT_NO_DIRECTIONALLY_STABLE_FEATURE",
        "freeze_file": freeze_path.name,
        "freeze_file_sha256": freeze_sha,
        "evidence_level": "RETROSPECTIVE_PROVISIONAL",
        "caveat": freeze["caveat"],
    }
    output = report_dir / "first_reversal_discovery_audit.json"
    _json_write(output, report)
    return {"report": str(output), "freeze": str(freeze_path), "selected_features": frozen_features, "decision": report["decision"], "labeled_signals": len(labels)}


def _quality_review_freeze(
    *,
    source_path: Path,
    pool_path: Path,
    calendar_path: Path,
    calendar_manifest_path: Path,
    preservation_manifest_path: Path,
    freeze_path: Path,
    qualified_freeze_path: Path,
    quality_report_path: Path,
) -> dict[str, object]:
    """Apply a transparent feature-availability review before opening 2024."""
    phase_opened_at = _utc_now()
    prior = json.loads(freeze_path.read_text(encoding="utf-8"))
    prior_features = list(prior.get("features", []))
    if not prior_features:
        raise ValueError("discovery selected no features to review")
    calendar_receipt = json.loads(calendar_manifest_path.read_text(encoding="utf-8"))
    calendar = SessionCalendar.from_csv(calendar_path, expected_sha256=calendar_receipt["csv_sha256"])
    preserved = json.loads(preservation_manifest_path.read_text(encoding="utf-8"))
    source_receipt = next(item for item in preserved["artifacts"] if item["member"] == source_path.name)
    source_sha = sha256_file(source_path)
    if source_sha != source_receipt["member_sha256"] or source_sha != prior.get("source_sha256"):
        raise ValueError("source hash differs from the frozen discovery phase")
    names = [str(item["feature"]) for item in prior_features]
    pool, pool_receipt = _verified_pool_period(
        pool_path, start="2022-07-01", through="2023-12-31", features=names,
    )
    if pool_receipt["sha256"] != prior.get("candidate_pool_sha256"):
        raise ValueError("candidate-pool hash differs from the frozen discovery phase")

    split_masks = {
        "2022H2": pool["date"].between("2022-07-01", "2022-12-31"),
        "2023": pool["date"].between("2023-01-01", "2023-12-31"),
    }
    feature_reviews: dict[str, dict[str, Any]] = {}
    accepted: list[dict[str, Any]] = []
    for item in prior_features:
        feature = str(item["feature"])
        values = pd.to_numeric(pool[feature], errors="coerce").to_numpy(dtype="float64")
        coverage: dict[str, dict[str, Any]] = {}
        for split, mask in split_masks.items():
            split_values = values[mask.to_numpy()]
            finite_rate = float(np.isfinite(split_values).mean()) if len(split_values) else 0.0
            coverage[split] = {
                "candidate_count": int(len(split_values)),
                "finite_count": int(np.isfinite(split_values).sum()),
                "missing_count": int((~np.isfinite(split_values)).sum()),
                "finite_rate": finite_rate,
            }
        reasons = []
        if any(row["finite_rate"] < FEATURE_QUALITY_SPEC["minimum_finite_feature_rate_each_discovery_split"] for row in coverage.values()):
            reasons.append("finite_feature_rate_below_95_percent_in_a_discovery_split")
        if feature == "days_since_drop5":
            reasons.append("NaN_conflates_no_prior_5_percent_drop_with_history_gap_reset")
        accepted_feature = not reasons
        feature_reviews[feature] = {
            "direction_from_discovery": item["direction"],
            "coverage_by_discovery_split": coverage,
            "accepted_for_confirmation": accepted_feature,
            "reasons": reasons,
        }
        if accepted_feature:
            accepted.append(item)

    final_spec = {
        "candidate_pool_spec_sha256": FIRST_REVERSAL_SPEC_SHA256,
        "feature_audit_spec_sha256": FEATURE_AUDIT_SPEC_SHA256,
        "feature_quality_spec_sha256": FEATURE_QUALITY_SPEC_SHA256,
        "features": accepted,
    }
    final_spec_sha = hashlib.sha256(
        json.dumps(final_spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    review = {
        "schema_version": 1,
        "experiment_id": "TVF-FR-FEATURE-20260913-01-QUALITY-REVIEW",
        "phase": "discovery_feature_availability_review",
        "phase_opened_at_utc": phase_opened_at,
        "created_at_utc": _utc_now(),
        "discovery_freeze_sha256": sha256_file(freeze_path),
        "candidate_pool_sha256": pool_receipt["sha256"],
        "source_sha256": source_sha,
        "calendar_sha256": calendar.sha256,
        "quality_spec": FEATURE_QUALITY_SPEC,
        "quality_spec_sha256": FEATURE_QUALITY_SPEC_SHA256,
        "feature_reviews": feature_reviews,
        "accepted_features": accepted,
        "replacement_search_performed": False,
        "historical_exposure_note": "This availability rule was added after seeing the discovery feature ranking but before opening 2024; it is a protocol revision, not an independent holdout result.",
        "decision": "LOCK_QUALIFIED_FEATURES" if accepted else "REJECT_FEATURE_AUDIT_NO_OPERATIONAL_FEATURE",
    }
    _json_write(quality_report_path, review)
    qualified_freeze = {
        **prior,
        "spec_id": "first_reversal_discovery_feature_freeze_qualified_v1",
        "spec_sha256": final_spec_sha,
        "created_at_utc": _utc_now(),
        "supersedes_freeze_sha256": review["discovery_freeze_sha256"],
        "feature_quality_spec": FEATURE_QUALITY_SPEC,
        "feature_quality_spec_sha256": FEATURE_QUALITY_SPEC_SHA256,
        "quality_report_sha256": sha256_file(quality_report_path),
        "features": accepted,
        "decision": review["decision"],
    }
    _json_write(qualified_freeze_path, qualified_freeze)
    return {
        "quality_report": str(quality_report_path),
        "qualified_freeze": str(qualified_freeze_path),
        "spec_sha256": final_spec_sha,
        "accepted_features": accepted,
        "feature_reviews": feature_reviews,
        "decision": review["decision"],
    }


def _confirm_later_period(
    *,
    phase: str,
    source_path: Path,
    pool_path: Path,
    calendar_path: Path,
    calendar_manifest_path: Path,
    preservation_manifest_path: Path,
    freeze_path: Path,
    report_dir: Path,
) -> dict[str, object]:
    if phase not in {"confirm_2024", "replay_2025"}:
        raise ValueError(f"unsupported later phase: {phase}")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    frozen_features = list(freeze.get("features", []))
    if freeze.get("first_reversal_spec_sha256") != FIRST_REVERSAL_SPEC_SHA256:
        raise ValueError("feature freeze refers to a different First Reversal candidate-pool spec")
    if freeze.get("feature_audit_spec_sha256") != FEATURE_AUDIT_SPEC_SHA256:
        raise ValueError("feature freeze uses a different feature-audit protocol")
    if not frozen_features:
        raise ValueError("discovery selected no features; later outcome data must remain unopened")

    phase_opened_at = _utc_now()
    year = 2024 if phase == "confirm_2024" else 2025
    start, through = f"{year}-01-01", f"{year}-12-31"
    access = validate_period_access(
        intent="locked_validation" if year == 2024 else "replay_2025",
        start=start,
        end=through,
        spec_sha256=str(freeze["spec_sha256"]),
        frozen_spec_sha256=str(freeze["spec_sha256"]),
        spec_frozen_at=freeze["created_at_utc"],
        phase_opened_at=phase_opened_at,
    )
    if year == 2025:
        confirm_path = report_dir / "first_reversal_validation_2024.json"
        confirm = json.loads(confirm_path.read_text(encoding="utf-8"))
        if confirm.get("freeze_file_sha256") != sha256_file(freeze_path):
            raise ValueError("2024 confirmation was not produced from this exact frozen feature spec")
        if confirm.get("decision") != "KEEP_FOR_LOCKED_2025_REPLAY":
            raise ValueError("2024 confirmation rejected the feature hypothesis; 2025 results remain unopened")

    calendar_receipt = json.loads(calendar_manifest_path.read_text(encoding="utf-8"))
    calendar = SessionCalendar.from_csv(calendar_path, expected_sha256=calendar_receipt["csv_sha256"])
    preserved = json.loads(preservation_manifest_path.read_text(encoding="utf-8"))
    source_receipt = next(item for item in preserved["artifacts"] if item["member"] == source_path.name)
    source_sha = sha256_file(source_path)
    if source_sha != source_receipt["member_sha256"] or source_sha != freeze.get("source_sha256"):
        raise ValueError("OHLCV source hash differs from the frozen discovery phase")
    features = [str(item["feature"]) for item in frozen_features]
    pool, pool_receipt = _verified_pool_period(pool_path, start=start, through=through, features=features)
    if pool_receipt["sha256"] != freeze.get("candidate_pool_sha256"):
        raise ValueError("candidate-pool hash differs from the frozen discovery phase")
    end_session = _session_end(calendar, year)
    purged, purge_count = _purge_to_period_end(
        pool.loc[pool["date"].between(start, through)],
        calendar=calendar, period_start=start, period_end=end_session,
    )
    prices = _read_prices_through(source_path, through=end_session)
    labels = build_five_session_labels(prices, purged, calendar)
    if labels["exit_date"].gt(end_session).any():
        raise RuntimeError(f"{year} labels cross the period-end purge boundary")

    effects: dict[str, dict[str, object]] = {}
    bands: dict[str, dict[str, object]] = {}
    confirmations: dict[str, dict[str, object]] = {}
    for frozen in frozen_features:
        feature = str(frozen["feature"])
        effect = feature_class_separation(labels, feature)
        band = feature_band_metrics(labels, feature, edges=frozen["tercile_edges"])
        effects[feature] = effect
        bands[feature] = band
        confirmations[feature] = directional_confirmation(
            effect, band, direction=str(frozen["direction"]),
        )
    outcomes = _outcome_summary(labels, calendar)
    confirmed = [feature for feature, result in confirmations.items() if result["confirmed"]]
    decision = (
        "KEEP_FOR_LOCKED_2025_REPLAY" if year == 2024 and confirmed
        else "REJECT_FIRST_REVERSAL" if year == 2024
        else "KEEP_FEATURE_DIAGNOSTIC" if confirmed
        else "REJECT_FEATURE_HYPOTHESIS"
    )
    report = {
        "schema_version": 1,
        "experiment_id": freeze["experiment_id"],
        "phase": "locked_2024_directional_confirmation" if year == 2024 else "locked_2025_historical_replay",
        "phase_opened_at_utc": phase_opened_at,
        "created_at_utc": _utc_now(),
        "access": access,
        "spec_sha256": freeze["spec_sha256"],
        "freeze_file_sha256": sha256_file(freeze_path),
        "candidate_pool_sha256": pool_receipt["sha256"],
        "source_sha256": source_sha,
        "calendar_sha256": calendar.sha256,
        "signal_count_before_purge": int(len(pool)),
        "purged_signal_count": purge_count,
        "labeled_signal_count": int(len(labels)),
        "outcomes": outcomes,
        "feature_effects": effects,
        "discovery_tercile_outcomes": bands,
        "directional_confirmation": confirmations,
        "confirmed_features": confirmed,
        "decision": decision,
        "evidence_level": "RETROSPECTIVE_PROVISIONAL",
        "caveat": freeze["caveat"],
    }
    filename = "first_reversal_validation_2024.json" if year == 2024 else "first_reversal_replay_2025.json"
    output = report_dir / filename
    _json_write(output, report)
    return {"report": str(output), "decision": decision, "confirmed_features": confirmed, "labeled_signals": len(labels)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("discovery", "quality_review", "confirm_2024", "replay_2025"), required=True)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--pool", type=Path, default=DEFAULT_POOL)
    parser.add_argument("--calendar", type=Path, default=DEFAULT_CALENDAR)
    parser.add_argument("--calendar-manifest", type=Path, default=DEFAULT_CALENDAR_MANIFEST)
    parser.add_argument("--preservation-manifest", type=Path, default=DEFAULT_PRESERVATION_MANIFEST)
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--qualified-freeze", type=Path, default=DEFAULT_QUALIFIED_FREEZE)
    parser.add_argument("--quality-report", type=Path, default=DEFAULT_QUALITY_REPORT)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()
    common = {
        "source_path": args.source,
        "pool_path": args.pool,
        "calendar_path": args.calendar,
        "calendar_manifest_path": args.calendar_manifest,
        "preservation_manifest_path": args.preservation_manifest,
        "freeze_path": args.freeze,
        "report_dir": args.report_dir,
    }
    if args.phase == "discovery":
        result = _discovery(**common)
    elif args.phase == "quality_review":
        quality_common = {key: value for key, value in common.items() if key != "report_dir"}
        result = _quality_review_freeze(
            **quality_common,
            qualified_freeze_path=args.qualified_freeze,
            quality_report_path=args.quality_report,
        )
    else:
        result = _confirm_later_period(phase=args.phase, **common)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
