"""Frozen stochastic-cross Core discovery; labels stay closed through pool commit."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from tvfree_screener.batch01 import evaluation
from tvfree_screener.batch01.session_calendar import SessionCalendar
from tvfree_screener.batch02 import core_stochastic_cross as strategy
from tvfree_screener.batch02.core_support_sweep_report_recovery import summarize


BATCH = Path(__file__).resolve().parent
B1 = BATCH.parent / "batch01"
CACHE = BATCH / ".cache"
REPORTS = BATCH / "reports"
FEATURE = B1 / ".cache/core_moderate_features_through_2023.parquet"
FEATURE_MANIFEST = FEATURE.with_suffix(FEATURE.suffix + ".manifest.json")
LABELS = B1 / ".cache/core_moderate_ridge_discovery_labels.parquet"
LABEL_MANIFEST = LABELS.with_suffix(LABELS.suffix + ".manifest.json")
LABEL_SOURCE_SPEC = B1 / "reports/core_moderate_ridge_spec.json"
LABEL_SOURCE_SPEC_SHA = "6f56fc4c0f914f6faec0285e915a393044003505bc5d71cabb52e4d7778dcfa7"
LABEL_BUILDER_SHA = "90a33285e8b3d4c7eac108eb96da4225b189ca75badc9e34c0186331b4e2c07e"
CALENDAR = B1 / "reference/xtks_sessions.csv"
CALENDAR_MANIFEST = B1 / "reference/xtks_sessions.manifest.json"
FAMILY_SPEC = BATCH / "FAMILY_SPEC.json"
FAMILY_SPEC_SHA = BATCH / "FAMILY_SPEC.sha256"
FAMILY_SPEC_EXPECTED_SHA = "4303a8033dfdffbd97eed21fca1b92b1b4012c3a0d4548be1eb78051d0e26e1f"
EXPERIMENT = "CORE-STOCHASTIC-CROSS-20260913-01"
START = pd.Timestamp("2022-07-01")
H2_LAST = pd.Timestamp("2022-12-23")
Y23_LAST = pd.Timestamp("2023-12-22")
Y23_EXIT = pd.Timestamp("2023-12-29")
COSTS = (0.0, 0.005, 0.01)
COST = 0.005
JOIN = ("date", "symbol", "family", "spec_hash")
SPEC = REPORTS / "core_stochastic_cross_spec.json"
SPEC_SHA = REPORTS / "core_stochastic_cross_spec.sha256"
POOL = CACHE / "core_stochastic_cross_pool.parquet"
RANKED = CACHE / "core_stochastic_cross_ranked.parquet"
SELECTED = CACHE / "core_stochastic_cross_selected.parquet"
PREPARE = REPORTS / "core_stochastic_cross_pool_receipt.json"
REPRODUCE = REPORTS / "core_stochastic_cross_pool_reproduction.json"
REPORT = REPORTS / "core_stochastic_cross_discovery.json"
REPORT_MD = REPORTS / "core_stochastic_cross_discovery.md"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def input_hashes() -> dict[str, str]:
    family_sidecar = FAMILY_SPEC_SHA.read_text(encoding="utf-8").split()[0].lower()
    if sha(FAMILY_SPEC) != FAMILY_SPEC_EXPECTED_SHA or family_sidecar != FAMILY_SPEC_EXPECTED_SHA:
        raise ValueError("the shared frozen FAMILY_SPEC changed")
    fm = json.loads(FEATURE_MANIFEST.read_text(encoding="utf-8"))
    lm = json.loads(LABEL_MANIFEST.read_text(encoding="utf-8"))
    cm = json.loads(CALENDAR_MANIFEST.read_text(encoding="utf-8"))
    if sha(FEATURE) != fm["sha256"] or fm.get("labels_included") is not False or fm.get("through") != Y23_EXIT.date().isoformat():
        raise ValueError("feature-only panel hash or cutoff mismatch")
    if sha(LABELS) != lm["sha256"] or lm.get("source_sha256") != fm.get("source_sha256"):
        raise ValueError("canonical outcome artifact hash/source mismatch")
    label_source_spec = json.loads(LABEL_SOURCE_SPEC.read_text(encoding="utf-8"))
    if (
        lm.get("spec_sha256") != LABEL_SOURCE_SPEC_SHA
        or label_source_spec.get("spec_sha256") != LABEL_SOURCE_SPEC_SHA
        or label_source_spec.get("code_sha256", {}).get("core_moderate_ridge_audit.py") != LABEL_BUILDER_SHA
    ):
        raise ValueError("canonical outcome target spec hash mismatch")
    if sha(CALENDAR) != cm["csv_sha256"]:
        raise ValueError("official XTKS calendar hash mismatch")
    return {
        "shared_family_spec_sha256": sha(FAMILY_SPEC),
        "feature_panel_sha256": sha(FEATURE),
        "feature_manifest_sha256": sha(FEATURE_MANIFEST),
        "canonical_labels_sha256": sha(LABELS),
        "canonical_labels_manifest_sha256": sha(LABEL_MANIFEST),
        "canonical_target_spec_sha256": sha(LABEL_SOURCE_SPEC),
        "canonical_target_spec_version_sha256": LABEL_SOURCE_SPEC_SHA,
        "daily_source_sha256": str(fm["source_sha256"]),
        "xtks_calendar_sha256": sha(CALENDAR),
        "xtks_calendar_manifest_sha256": sha(CALENDAR_MANIFEST),
    }


def implementation_hashes() -> dict[str, str]:
    files = {
        "candidate_selector": BATCH / "core_stochastic_cross.py",
        "audit_runner": Path(__file__),
        "evaluation_metrics": B1 / "evaluation.py",
        "session_calendar": B1 / "session_calendar.py",
        "one_to_one_report_summarizer": BATCH / "core_support_sweep_report_recovery.py",
    }
    return {key: sha(path) for key, path in files.items()}


def register() -> dict[str, object]:
    if any(path.exists() for path in (SPEC, SPEC_SHA, POOL, RANKED, SELECTED, PREPARE, REPRODUCE, REPORT, REPORT_MD)):
        raise FileExistsError("stochastic-cross experiment artifacts already exist")
    inputs = input_hashes()
    spec: dict[str, object] = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT,
        "family": strategy.FAMILY,
        "registered_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FROZEN_BEFORE_THIS_EXPERIMENTS_OUTCOME_ACCESS",
        "evidence_level": "RETROSPECTIVE_PROVISIONAL",
        "shared_frozen_family_spec_sha256": FAMILY_SPEC_EXPECTED_SHA,
        "historical_exposure": "2022H2 and 2023 outcomes were previously viewed for other experiments; this is new-family retrospective discovery, not untouched OOS.",
        "hypothesis": "A standard 14-session stochastic %K crossing above its 3-session %D after %K was at or below 20 on the prior official session, with a signal-day close in the upper half of its range, marks a short-term oversold turn.",
        "candidate_pool": {
            "universe": "Frozen daily XTKS OHLCV panel; each row must have internally valid positive-volume OHLCV.",
            "stochastic_k": "100 * (close - lowest low over the current and preceding 13 official XTKS sessions) / (highest high over those same 14 sessions - lowest low); flat denominators are missing.",
            "stochastic_d": "Simple mean of the current and two preceding session %K values.",
            "signal": "Prior %K <= prior %D and prior %K <= 20; current %K > current %D; current close location >= 0.50.",
            "complete_history": "All 14 official sessions and all three %K observations must be present; missing sessions are never bridged.",
            "no_market_volume_or_fundamental_filter": True,
            "no_future_or_outcome_fields": True,
        },
        "score_and_selection": {
            "score": "Current %K minus current %D.",
            "ranking": ["cross strength descending", "close location descending", "symbol ascending"],
            "selection": "Independent Top5 per official XTKS session; at most five names and abstain when the pool is empty.",
            "cooldown": "A selected symbol is ineligible for selection on the immediately following official XTKS session; unselected candidates do not update cooldown.",
            "multiple_names_per_day": True,
        },
        "target": "Signal-date close-known setup; enter next official XTKS session open and exit fifth official XTKS session close including entry; canonical label return is exit close / entry open - 1.",
        "target_actionability": "Use the frozen canonical target builder unchanged: every subsequent XTKS session through exit must have valid positive OHLCV, positive volume, and an open/previous-close ratio in [0.60, 1.40]. Missing/invalid/gap-flagged labels remain unresolved; no backfill or substitution.",
        "periods": {
            "2022H2_last_signal": H2_LAST.date().isoformat(),
            "2023_last_signal": Y23_LAST.date().isoformat(),
            "last_discovery_exit": Y23_EXIT.date().isoformat(),
            "2024": "closed; not feature-selection data",
            "2025": "closed",
            "2026": "report-only and closed to selection",
        },
        "discovery_gates_each_period": {
            "resolved_selected_minimum": 75,
            "selected_per_calendar_month_minimum": 5.0,
            "net_mean_median_and_top3_excluded_mean": "all strictly positive at 0.5% assumed round-trip cost and win rate > 0.50",
            "label_coverage_minimum": 0.90,
            "minus10_and_minus20_rates": "no higher than the all-candidate pool on the same signal dates",
            "positive_months": "at least half of resolved months",
            "complete_daily_cohorts": "at least 20 complete dates; cohort net mean, median, and top3-excluded mean strictly positive",
            "decision": "Both periods must pass every gate; otherwise reject without threshold or ranking replacement.",
        },
        "cost_assumption": {"round_trip_primary": COST, "sensitivity_scenarios": list(COSTS), "measured_live_execution_cost": False},
        "data": {"feature_panel_through": Y23_EXIT.date().isoformat(), "canonical_label_source": "batch01/.cache/core_moderate_ridge_discovery_labels.parquet", "2024_plus_numeric_ohlcv_opened": False},
        "input_sha256": inputs,
        "implementation_sha256": implementation_hashes(),
        "production_modified": False,
    }
    SPEC.write_text(json.dumps(spec, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    SPEC_SHA.write_text(sha(SPEC) + "  " + SPEC.name + "\n", encoding="utf-8")
    return {"experiment_id": EXPERIMENT, "spec_sha256": sha(SPEC), "status": spec["status"]}


def verify() -> tuple[dict[str, object], SessionCalendar]:
    if hashlib.sha256(SPEC.read_bytes()).hexdigest() != SPEC_SHA.read_text(encoding="utf-8").split()[0]:
        raise ValueError("stochastic-cross spec hash mismatch")
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    if spec["implementation_sha256"] != implementation_hashes() or spec["input_sha256"] != input_hashes():
        raise ValueError("stochastic-cross code or input changed after freeze")
    cm = json.loads(CALENDAR_MANIFEST.read_text(encoding="utf-8"))
    calendar = SessionCalendar.from_csv(CALENDAR, expected_sha256=cm["csv_sha256"])
    return spec, calendar


def decisions(spec_hash: str, calendar: SessionCalendar):
    panel = pd.read_parquet(FEATURE, columns=["date", "symbol", "open", "high", "low", "close", "volume"])
    panel["date"] = pd.to_datetime(panel["date"], errors="raise").dt.normalize()
    panel["symbol"] = panel["symbol"].astype("string")
    signal_calendar = calendar.sessions[calendar.sessions <= Y23_EXIT]
    pool, counts = strategy.build_candidate_pool(panel, signal_calendar, start=START, end=Y23_LAST)
    pool["family"], pool["spec_hash"] = strategy.FAMILY, spec_hash
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
        raise FileExistsError("stochastic-cross pool artifacts already exist")
    pool, ranked, selected, counts = decisions(sha(SPEC), calendar)
    CACHE.mkdir(parents=True, exist_ok=True)
    pool.to_parquet(POOL, index=False, compression="zstd")
    ranked.to_parquet(RANKED, index=False, compression="zstd")
    selected.to_parquet(SELECTED, index=False, compression="zstd")
    counts.update({"ranked_rows": len(ranked), "selected_rows": len(selected), "selected_days": int(selected["date"].nunique()), "zero_selection_days": int(len(calendar.sessions[(calendar.sessions >= START) & (calendar.sessions <= Y23_LAST)]) - selected["date"].nunique())})
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
        raise ValueError("stochastic-cross pool artifact hash mismatch")
    rebuilt = decisions(sha(SPEC), calendar)
    hashes = {key: frame_hash(frame) for key, frame in zip(("pool", "ranked", "selected"), rebuilt[:3], strict=True)}
    if hashes != receipt["decision_hashes"]:
        raise ValueError("stochastic-cross candidate/rank/selection failed exact reproduction")
    result = {"experiment_id": EXPERIMENT, "spec_sha256": sha(SPEC), "prepare_receipt_sha256": sha(PREPARE), "decision_hashes": hashes, "counts": receipt["counts"], "reproduced_exactly": True, "outcome_values_opened": False, "2024_plus_numeric_ohlcv_opened": False}
    REPRODUCE.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return result


def canonical_labels(keys: pd.DataFrame, spec_hash: str) -> tuple[pd.DataFrame, str]:
    manifest = json.loads(LABEL_MANIFEST.read_text(encoding="utf-8"))
    source_spec = json.loads(LABEL_SOURCE_SPEC.read_text(encoding="utf-8"))
    target = source_spec["family_spec"]["target"]
    if (
        sha(LABELS) != manifest.get("sha256")
        or manifest.get("spec_sha256") != LABEL_SOURCE_SPEC_SHA
        or source_spec.get("spec_sha256") != LABEL_SOURCE_SPEC_SHA
        or source_spec.get("code_sha256", {}).get("core_moderate_ridge_audit.py") != LABEL_BUILDER_SHA
        or "next XTKS session open" not in target
        or "fifth XTKS session including entry" not in target
    ):
        raise ValueError("canonical label file or declared target differs from the frozen source")
    source = pd.read_parquet(LABELS)
    source["date"] = pd.to_datetime(source["date"], errors="raise").dt.normalize()
    source["symbol"] = source["symbol"].astype("string")
    source = source.loc[:, ["date", "symbol", "entry_date", "exit_date", "entry_price", "exit_price", "gross_return", "label_status", "label_resolved", "label_available_at", "session_index"]]
    source["entry_date"] = pd.to_datetime(source["entry_date"], errors="coerce").dt.normalize()
    source["exit_date"] = pd.to_datetime(source["exit_date"], errors="coerce").dt.normalize()
    left = keys.loc[:, ["date", "symbol"]].drop_duplicates().copy()
    left["date"] = pd.to_datetime(left["date"], errors="raise").dt.normalize()
    left["symbol"] = left["symbol"].astype("string")
    if left.duplicated(["date", "symbol"]).any():
        raise ValueError("candidate decision keys are not unique")
    # Validate only keys needed for this frozen run. Missing canonical rows are
    # retained as explicitly unresolved rows; duplicates fail closed.
    matched = left.merge(source, on=["date", "symbol"], how="left", validate="one_to_one", indicator=True)
    missing = matched["_merge"].eq("left_only")
    matched["label_status"] = matched["label_status"].astype("string")
    matched.loc[missing, "label_status"] = "MISSING_CANONICAL_LABEL"
    matched["label_resolved"] = matched["label_resolved"].fillna(False).astype(bool)
    matched["family"], matched["spec_hash"] = strategy.FAMILY, spec_hash
    matched["canonical_source_missing"] = missing
    labels = matched.drop(columns="_merge")
    label_sha = hashlib.sha256(pd.util.hash_pandas_object(labels, index=False).to_numpy(dtype="uint64").tobytes()).hexdigest()
    return labels, label_sha


def evaluate_frozen() -> dict[str, object]:
    spec, calendar = verify()
    if not committed(PREPARE) or not committed(REPRODUCE):
        raise ValueError("outcome-free receipt and exact reproduction must be committed before label access")
    receipt = json.loads(PREPARE.read_text(encoding="utf-8"))
    reproduction = json.loads(REPRODUCE.read_text(encoding="utf-8"))
    if not reproduction.get("reproduced_exactly") or reproduction["decision_hashes"] != receipt["decision_hashes"]:
        raise ValueError("candidate/rank/selection is not frozen and reproduced")
    pool, selected = pd.read_parquet(POOL), pd.read_parquet(SELECTED)
    labels, label_sha = canonical_labels(pool[["date", "symbol"]], sha(SPEC))
    if labels["date"].max() > Y23_LAST or labels["exit_date"].dropna().max() > Y23_EXIT:
        raise ValueError("discovery labels escaped the purge-safe exit cutoff")
    periods: dict[str, object] = {}
    gates: dict[str, object] = {}
    definitions = (("2022H2", START, H2_LAST), ("2023", pd.Timestamp("2023-01-01"), Y23_LAST))
    for name, begin, last in definitions:
        pool_joined, pool_stats, pool_daily, pool_cohorts, pool_segments = summarize(pool, labels, calendar.sessions, begin, last)
        selected_joined, stats, daily, cohorts, segments = summarize(selected, labels, calendar.sessions, begin, last)
        net = stats["round_trip_cost_scenarios"][f"{COST:g}"]
        pool_net = pool_stats["round_trip_cost_scenarios"][f"{COST:g}"]
        coverage = net["resolved_count"] / max(net["selected_count"], 1)
        monthly = selected_joined.loc[selected_joined["label_resolved"].astype(bool)].copy()
        monthly["net"] = pd.to_numeric(monthly["gross_return"], errors="coerce") - COST
        monthly["month"] = monthly["date"].dt.to_period("M").astype(str)
        positive_month_share = float(sum(group["net"].mean() > 0 for _, group in monthly.groupby("month", sort=True)) / max(monthly["month"].nunique(), 1))
        month_count = max(len(pd.period_range(begin.to_period("M"), last.to_period("M"), freq="M")), 1)
        frequency = net["selected_count"] / month_count
        gate = {
            "resolved_selected_minimum": net["resolved_count"] >= 75,
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
        "experiment_id": EXPERIMENT, "decision": decision, "evidence_level": spec["evidence_level"],
        "spec_sha256": sha(SPEC), "pool_receipt_sha256": sha(PREPARE), "pool_reproduction_sha256": sha(REPRODUCE),
        "decision_hashes": receipt["decision_hashes"], "canonical_label_digest": label_sha,
        "canonical_label_join": "one-to-one date+symbol left join; missing source keys remain explicit unresolved rows; duplicate keys fail closed",
        "canonical_source_missing_count": int(labels["canonical_source_missing"].sum()),
        "outcome_values_opened_at_utc": datetime.now(timezone.utc).isoformat(), "periods": periods, "gates": gates,
        "2024_plus_numeric_ohlcv_opened": False, "production_modified": False,
    }
    REPORT.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    REPORT_MD.write_text(
        f"# Stochastic %K/%D Cross — discovery\n\n- Decision: `{decision}`.\n- The frozen rule uses a 14-session %K, 3-session %D, prior oversold cross, and up to five names per XTKS session.\n- Target: next-session open to fifth-session close including entry; primary cost is an assumed 0.5% round trip.\n- Only retrospective 2022H2/2023 discovery outcomes were opened; 2024+ stayed closed.\n- The one-to-one canonical-label join retained absent/unresolved labels; full metrics and period gates are in the JSON report.\n",
        encoding="utf-8",
    )
    return {"experiment_id": EXPERIMENT, "decision": decision, "report": str(REPORT), "canonical_label_digest": label_sha}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("register", "prepare", "reproduce", "evaluate"))
    action = parser.parse_args().action
    result = {"register": register, "prepare": prepare, "reproduce": reproduce, "evaluate": evaluate_frozen}[action]()
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
