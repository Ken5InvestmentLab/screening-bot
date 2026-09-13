"""Staged winner/loser feature audit with 2022-2023 discovery and 2024 confirmation."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tvfree_screener.batch01 import core_moderate_ridge_audit as label_builder
from tvfree_screener.batch01.artifact_store import sha256_file, write_parquet_artifact
from tvfree_screener.batch01.evaluation import label_summary
from tvfree_screener.batch01.feature_panel import FEATURE_COLUMNS, build_feature_panel
from tvfree_screener.batch01.session_calendar import SessionCalendar
from tvfree_screener.batch02.core_market_state_audit import (
    FEATURES,
    LOSER_THRESHOLD,
    MIN_ABSOLUTE_POOLED_CLIFFS_DELTA,
    MIN_CLASS_COUNT,
    MIN_FINITE_RATE,
    SIGNAL_GAP_RATIO_MAX,
    SIGNAL_GAP_RATIO_MIN,
    WINNER_THRESHOLD,
    build_universe_pool,
    confirm_features,
    discover_features,
    freeze_discovery_bands,
    period_frames,
)


BATCH = Path(__file__).resolve().parent
B1 = BATCH.parent / "batch01"
SOURCE = B1 / ".cache/artifacts/tse_daily.csv"
PRESERVATION = B1 / "PRESERVATION_MANIFEST.json"
CALENDAR = B1 / "reference/xtks_sessions.csv"
CALENDAR_MANIFEST = B1 / "reference/xtks_sessions.manifest.json"
SPEC = BATCH / "reports/core_market_state_audit_spec.json"
SPEC_SHA = BATCH / "reports/core_market_state_audit_spec.sha256"
CACHE = BATCH / ".cache"
PANEL = CACHE / "core_market_state_panel_2022_2024.parquet"
BOUNDED_SOURCE = CACHE / "core_market_state_source_through_2024.csv"
POOL = CACHE / "core_market_state_candidate_pool_2022_2024.parquet"
PREPARE = CACHE / "core_market_state_prepare_receipt.json"
DISCOVERY_LABELS = CACHE / "core_market_state_discovery_labels.parquet"
CONFIRMATION_LABELS = CACHE / "core_market_state_2024_labels.parquet"
DISCOVERY_REPORT = BATCH / "reports/core_market_state_discovery.json"
DISCOVERY_MD = BATCH / "reports/core_market_state_discovery.md"
FREEZE = BATCH / "reports/core_market_state_feature_freeze.json"
CONFIRMATION_REPORT = BATCH / "reports/core_market_state_confirmation_2024.json"
CONFIRMATION_MD = BATCH / "reports/core_market_state_confirmation_2024.md"
PANEL_START = "2022-01-04"
PANEL_THROUGH = "2024-12-30"
SIGNAL_START = "2022-07-01"
SIGNAL_THROUGH = "2024-12-20"
DISCOVERY_THROUGH = "2023-12-22"
CONFIRMATION_START = "2024-01-01"
COSTS = (0.0, 0.005, 0.01)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def frame_digest(frame: pd.DataFrame, columns: list[str]) -> str:
    selected = frame.loc[:, columns].copy()
    selected["date"] = pd.to_datetime(selected["date"], errors="raise").dt.strftime("%Y-%m-%d")
    selected["symbol"] = selected["symbol"].astype("string")
    digest = hashlib.sha256()
    for offset in range(0, len(selected), 100_000):
        values = pd.util.hash_pandas_object(selected.iloc[offset:offset + 100_000], index=False, categorize=True)
        digest.update(values.to_numpy(dtype="uint64").tobytes())
    return digest.hexdigest()


def implementation_hashes() -> dict[str, str]:
    paths = {
        "feature_audit": BATCH / "core_market_state_audit.py",
        "audit_runner": Path(__file__),
        "feature_audit_tests": BATCH / "test_core_market_state_audit.py",
        "feature_panel": B1 / "feature_panel.py",
        "feature_separation": B1 / "feature_separation.py",
        "artifact_store": B1 / "artifact_store.py",
        "canonical_label_builder": B1 / "core_moderate_ridge_audit.py",
        "session_calendar": B1 / "session_calendar.py",
        "evaluation": B1 / "evaluation.py",
    }
    return {name: sha(path) for name, path in paths.items()}


def git_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=BATCH.parents[1], text=True).strip()


def input_hashes() -> dict[str, str]:
    preservation = json.loads(PRESERVATION.read_text(encoding="utf-8"))
    source_receipt = next(item for item in preservation["artifacts"] if item["member"] == SOURCE.name)
    calendar_manifest = json.loads(CALENDAR_MANIFEST.read_text(encoding="utf-8"))
    actual_source = sha(SOURCE)
    actual_calendar = sha(CALENDAR)
    if actual_source != source_receipt["member_sha256"]:
        raise ValueError("daily source differs from preserved artifact manifest")
    if actual_calendar != calendar_manifest["csv_sha256"]:
        raise ValueError("XTKS calendar differs from its manifest")
    return {
        "source_daily_sha256": actual_source,
        "preservation_manifest_sha256": sha(PRESERVATION),
        "calendar_sha256": actual_calendar,
        "calendar_manifest_sha256": sha(CALENDAR_MANIFEST),
    }


def verify_spec() -> tuple[dict[str, Any], SessionCalendar]:
    if not SPEC.exists() or not SPEC_SHA.exists():
        raise FileNotFoundError("market-state audit spec and hash must be registered first")
    spec_bytes = SPEC.read_bytes()
    spec_hash = hashlib.sha256(spec_bytes).hexdigest()
    expected = SPEC_SHA.read_text(encoding="utf-8").strip().split()[0]
    if spec_hash != expected:
        raise ValueError("market-state audit spec differs from its frozen hash")
    spec = json.loads(spec_bytes.decode("utf-8"))
    if tuple(spec["features"]) != FEATURES:
        raise ValueError("frozen feature list differs from the implementation")
    if spec["inputs"] != input_hashes():
        raise ValueError("registered source/calendar hashes differ from the current inputs")
    if spec["implementation_sha256"] != implementation_hashes():
        raise ValueError("feature or label implementation changed after registration")
    calendar_meta = json.loads(CALENDAR_MANIFEST.read_text(encoding="utf-8"))
    calendar = SessionCalendar.from_csv(CALENDAR, expected_sha256=calendar_meta["csv_sha256"])
    return spec, calendar


def panel_hashes() -> dict[str, str]:
    manifest_path = PANEL.with_suffix(PANEL.suffix + ".manifest.json")
    if not PANEL.exists() or not manifest_path.exists():
        raise FileNotFoundError("bounded signal-time panel must be generated after registration")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["source_sha256"] != input_hashes()["source_daily_sha256"]:
        raise ValueError("bounded feature panel used a different daily source")
    if manifest["calendar_sha256"] != input_hashes()["calendar_sha256"]:
        raise ValueError("bounded feature panel used a different XTKS calendar")
    if manifest["through"] != PANEL_THROUGH or manifest["labels_included"] is not False:
        raise ValueError("feature panel is not the registered outcome-free 2022-2024 panel")
    return {"panel_sha256": sha(PANEL), "panel_manifest_sha256": sha(manifest_path)}


def build_panel() -> dict[str, Any]:
    spec, calendar = verify_spec()
    manifest_path = PANEL.with_suffix(PANEL.suffix + ".manifest.json")
    if PANEL.exists() or manifest_path.exists() or BOUNDED_SOURCE.exists():
        raise FileExistsError("market-state feature panel or bounded source already exists")
    CACHE.mkdir(parents=True, exist_ok=True)
    bounded_rows = 0
    filtered_rows = 0
    with SOURCE.open("rb") as source_stream, BOUNDED_SOURCE.open("xb") as bounded_stream:
        header = source_stream.readline()
        if header.rstrip(b"\r\n").split(b",", 1)[0] != b"date":
            raise ValueError("daily source does not begin with the expected date field")
        bounded_stream.write(header)
        for line in source_stream:
            date_text = line.partition(b",")[0].decode("ascii")
            if PANEL_START <= date_text <= PANEL_THROUGH:
                bounded_stream.write(line)
                bounded_rows += 1
            else:
                filtered_rows += 1
    bounded_sha = sha256_file(BOUNDED_SOURCE)
    bounded = pd.read_csv(
        BOUNDED_SOURCE,
        usecols=["date", "symbol", "open", "high", "low", "close", "volume"],
        dtype={
            "symbol": "string", "open": "float64", "high": "float64",
            "low": "float64", "close": "float64", "volume": "float64",
        },
        parse_dates=["date"],
    )
    bounded["date"] = pd.to_datetime(bounded["date"], errors="raise").dt.normalize()
    if len(bounded) != bounded_rows or bounded.empty:
        raise ValueError("bounded raw daily source row count is inconsistent")
    panel = build_feature_panel(
        bounded,
        sessions=calendar.sessions,
        progress=lambda done, total: print(f"feature panel: {done}/{total} symbols", flush=True),
    )
    if len(panel) != len(bounded) or panel.duplicated(["date", "symbol"]).any():
        raise RuntimeError("feature generation changed source coverage or duplicated sessions")
    if not set(FEATURE_COLUMNS).issubset(panel.columns):
        raise RuntimeError("feature panel is missing a registered signal-time feature")
    if any(any(token in str(column).lower() for token in ("future", "target", "label", "realized")) for column in panel.columns):
        raise RuntimeError("outcome-like field appeared in the signal-time feature panel")
    inputs = spec["inputs"]
    receipt = write_parquet_artifact(
        panel,
        PANEL,
        metadata={
            "schema_version": "tvfree-market-state-panel-v1",
            "source_sha256": inputs["source_daily_sha256"],
            "source_member": SOURCE.name,
            "bounded_source_sha256": bounded_sha,
            "bounded_source_rows": bounded_rows,
            "rows_filtered_using_date_prefix_before_numeric_parse": filtered_rows,
            "calendar_sha256": inputs["calendar_sha256"],
            "feature_columns": list(FEATURE_COLUMNS),
            "feature_timestamp": "official XTKS session close; same-day market features are available after close",
            "start": PANEL_START,
            "through": PANEL_THROUGH,
            "symbols": int(panel["symbol"].nunique()),
            "decision_time_only": True,
            "labels_included": False,
            "2025_plus_numeric_ohlcv_parsed": False,
        },
    )
    return {"status": "FEATURE_ONLY_PANEL_BUILT", "rows": receipt["rows"], "panel_sha256": sha(PANEL), "git_sha": git_sha(), "later_numeric_ohlcv_parsed": False}


def _read_panel(*, through: str | None = None, start: str | None = None) -> pd.DataFrame:
    panel_hashes()
    frame = pd.read_parquet(PANEL)
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    frame["symbol"] = frame["symbol"].astype("string")
    if start is not None:
        frame = frame.loc[frame["date"].ge(pd.Timestamp(start))]
    if through is not None:
        frame = frame.loc[frame["date"].le(pd.Timestamp(through))]
    return frame.copy()


def prepare() -> dict[str, Any]:
    if PREPARE.exists() or POOL.exists():
        raise FileExistsError("market-state candidate preparation already exists")
    spec, _calendar = verify_spec()
    panel = _read_panel()
    pool, counts = build_universe_pool(panel, start=SIGNAL_START, end=SIGNAL_THROUGH)
    POOL.parent.mkdir(parents=True, exist_ok=True)
    pool.to_parquet(POOL, index=False, compression="zstd")
    columns = list(dict.fromkeys(["date", "symbol", "open", "high", "low", "close", "volume", "gap", *FEATURES]))
    receipt = {
        "schema_version": 1,
        "experiment_id": spec["experiment_id"],
        "git_sha": git_sha(),
        "registered_spec_sha256": sha(SPEC),
        "input_hashes": spec["inputs"],
        "panel_hashes": panel_hashes(),
        "implementation_sha256": implementation_hashes(),
        "counts": counts,
        "candidate_pool_rows_sha256": frame_digest(pool, columns),
        "candidate_pool_artifact_sha256": sha(POOL),
        "signal_period": [SIGNAL_START, SIGNAL_THROUGH],
        "outcome_values_opened": False,
        "2024_outcome_values_opened": False,
        "2025_plus_features_or_outcomes_opened": False,
        "production_modified": False,
    }
    PREPARE.write_text(json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return receipt


def verify_prepare() -> tuple[dict[str, Any], pd.DataFrame, SessionCalendar]:
    spec, calendar = verify_spec()
    receipt = json.loads(PREPARE.read_text(encoding="utf-8"))
    if receipt["registered_spec_sha256"] != sha(SPEC) or receipt["panel_hashes"] != panel_hashes():
        raise ValueError("candidate preparation uses a different registered spec or feature panel")
    if receipt["candidate_pool_artifact_sha256"] != sha(POOL):
        raise ValueError("candidate-pool artifact bytes differ from preparation receipt")
    pool = pd.read_parquet(POOL)
    columns = list(dict.fromkeys(["date", "symbol", "open", "high", "low", "close", "volume", "gap", *FEATURES]))
    if frame_digest(pool, columns) != receipt["candidate_pool_rows_sha256"]:
        raise ValueError("candidate-pool rows differ from preparation receipt")
    panel = _read_panel()
    reproduced, counts = build_universe_pool(panel, start=SIGNAL_START, end=SIGNAL_THROUGH)
    if counts != receipt["counts"] or frame_digest(reproduced, columns) != receipt["candidate_pool_rows_sha256"]:
        raise ValueError("signal-time all-market candidate pool did not reproduce")
    return spec, pool, calendar


def _build_labels(pool: pd.DataFrame, prices: pd.DataFrame, calendar: SessionCalendar, *, spec_hash: str) -> pd.DataFrame:
    signals = pool.loc[:, ["date", "symbol", "close"]].copy()
    labels = label_builder.build_labels_for_eligible_signals(prices, signals, calendar)
    labels["experiment_id"] = "CORE-ALL-MARKET-STATE-20260913-01"
    labels["spec_hash"] = spec_hash
    if len(labels) != len(pool) or labels.duplicated(["date", "symbol"]).any():
        raise ValueError("canonical labels lost or duplicated all-market signal rows")
    return labels


def _join(pool: pd.DataFrame, labels: pd.DataFrame, calendar: SessionCalendar) -> pd.DataFrame:
    keys = ["date", "symbol"]
    left = pool.copy()
    right = labels.loc[:, [
        "date", "symbol", "entry_date", "exit_date", "entry_price", "exit_price",
        "gross_return", "label_status", "label_resolved", "label_available_at",
        "experiment_id", "spec_hash",
    ]]
    joined = left.merge(right, on=keys, how="left", validate="one_to_one", indicator=True)
    if joined["_merge"].ne("both").any():
        raise ValueError("canonical labels do not cover every frozen signal row")
    joined = joined.drop(columns="_merge")
    positions = {pd.Timestamp(day): i for i, day in enumerate(calendar.sessions)}
    signal_pos = joined["date"].map(positions).to_numpy(dtype="int64")
    if not pd.DatetimeIndex(joined["entry_date"]).equals(pd.DatetimeIndex(calendar.sessions[signal_pos + 1])):
        raise ValueError("canonical label entry date differs from next XTKS open")
    if not pd.DatetimeIndex(joined["exit_date"]).equals(pd.DatetimeIndex(calendar.sessions[signal_pos + 5])):
        raise ValueError("canonical label exit date differs from fifth XTKS close")
    if not joined["label_resolved"].equals(joined["label_status"].eq("RESOLVED")):
        raise ValueError("canonical label resolution/status mismatch")
    return joined


def _summary_by_period(joined: pd.DataFrame, calendar: SessionCalendar) -> dict[str, Any]:
    frames = period_frames(joined)
    results: dict[str, Any] = {
        name: label_summary(frames[name], costs=COSTS)
        for name in ("2022H2", "2023")
    }
    results["discovery_pooled"] = label_summary(pd.concat([frames["2022H2"], frames["2023"]], ignore_index=True), costs=COSTS)
    del calendar
    return results


def discover() -> dict[str, Any]:
    if DISCOVERY_REPORT.exists() or DISCOVERY_MD.exists() or FREEZE.exists() or DISCOVERY_LABELS.exists():
        raise FileExistsError("market-state discovery report or feature freeze already exists")
    spec, pool, calendar = verify_prepare()
    discovery_pool = pool.loc[pool["date"].le(pd.Timestamp(DISCOVERY_THROUGH))].copy()
    if discovery_pool.empty:
        raise ValueError("no frozen all-market candidate rows in discovery period")
    # The price frame ends in 2023 so post-discovery outcome bars are unavailable to this phase.
    prices = _read_panel(through="2023-12-29")
    prices = prices.loc[:, ["date", "symbol", "open", "high", "low", "close", "volume"]].copy()
    labels = _build_labels(discovery_pool, prices, calendar, spec_hash=sha(SPEC))
    DISCOVERY_LABELS.parent.mkdir(parents=True, exist_ok=True)
    labels.to_parquet(DISCOVERY_LABELS, index=False, compression="zstd")
    joined = _join(discovery_pool, labels, calendar)
    frames = period_frames(joined)
    effects, eligible = discover_features(frames)
    selected = freeze_discovery_bands(discovery_pool, eligible)
    decision = "FREEZE_FOR_2024_CONFIRMATION" if selected else "REJECT_NO_STABLE_DISCOVERY_FEATURE"
    freeze: dict[str, Any] | None = None
    if selected:
        freeze = {
            "schema_version": 1,
            "experiment_id": spec["experiment_id"],
            "git_sha": git_sha(),
            "registered_spec_sha256": sha(SPEC),
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "evidence_level": "RETROSPECTIVE_PROVISIONAL",
            "discovery_report_sha256": None,
            "features": selected,
            "selection_rule": spec["discovery_selection_rule"],
            "2024_confirmation_only": True,
            "2025_plus_features_or_outcomes_opened": False,
        }
    report: dict[str, Any] = {
        "schema_version": 1,
        "experiment_id": spec["experiment_id"],
        "git_sha": git_sha(),
        "decision": decision,
        "evidence_level": "RETROSPECTIVE_PROVISIONAL",
        "registered_spec_sha256": sha(SPEC),
        "prepare_receipt_sha256": sha(PREPARE),
        "panel_hashes": panel_hashes(),
        "candidate_pool_rows_sha256": json.loads(PREPARE.read_text(encoding="utf-8"))["candidate_pool_rows_sha256"],
        "discovery_labels_sha256": sha(DISCOVERY_LABELS),
        "2022_2023_only_outcome_values_opened": True,
        "2024_outcome_values_opened": False,
        "2025_plus_features_or_outcomes_opened": False,
        "period_counts": {
            period: {"eligible_rows": len(frames[period]), "resolved": int(frames[period]["label_resolved"].sum()), "winners_ge_10": int((frames[period]["gross_return"] >= WINNER_THRESHOLD).sum()), "losers_le_minus10": int((frames[period]["gross_return"] <= LOSER_THRESHOLD).sum())}
            for period in ("2022H2", "2023", "discovery_pooled")
        },
        "overall_return_summaries": _summary_by_period(joined, calendar),
        "feature_effects": effects,
        "discovery_features_selected_by_registered_rule": eligible,
        "frozen_features": selected,
        "complexity": "Low for audit; one all-market daily panel, 31 registered signal-time features, two purged discovery splits, and at most two broad tercile comparisons.",
        "reproducibility": {
            "feature_panel_is_outcome_free": True,
            "candidate_pool_reproduced_before_outcomes": True,
            "discovery_label_rows": int(len(labels)),
            "all_unresolved_rows_retained": True,
            "2024_outcome_values_opened": False,
            "2025_plus_features_or_outcomes_opened": False,
        },
        "production_modified": False,
    }
    if freeze is not None:
        report_hashless = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        DISCOVERY_REPORT.write_text(report_hashless, encoding="utf-8")
        freeze["discovery_report_sha256"] = sha(DISCOVERY_REPORT)
        FREEZE.write_text(json.dumps(freeze, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    else:
        DISCOVERY_REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    md = [
        "# All-market winner/loser state audit — discovery",
        "",
        f"- Decision: `{decision}`.",
        "- Signal universe is every valid, positive-volume TSE daily bar with signal-day gap ratio in [0.60, 1.40]. No First Reversal prefilter or ranking is applied.",
        "- Target: next XTKS session open through the fifth XTKS session close; large winner >= +10%, large loser <= -10%.",
        "- Discovery signals are separately purged to 2022H2 and 2023. Candidate features were frozen before outcomes; 2024 outcomes remain unopened.",
        "- This is descriptive feature research with repeated-symbol and cross-sectional dependence; effect sizes are not independent-sample significance tests.",
        "- 2025+ features/outcomes were not used. DD60 is excluded because its previous First Reversal direction reversed in 2024; days-since-drop is excluded because missingness was ambiguous.",
        "",
        "| Split | Eligible rows | Resolved | Winners >=10% | Losers <=-10% |",
        "|---|---:|---:|---:|---:|",
    ]
    for period, row in report["period_counts"].items():
        md.append(f"| {period} | {row['eligible_rows']} | {row['resolved']} | {row['winners_ge_10']} | {row['losers_le_minus10']} |")
    md.extend(["", "## Frozen discovery features", ""])
    if selected:
        for feature in selected:
            md.append(f"- `{feature['feature']}` — {feature['direction']}, pooled Cliff's delta {feature['pooled_cliffs_delta']:.4f}, discovery tercile edges {feature['tercile_edges']}.")
    else:
        md.append("No feature passed the preregistered split-direction, coverage, class-count, and effect-size rules.")
    md.extend(["", "Full per-feature effect sizes and period sample counts are in the JSON report."])
    DISCOVERY_MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    return {"decision": decision, "candidate_rows": len(discovery_pool), "label_rows": len(labels), "selected_features": selected}


def confirm_2024() -> dict[str, Any]:
    if CONFIRMATION_REPORT.exists() or CONFIRMATION_MD.exists() or CONFIRMATION_LABELS.exists():
        raise FileExistsError("2024 confirmation report or labels already exist")
    spec, pool, calendar = verify_prepare()
    discovery = json.loads(DISCOVERY_REPORT.read_text(encoding="utf-8"))
    if discovery["decision"] != "FREEZE_FOR_2024_CONFIRMATION" or not FREEZE.exists():
        raise ValueError("2024 confirmation requires a committed discovery feature freeze")
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    if freeze["registered_spec_sha256"] != sha(SPEC) or freeze["discovery_report_sha256"] != sha(DISCOVERY_REPORT):
        raise ValueError("frozen feature list is not bound to the discovery report")
    confirmation_pool = pool.loc[pool["date"].ge(pd.Timestamp(CONFIRMATION_START))].copy()
    if confirmation_pool.empty:
        raise ValueError("no frozen 2024 signal-time features are available")
    # This is the first phase allowed to load 2024 outcome bars; no 2025 price is included.
    prices = _read_panel(start="2024-01-04", through=PANEL_THROUGH)
    prices = prices.loc[:, ["date", "symbol", "open", "high", "low", "close", "volume"]].copy()
    labels = _build_labels(confirmation_pool, prices, calendar, spec_hash=sha(SPEC))
    CONFIRMATION_LABELS.parent.mkdir(parents=True, exist_ok=True)
    labels.to_parquet(CONFIRMATION_LABELS, index=False, compression="zstd")
    joined = _join(confirmation_pool, labels, calendar)
    confirmation = period_frames(joined)["2024_confirmation"]
    feature_results = confirm_features(confirmation, freeze["features"])
    all_confirmed = bool(feature_results) and all(row["confirmation_checks"]["confirmed"] for row in feature_results)
    decision = "PASS_2024_CONFIRMATION_REQUIRES_SEPARATE_2025_FREEZE" if all_confirmed else "REJECT_ALL_MARKET_STATE_FEATURES"
    result: dict[str, Any] = {
        "schema_version": 1,
        "experiment_id": spec["experiment_id"],
        "git_sha": git_sha(),
        "decision": decision,
        "evidence_level": "RETROSPECTIVE_DIRECTIONAL_CONFIRMATION",
        "registered_spec_sha256": sha(SPEC),
        "discovery_report_sha256": sha(DISCOVERY_REPORT),
        "feature_freeze_sha256": sha(FREEZE),
        "confirmation_labels_sha256": sha(CONFIRMATION_LABELS),
        "period": [CONFIRMATION_START, SIGNAL_THROUGH],
        "signal_rows": int(len(confirmation)),
        "resolved_rows": int(confirmation["label_resolved"].sum()),
        "winners_ge_10": int((confirmation["gross_return"] >= WINNER_THRESHOLD).sum()),
        "losers_le_minus10": int((confirmation["gross_return"] <= LOSER_THRESHOLD).sum()),
        "overall_return_summary": label_summary(confirmation, costs=COSTS),
        "frozen_feature_results": feature_results,
        "2025_plus_features_or_outcomes_opened": False,
        "production_modified": False,
    }
    CONFIRMATION_REPORT.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    lines = [
        "# All-market winner/loser state audit — 2024 confirmation",
        "",
        f"- Decision: `{decision}`.",
        "- 2024 was opened only after the discovery feature freeze; it is historical directional confirmation, not untouched OOS.",
        "- 2025+ features/outcomes were not opened. A failure rejects this feature family without replacement search or threshold changes.",
        "",
        "| Feature | Discovery direction | 2024 Cliff delta | Median delta | Effect sign | Outer tercile winner-share direction | Counts sufficient | Confirmed |",
        "|---|---|---:|---:|---|---|---|---|",
    ]
    for row in feature_results:
        effect = row["effect"]
        checks = row["confirmation_checks"]
        bands = row["broad_bands"]["bands"]
        high, low = bands["high"]["extreme_winner_share"], bands["low"]["extreme_winner_share"]
        lines.append(
            f"| {row['feature']} | {row['discovery_direction']} | {effect['cliffs_delta']} | {effect['median_delta_winner_minus_loser']} | "
            f"{checks['effect_direction_matches']} | high={high}, low={low} | {checks['sufficient_winner_and_loser_counts_in_both_outer_bands']} | {checks['confirmed']} |"
        )
    lines.extend(["", f"Resolved outcomes: {result['resolved_rows']} of {result['signal_rows']}; cost scenarios are in the JSON report."])
    CONFIRMATION_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"decision": decision, "signal_rows": len(confirmation), "resolved_rows": int(confirmation["label_resolved"].sum()), "feature_results": feature_results}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build-panel", "prepare", "verify-prepare", "discover", "confirm-2024"))
    args = parser.parse_args()
    if args.command == "build-panel":
        result = build_panel()
    elif args.command == "prepare":
        receipt = prepare()
        result = {"counts": receipt["counts"], "candidate_pool_rows_sha256": receipt["candidate_pool_rows_sha256"], "outcome_values_opened": receipt["outcome_values_opened"]}
    elif args.command == "verify-prepare":
        _spec, pool, _calendar = verify_prepare()
        result = {"status": "PREPARE_REPRODUCED", "candidate_rows": len(pool)}
    elif args.command == "discover":
        result = discover()
    else:
        result = confirm_2024()
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
