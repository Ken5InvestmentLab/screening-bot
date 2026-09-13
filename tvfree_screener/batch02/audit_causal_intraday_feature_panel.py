"""Offline causal intraday feature-panel materializer.

Reads raw hourly CSV only. It never reads strategy outcomes or precursor files.
Outputs belong in ignored .cache/ paths for research; commit only code/spec/report
summaries, not raw price rows.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

from tvfree_screener.batch02.causal_intraday_features import (
    MODEL_CANDIDATE_FEATURES_V1,
    extract_causal_features,
)
from tvfree_screener.batch02.raw_intraday_clock_bins import build_clock_bins


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def quantile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def read_raw_hourly(path: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    rows: list[dict[str, object]] = []
    all_keys: set[tuple[str, str]] = set()
    normal_keys: set[tuple[str, str]] = set()
    snapshot_keys: set[tuple[str, str]] = set()
    snapshot_rows = 0

    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            rows.append(row)
            try:
                stamp = datetime.fromisoformat(str(row["timestamp"]).replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
            key = (stamp.date().isoformat(), str(row.get("symbol", "")).strip())
            all_keys.add(key)
            try:
                snapshot = int(float(row.get("is_closing_snapshot", 0) or 0)) == 1
            except (TypeError, ValueError):
                snapshot = False
            if snapshot:
                snapshot_rows += 1
                snapshot_keys.add(key)
            else:
                normal_keys.add(key)

    metadata = {
        "raw_rows": len(rows),
        "snapshot_rows": snapshot_rows,
        "unique_symbol_sessions_all_rows": len(all_keys),
        "unique_symbol_sessions_normal_intraday": len(normal_keys),
        "unique_symbol_sessions_snapshot_only": len(snapshot_keys - normal_keys),
        "snapshot_only_keys": sorted(
            {"date": day, "symbol": symbol}
            for day, symbol in snapshot_keys - normal_keys
        ),
    }
    return rows, metadata


def numeric_feature_summary(
    rows: Iterable[dict[str, object]], feature: str
) -> dict[str, object]:
    values: list[float] = []
    total = 0
    for row in rows:
        total += 1
        value = row.get(feature)
        if value is None:
            continue
        number = float(value)
        if math.isfinite(number):
            values.append(number)
    return {
        "n": len(values),
        "coverage": len(values) / total if total else 0.0,
        "min": min(values) if values else None,
        "p01": quantile(values, 0.01),
        "median": quantile(values, 0.50),
        "p99": quantile(values, 0.99),
        "max": max(values) if values else None,
    }


def materialize(raw_hourly_csv: str | Path, output_dir: str | Path) -> dict[str, object]:
    raw_path = Path(raw_hourly_csv)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_rows, raw_metadata = read_raw_hourly(raw_path)
    bins, diagnostics = build_clock_bins(raw_rows)
    features = extract_causal_features(bins)

    output_csv = out_dir / "causal_intraday_feature_panel_v1.csv"
    fieldnames = sorted({key for row in features for key in row})
    with output_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(features)

    candidate_complete = sum(
        bool(row.get("model_candidate_v1_complete")) for row in features
    )
    summary = {
        "audit_id": "CAUSAL-INTRADAY-FEATURE-PANEL-V1",
        "strategy_outcomes_opened": False,
        "precursor_file_opened": False,
        "raw_sha256": sha256_file(raw_path),
        **raw_metadata,
        "complete_clock_bins": len(bins),
        "complete_bins_by_name": dict(Counter(bar.bin_name for bar in bins)),
        "clock_bin_status_counts": dict(Counter(item["status"] for item in diagnostics)),
        "model_candidate_features_v1": list(MODEL_CANDIDATE_FEATURES_V1),
        "model_candidate_complete_rows": candidate_complete,
        "model_candidate_complete_rate": (
            candidate_complete / len(features) if features else 0.0
        ),
        "feature_summary": {
            feature: numeric_feature_summary(features, feature)
            for feature in MODEL_CANDIDATE_FEATURES_V1
        },
        "diagnostic_only_features": [
            "body_pct",
            "body_to_range",
            "close_location",
            "volume_rel20",
        ],
        "output_csv": str(output_csv),
    }

    output_json = out_dir / "causal_intraday_feature_panel_v1_summary.json"
    with output_json.open("w", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=2, ensure_ascii=False, sort_keys=True)
        stream.write("\n")

    summary["output_csv_sha256"] = sha256_file(output_csv)
    summary["output_json_pre_hash_sha256"] = sha256_file(output_json)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-hourly", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    summary = materialize(args.raw_hourly, args.output_dir)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
