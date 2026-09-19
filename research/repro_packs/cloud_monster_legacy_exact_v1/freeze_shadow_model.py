"""Freeze the exact historical sklearn Cloud model into a portable JSON scorer."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from select_cloud_shadow_candidates import score_candidates


FEATURES = [
    "rsi", "stoch", "bbpct", "vsurge", "atrp", "body", "lowerwick", "draw20",
    "offlow20", "ret1", "ret2", "ret3", "d_rsi", "d_stoch", "d_bbpct",
    "d_vsurge", "d_atrp", "d_body", "macd_pos", "macd_cross", "close_gt_ema20",
    "close_gt_ema50", "close_gt_ema75", "ema20_up", "ema50_up", "body_pos",
    "body1", "body2", "wick30", "wick50", "vol12", "vol15", "vol20", "vol30",
    "atr_lt5", "atr_lt7", "d_macdpos", "d_ema20", "d_ema25", "d_ema50",
    "d_ema75", "d_rsi50_70", "d_rsi60", "d_stoch75", "d_bb80", "d_vol12",
    "d_vol20", "d_vol30", "d_body1", "d_body2", "d_atr5", "d_atr7",
]
UNION_SHA256 = "91f1f956a48a308e21e49aa2a80c7075677ac5aa6d5dfae5d26c1b1ad7db4a62"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--historical-frame", type=Path, required=True)
    parser.add_argument("--expected-union", type=Path, required=True)
    parser.add_argument("--model-output", type=Path, required=True)
    parser.add_argument("--pipeline-output", type=Path, required=True)
    parser.add_argument("--assertion-output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    if sha256(args.expected_union) != UNION_SHA256:
        raise RuntimeError("expected union SHA-256 drift")
    full = pd.read_pickle(args.historical_frame).copy()
    full["symbol"] = full["symbol"].astype(str)
    full["timestamp"] = pd.to_datetime(full["timestamp"])
    full["date"] = pd.to_datetime(full["date"]).dt.normalize()
    watch = full[
        full["date"].ge("2026-03-01")
        & full["date"].lt("2026-09-01")
        & full["d_pre3"]
        & full["d_gap"]
        & full["ret3"].ge(0.06)
        & full["ret3"].lt(5)
        & full["ret5"].notna()
    ].sort_values(["symbol", "date", "timestamp"]).drop_duplicates(
        ["symbol", "date"], keep="first"
    ).copy()
    watch["monster"] = watch["ret5"].ge(0.20).astype(int)
    training = watch["date"].lt("2026-07-01")
    model = make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(
            C=0.15,
            max_iter=500,
            class_weight="balanced",
            random_state=1,
        ),
    )
    x = watch[FEATURES].replace([np.inf, -np.inf], np.nan)
    model.fit(x[training], watch.loc[training, "monster"])
    scores = model.predict_proba(x)[:, 1]
    threshold = float(pd.Series(scores[training.to_numpy()]).quantile(0.90))
    imputer: SimpleImputer = model.named_steps["simpleimputer"]
    scaler: StandardScaler = model.named_steps["standardscaler"]
    classifier: LogisticRegression = model.named_steps["logisticregression"]

    args.pipeline_output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, args.pipeline_output, compress=0, protocol=4)

    artifact = {
        "identity": "CLOUD_MONSTER_FROZEN_SHADOW_MODEL_V1",
        "source_identity": "CLOUD_MONSTER_LEGACY_EXACT_V1",
        "status": "FROZEN_FROM_EXACT_HISTORICAL_MODEL",
        "features": FEATURES,
        "imputer_strategy": "median",
        "imputer_statistics": imputer.statistics_.tolist(),
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "logistic_coef": classifier.coef_[0].tolist(),
        "logistic_intercept": float(classifier.intercept_[0]),
        "logistic_classes": classifier.classes_.tolist(),
        "logistic_parameters": {
            "C": 0.15,
            "max_iter": 500,
            "class_weight": "balanced",
            "random_state": 1,
        },
        "pipeline_joblib": {
            "path": args.pipeline_output.name,
            "sha256": sha256(args.pipeline_output),
            "required_scikit_learn": sklearn.__version__,
        },
        "threshold": threshold,
        "threshold_definition": "90th percentile of training priority_score",
        "training_end_exclusive": "2026-07-01",
        "historical_watch_start": "2026-03-01",
        "historical_assertion_end_exclusive": "2026-09-01",
        "training_rows": int(training.sum()),
        "watch_rows": int(len(watch)),
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "forward_rule": "score only causally available feature rows; no outcome availability gate",
        "promotion_warning": "historical model used 2026 outcomes; only later prospective shadow can support promotion",
    }
    args.model_output.parent.mkdir(parents=True, exist_ok=True)
    args.model_output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    shadow = score_candidates(full, artifact, "2026-03-01", "2026-09-01", model)
    expected = pd.read_csv(args.expected_union, dtype={"symbol": str})
    expected = expected[expected["lane"].eq("Monster")].copy()
    expected["timestamp"] = pd.to_datetime(expected["timestamp"])
    expected["date"] = pd.to_datetime(expected["date"]).dt.normalize()
    expected_ids = set(zip(expected["date"], expected["timestamp"], expected["symbol"]))
    shadow_ids = set(zip(shadow["date"], shadow["timestamp"], shadow["symbol"]))
    sklearn_selected = watch.loc[scores >= threshold, ["date", "timestamp", "symbol"]].copy()
    sklearn_ids = set(
        zip(sklearn_selected["date"], sklearn_selected["timestamp"], sklearn_selected["symbol"])
    )
    extras = shadow_ids - expected_ids
    missing = expected_ids - shadow_ids
    if expected_ids != sklearn_ids or missing or len(extras) != 1:
        raise RuntimeError("frozen scorer drift exceeds the known outcome-availability difference")
    score_by_id = {
        (row.date, row.timestamp, row.symbol): float(score)
        for row, score in zip(watch.itertuples(), scores)
    }
    max_score_diff = max(
        abs(float(row.priority_score) - score_by_id[(row.date, row.timestamp, row.symbol)])
        for row in shadow.itertuples()
        if (row.date, row.timestamp, row.symbol) in expected_ids
    )
    output = shadow.copy()
    output["date"] = output["date"].dt.strftime("%Y-%m-%d")
    output["timestamp"] = output["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    args.assertion_output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.assertion_output, index=False, lineterminator="\n", float_format="%.17g")

    receipt = {
        "identity": "CLOUD_MONSTER_FROZEN_SHADOW_MODEL_V1",
        "status": "OUTCOME_BLIND_SCORER_MATCHES_63_EVALUATED_PLUS_1_UNEVALUATED",
        "model_artifact": {"path": args.model_output.name, "sha256": sha256(args.model_output)},
        "pipeline_joblib": {"path": args.pipeline_output.name, "sha256": sha256(args.pipeline_output)},
        "historical_assertion": {
            "rows": int(len(output)),
            "legacy_evaluated_rows": int(len(expected)),
            "legacy_evaluated_identity_subset_exact": True,
            "missing_legacy_evaluated_rows": 0,
            "additional_outcome_blind_rows": [
                {"date": str(date.date()), "timestamp": str(timestamp), "symbol": symbol}
                for date, timestamp, symbol in sorted(extras)
            ],
            "difference_reason": "legacy selector required ret5.notna; forward selection cannot use endpoint availability",
            "max_score_abs_diff_vs_sklearn": float(max_score_diff),
            "path": args.assertion_output.name,
            "sha256": sha256(args.assertion_output),
        },
        "expected_union_sha256": sha256(args.expected_union),
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
