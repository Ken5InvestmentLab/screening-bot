"""Frozen purge-safe discovery loop for the gap-up acceptance Core hypothesis."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from tvfree_screener.batch01.session_calendar import SessionCalendar
from tvfree_screener.batch02 import core_gap_up_continuation as strategy
from tvfree_screener.batch02 import core_stochastic_cross_audit as canonical
from tvfree_screener.batch02.core_support_sweep_report_recovery import summarize


BATCH = Path(__file__).resolve().parent
B1 = BATCH.parent / "batch01"
CACHE = BATCH / ".cache"
REPORTS = BATCH / "reports"
FEATURE = B1 / ".cache/core_moderate_features_through_2023.parquet"
FEATURE_MANIFEST = FEATURE.with_suffix(FEATURE.suffix + ".manifest.json")
CALENDAR = B1 / "reference/xtks_sessions.csv"
CALENDAR_MANIFEST = B1 / "reference/xtks_sessions.manifest.json"
EXPERIMENT = "CORE-GAP-UP-ACCEPTANCE-20260913-01"
START = pd.Timestamp("2022-07-01")
H2_LAST = pd.Timestamp("2022-12-23")
Y23_LAST = pd.Timestamp("2023-12-22")
Y23_EXIT = pd.Timestamp("2023-12-29")
COSTS = (0.0, 0.005, 0.01)
COST = 0.005
SPEC = REPORTS / "core_gap_up_continuation_spec.json"
SPEC_SHA = REPORTS / "core_gap_up_continuation_spec.sha256"
POOL = CACHE / "core_gap_up_continuation_pool.parquet"
RANKED = CACHE / "core_gap_up_continuation_ranked.parquet"
SELECTED = CACHE / "core_gap_up_continuation_selected.parquet"
PREPARE = REPORTS / "core_gap_up_continuation_pool_receipt.json"
REPRODUCE = REPORTS / "core_gap_up_continuation_pool_reproduction.json"
REPORT = REPORTS / "core_gap_up_continuation_discovery.json"
REPORT_MD = REPORTS / "core_gap_up_continuation_discovery.md"
JOIN = ("date", "symbol", "family", "spec_hash")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def input_hashes() -> dict[str, str]:
    shared = canonical.input_hashes()
    fm = json.loads(FEATURE_MANIFEST.read_text(encoding="utf-8"))
    cm = json.loads(CALENDAR_MANIFEST.read_text(encoding="utf-8"))
    if sha(FEATURE) != fm["sha256"] or fm.get("labels_included") is not False or fm.get("through") != Y23_EXIT.date().isoformat():
        raise ValueError("feature-only panel hash or cutoff mismatch")
    if sha(CALENDAR) != cm["csv_sha256"]:
        raise ValueError("official XTKS calendar hash mismatch")
    return {**shared, "feature_panel_sha256": sha(FEATURE), "feature_manifest_sha256": sha(FEATURE_MANIFEST), "xtks_calendar_sha256": sha(CALENDAR), "xtks_calendar_manifest_sha256": sha(CALENDAR_MANIFEST)}


def implementation_hashes() -> dict[str, str]:
    files = {
        "candidate_selector": BATCH / "core_gap_up_continuation.py",
        "audit_runner": Path(__file__),
        "shared_frozen_spec_verifier_and_label_rekey": BATCH / "core_stochastic_cross_audit.py",
        "canonical_label_rekey_family_source": BATCH / "core_stochastic_cross.py",
        "evaluation_metrics": B1 / "evaluation.py",
        "session_calendar": B1 / "session_calendar.py",
        "one_to_one_report_summarizer": BATCH / "core_support_sweep_report_recovery.py",
    }
    return {key: sha(path) for key, path in files.items()}


def register() -> dict[str, object]:
    if any(path.exists() for path in (SPEC, SPEC_SHA, POOL, RANKED, SELECTED, PREPARE, REPRODUCE, REPORT, REPORT_MD)):
        raise FileExistsError("gap-up acceptance experiment artifacts already exist")
    spec: dict[str, object] = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT,
        "family": strategy.FAMILY,
        "registered_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FROZEN_BEFORE_THIS_EXPERIMENTS_OUTCOME_ACCESS",
        "evidence_level": "RETROSPECTIVE_PROVISIONAL",
        "shared_frozen_family_spec_sha256": canonical.FAMILY_SPEC_EXPECTED_SHA,
        "historical_exposure": "2022H2 and 2023 outcomes were seen in other experiments; results are retrospective discovery, not untouched OOS.",
        "hypothesis": "A positive opening gap accompanied by unusually high signal-day volume, a bullish body, and a close near the session high may show institutional acceptance and short-horizon continuation.",
        "candidate_pool": {
            "universe": "Rows from the immutable feature-only daily XTKS panel with complete, internally valid positive-volume OHLCV. Historical membership is limited to symbols in the preserved Yahoo source; point-in-time delisted-symbol completeness is not guaranteed.",
            "gap": f"Prior-close-only open gap >= {strategy.GAP_MIN}; use the frozen panel's `gap` feature.",
            "volume": f"Current volume / prior 20 official-session mean volume >= {strategy.VOLUME_RATIO_MIN}; current volume is excluded from the denominator.",
            "candle_confirmation": f"Positive body (close > open) and close location >= {strategy.CLOSE_LOCATION_MIN}.",
            "market_fundamental_or_future_filters": "None.",
            "missingness": "Nonfinite signal-time features are outside the pool and counted; no session bridging or outcome-dependent substitution.",
        },
        "score_and_selection": {
            "score": "Equal-weight arithmetic mean of within-date percentile ranks (average ties) for gap, prior-average volume ratio, and close location; larger ranks are preferred.",
            "tie_breaks": ["mean percentile score descending", "close location descending", "prior-average volume ratio descending", "gap descending", "symbol ascending"],
            "selection": "Top5 per official XTKS session; multiple names allowed; abstain when no event passes.",
            "cooldown": "A selected symbol is suppressed on the immediately following official XTKS session; unselected candidates do not update cooldown.",
        },
        "target": "Enter next official XTKS session open; exit close of fifth official XTKS session including entry, using the pinned canonical labels and daily actionability statuses.",
        "periods": {"2022H2_last_signal": H2_LAST.date().isoformat(), "2023_last_signal": Y23_LAST.date().isoformat(), "last_discovery_exit": Y23_EXIT.date().isoformat(), "2024": "closed unless discovery gates pass; retrospective confirmation only", "2025": "closed", "2026": "report-only and closed to selection"},
        "discovery_gates_each_period": {
            "resolved_selected_minimum": 75,
            "selected_per_calendar_month_minimum": 5.0,
            "signal_net": "mean > 0, median > 0, win rate > 0.50, and mean excluding top three winners > 0 at 0.5% assumed round-trip cost",
            "label_coverage_minimum": 0.90,
            "tail_risk": "-10% and -20% rates no higher than full event pool on same dates",
            "monthly_stability": "at least half of resolved months positive",
            "daily_cohorts": "at least 20 complete selected dates and net mean, median, and mean excluding top three dates all > 0",
            "decision": "Both periods must pass every gate; otherwise reject without replacing thresholds or ranking.",
        },
        "cost_assumption": {"primary_round_trip": COST, "sensitivity_scenarios": list(COSTS), "measured_live_cost": False},
        "data": {"feature_panel_through": Y23_EXIT.date().isoformat(), "2024_plus_numeric_ohlcv_opened": False, "canonical_label_source": "batch01/.cache/core_moderate_ridge_discovery_labels.parquet"},
        "input_sha256": input_hashes(),
        "implementation_sha256": implementation_hashes(),
        "production_modified": False,
    }
    SPEC.write_text(json.dumps(spec, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    SPEC_SHA.write_text(sha(SPEC) + "  " + SPEC.name + "\n", encoding="utf-8")
    return {"experiment_id": EXPERIMENT, "spec_sha256": sha(SPEC), "status": spec["status"]}


def verify() -> tuple[dict[str, object], SessionCalendar]:
    if hashlib.sha256(SPEC.read_bytes()).hexdigest() != SPEC_SHA.read_text(encoding="utf-8").split()[0]:
        raise ValueError("gap-up acceptance spec hash mismatch")
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    if spec["input_sha256"] != input_hashes() or spec["implementation_sha256"] != implementation_hashes():
        raise ValueError("gap-up code or data changed after preregistration")
    cm = json.loads(CALENDAR_MANIFEST.read_text(encoding="utf-8"))
    calendar = SessionCalendar.from_csv(CALENDAR, expected_sha256=cm["csv_sha256"])
    return spec, calendar


def decisions(spec_hash: str, calendar: SessionCalendar):
    columns = ["date", "symbol", "open", "high", "low", "close", "volume", "gap", "volr20_prevavg", "close_location", "body_pct"]
    panel = pd.read_parquet(FEATURE, columns=columns)
    panel["date"] = pd.to_datetime(panel["date"], errors="raise").dt.normalize()
    panel["symbol"] = panel["symbol"].astype("string")
    signal_calendar = calendar.sessions[calendar.sessions <= Y23_EXIT]
    pool, counts = strategy.build_candidate_pool(panel, signal_calendar, start=START, end=Y23_LAST)
    pool["spec_hash"] = spec_hash
    ranked = strategy.rank_candidates(pool)
    ranked["spec_hash"] = spec_hash
    selected = strategy.select_candidates(ranked, calendar.sessions)
    selected["spec_hash"] = spec_hash
    return pool, ranked, selected, counts


def frame_hash(frame: pd.DataFrame) -> str:
    part = frame.copy()
    part["date"] = pd.to_datetime(part["date"], errors="raise").dt.strftime("%Y-%m-%d")
    part["symbol"] = part["symbol"].astype("string")
    digest = hashlib.sha256("\x1f".join(map(str, part.columns)).encode())
    for start in range(0, len(part), 100_000):
        digest.update(pd.util.hash_pandas_object(part.iloc[start:start + 100_000], index=False, categorize=True).to_numpy(dtype="uint64").tobytes())
    return digest.hexdigest()


def prepare() -> dict[str, object]:
    spec, calendar = verify()
    if any(path.exists() for path in (POOL, RANKED, SELECTED, PREPARE, REPRODUCE, REPORT, REPORT_MD)):
        raise FileExistsError("gap-up acceptance output artifacts already exist")
    pool, ranked, selected, counts = decisions(sha(SPEC), calendar)
    CACHE.mkdir(parents=True, exist_ok=True)
    pool.to_parquet(POOL, index=False, compression="zstd")
    ranked.to_parquet(RANKED, index=False, compression="zstd")
    selected.to_parquet(SELECTED, index=False, compression="zstd")
    active_sessions = calendar.sessions[(calendar.sessions >= START) & (calendar.sessions <= Y23_LAST)]
    counts.update({"ranked_rows": len(ranked), "selected_rows": len(selected), "selected_days": int(selected["date"].nunique()), "zero_selection_days": int(len(active_sessions) - selected["date"].nunique())})
    receipt = {
        "experiment_id": EXPERIMENT, "spec_sha256": sha(SPEC), "input_sha256": spec["input_sha256"],
        "implementation_sha256": spec["implementation_sha256"], "counts": counts,
        "decision_hashes": {"pool": frame_hash(pool), "ranked": frame_hash(ranked), "selected": frame_hash(selected)},
        "artifact_sha256": {"pool": sha(POOL), "ranked": sha(RANKED), "selected": sha(SELECTED)},
        "outcome_values_opened": False, "2024_plus_numeric_ohlcv_opened": False,
    }
    PREPARE.write_text(json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return receipt


def committed(path: Path) -> bool:
    relative = path.relative_to(BATCH.parents[1]).as_posix()
    return subprocess.run(["git", "cat-file", "-e", f"HEAD:{relative}"], capture_output=True).returncode == 0


def reproduce() -> dict[str, object]:
    spec, calendar = verify()
    receipt = json.loads(PREPARE.read_text(encoding="utf-8"))
    if receipt["artifact_sha256"] != {"pool": sha(POOL), "ranked": sha(RANKED), "selected": sha(SELECTED)}:
        raise ValueError("gap-up acceptance Parquet artifact hash mismatch")
    rebuilt = decisions(sha(SPEC), calendar)
    hashes = {name: frame_hash(frame) for name, frame in zip(("pool", "ranked", "selected"), rebuilt[:3], strict=True)}
    if hashes != receipt["decision_hashes"]:
        raise ValueError("gap-up acceptance candidates/ranks/selections failed exact reproduction")
    result = {"experiment_id": EXPERIMENT, "spec_sha256": sha(SPEC), "prepare_receipt_sha256": sha(PREPARE), "decision_hashes": hashes, "counts": receipt["counts"], "reproduced_exactly": True, "outcome_values_opened": False, "2024_plus_numeric_ohlcv_opened": False}
    REPRODUCE.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return result


def evaluate() -> dict[str, object]:
    spec, calendar = verify()
    if not committed(PREPARE) or not committed(REPRODUCE):
        raise ValueError("outcome-free receipt and exact reproduction must be committed before labels")
    receipt, reproduction = json.loads(PREPARE.read_text(encoding="utf-8")), json.loads(REPRODUCE.read_text(encoding="utf-8"))
    if not reproduction.get("reproduced_exactly") or reproduction["decision_hashes"] != receipt["decision_hashes"]:
        raise ValueError("candidate selection is not frozen and reproduced")
    pool, selected = pd.read_parquet(POOL), pd.read_parquet(SELECTED)
    if pool.empty or selected.empty:
        result = {"experiment_id": EXPERIMENT, "decision": "REJECT_NO_SELECTED_EVENTS", "spec_sha256": sha(SPEC), "decision_hashes": receipt["decision_hashes"], "outcome_values_opened": False, "2024_plus_numeric_ohlcv_opened": False, "production_modified": False}
        REPORT.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        REPORT_MD.write_text(f"# Gap-Up Acceptance — discovery\n\n- Decision: `REJECT_NO_SELECTED_EVENTS`. Frozen event has no selected candidates; no return labels were opened.\n", encoding="utf-8")
        return result
    labels, label_hash = canonical.canonical_labels(pool[["date", "symbol"]], sha(SPEC))
    labels["family"] = strategy.FAMILY
    if labels["date"].max() > Y23_LAST or labels["exit_date"].dropna().max() > Y23_EXIT:
        raise ValueError("gap-up discovery labels escaped the frozen purge boundary")
    periods: dict[str, object] = {}
    gates: dict[str, object] = {}
    for name, begin, last in (("2022H2", START, H2_LAST), ("2023", pd.Timestamp("2023-01-01"), Y23_LAST)):
        pool_joined, pool_stats, pool_daily, pool_cohorts, _ = summarize(pool, labels, calendar.sessions, begin, last)
        active_dates = set(selected.loc[selected["date"].between(begin, last), "date"].unique())
        active_pool = pool.loc[pool["date"].between(begin, last) & pool["date"].isin(active_dates)].copy()
        active_pool_joined, active_pool_stats, active_pool_daily, active_pool_cohorts, _ = summarize(
            active_pool, labels, calendar.sessions, begin, last
        )
        selected_joined, stats, daily, cohorts, segments = summarize(selected, labels, calendar.sessions, begin, last)
        net = stats["round_trip_cost_scenarios"][f"{COST:g}"]
        pool_net = active_pool_stats["round_trip_cost_scenarios"][f"{COST:g}"]
        requested, resolved = int(net["requested_count"]), int(net["resolved_count"])
        coverage = resolved / max(requested, 1)
        monthly = selected_joined.loc[selected_joined["label_resolved"].astype(bool)].copy()
        monthly["net"] = pd.to_numeric(monthly["gross_return"], errors="coerce") - COST
        monthly["month"] = monthly["date"].dt.to_period("M").astype(str)
        positive_month_share = float(sum(group["net"].mean() > 0 for _, group in monthly.groupby("month", sort=True)) / max(monthly["month"].nunique(), 1))
        month_count = max(len(pd.period_range(begin.to_period("M"), last.to_period("M"), freq="M")), 1)
        frequency = requested / month_count
        gate = {
            "resolved_selected_minimum": resolved >= 75,
            "minimum_monthly_frequency": frequency >= 5,
            "positive_mean_median_win_and_top3_excluded": all(net[key] is not None and net[key] > 0 for key in ("mean", "median", "mean_excluding_top3_winners")) and net["win_rate"] is not None and net["win_rate"] > 0.50,
            "label_coverage": coverage >= 0.90,
            "minus10_minus20_no_worse_than_same_active_date_pool": all(net[key] is not None and pool_net[key] is not None and net[key] <= pool_net[key] for key in ("minus10_rate", "minus20_rate")),
            "positive_month_majority": positive_month_share >= 0.50,
            "complete_daily_cohorts": int(cohorts["n"]) >= 20 and all(cohorts[key] is not None and cohorts[key] > 0 for key in ("mean", "median", "mean_excluding_top3_winners")),
        }
        gates[name] = gate
        periods[name] = {
            "candidate_pool_all_days": {"signal_metrics": pool_stats, "complete_day_metrics": pool_cohorts, "daily_coverage": {"complete": int(pool_daily["cohort_status"].eq("COMPLETE").sum()), "partial": int(pool_daily["cohort_status"].eq("PARTIAL_UNRESOLVED").sum()), "abstain": int(pool_daily["cohort_status"].eq("ABSTAIN").sum())}},
            "candidate_pool_same_active_dates": {"signal_metrics": active_pool_stats, "complete_day_metrics": active_pool_cohorts, "daily_coverage": {"complete": int(active_pool_daily["cohort_status"].eq("COMPLETE").sum()), "partial": int(active_pool_daily["cohort_status"].eq("PARTIAL_UNRESOLVED").sum()), "abstain": int(active_pool_daily["cohort_status"].eq("ABSTAIN").sum())}},
            "selected_top5": {"signal_metrics": stats, "complete_day_metrics": cohorts, "daily_coverage": {"complete": int(daily["cohort_status"].eq("COMPLETE").sum()), "partial": int(daily["cohort_status"].eq("PARTIAL_UNRESOLVED").sum()), "abstain": int(daily["cohort_status"].eq("ABSTAIN").sum())}, "month_week_symbol_concentration": segments},
            "frequency_per_calendar_month": frequency,
            "positive_month_share": positive_month_share,
            "gates": gate,
        }
    decision = "KEEP_REQUIRES_SEPARATE_FROZEN_CONFIRMATION" if all(all(row.values()) for row in gates.values()) else "REJECT_GAP_UP_ACCEPTANCE"
    result = {
        "experiment_id": EXPERIMENT, "decision": decision, "evidence_level": spec["evidence_level"],
        "spec_sha256": sha(SPEC), "pool_receipt_sha256": sha(PREPARE), "pool_reproduction_sha256": sha(REPRODUCE),
        "decision_hashes": receipt["decision_hashes"], "canonical_label_digest": label_hash,
        "canonical_source_missing_count": int(labels["canonical_source_missing"].sum()),
        "label_join": "One-to-one date+symbol canonical join; missing rows stay unresolved and duplicate keys fail closed.",
        "outcome_values_opened_at_utc": datetime.now(timezone.utc).isoformat(), "periods": periods, "gates": gates,
        "2024_plus_numeric_ohlcv_opened": False, "production_modified": False,
    }
    REPORT.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    REPORT_MD.write_text(
        f"# Gap-Up Acceptance — discovery\n\n- Decision: `{decision}`.\n- Frozen event: gap >= 1.5%, volume / prior-20-session mean >= 1.5, bullish candle and close location >= 70%; score is the mean of same-day percentile ranks.\n- Target: next-session open to fifth-session close including entry; primary cost is 0.5% assumed round trip.\n- Only purge-safe 2022H2/2023 labels were evaluated; 2024+ stayed closed.\n- Full metrics and per-period gates are in the JSON report.\n",
        encoding="utf-8",
    )
    return {"experiment_id": EXPERIMENT, "decision": decision, "report": str(REPORT), "canonical_label_digest": label_hash}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("register", "prepare", "reproduce", "evaluate"))
    action = parser.parse_args().action
    output = {"register": register, "prepare": prepare, "reproduce": reproduce, "evaluate": evaluate}[action]()
    print(json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
