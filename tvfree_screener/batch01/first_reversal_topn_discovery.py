"""Compare registered First Reversal rankers and Top-N policies on discovery only."""
from __future__ import annotations

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
from .feature_panel import FEATURE_COLUMNS
from .first_reversal import FIRST_REVERSAL_SPEC, FIRST_REVERSAL_SPEC_SHA256
from .first_reversal_feature_audit import (
    DEFAULT_QUALIFIED_FREEZE,
    DEFAULT_SOURCE,
    _read_prices_through,
    _session_end,
    _verified_pool_period,
)
from .selection import ALLOWED_TOP_N, PolicySpec, apply_selection_policy, rank_candidate_pool
from .session_calendar import SessionCalendar


BATCH_DIR = Path(__file__).resolve().parent
DEFAULT_POOL = BATCH_DIR / ".cache" / "first_reversal_candidate_pool.parquet"
DEFAULT_CALENDAR = BATCH_DIR / "reference" / "xtks_sessions.csv"
DEFAULT_CALENDAR_MANIFEST = BATCH_DIR / "reference" / "xtks_sessions.manifest.json"
DEFAULT_PRESERVATION_MANIFEST = BATCH_DIR / "PRESERVATION_MANIFEST.json"
DEFAULT_FREEZE = BATCH_DIR / "reports" / "first_reversal_selection_freeze.json"
DEFAULT_REPORT = BATCH_DIR / "reports" / "first_reversal_topn_discovery.json"

