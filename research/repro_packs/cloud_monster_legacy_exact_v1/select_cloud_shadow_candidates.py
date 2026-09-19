"""Outcome-blind scorer for the frozen exact Cloud Monster model.

This module never references a return, target, label, entry, or exit column.
It expects a causally generated feature frame containing only the required
signal-time fields plus the frozen ordered model features.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


SIGNAL_FIELDS = ["symbol", "timestamp", "date", "close", "d_pre3", "d_gap", "ret3"]
FORBIDDEN_NAMES = {
    "ret5",
    "ret5_jpx",
    "ret5_old",
    "monster",
    "danger",
    "target",
    "target_end_date",
    "entry_open",
    "exit_close",
    "gross_return",
}


def load_frame(path: Path, required: list[str]) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, usecols=lambda column: column in required, dtype={"symbol": str})
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path, columns=required)
    if suffix in {".pkl", ".pickle"}:
        # Pickle has no column projection. Subset immediately and never access outcomes.
        frame = pd.read_pickle(path)
        return frame.loc[:, required].copy()
    raise ValueError(f"unsupported feature-frame format: {path.suffix}")


def score_candidates(
    frame: pd.DataFrame,
    artifact: dict,
    start: str,
    end: str | None,
    model,
) -> pd.DataFrame:
    features = artifact["features"]
    required = list(dict.fromkeys(SIGNAL_FIELDS + features))
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise RuntimeError(f"missing required signal-time columns: {missing}")
    if set(features) & FORBIDDEN_NAMES:
        raise RuntimeError("frozen model artifact contains a forbidden outcome field")

    safe = frame.loc[:, required].copy()
    safe["symbol"] = safe["symbol"].astype(str)
    safe["timestamp"] = pd.to_datetime(safe["timestamp"])
    safe["date"] = pd.to_datetime(safe["date"]).dt.normalize()
    mask = (
        safe["date"].ge(start)
        & safe["d_pre3"].fillna(False).astype(bool)
        & safe["d_gap"].fillna(False).astype(bool)
        & safe["ret3"].ge(0.06)
        & safe["ret3"].lt(5)
    )
    if end is not None:
        mask &= safe["date"].lt(end)
    watch = (
        safe[mask]
        .sort_values(["symbol", "date", "timestamp"], kind="mergesort")
        .drop_duplicates(["symbol", "date"], keep="first")
        .copy()
    )

    values = watch[features].replace([np.inf, -np.inf], np.nan)
    watch["priority_score"] = model.predict_proba(values)[:, 1]
    selected = watch[watch["priority_score"].ge(float(artifact["threshold"]))].copy()
    selected["candidate_identity"] = (
        selected["symbol"]
        + "|"
        + selected["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    )
    return selected[
        ["date", "timestamp", "symbol", "candidate_identity", "close", "priority_score"]
    ].sort_values(["date", "symbol", "timestamp"], kind="mergesort")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feature-frame", type=Path, required=True)
    parser.add_argument("--model-artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", default="2026-03-01")
    parser.add_argument("--end")
    args = parser.parse_args()

    artifact = json.loads(args.model_artifact.read_text(encoding="utf-8"))
    pipeline_path = args.model_artifact.parent / artifact["pipeline_joblib"]["path"]
    model = joblib.load(pipeline_path)
    required = list(dict.fromkeys(SIGNAL_FIELDS + artifact["features"]))
    frame = load_frame(args.feature_frame, required)
    selected = score_candidates(frame, artifact, args.start, args.end, model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output = selected.copy()
    output["date"] = output["date"].dt.strftime("%Y-%m-%d")
    output["timestamp"] = output["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    output.to_csv(args.output, index=False, lineterminator="\n", float_format="%.17g")
    print(f"selected={len(output)} output={args.output}")


if __name__ == "__main__":
    main()
