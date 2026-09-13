"""Rebuild complete canonical labels for unchanged frozen trend-compression choices."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from tvfree_screener.batch01 import core_moderate_ridge_audit as label_builder
from tvfree_screener.batch01.evaluation import label_summary
from tvfree_screener.batch01.session_calendar import SessionCalendar
from tvfree_screener.batch02 import core_trend_compression_audit as audit


BATCH = Path(__file__).resolve().parent
B1 = BATCH.parent / "batch01"
SPEC = BATCH / "reports/core_trend_compression_label_recovery_spec.json"
SPEC_SHA = BATCH / "reports/core_trend_compression_label_recovery_spec.sha256"
LABELS = BATCH / ".cache/core_trend_compression_canonical_labels.parquet"
REPORT = BATCH / "reports/core_trend_compression_label_recovery.json"
REPORT_MD = BATCH / "reports/core_trend_compression_label_recovery.md"
FEATURE = B1 / ".cache/core_moderate_features_through_2023.parquet"
FEATURE_MANIFEST = FEATURE.with_suffix(FEATURE.suffix + ".manifest.json")
CALENDAR = B1 / "reference/xtks_sessions.csv"
CALENDAR_MANIFEST = B1 / "reference/xtks_sessions.manifest.json"
RAW_SOURCE = B1 / ".cache/artifacts/tse_daily.csv"
PRESERVATION = B1 / "PRESERVATION_MANIFEST.json"
TOP_NS = (1, 2, 3, 5)
PERIOD_START = pd.Timestamp("2022-07-01")
LAST_SIGNAL = pd.Timestamp("2023-12-22")
LAST_EXIT = pd.Timestamp("2023-12-29")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def decision_hashes(pool: pd.DataFrame, ranked: pd.DataFrame, selected: pd.DataFrame) -> dict[str, str]:
    return {
        "pool": audit.digest_frame(pool, ["date", "symbol", "ret20", "rv5", "rv20", "rv_ratio_5_20"]),
        "ranked": audit.digest_frame(ranked, ["date", "symbol", "raw_rank", "daily_candidate_count", "rv_ratio_5_20", "ret20"]),
        "selected": audit.digest_frame(selected, ["date", "symbol", "top_n", "raw_rank", "daily_candidate_count", "rv_ratio_5_20", "ret20"]),
    }


def freeze_spec() -> dict[str, object]:
    if REPORT.exists() or REPORT_MD.exists() or LABELS.exists():
        raise FileExistsError("label-recovery outcome output already exists")
    family_bytes = audit.SPEC.read_bytes()
    family_sha = hashlib.sha256(family_bytes).hexdigest()
    family = json.loads(family_bytes)
    if family_sha != audit.SPEC_SHA.read_text(encoding="utf-8").split()[0]:
        raise ValueError("family spec hash mismatch")
    topn_spec_path = BATCH / "reports/core_trend_compression_fixed_policy_diagnostic_spec.json"
    topn_spec_bytes = topn_spec_path.read_bytes()
    topn_spec_sha = hashlib.sha256(topn_spec_bytes).hexdigest()
    expected_topn_sha = (BATCH / "reports/core_trend_compression_fixed_policy_diagnostic_spec.sha256").read_text(encoding="utf-8").split()[0]
    if topn_spec_sha != expected_topn_sha:
        raise ValueError("frozen Top-N diagnostic spec hash mismatch")

    pool = pd.read_parquet(audit.POOL)
    ranked = pd.read_parquet(audit.RANKED)
    selected = pd.read_parquet(audit.SELECTED)
    prepared = audit.read_prepared()
    calculated_decisions = decision_hashes(pool, ranked, selected)
    if calculated_decisions != prepared["decision_hashes"]:
        raise ValueError("frozen candidate or selection decisions changed")
    if calculated_decisions != json.loads(topn_spec_bytes)["prepared_decision_hashes"]:
        raise ValueError("Top-N diagnostic decisions differ from the frozen prepare receipt")

    feature_manifest = json.loads(FEATURE_MANIFEST.read_text(encoding="utf-8"))
    calendar_manifest = json.loads(CALENDAR_MANIFEST.read_text(encoding="utf-8"))
    preservation = json.loads(PRESERVATION.read_text(encoding="utf-8"))
    raw_manifest = next(item for item in preservation["artifacts"] if item["member"] == RAW_SOURCE.name)
    if feature_manifest["labels_included"] is not False or feature_manifest["through"] != LAST_EXIT.date().isoformat():
        raise ValueError("frozen decision-only feature panel does not end at the registered 2023 horizon")
    if feature_manifest["source_sha256"] != raw_manifest["member_sha256"]:
        raise ValueError("feature panel is not derived from the preserved daily source")
    if sha(FEATURE) != feature_manifest["sha256"]:
        raise ValueError("feature panel hash differs from manifest")
    if sha(CALENDAR) != calendar_manifest["csv_sha256"]:
        raise ValueError("XTKS calendar hash differs from manifest")

    spec: dict[str, object] = {
        "schema_version": 1,
        "diagnostic_id": "CORE-TREND-COMPRESSION-LABEL-RECOVERY-20260913",
        "registered_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FROZEN_BEFORE_CANONICAL_LABEL_REBUILD",
        "evidence_level": "RETROSPECTIVE_REPAIR_DIAGNOSTIC",
        "reason": "The first Top-N readout joined policy choices to a label artifact scoped to a different model's eligible rows. LABEL_ROW_MISSING values are coverage failures, not non-tradable outcomes; the prior resolved-only policy summaries are invalid for strategy judgment.",
        "scope": "Rebuild the existing five-session outcomes for every row in the frozen full pool, then re-evaluate the same frozen Top1/2/3/5 selections jointly. No feature, threshold, candidate pool, ranking, tie-break, cooldown, Top-N, or period changes. No promotion is permitted.",
        "family_spec_sha256": family_sha,
        "prior_topn_diagnostic_spec_sha256": topn_spec_sha,
        "prior_incomplete_label_artifact": {
            "path": str(label_builder.BATCH_DIR / ".cache/core_moderate_ridge_discovery_labels.parquet"),
            "sha256": "abf9c3181dfa1f86f78b75528eafaa27ba9bb9250db17b5b14e8970d60ad2732",
            "used_as_corrected_outcome_source": False,
            "prior_policy_summaries_valid": False,
            "reason": "Its labels were scoped to another candidate model's feature-eligible signals and omitted otherwise valid trend-compression candidates.",
        },
        "decision_hashes": calculated_decisions,
        "policy_hashes": prepared["policy_hashes"],
        "decision_file_hashes": {
            "pool": sha(audit.POOL),
            "ranked": sha(audit.RANKED),
            "selected": sha(audit.SELECTED),
        },
        "price_input": {
            "path": str(FEATURE.relative_to(BATCH.parents[1])).replace("\\", "/"),
            "sha256": feature_manifest["sha256"],
            "manifest_sha256": sha(FEATURE_MANIFEST),
            "source_daily_csv_sha256": feature_manifest["source_sha256"],
            "source_daily_csv_rows": 4061361,
            "bounded_through": LAST_EXIT.date().isoformat(),
            "feature_panel_rows": feature_manifest["rows"],
            "labels_included": False,
            "later_numeric_ohlcv_values_included_or_opened": False,
        },
        "calendar": {
            "path": str(CALENDAR.relative_to(BATCH.parents[1])).replace("\\", "/"),
            "sha256": calendar_manifest["csv_sha256"],
            "manifest_sha256": sha(CALENDAR_MANIFEST),
            "calendar_id": "XTKS",
        },
        "period": {
            "first_signal": PERIOD_START.date().isoformat(),
            "last_signal": LAST_SIGNAL.date().isoformat(),
            "last_exit": LAST_EXIT.date().isoformat(),
            "post_2023_outcome_access": "PROHIBITED",
        },
        "target": "Signal date close is used only as a validity check; enter at the next official XTKS session open and exit at the fifth official XTKS session close including entry. Return = exit close / entry open - 1.",
        "actionability": "Use the frozen core_moderate_ridge_audit.build_labels_for_eligible_signals implementation. Require all five future daily bars, finite positive OHLC prices, internally consistent OHLC ranges, positive volume, and each overnight open/previous close ratio in [0.60,1.40]. Preserve every unresolved status; no row substitution.",
        "round_trip_costs": [0.0, 0.005, 0.01],
        "cost_primary": 0.005,
        "top_n_policies": list(TOP_NS),
        "policy_change_after_freeze": False,
        "selection_join": "date,symbol; verify one-to-one keys and exact next-session/fifth-session label dates; zero missing generated labels is required before evaluation.",
        "existing_outcome_access": {
            "prior_incomplete_policy_numeric_summaries_seen": True,
            "corrected_summary_is_untouched_oos": False,
            "promotion_allowed": False,
        },
        "implementation_sha256": {},
        "production_modified": False,
    }
    code_paths = {
        "recovery_runner": Path(__file__),
        "frozen_family_audit": Path(audit.__file__),
        "label_builder": Path(label_builder.__file__),
        "evaluation_helper": B1 / "evaluation.py",
        "session_calendar": B1 / "session_calendar.py",
        "selection_helper": B1 / "selection.py",
    }
    spec["implementation_sha256"] = {name: sha(path) for name, path in code_paths.items()}
    raw = json.dumps(spec, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    SPEC.parent.mkdir(parents=True, exist_ok=True)
    SPEC.write_bytes(raw.encode("utf-8"))
    SPEC_SHA.write_text(sha(SPEC) + "  " + SPEC.name + "\n", encoding="utf-8")
    return spec


def verify_spec() -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame, pd.DataFrame, SessionCalendar]:
    raw = SPEC.read_bytes()
    expected_spec_sha = SPEC_SHA.read_text(encoding="utf-8").split()[0]
    if hashlib.sha256(raw).hexdigest() != expected_spec_sha:
        raise ValueError("label-recovery spec hash mismatch")
    spec = json.loads(raw)
    code_paths = {
        "recovery_runner": Path(__file__),
        "frozen_family_audit": Path(audit.__file__),
        "label_builder": Path(label_builder.__file__),
        "evaluation_helper": B1 / "evaluation.py",
        "session_calendar": B1 / "session_calendar.py",
        "selection_helper": B1 / "selection.py",
    }
    current_code_hashes = {name: sha(path) for name, path in code_paths.items()}
    if current_code_hashes != spec["implementation_sha256"]:
        raise ValueError("pinned implementation changed after label-recovery freeze")
    if sha(FEATURE) != spec["price_input"]["sha256"] or sha(FEATURE_MANIFEST) != spec["price_input"]["manifest_sha256"]:
        raise ValueError("bounded price input changed after label-recovery freeze")
    if sha(CALENDAR) != spec["calendar"]["sha256"] or sha(CALENDAR_MANIFEST) != spec["calendar"]["manifest_sha256"]:
        raise ValueError("XTKS calendar changed after label-recovery freeze")
    if hashlib.sha256(audit.SPEC.read_bytes()).hexdigest() != spec["family_spec_sha256"]:
        raise ValueError("frozen family spec changed")
    pool = pd.read_parquet(audit.POOL)
    ranked = pd.read_parquet(audit.RANKED)
    selected = pd.read_parquet(audit.SELECTED)
    prepared = audit.read_prepared()
    if decision_hashes(pool, ranked, selected) != spec["decision_hashes"] or prepared["decision_hashes"] != spec["decision_hashes"]:
        raise ValueError("frozen selection decisions changed")
    for key, path in (("pool", audit.POOL), ("ranked", audit.RANKED), ("selected", audit.SELECTED)):
        if sha(path) != spec["decision_file_hashes"][key]:
            raise ValueError("frozen decision artifact file changed: " + key)
    calendar = SessionCalendar.from_csv(CALENDAR, expected_sha256=str(spec["calendar"]["sha256"]))
    return spec, pool, ranked, selected, calendar


def build_complete_labels(pool: pd.DataFrame, calendar: SessionCalendar) -> pd.DataFrame:
    if LABELS.exists():
        raise FileExistsError("canonical recovery labels already exist")
    price_columns = ["date", "symbol", "open", "high", "low", "close", "volume"]
    prices = pd.read_parquet(FEATURE, columns=price_columns)
    prices["date"] = pd.to_datetime(prices["date"], errors="raise").dt.normalize()
    prices["symbol"] = prices["symbol"].astype("string")
    if prices.duplicated(["date", "symbol"]).any():
        raise ValueError("bounded daily OHLCV contains duplicate symbol/session rows")
    if prices["date"].max() != LAST_EXIT:
        raise ValueError("bounded daily OHLCV does not end on the registered final exit session")

    keys = pool.loc[:, ["date", "symbol"]].copy()
    keys["date"] = pd.to_datetime(keys["date"], errors="raise").dt.normalize()
    keys["symbol"] = keys["symbol"].astype("string")
    signals = keys.merge(prices.loc[:, ["date", "symbol", "close"]], on=["date", "symbol"], how="left", validate="one_to_one", indicator=True)
    if not signals["_merge"].eq("both").all() or signals["close"].isna().any():
        raise ValueError("a frozen candidate is absent from its bounded signal-date daily OHLCV")
    signals = signals.drop(columns="_merge")
    labels = label_builder.build_labels_for_eligible_signals(prices, signals, calendar)
    labels["family"] = audit.EXPERIMENT
    labels["spec_hash"] = hashlib.sha256(SPEC.read_bytes()).hexdigest()
    positions = {pd.Timestamp(day): index for index, day in enumerate(calendar.sessions)}
    label_positions = labels["date"].map(positions)
    if label_positions.isna().any():
        raise ValueError("a label signal date is absent from the XTKS calendar")
    labels["session_index"] = label_positions.astype("int32")
    if len(labels) != len(pool) or labels.duplicated(["date", "symbol"]).any():
        raise ValueError("canonical label build did not preserve one row per frozen candidate")
    if not labels["label_resolved"].equals(labels["label_status"].eq("RESOLVED")):
        raise ValueError("canonical label resolution/status mismatch")
    entry_positions = label_positions.to_numpy(dtype="int64") + 1
    exit_positions = label_positions.to_numpy(dtype="int64") + 5
    if (exit_positions >= len(calendar.sessions)).any():
        raise ValueError("frozen discovery has unavailable fifth-session exits")
    if not pd.DatetimeIndex(calendar.sessions[entry_positions]).equals(pd.DatetimeIndex(labels["entry_date"])):
        raise ValueError("canonical label builder entry dates differ from registered target")
    if not pd.DatetimeIndex(calendar.sessions[exit_positions]).equals(pd.DatetimeIndex(labels["exit_date"])):
        raise ValueError("canonical label builder exit dates differ from registered target")
    LABELS.parent.mkdir(parents=True, exist_ok=True)
    labels.to_parquet(LABELS, index=False)
    return labels


def join_labels(decisions: pd.DataFrame, labels: pd.DataFrame, calendar: SessionCalendar) -> pd.DataFrame:
    left = decisions.loc[:, ["date", "symbol"]].copy()
    left["date"] = pd.to_datetime(left["date"], errors="raise").dt.normalize()
    left["symbol"] = left["symbol"].astype("string")
    right = labels.loc[:, [
        "date", "symbol", "entry_date", "exit_date", "entry_price", "exit_price",
        "gross_return", "label_status", "label_resolved", "label_available_at",
        "family", "spec_hash", "session_index",
    ]].copy()
    merged = left.merge(right, on=["date", "symbol"], how="left", validate="one_to_one", indicator=True)
    if merged["_merge"].ne("both").any():
        raise ValueError("frozen policy row has no rebuilt canonical label")
    merged = merged.drop(columns="_merge")
    if not merged["label_resolved"].equals(merged["label_status"].eq("RESOLVED")):
        raise ValueError("policy label status/resolution mismatch")
    positions = merged["date"].map({pd.Timestamp(day): index for index, day in enumerate(calendar.sessions)}).to_numpy(dtype="int64")
    expected_entry = pd.DatetimeIndex(calendar.sessions[positions + 1])
    expected_exit = pd.DatetimeIndex(calendar.sessions[positions + 5])
    if not pd.DatetimeIndex(merged["entry_date"]).equals(expected_entry) or not pd.DatetimeIndex(merged["exit_date"]).equals(expected_exit):
        raise ValueError("policy label timing differs from next-open/fifth-close specification")
    resolved = merged["label_resolved"].fillna(False).astype(bool)
    numeric = merged.loc[resolved, ["gross_return", "entry_price", "exit_price"]].apply(pd.to_numeric, errors="coerce")
    if len(numeric) and (not np.isfinite(numeric.to_numpy()).all() or (numeric["entry_price"] <= 0).any()):
        raise ValueError("resolved rebuilt policy labels contain invalid values")
    if len(numeric) and not np.allclose(numeric["exit_price"] / numeric["entry_price"] - 1.0, numeric["gross_return"], rtol=1e-8, atol=1e-10):
        raise ValueError("rebuilt policy return does not match its entry and exit prices")
    return merged


def evaluate() -> dict[str, object]:
    if REPORT.exists() or REPORT_MD.exists():
        raise FileExistsError("recovery report already exists")
    spec, pool, ranked, selected, calendar = verify_spec()
    labels = build_complete_labels(pool, calendar)
    if len(labels) != len(pool):
        raise ValueError("full-pool label coverage is incomplete; evaluation stopped")

    end_session_index = int(calendar.position(LAST_EXIT))
    active = calendar.sessions[
        (calendar.sessions >= PERIOD_START)
        & (np.arange(len(calendar.sessions)) <= end_session_index - 5)
    ]
    pool_joined = join_labels(pool, labels, calendar)
    pool_metrics = label_summary(pool_joined, costs=(0.0, audit.COST, 0.01))
    pool_segments = audit.segment_metrics(pool_joined)
    pool_cohort, pool_daily = audit.cohort(pool, pool_joined, active)
    policies: dict[str, object] = {}
    pool_complete = pool_daily.loc[pool_daily["cohort_status"].eq("COMPLETE"), ["date", "cohort_return"]]

    for top_n in TOP_NS:
        choices = selected.loc[selected["top_n"].eq(top_n)].copy()
        joined = join_labels(choices, labels, calendar)
        metrics = label_summary(joined, costs=(0.0, audit.COST, 0.01))
        segments = audit.segment_metrics(joined)
        cohort_metrics, daily = audit.cohort(choices, joined, active)
        common = daily.loc[daily["cohort_status"].eq("COMPLETE"), ["date", "cohort_return"]].merge(
            pool_complete, on="date", how="inner", validate="one_to_one", suffixes=("_policy", "_pool")
        )
        net = metrics["round_trip_cost_scenarios"][f"{audit.COST:g}"]
        common_days = int(len(common))
        paired_add = float((common["cohort_return_policy"] - common["cohort_return_pool"]).mean()) if common_days else None
        selected_per_day = choices.groupby("date", sort=True).size()
        coverage = {
            "active_days": int(selected_per_day.size),
            "complete_days": int(daily["cohort_status"].eq("COMPLETE").sum()),
            "partial_days": int(daily["cohort_status"].eq("PARTIAL_UNRESOLVED").sum()),
            "abstain_days": int(daily["cohort_status"].eq("ABSTAIN").sum()),
        }
        positive_signal = audit.positive(net)
        positive_cohort = audit.positive(cohort_metrics)
        tail_not_worse = all(
            net.get(key) is not None and pool_metrics["round_trip_cost_scenarios"][f"{audit.COST:g}"].get(key) is not None
            and net[key] <= pool_metrics["round_trip_cost_scenarios"][f"{audit.COST:g}"][key]
            for key in ("minus10_rate", "minus20_rate")
        )
        retrospective_gate = positive_signal and positive_cohort and common_days >= 20 and paired_add is not None and paired_add > 0 and tail_not_worse
        policies[str(top_n)] = {
            "policy_sha256": spec["policy_hashes"][str(top_n)]["policy_sha256"],
            "selection_sha256": spec["policy_hashes"][str(top_n)]["selection_sha256"],
            "selected_count": int(len(choices)),
            "resolved_count": int(metrics["resolved_count"]),
            "unresolved_count": int(metrics["unresolved_count"]),
            "selected_names_per_active_day": {
                "mean": float(selected_per_day.mean()),
                "median": float(selected_per_day.median()),
                "max": int(selected_per_day.max()),
                "distribution": {str(k): int(v) for k, v in selected_per_day.value_counts().sort_index().items()},
            },
            "signal_metrics": metrics,
            "signal_segments_and_concentration": segments,
            "complete_daily_cohort_metrics_net_0_5pct": cohort_metrics,
            "daily_cohort_coverage": coverage,
            "common_complete_days_vs_full_pool": common_days,
            "paired_daily_value_add_vs_full_pool": paired_add,
            "signal_gate_positive": positive_signal,
            "cohort_gate_positive": positive_cohort,
            "tail_risk_not_worse_than_full_pool": tail_not_worse,
            "retrospective_family_gate": "PASS_FOR_SEPARATE_2024_PRE_REGISTRATION" if retrospective_gate else "REJECT_FROZEN_POLICY",
            "promotion_status": "NOT_ALLOWED_BY_LABEL_RECOVERY_SPEC",
        }

    result: dict[str, object] = {
        "schema_version": 1,
        "diagnostic_id": spec["diagnostic_id"],
        "evidence_level": spec["evidence_level"],
        "recovery_spec_sha256": hashlib.sha256(SPEC.read_bytes()).hexdigest(),
        "runner_sha256": sha(Path(__file__)),
        "implementation_sha256": spec["implementation_sha256"],
        "price_input_sha256": spec["price_input"]["sha256"],
        "raw_source_sha256": spec["price_input"]["source_daily_csv_sha256"],
        "calendar_sha256": spec["calendar"]["sha256"],
        "family_spec_sha256": spec["family_spec_sha256"],
        "topn_decisions_unchanged": True,
        "outcome_label_artifact_sha256": sha(LABELS),
        "candidate_pool_rows": int(len(pool)),
        "full_pool_label_rows": int(len(labels)),
        "full_pool_label_coverage": 1.0,
        "period": f"{PERIOD_START.date()} through {LAST_SIGNAL.date()}; all exits no later than {LAST_EXIT.date()}",
        "target_definition": spec["target"],
        "actionability": spec["actionability"],
        "prior_incomplete_policy_summaries_invalid": True,
        "prior_incomplete_label_artifact_used": False,
        "post_2023_numeric_ohlcv_opened": False,
        "current_system_benchmark_context": json.loads((BATCH / "reports/core_trend_compression_fixed_policy_diagnostic_spec.json").read_text(encoding="utf-8"))["current_system_benchmark_context"],
        "full_candidate_pool_reference": {
            "signal_metrics": pool_metrics,
            "segments_and_concentration": pool_segments,
            "complete_daily_cohort_metrics_net_0_5pct": pool_cohort,
            "coverage": {
                "active_days": int(pool_daily["selected_count"].gt(0).sum()),
                "complete_days": int(pool_daily["cohort_status"].eq("COMPLETE").sum()),
                "partial_days": int(pool_daily["cohort_status"].eq("PARTIAL_UNRESOLVED").sum()),
                "abstain_days": int(pool_daily["cohort_status"].eq("ABSTAIN").sum()),
            },
        },
        "frozen_top_n_policies": policies,
        "promotion": "NONE; any future validation requires a separate pre-registered spec.",
        "production_modified": False,
    }
    REPORT.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    lines = [
        "# Core Trend Compression: canonical label-coverage recovery",
        "",
        "- Evidence: retrospective repair diagnostic; not untouched OOS.",
        "- The prior Top-N resolved-only summaries are invalid because labels were scoped to a different model's eligible rows.",
        "- Full candidate pool labels were rebuilt from the saved decision-only daily OHLCV panel; all frozen candidate rows were retained.",
        "- Top1/2/3/5 choices, rank, features, thresholds, cooldown, and period were unchanged.",
        "- No policy is promoted by this report. 2024+ numeric OHLCV was not opened.",
        "- Primary net return subtracts a hypothetical 0.5% round-trip cost; cost is not measured execution friction.",
        "",
        "| Frozen Top-N | selected | resolved | unresolved | net mean | median | win | +10% | +20% | +50% | -10% | -20% | top1 removed mean | top3 removed mean | complete days | family gate |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for top_n, item in policies.items():
        metrics = item["signal_metrics"]
        net = metrics["round_trip_cost_scenarios"][f"{audit.COST:g}"]
        lines.append(
            f"| {top_n} | {metrics['selected_count']} | {metrics['resolved_count']} | {metrics['unresolved_count']} | "
            f"{net.get('mean')} | {net.get('median')} | {net.get('win_rate')} | {net.get('plus10_rate')} | "
            f"{net.get('plus20_rate')} | {net.get('plus50_rate')} | {net.get('minus10_rate')} | {net.get('minus20_rate')} | "
            f"{net.get('mean_excluding_top1_winner')} | {net.get('mean_excluding_top3_winners')} | "
            f"{item['daily_cohort_coverage']['complete_days']} | {item['retrospective_family_gate']} |"
        )
    lines.extend([
        "",
        "The current Bot benchmark in the frozen diagnostic spec is not directly comparable: it uses BOTTOM-signal events and a different entry/target definition.",
    ])
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("freeze", "evaluate"))
    args = parser.parse_args()
    if args.command == "freeze":
        frozen = freeze_spec()
        print(json.dumps({"status": frozen["status"], "spec_sha256": hashlib.sha256(SPEC.read_bytes()).hexdigest()}, indent=2))
    else:
        output = evaluate()
        print(json.dumps({
            "diagnostic_id": output["diagnostic_id"],
            "full_pool_rows": output["full_pool_label_rows"],
            "top_n": {
                key: {
                    "selected": value["selected_count"],
                    "resolved": value["resolved_count"],
                    "net_mean": value["signal_metrics"]["round_trip_cost_scenarios"][f"{audit.COST:g}"]["mean"],
                    "median": value["signal_metrics"]["round_trip_cost_scenarios"][f"{audit.COST:g}"]["median"],
                    "win_rate": value["signal_metrics"]["round_trip_cost_scenarios"][f"{audit.COST:g}"]["win_rate"],
                    "gate": value["retrospective_family_gate"],
                }
                for key, value in output["frozen_top_n_policies"].items()
            },
        }, ensure_ascii=False, indent=2))
