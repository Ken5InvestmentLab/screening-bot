"""Frozen lower-Bollinger reclaim research loop with outcome gating."""
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
from tvfree_screener.batch01.session_calendar import SessionCalendar
from tvfree_screener.batch02 import core_bollinger_reclaim as strategy
from tvfree_screener.batch02.core_support_sweep_report_recovery import summarize


BATCH = Path(__file__).resolve().parent
B1 = BATCH.parent / "batch01"
FEATURE = B1 / ".cache/core_moderate_features_through_2023.parquet"
FEATURE_MANIFEST = FEATURE.with_suffix(FEATURE.suffix + ".manifest.json")
CALENDAR = B1 / "reference/xtks_sessions.csv"
CALENDAR_MANIFEST = B1 / "reference/xtks_sessions.manifest.json"
SPEC = BATCH / "reports/core_bollinger_reclaim_spec.json"
SPEC_SHA = BATCH / "reports/core_bollinger_reclaim_spec.sha256"
CACHE = BATCH / ".cache"
POOL = CACHE / "core_bollinger_reclaim_pool.parquet"
RANKED = CACHE / "core_bollinger_reclaim_ranked.parquet"
SELECTED = CACHE / "core_bollinger_reclaim_selected.parquet"
PREPARE = BATCH / "reports/core_bollinger_reclaim_pool_receipt.json"
REPRODUCE = BATCH / "reports/core_bollinger_reclaim_pool_reproduction.json"
REPORT = BATCH / "reports/core_bollinger_reclaim_discovery.json"
REPORT_MD = BATCH / "reports/core_bollinger_reclaim_discovery.md"
EXPERIMENT = "CORE-BOLLINGER-RECLAIM-20260913-01"
START = pd.Timestamp("2022-07-01")
H2_LAST = pd.Timestamp("2022-12-23")
Y23_LAST = pd.Timestamp("2023-12-22")
Y23_EXIT = pd.Timestamp("2023-12-29")
JOIN = ("date", "symbol", "family", "spec_hash")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def inputs() -> dict[str, str]:
    fm = json.loads(FEATURE_MANIFEST.read_text(encoding="utf-8"))
    cm = json.loads(CALENDAR_MANIFEST.read_text(encoding="utf-8"))
    if sha(FEATURE) != fm["sha256"] or fm.get("labels_included") is not False or fm.get("through") != Y23_EXIT.date().isoformat():
        raise ValueError("bounded decision-only feature panel mismatch")
    if sha(CALENDAR) != cm["csv_sha256"]:
        raise ValueError("XTKS calendar manifest mismatch")
    return {"feature_sha256": sha(FEATURE), "feature_manifest_sha256": sha(FEATURE_MANIFEST), "daily_source_sha256": str(fm["source_sha256"]), "calendar_sha256": sha(CALENDAR), "calendar_manifest_sha256": sha(CALENDAR_MANIFEST)}


def implementation_hashes() -> dict[str, str]:
    files = {
        "candidate_and_policy": BATCH / "core_bollinger_reclaim.py",
        "audit_runner": Path(__file__),
        "label_builder": Path(label_builder.__file__),
        "evaluation": B1 / "evaluation.py",
        "session_calendar": B1 / "session_calendar.py",
        "feature_panel": B1 / "feature_panel.py",
        "one_to_one_report_summarizer": BATCH / "core_support_sweep_report_recovery.py",
    }
    return {name: sha(path) for name, path in files.items()}