RANKERS: dict[str, dict[str, Any]] = {
    "legacy_reversal_rank": {
        "terms": [["ret1_minus_ret5_per5", False]],
        "features": ["ret1_minus_ret5_per5"],
        "missing_behavior": "term must be finite; reject if missing",
    },
    "dd60_strength_rank": {
        "terms": [["dd60_rank_value", False]],
        "features": ["dd60", "dd60_rank_value", "dd60_rank_missing"],
        "missing_behavior": "dd60 missing receives -2.0, below the valid domain dd60>-1; never drop or replace a candidate",
    },
}
TOP_N_VALUES = tuple(ALLOWED_TOP_N)
ROUND_TRIP_COST = 0.005
SELECTION_SPEC: dict[str, Any] = {
    "spec_id": "first_reversal_ranker_topn_discovery_v1",
    "candidate_family": FIRST_REVERSAL_SPEC["spec_id"],
    "discovery_period": "2022H2 and 2023; signal label exit must remain in its signal calendar year",
    "rankers": RANKERS,
    "top_n_values": list(TOP_N_VALUES),
    "cooldown": "one prior official XTKS session; per-ranker and per-N independent state; chosen rows only update state",
    "tie_break": "raw rank, then symbol ascending",
    "selection_rule": "full pool; select up to N rows per session; no post-hoc score/count gate",
    "candidate_pool_reference": "all preregistered pool rows on the policy active dates; never truncate the reference to N",
    "daily_cohort": "any unresolved or split-purged selected row makes that date incomplete; no survivor reweighting",
    "cost_assumption": "0.5% round trip, sensitivity only and not measured live cost",
    "evidence_level": "RETROSPECTIVE_PROVISIONAL; previously observed historical periods are not true OOS",
}
SELECTION_SPEC_SHA256 = hashlib.sha256(
    json.dumps(SELECTION_SPEC, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _read_pool(pool_path: Path, *, freeze_path: Path) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze.get("first_reversal_spec_sha256") != FIRST_REVERSAL_SPEC_SHA256:
        raise ValueError("qualified feature freeze refers to a different candidate-pool spec")
    frozen_features = {str(item["feature"]) for item in freeze.get("features", [])}
    if "dd60" not in frozen_features:
        raise ValueError("dd60 is not present in the qualified discovery feature freeze")
    pool, receipt = _verified_pool_period(
        pool_path,
        start="2022-07-01",
        through="2023-12-31",
        features=list(dict.fromkeys([*FEATURE_COLUMNS, "ret1_minus_ret5_per5", "dd60"])),
    )
    if receipt["sha256"] != freeze.get("candidate_pool_sha256"):
        raise ValueError("candidate-pool hash differs from qualified feature freeze")
    return pool, receipt, freeze


def _attach_outcomes(frame: pd.DataFrame, pool_labels: pd.DataFrame) -> pd.DataFrame:
    label_fields = ["date", "symbol", "gross_return", "entry_price", "exit_price", "entry_date", "exit_date", "label_status", "label_resolved", "entry_fill_quality", "label_definition"]
    out = frame.merge(
        pool_labels.loc[:, label_fields],
        on=["date", "symbol"], how="left", validate="many_to_one",
    )
    purged = out["label_status"].isna()
    out.loc[purged, "label_status"] = "PURGED_SPLIT_BOUNDARY"
    out["label_resolved"] = out["label_resolved"].astype("boolean").fillna(False).astype(bool)
    out["gross_return"] = pd.to_numeric(out["gross_return"], errors="coerce")
    return out


def _daily_table(
    selections: pd.DataFrame,
    labels: pd.DataFrame,
    *,
    sessions: pd.DatetimeIndex,
    policy_level: bool,
) -> pd.DataFrame:
    join = ["date", "symbol", "family", "spec_hash"]
    if policy_level:
        join.extend(["policy_id", "top_n"])
    return daily_cohorts(selections, labels, sessions=sessions, join_columns=join)


def _cohort_stats(
    frame: pd.DataFrame,
    *,
    sessions: pd.DatetimeIndex,
    policy_level: bool,
) -> tuple[dict[str, object], pd.DataFrame]:
    gross_daily = _daily_table(frame, frame, sessions=sessions, policy_level=policy_level)
    net_labels = frame.copy()
    net_labels["gross_return"] = np.where(
        net_labels["label_resolved"], net_labels["gross_return"] - ROUND_TRIP_COST, np.nan,
    )
    net_daily = _daily_table(frame, net_labels, sessions=sessions, policy_level=policy_level)
    return {
        "gross": cohort_summary(gross_daily, repetitions=2000),
        "net_cost_0_5pct": cohort_summary(net_daily, repetitions=2000),
        "daily_status_counts": {str(key): int(value) for key, value in net_daily["cohort_status"].value_counts().items()},
    }, net_daily


def _policy_result(
    *,
    ranker_name: str,
    top_n: int,
    selection: Any,
    selected_outcomes: pd.DataFrame,
    pool_outcomes: pd.DataFrame,
    calendar: SessionCalendar,
    period_months: pd.PeriodIndex,
) -> dict[str, Any]:
    active_dates = pd.DatetimeIndex(selected_outcomes.loc[
        selected_outcomes["selected_count"].fillna(0).gt(0), "date"
    ].unique()) if "selected_count" in selected_outcomes else pd.DatetimeIndex(selected_outcomes["date"].unique())
    if "selected_count" in selected_outcomes:
        active_dates = pd.DatetimeIndex(selected_outcomes.loc[selected_outcomes["selected_count"].gt(0), "date"].unique())
    elif "date" in selected_outcomes:
        active_dates = pd.DatetimeIndex(selected_outcomes["date"].unique())
    selected_cohorts, selected_daily = _cohort_stats(
        selected_outcomes,
        sessions=calendar.sessions,
        policy_level=True,
    )
    active = pd.Series(active_dates)
    active_set = set(active_dates)
    pool_active = pool_outcomes.loc[pool_outcomes["date"].isin(active_set)].copy()
    pool_cohorts, pool_daily = _cohort_stats(
        pool_active,
        sessions=calendar.sessions,
        policy_level=False,
    )
    common = selected_daily.merge(
        pool_daily.loc[:, ["date", "cohort_status", "cohort_return"]].rename(
            columns={"cohort_status": "pool_status", "cohort_return": "pool_net_return"}
        ),
        on="date", how="inner",
    )
    common = common.loc[common["cohort_status"].eq("COMPLETE") & common["pool_status"].eq("COMPLETE")]
    value_add = {
        "status": "MATCHED_COMPLETE_DATES_AVAILABLE" if len(common) else "INCONCLUSIVE_NO_COMMON_COMPLETE_DAILY_COHORTS",
        "common_complete_dates": int(len(common)),
        "selected_mean": float(common["cohort_return"].mean()) if len(common) else None,
        "pool_mean": float(common["pool_net_return"].mean()) if len(common) else None,
        "mean_difference_selected_minus_pool": (
            float(common["cohort_return"].mean() - common["pool_net_return"].mean()) if len(common) else None
        ),
    }
    signal = label_summary(selected_outcomes)
    pool_signal = label_summary(pool_active)
    net_signal = signal["round_trip_cost_scenarios"]["0.005"]
    pool_net_signal = pool_signal["round_trip_cost_scenarios"]["0.005"]
    policy_daily = selection.daily.copy()
    policy_daily["month"] = pd.to_datetime(policy_daily["date"]).dt.to_period("M")
    monthly_selected = policy_daily.groupby("month")["selected_count"].sum().reindex(period_months, fill_value=0)
    active_monthly_mean = float(monthly_selected.mean()) if len(monthly_selected) else 0.0
    checks = {
        "net_signal_mean_positive": bool(net_signal["mean"] is not None and net_signal["mean"] > 0),
        "net_signal_median_positive": bool(net_signal["median"] is not None and net_signal["median"] > 0),
        "net_signal_mean_excluding_top3_positive": bool(net_signal["mean_excluding_top3_winners"] is not None and net_signal["mean_excluding_top3_winners"] > 0),
        "net_daily_cohort_mean_positive": bool(selected_cohorts["net_cost_0_5pct"]["mean"] is not None and selected_cohorts["net_cost_0_5pct"]["mean"] > 0),
        "net_daily_cohort_median_positive": bool(selected_cohorts["net_cost_0_5pct"]["median"] is not None and selected_cohorts["net_cost_0_5pct"]["median"] > 0),
        "net_daily_cohort_mean_excluding_top3_positive": bool(selected_cohorts["net_cost_0_5pct"]["mean_excluding_top3_winners"] is not None and selected_cohorts["net_cost_0_5pct"]["mean_excluding_top3_winners"] > 0),
        "matched_date_daily_mean_improved": bool(value_add["mean_difference_selected_minus_pool"] is not None and value_add["mean_difference_selected_minus_pool"] > 0),
        "minus10_no_worse_than_matched_pool_signals": bool(net_signal["minus10_rate"] is not None and pool_net_signal["minus10_rate"] is not None and net_signal["minus10_rate"] <= pool_net_signal["minus10_rate"]),
        "minus20_no_worse_than_matched_pool_signals": bool(net_signal["minus20_rate"] is not None and pool_net_signal["minus20_rate"] is not None and net_signal["minus20_rate"] <= pool_net_signal["minus20_rate"]),
    }
    promotion_eligible = all(checks.values())
    return {
        "ranker": ranker_name,
        "top_n": top_n,
        "policy_id": str(selection.selected["policy_id"].iloc[0]) if not selection.selected.empty else f"fr-{ranker_name}-top{top_n}",
        "ranking_spec_sha256": (
            str(selection.selected["ranking_spec_sha256"].iloc[0])
            if not selection.selected.empty and "ranking_spec_sha256" in selection.selected.columns
            else None
        ),
        "policy_sha256": selection.policy_sha256,
        "selection_sha256": selection.selection_sha256,
        "ranked_candidate_rows": int(len(selection.candidate_trace)),
        "selected_signal_count_including_split_purges": int(len(selection.selected)),
        "selected_active_dates": int(selection.daily["selected_count"].gt(0).sum()),
        "cooldown_blocked_rows": int(selection.daily["cooldown_blocked_count"].sum()),
        "monthly_selected_count_mean_including_zero_months": active_monthly_mean,
        "core_frequency_target_5_per_month_met": bool(active_monthly_mean >= 5.0),
        "selection_signal_metrics": signal,
        "daily_cohort_metrics": selected_cohorts,
        "matched_active_date_pool_signal_metrics": pool_signal,
        "matched_active_date_pool_daily_cohort_metrics": pool_cohorts,
        "ranking_value_add": value_add,
        "promotion_checks": checks,
        "promotion_eligible_on_discovery": promotion_eligible,
    }


def run(
    *,
    source_path: Path = DEFAULT_SOURCE,
    pool_path: Path = DEFAULT_POOL,
    calendar_path: Path = DEFAULT_CALENDAR,
    calendar_manifest_path: Path = DEFAULT_CALENDAR_MANIFEST,
    preservation_manifest_path: Path = DEFAULT_PRESERVATION_MANIFEST,
    qualified_freeze_path: Path = DEFAULT_QUALIFIED_FREEZE,
    output_path: Path = DEFAULT_REPORT,
    selection_freeze_path: Path = DEFAULT_FREEZE,
) -> dict[str, Any]:
    opened_at = _now()
    pool, pool_receipt, feature_freeze = _read_pool(pool_path, freeze_path=qualified_freeze_path)
    calendar_meta = json.loads(calendar_manifest_path.read_text(encoding="utf-8"))
    calendar = SessionCalendar.from_csv(calendar_path, expected_sha256=calendar_meta["csv_sha256"])
    preservation = json.loads(preservation_manifest_path.read_text(encoding="utf-8"))
    source_receipt = next(item for item in preservation["artifacts"] if item["member"] == source_path.name)
    source_sha = sha256_file(source_path)
    if source_sha != source_receipt["member_sha256"] or source_sha != feature_freeze["source_sha256"]:
        raise ValueError("OHLCV source differs from the frozen discovery inputs")

    pool["dd60_rank_missing"] = ~np.isfinite(pd.to_numeric(pool["dd60"], errors="coerce").to_numpy(dtype="float64"))
    pool["dd60_rank_value"] = pd.to_numeric(pool["dd60"], errors="coerce").fillna(-2.0)
    ranked_by_lane: dict[str, pd.DataFrame] = {}
    ranking_hashes: dict[str, str] = {}
    for lane, definition in RANKERS.items():
        terms = [(str(column), bool(ascending)) for column, ascending in definition["terms"]]
        ranked = rank_candidate_pool(
            pool,
            sessions=calendar.sessions,
            feature_columns=definition["features"],
            ranking_terms=terms,
        )
        ranking_spec = {
            "selection_spec_sha256": SELECTION_SPEC_SHA256,
            "lane": lane,
            "terms": definition["terms"],
            "feature_columns": definition["features"],
            "tie_break": "symbol ascending",
            "missing_behavior": definition["missing_behavior"],
        }
        ranking_hash = hashlib.sha256(
            json.dumps(ranking_spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        ranked["ranking_spec_sha256"] = ranking_hash
        ranked_by_lane[lane] = ranked
        ranking_hashes[lane] = ranking_hash

    policy_results: dict[str, Any] = {}
    selected_parts: list[pd.DataFrame] = []
    selection_objects: dict[str, Any] = {}
    for lane, ranked in ranked_by_lane.items():
        for top_n in TOP_N_VALUES:
            policy_id = f"fr-{lane}-top{top_n}"
            result = apply_selection_policy(
                ranked,
                sessions=calendar.sessions,
                policy=PolicySpec("core", top_n, policy_id),
            )
            selected = result.selected.copy()
            selected["ranking_lane"] = lane
            selected["ranking_spec_sha256"] = ranking_hashes[lane]
            selected_parts.append(selected)
            selection_objects[policy_id] = result

    all_selected = pd.concat(selected_parts, ignore_index=True) if selected_parts else pool.iloc[0:0].copy()
    year_ends = {year: _session_end(calendar, year) for year in (2022, 2023)}
    positions = calendar.sessions.get_indexer(pd.DatetimeIndex(pool["date"]))
    cutoff_positions = {year: calendar.position(end) for year, end in year_ends.items()}
    labelable = np.array([
        positions[idx] + 5 <= cutoff_positions[int(day.year)]
        for idx, day in enumerate(pool["date"])
    ], dtype=bool)
    labelable_pool = pool.loc[labelable].copy()
    purge_pool_count = int((~labelable).sum())
    prices = _read_prices_through(source_path, through=year_ends[2023])
    pool_labels = build_five_session_labels(prices, labelable_pool, calendar)
    if pool_labels["exit_date"].gt(pool_labels["date"].map(
        lambda day: year_ends[int(day.year)]
    )).any():
        raise RuntimeError("candidate-pool outcomes crossed a discovery split boundary")
    pool_outcomes = _attach_outcomes(pool, pool_labels)
    selected_outcomes = _attach_outcomes(all_selected, pool_labels)

    periods = pd.period_range("2022-07", "2023-12", freq="M")
    for policy_id, selection in selection_objects.items():
        parts = selected_outcomes.loc[selected_outcomes["policy_id"].eq(policy_id)].copy()
        result = _policy_result(
            ranker_name=str(parts["ranking_lane"].iloc[0]) if not parts.empty else policy_id.rsplit("-top", 1)[0].removeprefix("fr-"),
            top_n=int(parts["top_n"].iloc[0]) if not parts.empty else int(policy_id.rsplit("top", 1)[1]),
            selection=selection,
            selected_outcomes=parts,
            pool_outcomes=pool_outcomes,
            calendar=calendar,
            period_months=periods,
        )
        result["split_purged_selected_count"] = int(parts["label_status"].eq("PURGED_SPLIT_BOUNDARY").sum())
        result["split_purged_candidate_pool_count"] = purge_pool_count
        policy_results[policy_id] = result

    eligible = [
        (policy_id, result) for policy_id, result in policy_results.items()
        if result["promotion_eligible_on_discovery"]
    ]
    eligible.sort(key=lambda pair: (
        -float(pair[1]["daily_cohort_metrics"]["net_cost_0_5pct"]["mean"]),
        int(pair[1]["top_n"]), str(pair[1]["ranker"]),
    ))
    chosen = eligible[0] if eligible else None
    freeze: dict[str, Any] | None = None
    if chosen:
        policy_id, result = chosen
        freeze = {
            "schema_version": 1,
            "experiment_id": "TVF-FR-TOPN-20260913-01",
            "spec_id": "first_reversal_discovery_selection_freeze_v1",
            "spec_sha256": SELECTION_SPEC_SHA256,
            "created_at_utc": _now(),
            "source_sha256": source_sha,
            "candidate_pool_sha256": pool_receipt["sha256"],
            "candidate_pool_spec_sha256": FIRST_REVERSAL_SPEC_SHA256,
            "qualified_feature_freeze_sha256": sha256_file(qualified_freeze_path),
            "calendar_sha256": calendar.sha256,
            "policy_id": policy_id,
            "ranker": result["ranker"],
            "ranking_spec_sha256": ranking_hashes[str(result["ranker"])],
            "top_n": result["top_n"],
            "selection_sha256": result["selection_sha256"],
            "policy_sha256": result["policy_sha256"],
            "missing_feature_behavior": RANKERS[str(result["ranker"])]["missing_behavior"],
            "feature_timestamp": "signal-date official-session close; lagged market prefilter as fixed in candidate spec",
            "cooldown": "previous official TSE session; update state only with selected symbols; per policy",
            "tie_break": "raw rank then symbol ascending",
            "evidence_level": "RETROSPECTIVE_PROVISIONAL",
        }
        _write_json(selection_freeze_path, freeze)

    report = {
        "schema_version": 1,
        "experiment_id": "TVF-FR-TOPN-20260913-01",
        "phase": "discovery_only_top_n_ranker_comparison",
        "phase_opened_at_utc": opened_at,
        "created_at_utc": _now(),
        "spec_sha256": SELECTION_SPEC_SHA256,
        "candidate_pool_sha256": pool_receipt["sha256"],
        "candidate_pool_spec_sha256": FIRST_REVERSAL_SPEC_SHA256,
        "qualified_feature_freeze_sha256": sha256_file(qualified_freeze_path),
        "source_sha256": source_sha,
        "calendar_sha256": calendar.sha256,
        "candidate_pool_rows": int(len(pool)),
        "labelable_candidate_pool_rows": int(len(labelable_pool)),
        "split_purged_candidate_pool_rows": purge_pool_count,
        "candidate_pool_outcomes": label_summary(pool_outcomes),
        "policy_results": policy_results,
        "promotion_eligible_policy_count": len(eligible),
        "frozen_policy": freeze,
        "decision": "LOCK_POLICY_FOR_2024_CONFIRMATION" if freeze else "SELECTION_COUNT_UNRESOLVED",
        "evidence_level": "RETROSPECTIVE_PROVISIONAL",
        "caveat": "Historical 2024 aggregate First Reversal results were previously disclosed. Any next-year check is retrospective confirmation, not independent OOS.",
    }
    _write_json(output_path, report)
    return {"report": str(output_path), "decision": report["decision"], "frozen_policy": freeze, "policy_count": len(policy_results), "eligible_policy_count": len(eligible)}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--pool", type=Path, default=DEFAULT_POOL)
    parser.add_argument("--calendar", type=Path, default=DEFAULT_CALENDAR)
    parser.add_argument("--calendar-manifest", type=Path, default=DEFAULT_CALENDAR_MANIFEST)
    parser.add_argument("--preservation-manifest", type=Path, default=DEFAULT_PRESERVATION_MANIFEST)
    parser.add_argument("--qualified-freeze", type=Path, default=DEFAULT_QUALIFIED_FREEZE)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--selection-freeze", type=Path, default=DEFAULT_FREEZE)
    args = parser.parse_args()
    result = run(
        source_path=args.source,
        pool_path=args.pool,
        calendar_path=args.calendar,
        calendar_manifest_path=args.calendar_manifest,
        preservation_manifest_path=args.preservation_manifest,
        qualified_freeze_path=args.qualified_freeze,
        output_path=args.output,
        selection_freeze_path=args.selection_freeze,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
