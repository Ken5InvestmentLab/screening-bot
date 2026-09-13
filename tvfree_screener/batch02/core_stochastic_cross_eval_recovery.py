"""Report-only recovery for the frozen stochastic evaluation's metric-key bug."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from tvfree_screener.batch01.session_calendar import SessionCalendar
from tvfree_screener.batch02 import core_stochastic_cross_audit as audit
from tvfree_screener.batch02.core_support_sweep_report_recovery import summarize


BATCH = Path(__file__).resolve().parent
REPORT = BATCH / "reports/core_stochastic_cross_discovery_recovery.json"
REPORT_MD = BATCH / "reports/core_stochastic_cross_discovery_recovery.md"
COST = audit.COST


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run() -> dict[str, object]:
    spec, calendar = audit.verify()
    if not audit.committed(audit.PREPARE) or not audit.committed(audit.REPRODUCE):
        raise ValueError("both outcome-free candidate receipts must be committed before recovery")
    receipt = json.loads(audit.PREPARE.read_text(encoding="utf-8"))
    reproduction = json.loads(audit.REPRODUCE.read_text(encoding="utf-8"))
    if not reproduction.get("reproduced_exactly") or reproduction["decision_hashes"] != receipt["decision_hashes"]:
        raise ValueError("frozen candidate/rank/selection digests do not match")
    pool, selected = pd.read_parquet(audit.POOL), pd.read_parquet(audit.SELECTED)
    labels, label_sha = audit.canonical_labels(pool[["date", "symbol"]], sha(audit.SPEC))
    if labels["date"].max() > audit.Y23_LAST or labels["exit_date"].dropna().max() > audit.Y23_EXIT:
        raise ValueError("recovery label rows escaped the frozen 2023 purge boundary")
    periods: dict[str, object] = {}
    gates: dict[str, object] = {}
    definitions = (("2022H2", audit.START, audit.H2_LAST), ("2023", pd.Timestamp("2023-01-01"), audit.Y23_LAST))
    for name, begin, last in definitions:
        pool_joined, pool_stats, pool_daily, pool_cohorts, _ = summarize(pool, labels, calendar.sessions, begin, last)
        selected_joined, stats, daily, cohorts, segments = summarize(selected, labels, calendar.sessions, begin, last)
        # return_metrics reports the full requested denominator under this key;
        # resolved_count alone is the numerator after unresolved labels remain visible.
        net = stats["round_trip_cost_scenarios"][f"{COST:g}"]
        pool_net = pool_stats["round_trip_cost_scenarios"][f"{COST:g}"]
        requested = int(net["requested_count"])
        resolved = int(net["resolved_count"])
        coverage = resolved / max(requested, 1)
        monthly = selected_joined.loc[selected_joined["label_resolved"].astype(bool)].copy()
        monthly["net"] = pd.to_numeric(monthly["gross_return"], errors="coerce") - COST
        monthly["month"] = monthly["date"].dt.to_period("M").astype(str)
        positive_month_share = float(sum(group["net"].mean() > 0 for _, group in monthly.groupby("month", sort=True)) / max(monthly["month"].nunique(), 1))
        month_count = max(len(pd.period_range(begin.to_period("M"), last.to_period("M"), freq="M")), 1)
        frequency = requested / month_count
        gate = {
            "resolved_selected_minimum": resolved >= 75,
            "minimum_monthly_frequency": frequency >= 5.0,
            "mean_median_win_and_top3_excluded": all(net[key] is not None and net[key] > 0 for key in ("mean", "median", "mean_excluding_top3_winners")) and net["win_rate"] is not None and net["win_rate"] > 0.50,
            "label_coverage": coverage >= 0.90,
            "minus10_minus20_no_worse_than_candidate_pool": all(net[key] is not None and pool_net[key] is not None and net[key] <= pool_net[key] for key in ("minus10_rate", "minus20_rate")),
            "positive_month_majority": positive_month_share >= 0.50,
            "complete_daily_cohorts": int(cohorts["n"]) >= 20 and all(cohorts[key] is not None and cohorts[key] > 0 for key in ("mean", "median", "mean_excluding_top3_winners")),
        }
        gates[name] = gate
        periods[name] = {
            "candidate_pool": {"signal_metrics": pool_stats, "complete_day_metrics": pool_cohorts, "daily_coverage": {"complete": int(pool_daily["cohort_status"].eq("COMPLETE").sum()), "partial": int(pool_daily["cohort_status"].eq("PARTIAL_UNRESOLVED").sum()), "abstain": int(pool_daily["cohort_status"].eq("ABSTAIN").sum())}},
            "selected_top5": {"signal_metrics": stats, "complete_day_metrics": cohorts, "daily_coverage": {"complete": int(daily["cohort_status"].eq("COMPLETE").sum()), "partial": int(daily["cohort_status"].eq("PARTIAL_UNRESOLVED").sum()), "abstain": int(daily["cohort_status"].eq("ABSTAIN").sum())}, "month_week_symbol_concentration": segments},
            "frequency_per_calendar_month": frequency,
            "positive_month_share": positive_month_share,
            "gates": gate,
        }
    decision = "KEEP_REQUIRES_SEPARATE_FROZEN_CONFIRMATION" if all(all(values.values()) for values in gates.values()) else "REJECT_STOCHASTIC_CROSS"
    result = {
        "experiment_id": audit.EXPERIMENT,
        "decision": decision,
        "evidence_level": spec["evidence_level"],
        "report_recovery": "Only the reporting denominator key was corrected from nonexistent selected_count to requested_count. Candidate code, frozen spec, input data, labels, selected keys, and gates are unchanged.",
        "initial_evaluation_error": "KeyError: selected_count; evaluation_metrics.return_metrics exposes the requested denominator as requested_count.",
        "recovery_code_sha256": sha(Path(__file__)),
        "spec_sha256": sha(audit.SPEC),
        "pool_receipt_sha256": sha(audit.PREPARE),
        "pool_reproduction_sha256": sha(audit.REPRODUCE),
        "decision_hashes_unchanged": reproduction["decision_hashes"],
        "canonical_label_digest": label_sha,
        "canonical_source_missing_count": int(labels["canonical_source_missing"].sum()),
        "label_join": "Exact one-to-one date+symbol join; absent source keys remain explicit unresolved rows; duplicate keys fail closed.",
        "outcome_values_reprocessed_at_utc": datetime.now(timezone.utc).isoformat(),
        "periods": periods,
        "gates": gates,
        "2024_plus_numeric_ohlcv_opened": False,
        "production_modified": False,
    }
    REPORT.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    REPORT_MD.write_text(
        f"# Stochastic %K/%D Cross — corrected discovery evaluation\n\n- Decision: `{decision}`.\n- The first report attempt stopped on a metric-field name error; this recovery changes only the requested-sample denominator reference.\n- Candidate, rank, selection, spec, data, labels and frozen gates are unchanged; all three decision hashes still match.\n- Purge-safe 2022H2/2023 only; 2024+ outcomes were not opened. Full metrics and gate results are in the JSON report.\n",
        encoding="utf-8",
    )
    return {"experiment_id": audit.EXPERIMENT, "decision": decision, "report": str(REPORT), "canonical_label_digest": label_sha}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False, allow_nan=False))
