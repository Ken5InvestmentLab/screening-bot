"""Research-only OSS validation helpers for TV-Free experiments.

This module does not select strategies and must not be used to reopen rejected
families. It adds an independent leakage / selection-bias audit layer using
the MIT-licensed purgedcv package.

Two audits are intentionally separated:

* cv checks that label horizons do not overlap across purged CV folds.
* dsr reports PSR/DSR sensitivity for an already-defined return stream.

For the canonical 5BD research, do not feed raw per-signal returns to dsr
when those observations overlap heavily in calendar time. Prefer a
strategy/cohort return stream whose sampling unit has already been defined and
frozen. This tool is supporting evidence, never a replacement for the
repository's locked 2022H2-2023 / 2024 / 2025 / 2026 temporal policy.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from purgedcv import (
    PurgedKFold,
    audit_splitter,
    deflated_sharpe_ratio_full,
    effective_n_trials,
    minimum_backtest_length,
    probabilistic_sharpe_ratio,
)


def _finite_vector(values: Sequence[float] | pd.Series, *, name: str) -> np.ndarray:
    arr = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=float)
    if arr.ndim != 1 or arr.size < 2:
        raise ValueError(f"{name} must contain at least two observations")
    if not np.isfinite(arr).all():
        raise ValueError(f"{name} contains missing or non-finite values")
    if float(arr.std(ddof=0)) == 0.0:
        raise ValueError(f"{name} has zero variance")
    return arr


def purged_kfold_audit(
    frame: pd.DataFrame,
    *,
    prediction_column: str = "date",
    evaluation_column: str = "exit_date",
    n_splits: int = 5,
    embargo_observations: int = 0,
) -> pd.DataFrame:
    """Audit label-horizon leakage with an independent PurgedKFold implementation."""
    missing = sorted({prediction_column, evaluation_column}.difference(frame.columns))
    if missing:
        raise ValueError(f"missing temporal columns: {missing}")

    work = frame.loc[:, [prediction_column, evaluation_column]].copy()
    work[prediction_column] = pd.to_datetime(work[prediction_column], errors="raise")
    work[evaluation_column] = pd.to_datetime(work[evaluation_column], errors="raise")
    if work.isna().any().any():
        raise ValueError("temporal audit contains missing timestamps")
    if (work[evaluation_column] < work[prediction_column]).any():
        raise ValueError("evaluation time precedes prediction time")

    work = work.sort_values(
        [prediction_column, evaluation_column], kind="stable"
    ).reset_index(drop=True)

    kwargs: dict[str, object] = {}
    if embargo_observations:
        kwargs["embargo_observations"] = int(embargo_observations)

    cv = PurgedKFold(
        n_splits=int(n_splits),
        prediction_times=work[prediction_column],
        evaluation_times=work[evaluation_column],
        **kwargs,
    )
    report = audit_splitter(cv, np.zeros((len(work), 1), dtype=float))
    report["audit_clean"] = (
        report["temporal_leakage_free"].astype(bool)
        & report["train_nonempty"].astype(bool)
        & report["final_overlap_fraction"].eq(0.0)
    )
    return report


def selection_bias_summary(
    returns: Sequence[float] | pd.Series,
    *,
    trial_sharpes: Sequence[float] | pd.Series | None = None,
    benchmark_skill: float = 0.0,
    trial_sharpes_annualized: bool = False,
    bars_per_year: int | None = None,
) -> dict[str, object]:
    """Report PSR plus raw/effective-trial DSR for a frozen return stream."""
    arr = _finite_vector(returns, name="returns")
    observed_sr = float(arr.mean() / arr.std(ddof=0))
    out: dict[str, object] = {
        "n_observations": int(arr.size),
        "observed_sharpe_per_observation": observed_sr,
        "benchmark_skill": float(benchmark_skill),
        "psr": float(probabilistic_sharpe_ratio(arr, benchmark_skill=float(benchmark_skill))),
        "selection_bias": None,
    }

    if trial_sharpes is None:
        return out

    trials = _finite_vector(trial_sharpes, name="trial_sharpes")
    if trial_sharpes_annualized and bars_per_year is None:
        raise ValueError("bars_per_year is required when trial Sharpes are annualized")
    if bars_per_year is not None and bars_per_year <= 0:
        raise ValueError("bars_per_year must be positive")

    var_sharpe = float(np.var(trials, ddof=1))
    raw_n = int(trials.size)
    effective_n = int(effective_n_trials(trials))
    conversion = int(bars_per_year) if trial_sharpes_annualized else None

    raw_diag = deflated_sharpe_ratio_full(
        arr,
        n_trials=raw_n,
        var_sharpe=var_sharpe,
        bars_per_year=conversion,
    )
    effective_diag = deflated_sharpe_ratio_full(
        arr,
        n_trials=effective_n,
        var_sharpe=var_sharpe,
        bars_per_year=conversion,
    )
    out["selection_bias"] = {
        "trial_count_raw": raw_n,
        "trial_count_effective_autocorr": effective_n,
        "trial_sharpe_variance_input": var_sharpe,
        "trial_sharpes_annualized": bool(trial_sharpes_annualized),
        "bars_per_year": conversion,
        "dsr_raw_trial_count": asdict(raw_diag),
        "dsr_effective_trial_count": asdict(effective_diag),
        "minimum_backtest_years_for_annualized_sr_1_raw_trials": float(
            minimum_backtest_length(raw_n, target_sharpe=1.0)
        ),
        "minimum_backtest_years_for_annualized_sr_1_effective_trials": float(
            minimum_backtest_length(effective_n, target_sharpe=1.0)
        ),
        "interpretation_rule": (
            "Treat DSR as sensitivity evidence, not an automatic promotion gate. "
            "The effective-trial estimate is heuristic and overlapping return "
            "observations can invalidate naive Sharpe inference."
        ),
    }
    return out


def _write_json(data: object, output: str | None) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    print(text)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)

    cv = sub.add_parser("cv", help="independent purged-CV leakage audit")
    cv.add_argument("--input", required=True)
    cv.add_argument("--prediction-column", default="date")
    cv.add_argument("--evaluation-column", default="exit_date")
    cv.add_argument("--n-splits", type=int, default=5)
    cv.add_argument("--embargo-observations", type=int, default=0)
    cv.add_argument("--output")

    dsr = sub.add_parser("dsr", help="PSR/DSR selection-bias audit")
    dsr.add_argument("--returns", required=True)
    dsr.add_argument("--return-column", required=True)
    dsr.add_argument("--trial-sharpes")
    dsr.add_argument("--trial-sharpe-column", default="sharpe")
    dsr.add_argument("--benchmark-skill", type=float, default=0.0)
    dsr.add_argument("--trial-sharpes-annualized", action="store_true")
    dsr.add_argument("--bars-per-year", type=int)
    dsr.add_argument("--output")

    args = parser.parse_args()

    if args.mode == "cv":
        frame = pd.read_csv(args.input)
        report = purged_kfold_audit(
            frame,
            prediction_column=args.prediction_column,
            evaluation_column=args.evaluation_column,
            n_splits=args.n_splits,
            embargo_observations=args.embargo_observations,
        )
        payload = {
            "rows": int(len(frame)),
            "folds": int(len(report)),
            "all_folds_clean": bool(report["audit_clean"].all()),
            "report": report.to_dict(orient="records"),
        }
        _write_json(payload, args.output)
        return

    returns_frame = pd.read_csv(args.returns)
    if args.return_column not in returns_frame.columns:
        raise ValueError(f"missing return column: {args.return_column}")
    trial_values = None
    if args.trial_sharpes:
        trial_frame = pd.read_csv(args.trial_sharpes)
        if args.trial_sharpe_column not in trial_frame.columns:
            raise ValueError(f"missing trial Sharpe column: {args.trial_sharpe_column}")
        trial_values = trial_frame[args.trial_sharpe_column]

    payload = selection_bias_summary(
        returns_frame[args.return_column],
        trial_sharpes=trial_values,
        benchmark_skill=args.benchmark_skill,
        trial_sharpes_annualized=args.trial_sharpes_annualized,
        bars_per_year=args.bars_per_year,
    )
    _write_json(payload, args.output)


if __name__ == "__main__":
    main()
