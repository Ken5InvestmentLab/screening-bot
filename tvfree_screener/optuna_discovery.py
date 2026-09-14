"""Optuna discovery-only harness for a new TV-Free research family.

The harness is deliberately narrow:

* only candidate dates from 2022-07-01 through 2023-12-31 are accepted;
* label/evaluation timestamps must also resolve by 2023-12-31;
* walk-forward folds train only on earlier dates and purge overlapping labels;
* the candidate universe, features, target threshold, top-N and trading cost are
  fixed inputs -- Optuna tunes only LogisticRegression C;
* the optimization objective is the per-active-date Sharpe of a fixed top-N
  cohort return stream;
* every completed trial's Sharpe is retained so purgedcv can report a DSR
  sensitivity for the selected trial.

This is research infrastructure. It does not reopen any rejected family and
must not consume 2024/2025/2026 outcomes for parameter selection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import optuna
import pandas as pd
from purgedcv import WalkForwardSplit, audit_splitter
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler

try:
    from tvfree_screener.oss_validation import selection_bias_summary
except ModuleNotFoundError:  # direct script execution
    from oss_validation import selection_bias_summary


DISCOVERY_START = pd.Timestamp("2022-07-01")
DISCOVERY_END = pd.Timestamp("2023-12-31")
DEFAULT_SEED = 20260914


def validate_discovery_frame(
    frame: pd.DataFrame,
    *,
    feature_columns: Iterable[str],
    prediction_column: str = "date",
    evaluation_column: str = "exit_date",
    return_column: str = "endpoint_gross_return",
    feature_cutoff_column: str | None = None,
) -> pd.DataFrame:
    """Fail closed if any selection input reaches outside the discovery window."""
    features = tuple(feature_columns)
    required = {prediction_column, evaluation_column, return_column, *features}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"missing discovery columns: {missing}")
    if not features:
        raise ValueError("at least one feature column is required")

    z = frame.copy()
    z[prediction_column] = pd.to_datetime(z[prediction_column], errors="raise")
    z[evaluation_column] = pd.to_datetime(z[evaluation_column], errors="raise")
    if z[[prediction_column, evaluation_column]].isna().any().any():
        raise ValueError("discovery frame contains missing temporal values")

    prediction_day = z[prediction_column].dt.tz_localize(None).dt.normalize()
    evaluation_day = z[evaluation_column].dt.tz_localize(None).dt.normalize()
    if prediction_day.min() < DISCOVERY_START or prediction_day.max() > DISCOVERY_END:
        raise ValueError("candidate dates must stay inside 2022-07-01..2023-12-31")
    if evaluation_day.max() > DISCOVERY_END:
        raise ValueError("discovery labels must resolve no later than 2023-12-31")
    if (evaluation_day < prediction_day).any():
        raise ValueError("evaluation timestamp precedes prediction timestamp")

    if feature_cutoff_column is not None:
        if feature_cutoff_column not in z.columns:
            raise ValueError(f"missing feature cutoff column: {feature_cutoff_column}")
        cutoff = pd.to_datetime(z[feature_cutoff_column], errors="raise")
        if cutoff.isna().any():
            raise ValueError("feature cutoff contains missing timestamps")
        cutoff_day = cutoff.dt.tz_localize(None).dt.normalize()
        if (cutoff_day > prediction_day).any():
            raise ValueError("feature cutoff occurs after candidate date")

    for column in features:
        z[column] = pd.to_numeric(z[column], errors="coerce")
    z[return_column] = pd.to_numeric(z[return_column], errors="coerce")
    numeric = [*features, return_column]
    if not np.isfinite(z[numeric].to_numpy(dtype=float)).all():
        raise ValueError("discovery input contains missing/non-finite features or returns")

    if "label_resolved" in z.columns and not z["label_resolved"].fillna(False).astype(bool).all():
        raise ValueError("unresolved labels are not allowed to disappear inside optimization")
    if "endpoint_label_resolved" in z.columns and not z["endpoint_label_resolved"].fillna(False).astype(bool).all():
        raise ValueError("unresolved endpoint labels are not allowed inside optimization")

    sort_columns = [prediction_column]
    if "symbol" in z.columns:
        z["symbol"] = z["symbol"].astype("string")
        sort_columns.append("symbol")
    z = z.sort_values(sort_columns, kind="stable").reset_index(drop=True)
    return z


def build_date_level_walkforward(
    frame: pd.DataFrame,
    *,
    prediction_column: str,
    evaluation_column: str,
    n_splits: int,
    test_dates: int,
) -> tuple[list[tuple[np.ndarray, np.ndarray]], pd.DataFrame]:
    """Create causal folds without splitting one candidate date across train/test."""
    day_frame = (
        frame.groupby(prediction_column, sort=True, as_index=False)[evaluation_column]
        .max()
        .sort_values(prediction_column, kind="stable")
        .reset_index(drop=True)
    )
    if len(day_frame) <= n_splits * test_dates:
        raise ValueError(
            "not enough unique candidate dates for requested walk-forward layout: "
            f"{len(day_frame)} <= {n_splits}*{test_dates}"
        )

    cv = WalkForwardSplit(
        n_splits=int(n_splits),
        test_size=int(test_dates),
        window="expanding",
        prediction_times=day_frame[prediction_column],
        evaluation_times=day_frame[evaluation_column],
    )
    audit = audit_splitter(cv, np.zeros((len(day_frame), 1), dtype=float))
    if not audit["temporal_leakage_free"].astype(bool).all():
        raise AssertionError("purgedcv walk-forward audit found temporal leakage")
    if not audit["train_nonempty"].astype(bool).all():
        raise ValueError("walk-forward produced an empty training fold")

    splits: list[tuple[np.ndarray, np.ndarray]] = []
    prediction_values = pd.to_datetime(frame[prediction_column])
    for train_day_idx, test_day_idx in cv.split(np.zeros((len(day_frame), 1), dtype=float)):
        train_days = set(pd.to_datetime(day_frame.iloc[train_day_idx][prediction_column]).tolist())
        test_days_set = set(pd.to_datetime(day_frame.iloc[test_day_idx][prediction_column]).tolist())
        train_rows = np.flatnonzero(prediction_values.isin(train_days).to_numpy())
        test_rows = np.flatnonzero(prediction_values.isin(test_days_set).to_numpy())
        if len(train_rows) == 0 or len(test_rows) == 0:
            raise ValueError("row-level walk-forward mapping produced an empty fold")
        splits.append((train_rows, test_rows))
    return splits, audit


def _daily_topn_returns(
    scored: pd.DataFrame,
    *,
    prediction_column: str,
    return_column: str,
    top_n: int,
    round_trip_cost: float,
) -> pd.Series:
    order = [prediction_column, "_prob_positive"]
    ascending = [True, False]
    if "symbol" in scored.columns:
        order.append("symbol")
        ascending.append(True)
    ranked = scored.sort_values(order, ascending=ascending, kind="stable")
    selected = ranked.groupby(prediction_column, sort=True, group_keys=False).head(int(top_n)).copy()
    selected["_net_return"] = selected[return_column] - float(round_trip_cost)
    daily = selected.groupby(prediction_column, sort=True)["_net_return"].mean()
    if daily.empty:
        raise ValueError("selection produced no active dates")
    return daily.astype(float)


def _return_metrics(values: pd.Series) -> dict[str, float | int | None]:
    x = pd.Series(values, dtype=float)
    if x.empty:
        return {
            "active_days": 0,
            "mean": None,
            "median": None,
            "win_rate": None,
            "minus10_rate": None,
            "plus20_rate": None,
            "top3_removed_mean": None,
            "sharpe_per_active_day": None,
        }
    std = float(x.std(ddof=0))
    top3 = x.drop(index=x.nlargest(min(3, len(x))).index)
    return {
        "active_days": int(len(x)),
        "mean": float(x.mean()),
        "median": float(x.median()),
        "win_rate": float((x > 0).mean()),
        "minus10_rate": float((x <= -0.10).mean()),
        "plus20_rate": float((x >= 0.20).mean()),
        "top3_removed_mean": float(top3.mean()) if len(top3) else None,
        "sharpe_per_active_day": float(x.mean() / std) if std > 0 else None,
    }


def evaluate_c(
    frame: pd.DataFrame,
    *,
    feature_columns: list[str],
    splits: list[tuple[np.ndarray, np.ndarray]],
    c_value: float,
    prediction_column: str,
    return_column: str,
    target_threshold: float,
    top_n: int,
    round_trip_cost: float,
) -> tuple[pd.Series, dict[str, object]]:
    """Evaluate one fixed-C model as a purged walk-forward top-N strategy."""
    oos_daily: list[pd.Series] = []
    fold_meta: list[dict[str, object]] = []

    for fold, (train_idx, test_idx) in enumerate(splits):
        train = frame.iloc[train_idx].copy()
        test = frame.iloc[test_idx].copy()
        y = (train[return_column] > float(target_threshold)).astype(int)
        if y.nunique() < 2:
            raise ValueError(f"fold {fold} training target has only one class")

        model = Pipeline(
            steps=[
                ("scale", RobustScaler(quantile_range=(25.0, 75.0))),
                (
                    "model",
                    LogisticRegression(
                        C=float(c_value),
                        solver="lbfgs",
                        max_iter=1000,
                        class_weight="balanced",
                        random_state=DEFAULT_SEED,
                    ),
                ),
            ]
        )
        model.fit(train[feature_columns], y)
        scored = test.copy()
        scored["_prob_positive"] = model.predict_proba(test[feature_columns])[:, 1]
        daily = _daily_topn_returns(
            scored,
            prediction_column=prediction_column,
            return_column=return_column,
            top_n=top_n,
            round_trip_cost=round_trip_cost,
        )
        oos_daily.append(daily)
        fold_meta.append(
            {
                "fold": int(fold),
                "train_rows": int(len(train)),
                "test_rows": int(len(test)),
                "train_max_date": str(pd.Timestamp(train[prediction_column].max()).date()),
                "test_min_date": str(pd.Timestamp(test[prediction_column].min()).date()),
                "test_max_date": str(pd.Timestamp(test[prediction_column].max()).date()),
                "active_days": int(len(daily)),
            }
        )

    combined = pd.concat(oos_daily).sort_index()
    if combined.index.duplicated().any():
        raise AssertionError("walk-forward folds produced duplicate OOS dates")
    metrics = _return_metrics(combined)
    metrics["folds"] = fold_meta
    return combined, metrics


def run_study(
    frame: pd.DataFrame,
    *,
    feature_columns: list[str],
    prediction_column: str = "date",
    evaluation_column: str = "exit_date",
    return_column: str = "endpoint_gross_return",
    feature_cutoff_column: str | None = None,
    target_threshold: float = 0.0,
    top_n: int = 1,
    round_trip_cost: float = 0.005,
    n_splits: int = 4,
    test_dates: int = 20,
    n_trials: int = 30,
    c_low: float = 1e-3,
    c_high: float = 100.0,
    seed: int = DEFAULT_SEED,
) -> tuple[dict[str, object], pd.DataFrame]:
    """Run the one-parameter discovery search and return an auditable summary."""
    if top_n < 1:
        raise ValueError("top_n must be >= 1")
    if not (0 <= round_trip_cost < 1):
        raise ValueError("round_trip_cost must be in [0, 1)")
    if n_trials < 2:
        raise ValueError("n_trials must be >= 2")
    if not (0 < c_low < c_high):
        raise ValueError("C search bounds must satisfy 0 < low < high")

    data = validate_discovery_frame(
        frame,
        feature_columns=feature_columns,
        prediction_column=prediction_column,
        evaluation_column=evaluation_column,
        return_column=return_column,
        feature_cutoff_column=feature_cutoff_column,
    )
    splits, split_audit = build_date_level_walkforward(
        data,
        prediction_column=prediction_column,
        evaluation_column=evaluation_column,
        n_splits=n_splits,
        test_dates=test_dates,
    )

    trial_returns: dict[int, pd.Series] = {}

    def objective(trial: optuna.Trial) -> float:
        c_value = trial.suggest_float("C", float(c_low), float(c_high), log=True)
        daily, metrics = evaluate_c(
            data,
            feature_columns=feature_columns,
            splits=splits,
            c_value=c_value,
            prediction_column=prediction_column,
            return_column=return_column,
            target_threshold=target_threshold,
            top_n=top_n,
            round_trip_cost=round_trip_cost,
        )
        sharpe = metrics["sharpe_per_active_day"]
        if sharpe is None or not np.isfinite(float(sharpe)):
            raise optuna.TrialPruned("undefined OOS daily Sharpe")
        trial_returns[trial.number] = daily
        for key in (
            "active_days",
            "mean",
            "median",
            "win_rate",
            "minus10_rate",
            "plus20_rate",
            "top3_removed_mean",
            "sharpe_per_active_day",
        ):
            trial.set_user_attr(key, metrics[key])
        return float(sharpe)

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=int(seed)),
        study_name="tvfree-discovery-only-logreg-c",
    )
    study.optimize(objective, n_trials=int(n_trials), show_progress_bar=False)

    completed = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    if len(completed) < 2:
        raise RuntimeError("fewer than two completed Optuna trials")
    best = study.best_trial
    best_daily, best_metrics = evaluate_c(
        data,
        feature_columns=feature_columns,
        splits=splits,
        c_value=float(best.params["C"]),
        prediction_column=prediction_column,
        return_column=return_column,
        target_threshold=target_threshold,
        top_n=top_n,
        round_trip_cost=round_trip_cost,
    )

    trial_sharpes = [
        float(t.user_attrs["sharpe_per_active_day"])
        for t in sorted(completed, key=lambda x: x.number)
    ]
    try:
        selection_bias = selection_bias_summary(
            best_daily,
            trial_sharpes=trial_sharpes,
        )
        selection_bias_error = None
    except ValueError as exc:
        selection_bias = None
        selection_bias_error = f"{type(exc).__name__}: {exc}"

    trial_rows = []
    for t in study.trials:
        row = {
            "trial": int(t.number),
            "state": str(t.state.name),
            "objective_sharpe": float(t.value) if t.value is not None else np.nan,
            "C": float(t.params["C"]) if "C" in t.params else np.nan,
        }
        row.update({k: t.user_attrs.get(k) for k in (
            "active_days", "mean", "median", "win_rate", "minus10_rate",
            "plus20_rate", "top3_removed_mean", "sharpe_per_active_day",
        )})
        trial_rows.append(row)

    summary: dict[str, object] = {
        "status": "DISCOVERY_ONLY_NOT_PROMOTED",
        "period": {
            "candidate_start": str(pd.Timestamp(data[prediction_column].min()).date()),
            "candidate_end": str(pd.Timestamp(data[prediction_column].max()).date()),
            "label_end_max": str(pd.Timestamp(data[evaluation_column].max()).date()),
        },
        "rows": int(len(data)),
        "unique_candidate_dates": int(data[prediction_column].nunique()),
        "features": list(feature_columns),
        "target": f"{return_column} > {float(target_threshold)}",
        "selection": {
            "top_n": int(top_n),
            "round_trip_cost": float(round_trip_cost),
        },
        "walk_forward": {
            "n_splits": int(n_splits),
            "test_dates": int(test_dates),
            "audit": split_audit.to_dict(orient="records"),
        },
        "search": {
            "sampler": "Optuna TPESampler",
            "seed": int(seed),
            "n_trials_requested": int(n_trials),
            "n_trials_completed": int(len(completed)),
            "parameter_space": {"C": {"low": float(c_low), "high": float(c_high), "log": True}},
            "only_optimized_parameter": "C",
        },
        "best_trial": {
            "number": int(best.number),
            "C": float(best.params["C"]),
            "objective_sharpe_per_active_day": float(best.value),
            "metrics": best_metrics,
        },
        "selection_bias": selection_bias,
        "selection_bias_error": selection_bias_error,
        "guardrails": {
            "uses_2024_for_selection": False,
            "uses_2025_for_selection": False,
            "uses_2026_for_selection": False,
            "may_reopen_rejected_family": False,
            "promotion_authorized": False,
        },
    }
    return summary, pd.DataFrame(trial_rows)


def _sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--features", required=True, help="comma-separated frozen feature columns")
    p.add_argument("--prediction-column", default="date")
    p.add_argument("--evaluation-column", default="exit_date")
    p.add_argument("--return-column", default="endpoint_gross_return")
    p.add_argument("--feature-cutoff-column")
    p.add_argument("--target-threshold", type=float, default=0.0)
    p.add_argument("--top-n", type=int, default=1)
    p.add_argument("--round-trip-cost", type=float, default=0.005)
    p.add_argument("--n-splits", type=int, default=4)
    p.add_argument("--test-dates", type=int, default=20)
    p.add_argument("--n-trials", type=int, default=30)
    p.add_argument("--c-low", type=float, default=1e-3)
    p.add_argument("--c-high", type=float, default=100.0)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--output", required=True)
    p.add_argument("--trials-output", required=True)
    a = p.parse_args()

    features = [x.strip() for x in a.features.split(",") if x.strip()]
    frame = pd.read_csv(a.input)
    summary, trials = run_study(
        frame,
        feature_columns=features,
        prediction_column=a.prediction_column,
        evaluation_column=a.evaluation_column,
        return_column=a.return_column,
        feature_cutoff_column=a.feature_cutoff_column,
        target_threshold=a.target_threshold,
        top_n=a.top_n,
        round_trip_cost=a.round_trip_cost,
        n_splits=a.n_splits,
        test_dates=a.test_dates,
        n_trials=a.n_trials,
        c_low=a.c_low,
        c_high=a.c_high,
        seed=a.seed,
    )
    summary["input"] = {
        "path": str(a.input),
        "sha256": _sha256(a.input),
    }
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    trial_path = Path(a.trials_output)
    trial_path.parent.mkdir(parents=True, exist_ok=True)
    trials.to_csv(trial_path, index=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
