"""Post-hoc, local-only audit of CMF rows absent from the canonical label cache."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tvfree_screener.batch01 import evaluation
from tvfree_screener.batch01.session_calendar import SessionCalendar
from tvfree_screener.batch02 import core_cmf_flow_acceleration_audit as cmf
from tvfree_screener.batch02 import core_stochastic_cross_audit as canonical


REPORT_JSON = cmf.REPORTS / "cmf_local_label_coverage_recovery.json"
REPORT_MD = cmf.REPORTS / "cmf_local_label_coverage_recovery.md"
PERIODS = (
    ("2022H2", pd.Timestamp("2022-07-01"), pd.Timestamp("2022-12-23")),
    ("2023", pd.Timestamp("2023-01-01"), pd.Timestamp("2023-12-22")),
)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evaluate() -> dict[str, object]:
    feature_manifest = json.loads(cmf.FEATURE_MANIFEST.read_text(encoding="utf-8"))
    calendar_manifest = json.loads(cmf.CALENDAR_MANIFEST.read_text(encoding="utf-8"))
    if sha(cmf.FEATURE) != feature_manifest["sha256"]:
        raise ValueError("feature-only price panel hash mismatch")
    if feature_manifest.get("labels_included") is not False or feature_manifest.get("through") != cmf.Y23_EXIT.date().isoformat():
        raise ValueError("price panel is not the frozen label-free panel through the discovery exit")
    calendar = SessionCalendar.from_csv(cmf.CALENDAR, expected_sha256=calendar_manifest["csv_sha256"])

    selected = pd.read_parquet(cmf.SELECTED).copy()
    selected["date"] = pd.to_datetime(selected["date"], errors="raise").dt.normalize()
    in_scope = (
        selected["date"].between(PERIODS[0][1], PERIODS[0][2])
        | selected["date"].between(PERIODS[1][1], PERIODS[1][2])
    )
    selected = selected.loc[in_scope, ["date", "symbol", "family", "spec_hash"]].copy()
    selected = selected.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True)
    selected["symbol"] = selected["symbol"].astype("string")
    if len(selected) != 1800 or selected.duplicated(["date", "symbol"]).any():
        raise ValueError("frozen discovery selection scope or key uniqueness changed")

    cached, cached_hash = canonical.canonical_labels(selected[["date", "symbol"]], cmf.sha(cmf.SPEC))
    prices = pd.read_parquet(cmf.FEATURE, columns=["date", "symbol", "open", "high", "low", "close", "volume"])
    rebuilt = evaluation.build_five_session_labels(prices, selected, calendar)
    cached = cached.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True)
    rebuilt = rebuilt.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True)
    if not cached[["date", "symbol"]].equals(rebuilt[["date", "symbol"]]):
        raise ValueError("cached and rebuilt label keys do not match")

    present = ~cached["canonical_source_missing"].astype(bool)
    comparisons: dict[str, object] = {}
    for column in ("label_status", "label_resolved", "entry_date", "exit_date"):
        old = cached.loc[present, column].reset_index(drop=True)
        new = rebuilt.loc[present, column].reset_index(drop=True)
        if column == "label_status":
            old, new = old.astype("string"), new.astype("string")
        elif column == "label_resolved":
            old, new = old.astype(bool), new.astype(bool)
        else:
            old, new = pd.to_datetime(old), pd.to_datetime(new)
        same = old.equals(new)
        comparisons[column] = bool(same)
        if not same:
            raise ValueError(f"local label rebuild disagrees with existing cached {column}")
    previously_resolved = present & cached["label_resolved"].astype(bool)
    for column in ("entry_price", "exit_price", "gross_return"):
        old = pd.to_numeric(cached.loc[previously_resolved, column], errors="coerce").to_numpy(dtype=float)
        new = pd.to_numeric(rebuilt.loc[previously_resolved, column], errors="coerce").to_numpy(dtype=float)
        same = bool(np.allclose(old, new, rtol=0, atol=1e-12, equal_nan=True))
        comparisons[column] = same
        if not same:
            raise ValueError(f"local label rebuild disagrees with existing cached {column}")

    missing_join = cached["canonical_source_missing"].astype(bool)
    missing_status = rebuilt.loc[missing_join, "label_status"].value_counts().sort_index().to_dict()
    cost = cmf.COST
    period_metrics: dict[str, object] = {}
    for name, start, end in PERIODS:
        period_mask = selected["date"].between(start, end)
        row: dict[str, object] = {"requested": int(period_mask.sum())}
        for label, source in (("cached", cached), ("rebuilt", rebuilt)):
            resolved = source.loc[period_mask & source["label_resolved"].astype(bool), "gross_return"]
            net = pd.to_numeric(resolved, errors="coerce") - cost
            metrics = evaluation.return_metrics(net, requested_count=int(period_mask.sum()))
            row[label] = {
                "resolved": metrics["resolved_count"],
                "unresolved": int(period_mask.sum()) - int(metrics["resolved_count"]),
                "mean": metrics["mean"],
                "median": metrics["median"],
                "win_rate": metrics["win_rate"],
                "plus10_rate": metrics["plus10_rate"],
                "minus10_rate": metrics["minus10_rate"],
            }
        period_metrics[name] = row

    result: dict[str, object] = {
        "experiment_id": "DATA-QUALITY-CMF-LOCAL-LABEL-COVERAGE-20260913-01",
        "parent_experiment_id": cmf.EXPERIMENT,
        "scope": "Frozen selected signals in 2022H2 and 2023 only; local cached OHLCV only; no external data or 2024+ values.",
        "selected_count": int(len(selected)),
        "canonical_label_source_missing_count": int(missing_join.sum()),
        "rebuilt_status_for_missing_source_rows": {str(key): int(value) for key, value in missing_status.items()},
        "existing_cached_labels_match_rebuild": comparisons,
        "resolved_value_comparison_rows": int(previously_resolved.sum()),
        "period_metrics_at_assumed_0_5pct_round_trip_cost": period_metrics,
        "input_sha256": {
            "feature_panel": sha(cmf.FEATURE),
            "feature_manifest": sha(cmf.FEATURE_MANIFEST),
            "selected_artifact": sha(cmf.SELECTED),
            "canonical_label_artifact": sha(canonical.LABELS),
            "calendar": sha(cmf.CALENDAR),
            "cmf_spec": sha(cmf.SPEC),
            "canonical_label_join_digest": cached_hash,
        },
        "decision": "DIAGNOSE_LABEL_COVERAGE_ONLY; original CMF rejection and thresholds are unchanged.",
        "external_data_fetched": False,
        "production_modified": False,
    }
    REPORT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    lines = [
        "# CMF local label coverage audit",
        "",
        "- Scope: frozen 2022H2/2023 selected rows only; cached local OHLCV; no network and no later-period values.",
        f"- Canonical label-cache rows absent: {int(missing_join.sum())} / {len(selected)}.",
        f"- Rebuilt statuses for absent rows: `{json.dumps(result['rebuilt_status_for_missing_source_rows'], ensure_ascii=False, sort_keys=True)}`.",
        f"- Existing cached labels match local rebuild: `{json.dumps(comparisons, ensure_ascii=False, sort_keys=True)}`.",
        "- Returns use an assumed 0.5% round-trip cost. Rebuilding labels only diagnoses coverage; it does not retune or promote the rejected CMF rule.",
        "",
        "| Period | Requested | Cached resolved | Rebuilt resolved | Cached mean | Rebuilt mean | Cached median | Rebuilt median |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, row in period_metrics.items():
        before, after = row["cached"], row["rebuilt"]
        lines.append(f"| {name} | {row['requested']} | {before['resolved']} | {after['resolved']} | {before['mean']:.4%} | {after['mean']:.4%} | {before['median']:.4%} | {after['median']:.4%} |")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
