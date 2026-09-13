"""Repair only report-side selection/label joins for the frozen support-sweep run."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from tvfree_screener.batch01 import core_moderate_ridge_audit as label_builder
from tvfree_screener.batch01.evaluation import cohort_summary, daily_cohorts, label_summary
from tvfree_screener.batch02 import core_support_sweep as strategy
from tvfree_screener.batch02 import core_support_sweep_audit as audit


BATCH = Path(__file__).resolve().parent
REPAIR_REPORT = BATCH / "reports/core_support_sweep_discovery_recovery.json"
REPAIR_MD = BATCH / "reports/core_support_sweep_discovery_recovery.md"
INVALIDATION = BATCH / "reports/core_support_sweep_discovery_INVALID_JOIN.md"
COSTS = (0.0, 0.005, 0.01)
COST = 0.005
JOIN = ("date", "symbol", "family", "spec_hash")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def match_labels_to_decisions(keys: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """Return exactly one label per frozen decision key, rejecting missing/extra joins."""
    left = keys.loc[:, list(JOIN)].copy()
    right = labels.copy()
    left["date"] = pd.to_datetime(left["date"], errors="raise").dt.normalize()
    right["date"] = pd.to_datetime(right["date"], errors="raise").dt.normalize()
    left["symbol"] = left["symbol"].astype("string")
    right["symbol"] = right["symbol"].astype("string")
    if left.duplicated(list(JOIN)).any() or right.duplicated(list(JOIN)).any():
        raise ValueError("recovery join identity is not unique")
    merged = left.merge(right, on=list(JOIN), how="left", validate="one_to_one", indicator=True)
    if not merged["_merge"].eq("both").all() or len(merged) != len(left):
        raise ValueError("not every frozen decision maps to exactly one canonical label")
    return merged.drop(columns="_merge")


def summarize(keys: pd.DataFrame, labels: pd.DataFrame, sessions: pd.DatetimeIndex, start: pd.Timestamp, last: pd.Timestamp):
    decisions = keys.loc[keys["date"].between(start, last)].copy()
    matched = match_labels_to_decisions(decisions, labels)
    signal_stats = label_summary(matched, costs=COSTS)
    active = sessions[(sessions >= start) & (sessions <= last)]
    daily = daily_cohorts(decisions, labels, sessions=active, join_columns=JOIN)
    daily.loc[daily["cohort_status"].eq("COMPLETE"), "cohort_return"] -= COST
    daily_stats = cohort_summary(daily, repetitions=2000)
    resolved = matched.loc[matched["label_resolved"].astype(bool)].copy()
    resolved["net"] = pd.to_numeric(resolved["gross_return"], errors="coerce") - COST
    resolved["month"] = resolved["date"].dt.to_period("M").astype(str)
    resolved["week"] = resolved["date"].dt.strftime("%G-W%V")
    monthly = {str(k): {"n": int(len(g)), "net_mean": float(g["net"].mean()), "net_median": float(g["net"].median())} for k, g in resolved.groupby("month", sort=True)}
    weekly = {str(k): {"n": int(len(g)), "net_mean": float(g["net"].mean()), "net_median": float(g["net"].median())} for k, g in resolved.groupby("week", sort=True)}
    counts = resolved["symbol"].value_counts(normalize=True)
    concentration = {"distinct_symbols": int(len(counts)), "top1_share": float(counts.iloc[0]) if len(counts) else None, "top5_share": float(counts.head(5).sum()) if len(counts) else None}
    return matched, signal_stats, daily, daily_stats, {"monthly": monthly, "weekly": weekly, "symbol_concentration": concentration}


def run() -> dict[str, object]:
    spec, calendar = audit.verify()
    if not audit.committed(audit.PREPARE) or not audit.committed(audit.REPRODUCE):
        raise ValueError("outcome-free pool receipt and reproduction must be committed")
    original_path = audit.REPORT
    if not original_path.exists():
        raise FileNotFoundError("original report to invalidate is missing")
    original_hash = sha(original_path)
    original = json.loads(original_path.read_text(encoding="utf-8"))
    if original.get("decision") != "REJECT_SUPPORT_SWEEP" or original.get("spec_sha256") != sha(audit.SPEC):
        raise ValueError("original report identity differs from this frozen experiment")
    receipt = json.loads(audit.PREPARE.read_text(encoding="utf-8"))
    reproduced = json.loads(audit.REPRODUCE.read_text(encoding="utf-8"))
    pool, selected = pd.read_parquet(audit.POOL), pd.read_parquet(audit.SELECTED)
    expected = receipt["decision_hashes"]
    if not reproduced.get("reproduced_exactly") or expected["pool"] != audit.frame_hash(pool) or expected["selected"] != audit.frame_hash(selected, ("raw_rank", "policy_id", "policy_rank", "selection_status")):
        raise ValueError("recovery candidate/rank/selection differs from committed frozen pool")
    price = pd.read_parquet(audit.FEATURE, columns=["date", "symbol", "open", "high", "low", "close", "volume"])
    price["date"] = pd.to_datetime(price["date"], errors="raise").dt.normalize()
    if price["date"].max() != audit.Y23_EXIT:
        raise ValueError("recovery prices escaped the frozen 2023 exit cutoff")
    labels = label_builder.build_labels_for_eligible_signals(price, pool[["date", "symbol", "close"]], calendar)
    labels["family"], labels["spec_hash"] = strategy.FAMILY, sha(audit.SPEC)
    labels["date"] = pd.to_datetime(labels["date"], errors="raise").dt.normalize()
    label_hash = hashlib.sha256(pd.util.hash_pandas_object(labels, index=False).to_numpy(dtype="uint64").tobytes()).hexdigest()
    if label_hash != original.get("labels_sha256"):
        raise ValueError("canonical labels differ from the already-opened first evaluation")
    periods: dict[str, object] = {}
    gates: dict[str, object] = {}
    definitions = (("2022H2", audit.START, audit.H2_LAST), ("2023", pd.Timestamp("2023-01-01"), audit.Y23_LAST))
    for name, start, last in definitions:
        pool_joined, pool_stats, pool_daily, pool_daily_stats, pool_segments = summarize(pool, labels, calendar.sessions, start, last)
        chosen_joined, chosen_stats, chosen_daily, chosen_daily_stats, chosen_segments = summarize(selected, labels, calendar.sessions, start, last)
        net = chosen_stats["round_trip_cost_scenarios"][f"{COST:g}"]
        pool_net = pool_stats["round_trip_cost_scenarios"][f"{COST:g}"]
        month_rows = chosen_joined.loc[chosen_joined["label_resolved"].astype(bool)].copy()
        month_rows["net"] = pd.to_numeric(month_rows["gross_return"], errors="coerce") - COST
        month_rows["month"] = month_rows["date"].dt.to_period("M").astype(str)
        positive_month_share = float(sum(g["net"].mean() > 0 for _, g in month_rows.groupby("month", sort=True)) / max(month_rows["month"].nunique(), 1))
        coverage = net["resolved_count"] / max(net["selected_count"], 1)
        freq = len(selected.loc[selected["date"].between(start, last)]) / max(len(pd.period_range(start.to_period("M"), last.to_period("M"), freq="M")), 1)
        gate = {
            "minimum_sample": net["resolved_count"] >= 75,
            "minimum_monthly_frequency": freq >= 5.0,
            "positive_mean_median_win_top3": all(net[k] is not None and net[k] > 0 for k in ("mean", "median", "mean_excluding_top3_winners")) and net["win_rate"] is not None and net["win_rate"] > 0.50,
            "label_coverage": coverage >= 0.90,
            "downside_no_worse_than_candidate_pool": all(net[k] is not None and pool_net[k] is not None and net[k] <= pool_net[k] for k in ("minus10_rate", "minus20_rate")),
            "positive_month_majority": positive_month_share >= 0.50,
            "complete_daily_cohorts": int(chosen_daily_stats["n"]) >= 20 and all(chosen_daily_stats[k] is not None and chosen_daily_stats[k] > 0 for k in ("mean", "median", "mean_excluding_top3_winners")),
        }
        gates[name] = gate
        periods[name] = {
            "candidate_pool": {"selected_count": len(pool_joined), "signal_metrics": pool_stats, "complete_day_metrics": pool_daily_stats, "daily_coverage": {"complete": int(pool_daily["cohort_status"].eq("COMPLETE").sum()), "partial": int(pool_daily["cohort_status"].eq("PARTIAL_UNRESOLVED").sum()), "abstain": int(pool_daily["cohort_status"].eq("ABSTAIN").sum())}},
            "selected_top5": {"selected_count": len(chosen_joined), "signal_metrics": chosen_stats, "complete_day_metrics": chosen_daily_stats, "daily_coverage": {"complete": int(chosen_daily["cohort_status"].eq("COMPLETE").sum()), "partial": int(chosen_daily["cohort_status"].eq("PARTIAL_UNRESOLVED").sum()), "abstain": int(chosen_daily["cohort_status"].eq("ABSTAIN").sum())}, "month_week_concentration": chosen_segments},
            "gates": gate,
        }
    decision = "KEEP_REQUIRES_SEPARATE_FROZEN_CONFIRMATION" if all(all(g.values()) for g in gates.values()) else "REJECT_SUPPORT_SWEEP"
    result = {
        "experiment_id": spec["experiment_id"], "evidence_level": spec["evidence_level"], "decision": decision,
        "status": "CORRECTED_REPORT_JOIN; original report invalidated",
        "original_report_path": str(original_path.relative_to(BATCH.parents[1])).replace("\\", "/"), "original_report_sha256": original_hash,
        "spec_sha256": sha(audit.SPEC), "prepare_receipt_sha256": sha(audit.PREPARE), "pool_reproduction_sha256": sha(audit.REPRODUCE),
        "candidate_and_selection_hashes_unchanged": True, "canonical_label_sha256_matches_original_read": label_hash,
        "recovery_code_sha256": sha(Path(__file__)),
        "label_join": "Signal metrics are computed only after a one-to-one join from the exact frozen selection keys to the canonical labels.",
        "outcome_values_reprocessed_at_utc": datetime.now(timezone.utc).isoformat(), "periods": periods, "gates": gates,
        "2024_plus_numeric_ohlcv_opened": False, "production_modified": False,
    }
    REPAIR_REPORT.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    REPAIR_MD.write_text(
        f"# Support-Sweep Reclaim — corrected evaluation\n\n- Decision: `{decision}`.\n- This recovery repairs only the report-side join: frozen candidate and selection hashes are unchanged.\n- The initial report `{original_hash}` is invalid because it used the full candidate label set for selected-signal metrics; do not cite its signal metrics.\n- Canonical label digest matches the labels opened in the first pass. Only purge-safe 2022H2/2023 outcomes were processed; 2024+ stayed closed.\n- Complete per-period metrics and gates are in the matching JSON.\n",
        encoding="utf-8",
    )
    INVALIDATION.write_text(
        f"# Invalidated report notice\n\n`core_support_sweep_discovery.json` SHA-256 `{original_hash}` has an incorrect selected-signal metric join. Its signal metrics and gates must not be used. The corrected evaluation is `core_support_sweep_discovery_recovery.json` and applies labels only to the exact frozen selection keys. Candidate/ranking/selection hashes were not changed.\n",
        encoding="utf-8",
    )
    return {"experiment_id": spec["experiment_id"], "decision": decision, "original_report_invalidated": original_hash, "corrected_report": str(REPAIR_REPORT)}