def register() -> dict[str, object]:
    if any(p.exists() for p in (POOL, RANKED, SELECTED, PREPARE, REPRODUCE, REPORT, REPORT_MD)):
        raise FileExistsError("Bollinger-reclaim artifacts already exist")
    spec: dict[str, object] = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT,
        "family": strategy.FAMILY,
        "registered_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FROZEN_BEFORE_DISCOVERY_OUTCOME_ACCESS",
        "evidence_level": "RETROSPECTIVE_PROVISIONAL",
        "historical_exposure": "2022H2-2023 outcomes have been viewed in other unrelated strategy families; results are retrospective, not untouched OOS. No threshold changes after evaluation.",
        "hypothesis": "An intraday excursion below the prior-close-only 20-session lower Bollinger band, followed by a close back above that band in the upper half of the session range, may identify a volatility-normalized failed breakdown.",
        "candidate_pool": {
            "universe": "Rows in the frozen Yahoo daily OHLCV panel with complete, internally valid positive-volume bars.",
            "band": "Prior lower band = mean of the immediately preceding 20 official-session closes minus 2 population standard deviations; the signal-day close is excluded from band estimation.",
            "event": "Signal-day low < prior lower band and signal-day close > prior lower band.",
            "close_location_minimum": strategy.CLOSE_LOCATION_MIN,
            "full_official_session_history_required": True,
            "no_gap_market_volume_or_fundamental_filter": True,
            "no_future_or_outcome_fields": True,
        },
        "score_and_selection": {
            "score": "Equal-weight mean of signal-day close location and (close - prior lower band)/(high - low).",
            "selection": f"Score descending, at most {strategy.MAX_NAMES_PER_DAY} names per XTKS session, up to five eligible candidates; abstain if empty.",
            "tie_breaks": ["score descending", "close_location descending", "band_reclaim_quality descending", "symbol ascending"],
            "cooldown": "One immediately following official XTKS session per selected symbol; only selected rows update cooldown.",
            "multiple_names_per_day": True,
        },
        "target": "Signal-date OHLCV setup; enter next official XTKS session open and exit fifth official XTKS session close, with 0.5% primary round-trip cost assumption.",
        "periods": {"2022H2_last_signal": H2_LAST.date().isoformat(), "2023_last_signal": Y23_LAST.date().isoformat(), "last_exit": Y23_EXIT.date().isoformat(), "2024": "closed", "2025": "closed", "2026": "report-only and closed to selection"},
        "gates_each_discovery_period": {
            "resolved_selected_minimum": 75,
            "mean_selected_per_calendar_month_minimum": 5.0,
            "net_mean_median_and_top3_excluded_mean": "all > 0 and win rate > 0.50",
            "label_coverage_minimum": 0.90,
            "minus10_minus20_rates": "no higher than the complete candidate pool on the same dates",
            "positive_months": "at least half of resolved selection months",
            "complete_daily_cohorts": "at least 20 complete dates; net mean, median, and top3-excluded mean all > 0",
            "family_decision": "Both 2022H2 and 2023 must pass every gate; otherwise reject without replacement parameters.",
        },
        "cost_assumption": {"round_trip": 0.005, "sensitivity_scenarios": [0.0, 0.005, 0.01], "measured_live_cost": False},
        "data": {"feature_end": Y23_EXIT.date().isoformat(), "2024_plus_numeric_ohlcv_opened": False},
        "input_sha256": inputs(),
        "implementation_sha256": implementation_hashes(),
        "production_modified": False,
    }
    SPEC.write_text(json.dumps(spec, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    SPEC_SHA.write_text(sha(SPEC) + "  " + SPEC.name + "\n", encoding="utf-8")
    return {"experiment_id": EXPERIMENT, "spec_sha256": sha(SPEC), "status": spec["status"]}


def verify() -> tuple[dict[str, object], SessionCalendar]:
    raw = SPEC.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SPEC_SHA.read_text(encoding="utf-8").split()[0]:
        raise ValueError("Bollinger-reclaim spec hash mismatch")
    spec = json.loads(raw)
    if spec["implementation_sha256"] != implementation_hashes() or spec["input_sha256"] != inputs():
        raise ValueError("Bollinger-reclaim input or implementation changed after freeze")
    cm = json.loads(CALENDAR_MANIFEST.read_text(encoding="utf-8"))
    return spec, SessionCalendar.from_csv(CALENDAR, expected_sha256=cm["csv_sha256"])


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


def frame_hash(frame: pd.DataFrame) -> str:
    part = frame.copy()
    part["date"] = pd.to_datetime(part["date"], errors="raise").dt.strftime("%Y-%m-%d")
    if "symbol" in part:
        part["symbol"] = part["symbol"].astype("string")
    h = hashlib.sha256()
    h.update("\x1f".join(map(str, part.columns)).encode())
    for start in range(0, len(part), 100_000):
        h.update(pd.util.hash_pandas_object(part.iloc[start:start + 100_000], index=False, categorize=True).to_numpy(dtype="uint64").tobytes())
    return h.hexdigest()


def prepare() -> dict[str, object]:
    spec, calendar = verify()
    if any(p.exists() for p in (POOL, RANKED, SELECTED, PREPARE, REPRODUCE, REPORT, REPORT_MD)):
        raise FileExistsError("Bollinger-reclaim pool output already exists")
    pool, ranked, selected, counts = decision_frames(sha(SPEC), calendar)
    CACHE.mkdir(parents=True, exist_ok=True)
    pool.to_parquet(POOL, index=False, compression="zstd")
    ranked.to_parquet(RANKED, index=False, compression="zstd")
    selected.to_parquet(SELECTED, index=False, compression="zstd")
    counts.update({"ranked_rows": len(ranked), "selected_rows": len(selected), "selected_days": int(selected["date"].nunique())})
    receipt = {"experiment_id": EXPERIMENT, "spec_sha256": sha(SPEC), "inputs": spec["input_sha256"], "implementation_sha256": spec["implementation_sha256"], "counts": counts, "decision_hashes": {"pool": frame_hash(pool), "ranked": frame_hash(ranked), "selected": frame_hash(selected)}, "artifact_sha256": {"pool": sha(POOL), "ranked": sha(RANKED), "selected": sha(SELECTED)}, "outcome_values_opened": False, "2024_plus_numeric_ohlcv_opened": False}
    PREPARE.write_text(json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return receipt


def reproduce() -> dict[str, object]:
    spec, calendar = verify()
    receipt = json.loads(PREPARE.read_text(encoding="utf-8"))
    if receipt["artifact_sha256"] != {"pool": sha(POOL), "ranked": sha(RANKED), "selected": sha(SELECTED)}:
        raise ValueError("Bollinger-reclaim pool artifact changed")
    rebuilt = decision_frames(sha(SPEC), calendar)
    hashes = {"pool": frame_hash(rebuilt[0]), "ranked": frame_hash(rebuilt[1]), "selected": frame_hash(rebuilt[2])}
    if hashes != receipt["decision_hashes"]:
        raise ValueError("Bollinger-reclaim candidate/rank/selection failed exact reproduction")
    result = {"experiment_id": EXPERIMENT, "spec_sha256": sha(SPEC), "prepare_receipt_sha256": sha(PREPARE), "decision_hashes": hashes, "counts": receipt["counts"], "reproduced_exactly": True, "outcome_values_opened": False, "2024_plus_numeric_ohlcv_opened": False}
    REPRODUCE.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return result


def committed(path: Path) -> bool:
    relative = path.relative_to(BATCH.parents[1]).as_posix()
    return subprocess.run(["git", "cat-file", "-e", f"HEAD:{relative}"], capture_output=True).returncode == 0


def evaluate() -> dict[str, object]:
    spec, calendar = verify()
    if not committed(PREPARE) or not committed(REPRODUCE):
        raise ValueError("outcome-free receipt and reproduction must be committed first")
    receipt, reproduction = json.loads(PREPARE.read_text(encoding="utf-8")), json.loads(REPRODUCE.read_text(encoding="utf-8"))
    if not reproduction.get("reproduced_exactly") or reproduction["decision_hashes"] != receipt["decision_hashes"]:
        raise ValueError("Bollinger-reclaim selection was not frozen and reproduced")
    pool, selected = pd.read_parquet(POOL), pd.read_parquet(SELECTED)
    if pool.empty or selected.empty:
        raise ValueError("no selected candidates; do not open labels or change conditions")
    price = pd.read_parquet(FEATURE, columns=["date", "symbol", "open", "high", "low", "close", "volume"])
    price["date"] = pd.to_datetime(price["date"], errors="raise").dt.normalize()
    if price["date"].max() != Y23_EXIT:
        raise ValueError("price data escaped the registered cutoff")
    labels = label_builder.build_labels_for_eligible_signals(price, pool[["date", "symbol", "close"]], calendar)
    labels["family"], labels["spec_hash"] = strategy.FAMILY, sha(SPEC)
    labels["date"] = pd.to_datetime(labels["date"], errors="raise").dt.normalize()
    label_hash = hashlib.sha256(pd.util.hash_pandas_object(labels, index=False).to_numpy(dtype="uint64").tobytes()).hexdigest()
    periods, gates = {}, {}
    for name, begin, last in (("2022H2", START, H2_LAST), ("2023", pd.Timestamp("2023-01-01"), Y23_LAST)):
        pjoined, pstats, _, pday, _ = summarize(pool, labels, calendar.sessions, begin, last)
        sj, stats, daily, day, segments = summarize(selected, labels, calendar.sessions, begin, last)
        net = stats["round_trip_cost_scenarios"]["0.005"]
        pnet = pstats["round_trip_cost_scenarios"]["0.005"]
        coverage = stats["resolved_count"] / max(stats["selected_count"], 1)
        month_means = [item["net_mean"] for item in segments["monthly"].values()]
        positive_month_share = sum(m > 0 for m in month_means) / max(len(month_means), 1)
        freq = len(selected.loc[selected["date"].between(begin, last)]) / max(len(pd.period_range(begin.to_period("M"), last.to_period("M"), freq="M")), 1)
        gate = {
            "minimum_sample": net["n"] >= 75,
            "minimum_monthly_frequency": freq >= 5.0,
            "positive_mean_median_win_top3": all(net[k] is not None and net[k] > 0 for k in ("mean", "median", "mean_excluding_top3_winners")) and net["win_rate"] is not None and net["win_rate"] > 0.50,
            "label_coverage": coverage >= 0.90,
            "downside_no_worse_than_pool": all(net[k] is not None and pnet[k] is not None and net[k] <= pnet[k] for k in ("minus10_rate", "minus20_rate")),
            "positive_month_majority": positive_month_share >= 0.50,
            "complete_daily_cohorts": day["n"] >= 20 and all(day[k] is not None and day[k] > 0 for k in ("mean", "median", "mean_excluding_top3_winners")),
        }
        gates[name] = gate
        periods[name] = {"candidate_pool": {"rows": len(pjoined), "signal_metrics": pstats, "complete_day_metrics": pday}, "selected_top5": {"rows": len(sj), "signal_metrics": stats, "complete_day_metrics": day, "daily_coverage": {"complete": int(daily["cohort_status"].eq("COMPLETE").sum()), "partial": int(daily["cohort_status"].eq("PARTIAL_UNRESOLVED").sum()), "abstain": int(daily["cohort_status"].eq("ABSTAIN").sum())}, "segments": segments}, "gates": gate}
    decision = "KEEP_REQUIRES_SEPARATE_CONFIRMATION" if all(all(g.values()) for g in gates.values()) else "REJECT_BOLLINGER_RECLAIM"
    result = {"experiment_id": EXPERIMENT, "evidence_level": spec["evidence_level"], "decision": decision, "spec_sha256": sha(SPEC), "pool_receipt_sha256": sha(PREPARE), "pool_reproduction_sha256": sha(REPRODUCE), "decision_hashes": receipt["decision_hashes"], "label_sha256": label_hash, "outcome_values_opened_at_utc": datetime.now(timezone.utc).isoformat(), "periods": periods, "gates": gates, "2024_plus_numeric_ohlcv_opened": False, "production_modified": False}
    REPORT.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    REPORT_MD.write_text(f"# Lower-Bollinger Reclaim — discovery\n\n- Decision: `{decision}`.\n- Frozen prior-20-session lower-band event; up to five selections/day.\n- Target: next-session open to fifth-session close; 0.5% assumed round-trip cost.\n- Only purge-safe 2022H2/2023 outcomes were opened; 2024+ stayed closed.\n- Full period metrics and gate failures are in the JSON report.\n", encoding="utf-8")
    return {"experiment_id": EXPERIMENT, "decision": decision, "report": str(REPORT), "label_sha256": label_hash}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "prepare", "reproduce", "evaluate"))
    action = parser.parse_args().action
    result = {"register": register, "prepare": prepare, "reproduce": reproduce, "evaluate": evaluate}[action]()
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
