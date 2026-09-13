"""Frozen preparation and retrospective discovery for support-sweep reclaim."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from tvfree_screener.batch01 import core_moderate_ridge_audit as label_builder
from tvfree_screener.batch01.evaluation import cohort_summary, daily_cohorts, label_summary
from tvfree_screener.batch01.session_calendar import SessionCalendar
from tvfree_screener.batch02 import core_support_sweep as strategy


BATCH = Path(__file__).resolve().parent
B1 = BATCH.parent / "batch01"
FEATURE = B1 / ".cache/core_moderate_features_through_2023.parquet"
FEATURE_MANIFEST = FEATURE.with_suffix(FEATURE.suffix + ".manifest.json")
CALENDAR = B1 / "reference/xtks_sessions.csv"
CALENDAR_MANIFEST = B1 / "reference/xtks_sessions.manifest.json"
SPEC = BATCH / "reports/core_support_sweep_spec.json"
SPEC_SHA = BATCH / "reports/core_support_sweep_spec.sha256"
CACHE = BATCH / ".cache"
POOL = CACHE / "core_support_sweep_pool.parquet"
RANKED = CACHE / "core_support_sweep_ranked.parquet"
SELECTED = CACHE / "core_support_sweep_selected.parquet"
PREPARE = BATCH / "reports/core_support_sweep_pool_receipt.json"
REPRODUCE = BATCH / "reports/core_support_sweep_pool_reproduction.json"
REPORT = BATCH / "reports/core_support_sweep_discovery.json"
REPORT_MD = BATCH / "reports/core_support_sweep_discovery.md"
EXPERIMENT = "CORE-SUPPORT-SWEEP-20260913-01"
START = pd.Timestamp("2022-07-01")
H2_LAST = pd.Timestamp("2022-12-23")
H2_EXIT = pd.Timestamp("2022-12-30")
Y23_LAST = pd.Timestamp("2023-12-22")
Y23_EXIT = pd.Timestamp("2023-12-29")
COSTS = (0.0, 0.005, 0.01)
COST = 0.005
JOIN = ("date", "symbol", "family", "spec_hash")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def inputs() -> dict[str, str]:
    manifest = json.loads(FEATURE_MANIFEST.read_text(encoding="utf-8"))
    cal_manifest = json.loads(CALENDAR_MANIFEST.read_text(encoding="utf-8"))
    if sha(FEATURE) != manifest["sha256"] or manifest.get("labels_included") is not False:
        raise ValueError("bounded decision-only feature panel does not match its receipt")
    if manifest.get("through") != Y23_EXIT.date().isoformat():
        raise ValueError("feature panel does not end at the registered 2023 exit cutoff")
    if sha(CALENDAR) != cal_manifest["csv_sha256"]:
        raise ValueError("XTKS calendar hash differs from its receipt")
    return {
        "feature_sha256": sha(FEATURE),
        "feature_manifest_sha256": sha(FEATURE_MANIFEST),
        "daily_source_sha256": str(manifest["source_sha256"]),
        "calendar_sha256": sha(CALENDAR),
        "calendar_manifest_sha256": sha(CALENDAR_MANIFEST),
    }


def implementations() -> dict[str, str]:
    files = {
        "candidate_and_selection": BATCH / "core_support_sweep.py",
        "audit_runner": Path(__file__),
        "canonical_label_builder": Path(label_builder.__file__),
        "evaluation": B1 / "evaluation.py",
        "session_calendar": B1 / "session_calendar.py",
        "feature_panel": B1 / "feature_panel.py",
    }
    return {name: sha(path) for name, path in files.items()}


def register() -> dict[str, object]:
    if any(p.exists() for p in (POOL, RANKED, SELECTED, PREPARE, REPRODUCE, REPORT, REPORT_MD)):
        raise FileExistsError("support-sweep artifacts already exist")
    feature_manifest = json.loads(FEATURE_MANIFEST.read_text(encoding="utf-8"))
    spec: dict[str, object] = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT,
        "family": strategy.FAMILY,
        "registered_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FROZEN_BEFORE_DISCOVERY_OUTCOME_ACCESS",
        "evidence_level": "RETROSPECTIVE_PROVISIONAL",
        "historical_exposure": "2022H2-2023 outcomes were viewed in other strategy families; this candidate-conditioned policy result is retrospective, not untouched OOS. No threshold changes are allowed after evaluation.",
        "hypothesis": "A stock that trades below its minimum low from the five immediately preceding XTKS sessions but closes back above that support in the top quartile of its signal-day range may reflect a failed breakdown and short-term demand absorption.",
        "candidate_pool": {
            "universe": "Rows from the frozen Yahoo daily OHLCV feature panel; only internally valid positive-volume daily bars are actionable.",
            "support": "Signal-day low is strictly below the minimum low of the five immediately preceding official XTKS sessions; signal-day close is strictly above that minimum.",
            "rejection_quality": f"(close-low)/(high-low) >= {strategy.CLOSE_LOCATION_MIN}; zero-range or incomplete five-session history is ineligible.",
            "no_market_or_gap_filter": True,
            "no_fundamental_or_future_fields": True,
        },
        "score_and_selection": {
            "score": "Equal-weight mean of signal-day close location and (close - prior-five-session-low)/(high-low).",
            "daily_selection": f"Score descending; at most {strategy.MAX_NAMES_PER_DAY} symbols per XTKS session. Include up to five available candidates; abstain if none.",
            "tie_breaks": ["score descending", "close_location descending", "support_reclaim_quality descending", "symbol ascending"],
            "cooldown": "Suppress the same symbol on the immediately following official XTKS session after selection; only selected rows update cooldown state.",
            "multiple_names_per_day": True,
        },
        "target": "Signal-date OHLCV determines the setup. Enter at next official XTKS session open and exit at close of the fifth official XTKS session including entry; return is exit close / entry open - 1.",
        "periods": {
            "2022H2_discovery_signal_end": H2_LAST.date().isoformat(),
            "2022H2_last_exit": H2_EXIT.date().isoformat(),
            "2023_discovery_signal_end": Y23_LAST.date().isoformat(),
            "2023_last_exit": Y23_EXIT.date().isoformat(),
            "2024": "Closed; no candidate family result may be selected or tuned from it.",
            "2025": "Closed.",
            "2026": "Report-only; closed to selection and tuning.",
        },
        "gates_each_discovery_period": {
            "resolved_selected_minimum": 75,
            "mean_selected_per_calendar_month_including_zero_minimum": 5.0,
            "net_0_5pct": "mean > 0, median > 0, win_rate > 0.50, mean excluding top3 winners > 0",
            "label_coverage_minimum": 0.90,
            "downside_vs_full_candidate_pool": "-10% and -20% rates no higher than full candidate pool on the same dates",
            "monthly_robustness": "At least half of resolved selection months have positive net mean.",
            "complete_daily_cohorts": "At least 20 complete days with positive net mean, median, and mean excluding top3 winners.",
            "family_decision": "Both 2022H2 and 2023 must pass every gate. Otherwise REJECT; no replacement feature, cutoff, or ranking is tested.",
        },
        "costs": {"scenarios": list(COSTS), "primary_round_trip_assumption": COST, "note": "0.5% is a sensitivity assumption, not measured execution cost."},
        "data": {"feature_panel": str(FEATURE.relative_to(BATCH.parents[1])).replace("\\", "/"), "feature_end": feature_manifest["through"], "2024_plus_numeric_ohlcv_opened": False},
        "input_sha256": inputs(),
        "implementation_sha256": implementations(),
        "production_modified": False,
    }
    raw = json.dumps(spec, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    SPEC.write_text(raw, encoding="utf-8")
    SPEC_SHA.write_text(sha(SPEC) + "  " + SPEC.name + "\n", encoding="utf-8")
    return {"experiment_id": EXPERIMENT, "spec_sha256": sha(SPEC), "status": spec["status"]}


def verify() -> tuple[dict[str, object], SessionCalendar]:
    raw = SPEC.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SPEC_SHA.read_text(encoding="utf-8").split()[0]:
        raise ValueError("support-sweep frozen spec hash mismatch")
    spec = json.loads(raw)
    if spec["implementation_sha256"] != implementations() or spec["input_sha256"] != inputs():
        raise ValueError("support-sweep implementation or input changed after freeze")
    cal_manifest = json.loads(CALENDAR_MANIFEST.read_text(encoding="utf-8"))
    calendar = SessionCalendar.from_csv(CALENDAR, expected_sha256=cal_manifest["csv_sha256"])
    return spec, calendar


def decision_frames(spec_hash: str, calendar: SessionCalendar):
    panel = pd.read_parquet(FEATURE, columns=["date", "symbol", "open", "high", "low", "close", "volume"])
    panel["date"] = pd.to_datetime(panel["date"], errors="raise").dt.normalize()
    panel["symbol"] = panel["symbol"].astype("string")
    pool, counts = strategy.build_candidate_pool(panel, calendar.sessions, start=START, end=Y23_LAST)
    pool["family"], pool["spec_hash"] = strategy.FAMILY, spec_hash
    ranked = strategy.rank_candidates(pool)
    ranked["spec_hash"] = spec_hash
    selected = strategy.select_candidates(ranked, calendar.sessions)
    selected["spec_hash"] = spec_hash
    return pool, ranked, selected, counts


def frame_hash(frame: pd.DataFrame, extra: tuple[str, ...] = ()) -> str:
    keys = ["date", "symbol", "prior5_low", "close_location", "support_reclaim_quality", "score", "family", "spec_hash", *extra]
    part = frame.loc[:, keys].copy()
    part["date"] = pd.to_datetime(part["date"], errors="raise").dt.strftime("%Y-%m-%d")
    part["symbol"] = part["symbol"].astype("string")
    h = hashlib.sha256()
    for offset in range(0, len(part), 100_000):
        h.update(pd.util.hash_pandas_object(part.iloc[offset:offset + 100_000], index=False, categorize=True).to_numpy(dtype="uint64").tobytes())
    return h.hexdigest()


def prepare() -> dict[str, object]:
    spec, calendar = verify()
    if any(p.exists() for p in (POOL, RANKED, SELECTED, PREPARE, REPRODUCE, REPORT, REPORT_MD)):
        raise FileExistsError("support-sweep pool artifacts already exist")
    spec_hash = sha(SPEC)
    pool, ranked, selected, counts = decision_frames(spec_hash, calendar)
    CACHE.mkdir(parents=True, exist_ok=True)
    pool.to_parquet(POOL, index=False, compression="zstd")
    ranked.to_parquet(RANKED, index=False, compression="zstd")
    selected.to_parquet(SELECTED, index=False, compression="zstd")
    hashes = {
        "pool": frame_hash(pool),
        "ranked": frame_hash(ranked, ("raw_rank",)),
        "selected": frame_hash(selected, ("raw_rank", "policy_id", "policy_rank", "selection_status")),
    }
    months = len(pd.period_range(START.to_period("M"), Y23_LAST.to_period("M"), freq="M"))
    counts.update({"ranked_rows": len(ranked), "selected_rows": len(selected), "selected_days": int(selected["date"].nunique()), "candidate_days": int(pool["date"].nunique()), "mean_selected_per_month_including_zero_months": len(selected) / months})
    receipt = {
        "experiment_id": EXPERIMENT, "prepared_at_utc": datetime.now(timezone.utc).isoformat(), "spec_sha256": spec_hash,
        "input_sha256": spec["input_sha256"], "implementation_sha256": spec["implementation_sha256"],
        "counts": counts, "decision_hashes": hashes,
        "artifact_sha256": {"pool": sha(POOL), "ranked": sha(RANKED), "selected": sha(SELECTED)},
        "outcome_values_opened": False, "2024_plus_numeric_ohlcv_opened": False, "production_modified": False,
    }
    PREPARE.write_text(json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return receipt


def reproduce() -> dict[str, object]:
    spec, calendar = verify()
    receipt = json.loads(PREPARE.read_text(encoding="utf-8"))
    if receipt["spec_sha256"] != sha(SPEC) or receipt["artifact_sha256"] != {"pool": sha(POOL), "ranked": sha(RANKED), "selected": sha(SELECTED)}:
        raise ValueError("support-sweep pool receipt/artifact mismatch")
    rebuilt = decision_frames(sha(SPEC), calendar)
    hashes = {"pool": frame_hash(rebuilt[0]), "ranked": frame_hash(rebuilt[1], ("raw_rank",)), "selected": frame_hash(rebuilt[2], ("raw_rank", "policy_id", "policy_rank", "selection_status"))}
    if hashes != receipt["decision_hashes"]:
        raise ValueError("independently rebuilt support-sweep decisions differ")
    report = {"experiment_id": EXPERIMENT, "spec_sha256": sha(SPEC), "prepare_receipt_sha256": sha(PREPARE), "decision_hashes": hashes, "counts": receipt["counts"], "reproduced_exactly": True, "outcome_values_opened": False, "2024_plus_numeric_ohlcv_opened": False}
    REPRODUCE.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return report


def committed(path: Path) -> bool:
    relative = path.relative_to(BATCH.parents[1]).as_posix()
    return subprocess.run(["git", "cat-file", "-e", f"HEAD:{relative}"], capture_output=True).returncode == 0


def _net(summary: dict[str, object]) -> dict[str, object]:
    return summary["round_trip_cost_scenarios"][f"{COST:g}"]


def _summarize_selection(keys: pd.DataFrame, labels: pd.DataFrame, calendar: SessionCalendar, start: pd.Timestamp, last: pd.Timestamp):
    subset_keys = keys.loc[keys["date"].between(start, last)].copy()
    subset_labels = labels.loc[labels["date"].between(start, last)].copy()
    base = label_summary(subset_labels, costs=COSTS)
    daily = daily_cohorts(subset_keys, subset_labels, sessions=calendar.sessions[(calendar.sessions >= start) & (calendar.sessions <= last)], join_columns=JOIN)
    daily.loc[daily["cohort_status"].eq("COMPLETE"), "cohort_return"] -= COST
    cohort = cohort_summary(daily, repetitions=2000)
    resolved = subset_labels.loc[subset_labels["label_resolved"].astype(bool)].copy()
    resolved["net"] = pd.to_numeric(resolved["gross_return"], errors="coerce") - COST
    resolved["month"] = resolved["date"].dt.to_period("M").astype(str)
    positive_months = int(sum(g["net"].mean() > 0 for _, g in resolved.groupby("month", sort=True))) if len(resolved) else 0
    resolved["week"] = resolved["date"].dt.strftime("%G-W%V")
    monthly_weekly = {
        "monthly": {str(k): {"n": len(g), "net_mean": float(g["net"].mean()), "net_median": float(g["net"].median())} for k, g in resolved.groupby("month", sort=True)},
        "weekly": {str(k): {"n": len(g), "net_mean": float(g["net"].mean()), "net_median": float(g["net"].median())} for k, g in resolved.groupby("week", sort=True)},
        "symbol_concentration": {"distinct_symbols": int(resolved["symbol"].nunique()), "top1_share": float(resolved["symbol"].value_counts(normalize=True).iloc[0]) if len(resolved) else None, "top5_share": float(resolved["symbol"].value_counts(normalize=True).head(5).sum()) if len(resolved) else None},
        "positive_resolved_months": positive_months,
        "resolved_months": int(resolved["month"].nunique()),
    }
    return base, cohort, daily, monthly_weekly


def evaluate() -> dict[str, object]:
    spec, calendar = verify()
    if not committed(PREPARE) or not committed(REPRODUCE):
        raise ValueError("prepare receipt and exact reproduction report must be committed before labels")
    receipt = json.loads(PREPARE.read_text(encoding="utf-8"))
    reproduced = json.loads(REPRODUCE.read_text(encoding="utf-8"))
    if not reproduced.get("reproduced_exactly") or reproduced["spec_sha256"] != sha(SPEC):
        raise ValueError("support-sweep candidate decisions are not frozen and reproduced")
    pool, selected = pd.read_parquet(POOL), pd.read_parquet(SELECTED)
    if pool.empty or selected.empty:
        raise ValueError("no selected candidates; do not open outcomes or revise the policy")
    price = pd.read_parquet(FEATURE, columns=["date", "symbol", "open", "high", "low", "close", "volume"])
    price["date"] = pd.to_datetime(price["date"], errors="raise").dt.normalize()
    if price["date"].max() != Y23_EXIT:
        raise ValueError("price frame exceeds or misses the registered discovery cutoff")
    labels = label_builder.build_labels_for_eligible_signals(price, pool[["date", "symbol", "close"]], calendar)
    labels["family"], labels["spec_hash"] = strategy.FAMILY, sha(SPEC)
    labels["date"] = pd.to_datetime(labels["date"], errors="raise").dt.normalize()
    pool_stats, pool_cohort, _, _ = _summarize_selection(pool, labels, calendar, START, Y23_LAST)
    policy_stats, policy_cohort, daily, segments = _summarize_selection(selected, labels, calendar, START, Y23_LAST)
    periods = {}
    gates = {}
    for name, start, last in (("2022H2", START, H2_LAST), ("2023", pd.Timestamp("2023-01-01"), Y23_LAST)):
        pstats, pcohort, pdaily, seg = _summarize_selection(pool, labels, calendar, start, last)
        sstats, scohort, sdaily, sseg = _summarize_selection(selected, labels, calendar, start, last)
        pool_net, net = _net(pstats), _net(sstats)
        month_share = sseg["positive_resolved_months"] / max(sseg["resolved_months"], 1)
        coverage = net["n"] / max(net["requested_count"], 1)
        gate = {
            "minimum_sample": net["n"] >= 75,
            "minimum_monthly_frequency": float(len(selected.loc[selected["date"].between(start, last)]) / max(len(pd.period_range(start.to_period("M"), last.to_period("M"), freq="M")), 1)) >= 5.0,
            "positive_mean_median_win_top3": all(net[k] is not None and net[k] > 0 for k in ("mean", "median", "mean_excluding_top3_winners")) and net["win_rate"] is not None and net["win_rate"] > 0.50,
            "label_coverage": coverage >= 0.90,
            "downside_no_worse_than_candidate_pool": all(net[k] is not None and pool_net[k] is not None and net[k] <= pool_net[k] for k in ("minus10_rate", "minus20_rate")),
            "positive_month_majority": month_share >= 0.50,
            "complete_daily_cohorts": int(scohort["n"]) >= 20 and all(scohort[k] is not None and scohort[k] > 0 for k in ("mean", "median", "mean_excluding_top3_winners")),
        }
        gates[name] = gate
        periods[name] = {"candidate_pool": {"signal_metrics": pstats, "complete_day_metrics": pcohort}, "selected": {"signal_metrics": sstats, "complete_day_metrics": scohort, "daily_coverage": {"complete": int(sdaily["cohort_status"].eq("COMPLETE").sum()), "partial": int(sdaily["cohort_status"].eq("PARTIAL_UNRESOLVED").sum()), "abstain": int(sdaily["cohort_status"].eq("ABSTAIN").sum())}, "month_week_concentration": sseg}}
    decision = "KEEP_REQUIRES_SEPARATE_FROZEN_CONFIRMATION" if all(all(g.values()) for g in gates.values()) else "REJECT_SUPPORT_SWEEP"
    result = {
        "experiment_id": EXPERIMENT, "evidence_level": spec["evidence_level"], "decision": decision,
        "spec_sha256": sha(SPEC), "prepare_receipt_sha256": sha(PREPARE), "pool_reproduction_sha256": sha(REPRODUCE),
        "outcome_values_opened_at_utc": datetime.now(timezone.utc).isoformat(), "periods": periods, "gates": gates,
        "discovery_pooled": {"candidate_pool": pool_stats, "selected": policy_stats, "selected_complete_day_metrics": policy_cohort, "segments": segments},
        "labels_sha256": None, "2024_plus_numeric_ohlcv_opened": False, "production_modified": False,
    }
    result["labels_sha256"] = hashlib.sha256(pd.util.hash_pandas_object(labels, index=False).to_numpy(dtype="uint64").tobytes()).hexdigest()
    REPORT.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    REPORT_MD.write_text(
        f"# Support-Sweep Reclaim — discovery\n\n- Decision: `{decision}`.\n- Frozen setup: undercut and reclaim the prior five XTKS-session low; close location at least {strategy.CLOSE_LOCATION_MIN:.0%}; up to five names per day.\n- Target: next-session open to fifth-session close; net metrics assume 0.5% round-trip cost.\n- 2024+ outcomes were not opened. This is retrospective development evidence, not OOS.\n- Full period metrics and per-period gates are in the matching JSON report.\n",
        encoding="utf-8",
    )
    return {"experiment_id": EXPERIMENT, "decision": decision, "report": str(REPORT), "spec_sha256": sha(SPEC), "labels_sha256": result["labels_sha256"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "prepare", "reproduce", "evaluate"))
    args = parser.parse_args()
    result = {"register": register, "prepare": prepare, "reproduce": reproduce, "evaluate": evaluate}[args.action]()
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
