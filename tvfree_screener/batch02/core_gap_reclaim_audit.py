"""Pre-registered discovery runner for a daily gap-down reclaim Core hypothesis."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from tvfree_screener.batch01 import core_moderate_ridge_audit as label_builder
from tvfree_screener.batch01.evaluation import label_summary
from tvfree_screener.batch01.session_calendar import SessionCalendar
from tvfree_screener.batch02 import core_trend_compression_audit as metrics
from tvfree_screener.batch02.core_gap_reclaim import (
    DAILY_SCORE_QUANTILE,
    FAMILY,
    GAP_MAX,
    POLICY,
    RECLAIM_MAX_EXCLUSIVE,
    RECLAIM_MIN,
    CLOSE_LOCATION_MIN,
    build_candidate_pool,
    rank_candidates,
    select_candidates,
)


BATCH = Path(__file__).resolve().parent
B1 = BATCH.parent / "batch01"
SPEC = BATCH / "reports/core_gap_reclaim_spec.json"
SPEC_SHA = BATCH / "reports/core_gap_reclaim_spec.sha256"
FEATURE = B1 / ".cache/core_moderate_features_through_2023.parquet"
FEATURE_MANIFEST = FEATURE.with_suffix(FEATURE.suffix + ".manifest.json")
CALENDAR = B1 / "reference/xtks_sessions.csv"
CALENDAR_MANIFEST = B1 / "reference/xtks_sessions.manifest.json"
CACHE = BATCH / ".cache"
POOL = CACHE / "core_gap_reclaim_candidate_pool.parquet"
RANKED = CACHE / "core_gap_reclaim_ranked_pool.parquet"
SELECTED = CACHE / "core_gap_reclaim_selected.parquet"
PREPARE = CACHE / "core_gap_reclaim_prepare_receipt.json"
LABELS = CACHE / "core_gap_reclaim_discovery_labels.parquet"
REPORT = BATCH / "reports/core_gap_reclaim_discovery.json"
REPORT_MD = BATCH / "reports/core_gap_reclaim_discovery.md"
START = pd.Timestamp("2022-07-01")
LAST_SIGNAL = pd.Timestamp("2023-12-22")
LAST_EXIT = pd.Timestamp("2023-12-29")
COSTS = (0.0, 0.005, 0.01)
PRIMARY_COST = 0.005
FREQUENCY_TARGET_PER_MONTH = 5.0


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def digest_frame(frame: pd.DataFrame, columns: list[str]) -> str:
    part = frame.loc[:, columns].copy()
    part["date"] = pd.to_datetime(part["date"], errors="raise").dt.strftime("%Y-%m-%d")
    part["symbol"] = part["symbol"].astype("string")
    digest = hashlib.sha256()
    for start in range(0, len(part), 100_000):
        values = pd.util.hash_pandas_object(part.iloc[start:start + 100_000], index=False, categorize=True)
        digest.update(values.to_numpy(dtype="uint64").tobytes())
    return digest.hexdigest()


def input_hashes() -> dict[str, str]:
    feature_manifest = json.loads(FEATURE_MANIFEST.read_text(encoding="utf-8"))
    calendar_manifest = json.loads(CALENDAR_MANIFEST.read_text(encoding="utf-8"))
    feature_hash = sha(FEATURE)
    calendar_hash = sha(CALENDAR)
    if feature_hash != feature_manifest["sha256"] or feature_manifest["labels_included"] is not False:
        raise ValueError("decision-only feature panel hash or outcome-free receipt mismatch")
    if feature_manifest["through"] != LAST_EXIT.date().isoformat():
        raise ValueError("bounded feature panel does not end at the registered discovery horizon")
    if calendar_hash != calendar_manifest["csv_sha256"]:
        raise ValueError("XTKS calendar hash differs from manifest")
    return {
        "feature_sha256": feature_hash,
        "feature_manifest_sha256": sha(FEATURE_MANIFEST),
        "daily_source_sha256": str(feature_manifest["source_sha256"]),
        "calendar_sha256": calendar_hash,
        "calendar_manifest_sha256": sha(CALENDAR_MANIFEST),
    }


def implementation_hashes() -> dict[str, str]:
    code = {
        "hypothesis": BATCH / "core_gap_reclaim.py",
        "audit_runner": Path(__file__),
        "frozen_label_builder": Path(label_builder.__file__),
        "candidate_metrics": BATCH / "core_trend_compression_audit.py",
        "evaluation_helper": B1 / "evaluation.py",
        "session_calendar": B1 / "session_calendar.py",
        "feature_panel": B1 / "feature_panel.py",
    }
    return {name: sha(path) for name, path in code.items()}


def freeze_spec() -> dict[str, object]:
    if PREPARE.exists() or REPORT.exists() or REPORT_MD.exists() or LABELS.exists():
        raise FileExistsError("gap-reclaim preparation or outcome artifacts already exist")
    inputs = input_hashes()
    spec: dict[str, object] = {
        "schema_version": 1,
        "experiment_id": "CORE-GAP-DOWN-PARTIAL-RECLAIM-20260913-01",
        "family": FAMILY,
        "registered_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FROZEN_BEFORE_DISCOVERY_FEATURE_READ",
        "evidence_level": "RETROSPECTIVE_PROVISIONAL",
        "hypothesis": "A daily gap-down that recovers at least half, but not all, of its opening gap and closes in the top quarter of its range may reflect absorption of opening sell pressure before a multi-session rebound.",
        "historical_exposure": "2022H2-2023 returns have been viewed in other families and are not an untouched OOS sample. This is one preregistered retrospective screen; do not tune it toward these outcomes.",
        "data": {
            "feature_panel": str(FEATURE.relative_to(BATCH.parents[1])).replace("\\", "/"),
            "feature_sha256": inputs["feature_sha256"],
            "feature_manifest_sha256": inputs["feature_manifest_sha256"],
            "source_daily_sha256": inputs["daily_source_sha256"],
            "calendar_sha256": inputs["calendar_sha256"],
            "feature_timestamp": "official XTKS session close; every used field is available by that close",
            "ohlcv_source_cutoff": LAST_EXIT.date().isoformat(),
            "2024_plus_numeric_ohlcv_opened": False,
        },
        "candidate_pool": {
            "universe": "Every symbol/session in the frozen daily feature panel with complete, internally consistent positive signal-day OHLCV and finite gap/close-location inputs; no current-list substitution is applied within this dataset.",
            "gap": f"open / prior official XTKS close - 1 <= {GAP_MAX}",
            "close_location": f"(close - low) / (high - low) >= {CLOSE_LOCATION_MIN}",
            "partial_reclaim": f"0 < (close - open) / (prior close - open), with fraction >= {RECLAIM_MIN} and < {RECLAIM_MAX_EXCLUSIVE}; this implies close remains below prior close and excludes the First Reversal positive-ret1 setup.",
            "no_market_regime_filter": True,
            "no_volume_or_fundamental_filter": True,
            "no_future_or_outcome_fields": True,
        },
        "score_and_selection": {
            "score": "Equal-weight arithmetic mean of close_location and gap_reclaim_fraction; no fitted weights.",
            "daily_threshold": f"Within each XTKS date's complete frozen candidate pool, select every score >= the linear empirical {DAILY_SCORE_QUANTILE:.0%} quantile. Include all ties; no Top-N cap.",
            "tie_breaks": ["score descending", "gap_reclaim_fraction descending", "close_location descending", "symbol ascending"],
            "cooldown": "One immediately prior official XTKS session per selected symbol; only actually selected rows update cooldown state.",
            "multiple_names_per_day": True,
            "empty_day": "Abstain; do not substitute another signal or lower the threshold.",
        },
        "target": "Signal date official close is used only for signal-time features; enter at next official XTKS session open and exit at close of the fifth XTKS session including entry. Return = exit close / entry open - 1.",
        "actionability": "Reuse the frozen core_moderate_ridge_audit.build_labels_for_eligible_signals builder. Retain each selected/candidate row, including missing bars, zero/unknown volume, invalid OHLC, or extreme-gap statuses; no row substitution.",
        "periods": {
            "discovery_start": START.date().isoformat(),
            "last_signal": LAST_SIGNAL.date().isoformat(),
            "last_exit": LAST_EXIT.date().isoformat(),
            "2024": "Open only if frozen discovery gate passes; retrospective confirmation, never called untouched OOS.",
            "2025": "Open only after separate 2024 pass and separate frozen replay; prior cross-family exposure must be disclosed.",
            "2026": "Report-only; never tune or promote from 2026.",
        },
        "cost_scenarios": list(COSTS),
        "primary_round_trip_cost_assumption": PRIMARY_COST,
        "discovery_gates": {
            "resolved_signals_minimum": 75,
            "average_selected_signals_per_calendar_month_minimum": FREQUENCY_TARGET_PER_MONTH,
            "signal_net_at_0_5pct": ["mean > 0", "median > 0", "win rate > 0.50", "mean excluding top three winners > 0"],
            "resolved_label_coverage_minimum": 0.90,
            "negative_tail_vs_candidate_pool": ["-10% rate no higher", "-20% rate no higher"],
            "monthly_robustness": "At least half of months with resolved selections have positive net mean.",
            "complete_daily_cohort": "At least 20 complete selected-date cohorts and positive net mean, median, and top-three-excluded mean; report partial and abstain dates without reweighting.",
            "decision": "Only a pass may open a separately frozen 2024 confirmation. No parameter adjustment follows a failure.",
        },
        "benchmark_context": {
            "current_bot_stable6": {"n": 55, "mean": 0.066, "median": 0.015, "win_rate": 0.564},
            "directly_comparable": False,
            "reason": "Current Bot statistics use TradingView BOTTOM events and a different signal/entry timestamp; this study uses all-TSE daily events and next-session-open entry.",
        },
        "inputs": inputs,
        "implementation_sha256": implementation_hashes(),
        "production_modified": False,
    }
    payload = json.dumps(spec, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    SPEC.parent.mkdir(parents=True, exist_ok=True)
    SPEC.write_bytes(payload.encode("utf-8"))
    SPEC_SHA.write_text(sha(SPEC) + "  " + SPEC.name + "\n", encoding="utf-8")
    return spec


def verify_spec() -> tuple[dict[str, object], pd.DataFrame, SessionCalendar]:
    raw = SPEC.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SPEC_SHA.read_text(encoding="utf-8").split()[0]:
        raise ValueError("gap-reclaim spec hash mismatch")
    spec = json.loads(raw)
    if spec["implementation_sha256"] != implementation_hashes():
        raise ValueError("gap-reclaim implementation changed after freeze")
    if spec["inputs"] != input_hashes():
        raise ValueError("gap-reclaim input hash or manifest changed after freeze")
    calendar_manifest = json.loads(CALENDAR_MANIFEST.read_text(encoding="utf-8"))
    calendar = SessionCalendar.from_csv(CALENDAR, expected_sha256=str(calendar_manifest["csv_sha256"]))
    return spec, json.loads(FEATURE_MANIFEST.read_text(encoding="utf-8")), calendar


def _read_feature_panel() -> pd.DataFrame:
    columns = ["date", "symbol", "open", "high", "low", "close", "volume", "gap", "close_location"]
    panel = pd.read_parquet(FEATURE, columns=columns)
    panel["date"] = pd.to_datetime(panel["date"], errors="raise").dt.normalize()
    panel["symbol"] = panel["symbol"].astype("string")
    return panel


def _decision_hashes(pool: pd.DataFrame, ranked: pd.DataFrame, selected: pd.DataFrame) -> dict[str, str]:
    common = ["date", "symbol", "score", "gap", "close_location", "gap_reclaim_fraction"]
    return {
        "pool": digest_frame(pool, common),
        "ranked": digest_frame(ranked, common + ["daily_score_cutoff", "daily_candidate_count", "raw_rank"]),
        "selected": digest_frame(selected, common + ["daily_score_cutoff", "daily_candidate_count", "raw_rank", "policy_id", "policy_rank", "selection_status"]),
    }


def _create_decisions(panel: pd.DataFrame, calendar: SessionCalendar, spec_hash: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, int]]:
    pool, counts = build_candidate_pool(panel, start=START, end=LAST_SIGNAL)
    pool["family"] = FAMILY
    pool["spec_hash"] = spec_hash
    ranked = rank_candidates(pool)
    ranked["spec_hash"] = spec_hash
    selected = select_candidates(ranked, calendar.sessions)
    selected["spec_hash"] = spec_hash
    return pool, ranked, selected, counts


def prepare() -> dict[str, object]:
    if PREPARE.exists() or POOL.exists() or RANKED.exists() or SELECTED.exists():
        raise FileExistsError("gap-reclaim decision artifacts already exist")
    spec, feature_manifest, calendar = verify_spec()
    panel = _read_feature_panel()
    family_sha = hashlib.sha256(SPEC.read_bytes()).hexdigest()
    pool, ranked, selected, counts = _create_decisions(panel, calendar, family_sha)
    if selected["date"].gt(LAST_SIGNAL).any() or pool["date"].lt(START).any():
        raise ValueError("gap-reclaim decisions escaped the frozen discovery period")
    CACHE.mkdir(parents=True, exist_ok=True)
    pool.to_parquet(POOL, index=False, compression="zstd")
    ranked.to_parquet(RANKED, index=False, compression="zstd")
    selected.to_parquet(SELECTED, index=False, compression="zstd")
    hashes = _decision_hashes(pool, ranked, selected)
    month_count = len(pd.period_range(START.to_period("M"), LAST_SIGNAL.to_period("M"), freq="M"))
    counts["ranked_candidate_rows"] = int(len(ranked))
    counts["selected_rows"] = int(len(selected))
    counts["active_selection_days"] = int(selected["date"].nunique())
    counts["empty_candidate_days"] = int(len(calendar.sessions[(calendar.sessions >= START) & (calendar.sessions <= LAST_SIGNAL)]) - pool["date"].nunique())
    counts["empty_selection_days"] = int(len(calendar.sessions[(calendar.sessions >= START) & (calendar.sessions <= LAST_SIGNAL)]) - selected["date"].nunique())
    counts["discovery_months_including_zero_months"] = int(month_count)
    counts["mean_selected_per_calendar_month"] = float(len(selected) / month_count) if month_count else 0.0
    receipt = {
        "schema_version": 1,
        "experiment_id": spec["experiment_id"],
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "spec_sha256": family_sha,
        "input_hashes": spec["inputs"],
        "candidate_rule_parameters": spec["candidate_pool"],
        "score_and_selection_parameters": spec["score_and_selection"],
        "implementation_sha256": spec["implementation_sha256"],
        "counts": counts,
        "decision_hashes": hashes,
        "artifact_sha256": {"pool": sha(POOL), "ranked": sha(RANKED), "selected": sha(SELECTED)},
        "outcome_values_opened": False,
        "later_periods_opened": False,
        "production_modified": False,
    }
    PREPARE.write_text(json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return receipt


def verify_prepare() -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame, pd.DataFrame, SessionCalendar]:
    spec, _feature_manifest, calendar = verify_spec()
    receipt = json.loads(PREPARE.read_text(encoding="utf-8"))
    if receipt["spec_sha256"] != hashlib.sha256(SPEC.read_bytes()).hexdigest():
        raise ValueError("gap-reclaim preparation is for a different spec")
    paths = {"pool": POOL, "ranked": RANKED, "selected": SELECTED}
    if {key: sha(path) for key, path in paths.items()} != receipt["artifact_sha256"]:
        raise ValueError("gap-reclaim frozen decision artifact hash mismatch")
    pool = pd.read_parquet(POOL)
    ranked = pd.read_parquet(RANKED)
    selected = pd.read_parquet(SELECTED)
    panel = _read_feature_panel()
    reproduced = _create_decisions(panel, calendar, receipt["spec_sha256"])
    reproduced_hashes = _decision_hashes(*reproduced[:3])
    if reproduced_hashes != receipt["decision_hashes"]:
        raise ValueError("gap-reclaim candidate pool, ranking, or selection did not reproduce")
    return spec, pool, ranked, selected, calendar


def _build_labels(pool: pd.DataFrame, calendar: SessionCalendar, spec_hash: str, prices: pd.DataFrame) -> pd.DataFrame:
    signals = pool.loc[:, ["date", "symbol", "close"]].copy()
    labels = label_builder.build_labels_for_eligible_signals(prices, signals, calendar)
    labels["family"] = FAMILY
    labels["spec_hash"] = spec_hash
    positions = {pd.Timestamp(day): i for i, day in enumerate(calendar.sessions)}
    labels["session_index"] = labels["date"].map(positions).astype("int32")
    if len(labels) != len(pool) or labels.duplicated(["date", "symbol"]).any():
        raise ValueError("canonical gap-reclaim label build lost or duplicated candidate rows")
    return labels


def _join(decisions: pd.DataFrame, labels: pd.DataFrame, calendar: SessionCalendar) -> pd.DataFrame:
    keys = ["date", "symbol"]
    left = decisions.loc[:, keys].copy()
    left["date"] = pd.to_datetime(left["date"], errors="raise").dt.normalize()
    left["symbol"] = left["symbol"].astype("string")
    right = labels.loc[:, [
        "date", "symbol", "entry_date", "exit_date", "entry_price", "exit_price",
        "gross_return", "label_status", "label_resolved", "label_available_at",
        "family", "spec_hash", "session_index",
    ]]
    out = left.merge(right, on=keys, how="left", validate="one_to_one", indicator=True)
    if out["_merge"].ne("both").any():
        raise ValueError("frozen gap-reclaim decision has no canonical label row")
    out = out.drop(columns="_merge")
    if not out["label_resolved"].equals(out["label_status"].eq("RESOLVED")):
        raise ValueError("gap-reclaim label resolution/status mismatch")
    position = {pd.Timestamp(day): i for i, day in enumerate(calendar.sessions)}
    signal_positions = out["date"].map(position).to_numpy(dtype="int64")
    expected_entry = pd.DatetimeIndex(calendar.sessions[signal_positions + 1])
    expected_exit = pd.DatetimeIndex(calendar.sessions[signal_positions + 5])
    if not pd.DatetimeIndex(out["entry_date"]).equals(expected_entry) or not pd.DatetimeIndex(out["exit_date"]).equals(expected_exit):
        raise ValueError("gap-reclaim target date differs from the frozen next-open/fifth-close target")
    resolved = out["label_resolved"].fillna(False).astype(bool)
    numeric = out.loc[resolved, ["gross_return", "entry_price", "exit_price"]].apply(pd.to_numeric, errors="coerce")
    if len(numeric) and (not np.isfinite(numeric.to_numpy()).all() or (numeric["entry_price"] <= 0).any()):
        raise ValueError("resolved gap-reclaim labels have invalid prices")
    if len(numeric) and not np.allclose(numeric["exit_price"] / numeric["entry_price"] - 1.0, numeric["gross_return"], rtol=1e-8, atol=1e-10):
        raise ValueError("gap-reclaim label return does not match entry/exit prices")
    return out


def evaluate() -> dict[str, object]:
    if REPORT.exists() or REPORT_MD.exists() or LABELS.exists():
        raise FileExistsError("gap-reclaim outcome report or labels already exist")
    spec, pool, ranked, selected, calendar = verify_prepare()
    if pool.empty or selected.empty:
        receipt = json.loads(PREPARE.read_text(encoding="utf-8"))
        result: dict[str, object] = {
            "schema_version": 1,
            "experiment_id": spec["experiment_id"],
            "evidence_level": spec["evidence_level"],
            "decision": "REJECT_NO_ACTIONABLE_CANDIDATES",
            "spec_sha256": hashlib.sha256(SPEC.read_bytes()).hexdigest(),
            "prepare_receipt_sha256": sha(PREPARE),
            "decision_hashes": receipt["decision_hashes"],
            "candidate_counts": receipt["counts"],
            "outcome_values_opened": False,
            "reason": "The frozen signal-time rules produced no selected candidates; no outcome labels were opened.",
            "production_modified": False,
        }
        REPORT.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        REPORT_MD.write_text(
            "# Core Gap-Down Partial Reclaim — discovery\n\n"
            "- Decision: `REJECT_NO_ACTIONABLE_CANDIDATES`.\n"
            "- The frozen signal-time rules produced no selected candidates; outcome labels were not opened.\n"
            "- No threshold or selection adjustment was made.\n",
            encoding="utf-8",
        )
        return result
    prices = pd.read_parquet(FEATURE, columns=["date", "symbol", "open", "high", "low", "close", "volume"])
    prices["date"] = pd.to_datetime(prices["date"], errors="raise").dt.normalize()
    prices["symbol"] = prices["symbol"].astype("string")
    if prices["date"].max() != LAST_EXIT or prices.duplicated(["date", "symbol"]).any():
        raise ValueError("bounded OHLCV price panel is inconsistent with the frozen final exit")
    labels = _build_labels(pool, calendar, hashlib.sha256(SPEC.read_bytes()).hexdigest(), prices)
    LABELS.parent.mkdir(parents=True, exist_ok=True)
    labels.to_parquet(LABELS, index=False, compression="zstd")
    pool_joined = _join(pool, labels, calendar)
    selected_joined = _join(selected, labels, calendar)
    pool_stats = label_summary(pool_joined, costs=COSTS)
    selected_stats = label_summary(selected_joined, costs=COSTS)
    pool_segments = metrics.segment_metrics(pool_joined)
    selected_segments = metrics.segment_metrics(selected_joined)
    active = calendar.sessions[(calendar.sessions >= START) & (calendar.sessions <= LAST_SIGNAL)]
    pool_cohort, pool_daily = metrics.cohort(pool, pool_joined, active)
    selected_cohort, selected_daily = metrics.cohort(selected, selected_joined, active)
    months = pd.period_range(START.to_period("M"), LAST_SIGNAL.to_period("M"), freq="M")
    selected_month_counts = selected.groupby(selected["date"].dt.to_period("M"), sort=True).size().reindex(months, fill_value=0)
    resolved = selected_joined.loc[selected_joined["label_resolved"].fillna(False)].copy()
    resolved["net"] = pd.to_numeric(resolved["gross_return"], errors="coerce") - PRIMARY_COST
    resolved["month"] = resolved["date"].dt.to_period("M").astype(str)
    monthly_net = {str(k): metrics.return_metrics(g["net"], requested_count=len(g)) for k, g in resolved.groupby("month", sort=True)}
    positive_months = sum(value["mean"] is not None and value["mean"] > 0 for value in monthly_net.values())
    month_share = float(positive_months / len(monthly_net)) if monthly_net else 0.0
    net = selected_stats["round_trip_cost_scenarios"][f"{PRIMARY_COST:g}"]
    pool_net = pool_stats["round_trip_cost_scenarios"][f"{PRIMARY_COST:g}"]
    coverage = float(selected_stats["resolved_count"] / selected_stats["selected_count"]) if selected_stats["selected_count"] else 0.0
    frequency = float(selected_month_counts.mean()) if len(selected_month_counts) else 0.0
    tail_not_worse = all(net[key] is not None and pool_net[key] is not None and net[key] <= pool_net[key] for key in ("minus10_rate", "minus20_rate"))
    cohort_coverage = {
        "active_xtks_sessions": int(len(active)),
        "complete_days": int(selected_daily["cohort_status"].eq("COMPLETE").sum()),
        "partial_days": int(selected_daily["cohort_status"].eq("PARTIAL_UNRESOLVED").sum()),
        "abstain_days": int(selected_daily["cohort_status"].eq("ABSTAIN").sum()),
    }
    positive_signal = metrics.positive(net) and net["win_rate"] is not None and net["win_rate"] > 0.50
    positive_cohort = metrics.positive(selected_cohort)
    gates = {
        "resolved_signals_minimum": int(selected_stats["resolved_count"]) >= 75,
        "frequency_target": frequency >= FREQUENCY_TARGET_PER_MONTH,
        "signal_mean_median_win_top3_exclusion": bool(positive_signal),
        "resolved_label_coverage": coverage >= 0.90,
        "negative_tail_not_worse_than_full_candidate_pool": bool(tail_not_worse),
        "at_least_half_active_months_positive": month_share >= 0.50,
        "complete_cohort_sample_and_positive_metrics": cohort_coverage["complete_days"] >= 20 and bool(positive_cohort),
    }
    decision = "PASS_DISCOVERY_REQUIRES_SEPARATE_2024_FREEZE" if all(gates.values()) else "REJECT_GAP_RECLAIM_DISCOVERY"
    result: dict[str, object] = {
        "schema_version": 1,
        "experiment_id": spec["experiment_id"],
        "evidence_level": spec["evidence_level"],
        "decision": decision,
        "spec_sha256": hashlib.sha256(SPEC.read_bytes()).hexdigest(),
        "prepare_receipt_sha256": sha(PREPARE),
        "runner_sha256": sha(Path(__file__)),
        "implementation_sha256": spec["implementation_sha256"],
        "input_hashes": spec["inputs"],
        "decision_hashes": json.loads(PREPARE.read_text(encoding="utf-8"))["decision_hashes"],
        "labels_sha256": sha(LABELS),
        "outcome_values_opened_at_utc": datetime.now(timezone.utc).isoformat(),
        "feature_values_used_from_later_dates": False,
        "later_numeric_ohlcv_opened": False,
        "period": f"{START.date()} through {LAST_SIGNAL.date()}; all exits no later than {LAST_EXIT.date()}",
        "candidate_pool": {
            "counts": json.loads(PREPARE.read_text(encoding="utf-8"))["counts"],
            "signal_metrics": pool_stats,
            "segments_and_concentration": pool_segments,
            "complete_daily_cohort_net_0_5pct": pool_cohort,
            "daily_coverage": {
                "active_days": int(pool_daily["selected_count"].gt(0).sum()),
                "complete_days": int(pool_daily["cohort_status"].eq("COMPLETE").sum()),
                "partial_days": int(pool_daily["cohort_status"].eq("PARTIAL_UNRESOLVED").sum()),
                "abstain_days": int(pool_daily["cohort_status"].eq("ABSTAIN").sum()),
            },
        },
        "selected_policy": {
            "policy": spec["score_and_selection"],
            "selected_count": int(len(selected)),
            "signal_metrics": selected_stats,
            "segments_and_concentration": selected_segments,
            "complete_daily_cohort_net_0_5pct": selected_cohort,
            "daily_coverage": cohort_coverage,
            "selected_per_calendar_month": {str(month): int(count) for month, count in selected_month_counts.items()},
            "mean_selected_per_month_including_zero_months": frequency,
            "months_with_resolved_signals": len(monthly_net),
            "positive_months": int(positive_months),
            "positive_month_share": month_share,
            "monthly_net_metrics": monthly_net,
        },
        "gates": gates,
        "current_system_benchmark_context": spec["benchmark_context"],
        "complexity": "Low: four fixed setup gates, equal-weight two-feature score, one daily cross-sectional quantile, and one-session symbol cooldown.",
        "reproducibility": {
            "candidate_pool_ranking_and_selection_reproduced_before_outcomes": True,
            "full_candidate_pool_label_rows": int(len(labels)),
            "all_unresolved_rows_retained": True,
            "2024_2025_2026_outcomes_opened": False,
        },
        "production_modified": False,
    }
    REPORT.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    lines = [
        "# Core Gap-Down Partial Reclaim — discovery",
        "",
        f"- Decision: `{decision}`.",
        "- This is retrospective screening evidence; these years were already viewed in other families and are not untouched OOS.",
        "- Candidate, score, q80 policy, and cooldown were frozen before outcomes. There is no Top-N cap; all ties at the daily q80 cutoff are selected.",
        "- The 2024+ numerical OHLCV values were not opened. Failure means reject this family without threshold tuning.",
        "- Primary return subtracts a hypothetical 0.5% round-trip cost; actual fills and friction are unmeasured.",
        "",
        "| Selected | Resolved | Coverage | Net mean | Median | Win | +10% | +20% | +50% | -10% | -20% | Ex-top1 mean | Ex-top3 mean | Complete days | Avg/month | Positive months | Gate |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    lines.append(
        f"| {selected_stats['selected_count']} | {selected_stats['resolved_count']} | {coverage:.3f} | {net['mean']} | {net['median']} | {net['win_rate']} | "
        f"{net['plus10_rate']} | {net['plus20_rate']} | {net['plus50_rate']} | {net['minus10_rate']} | {net['minus20_rate']} | "
        f"{net['mean_excluding_top1_winner']} | {net['mean_excluding_top3_winners']} | {cohort_coverage['complete_days']} | {frequency:.2f} | {positive_months}/{len(monthly_net)} | {decision} |"
    )
    lines.extend([
        "",
        f"The unchanged full candidate pool contains {len(pool)} signals; its resolved net mean / median / win rate are {pool_net['mean']} / {pool_net['median']} / {pool_net['win_rate']}.",
        "The current Bot context is not directly comparable because its BOTTOM-signal timing and entry definition differ.",
    ])
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("freeze", "prepare", "verify-prepare", "evaluate"))
    args = parser.parse_args()
    if args.command == "freeze":
        spec = freeze_spec()
        print(json.dumps({"status": spec["status"], "spec_sha256": sha(SPEC)}, indent=2))
    elif args.command == "prepare":
        receipt = prepare()
        print(json.dumps({"counts": receipt["counts"], "decision_hashes": receipt["decision_hashes"]}, ensure_ascii=False, indent=2))
    elif args.command == "verify-prepare":
        spec, pool, ranked, selected, _calendar = verify_prepare()
        print(json.dumps({"status": "PREPARE_REPRODUCED", "candidate_rows": len(pool), "ranked_rows": len(ranked), "selected_rows": len(selected), "spec": spec["experiment_id"]}, indent=2))
    else:
        report = evaluate()
        if "selected_policy" not in report:
            print(json.dumps({"decision": report["decision"], "candidate_counts": report["candidate_counts"]}, ensure_ascii=False, indent=2))
            return
        net = report["selected_policy"]["signal_metrics"]["round_trip_cost_scenarios"][f"{PRIMARY_COST:g}"]
        print(json.dumps({
            "decision": report["decision"],
            "candidate_rows": report["candidate_pool"]["counts"]["candidate_rows"],
            "selected": report["selected_policy"]["selected_count"],
            "resolved": report["selected_policy"]["signal_metrics"]["resolved_count"],
            "net_mean": net["mean"],
            "median": net["median"],
            "win_rate": net["win_rate"],
            "coverage": report["selected_policy"]["signal_metrics"]["resolved_count"] / max(1, report["selected_policy"]["selected_count"]),
            "gates": report["gates"],
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
