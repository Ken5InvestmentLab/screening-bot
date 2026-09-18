#!/usr/bin/env python3
"""Generate the frozen five-candidate 2023-2026 report and rankings.

2026 is reporting/robustness-only. Candidate definitions and ranking contract
are frozen outside this program before the 2026 output is generated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
import xgboost


PACK = Path(__file__).resolve().parent
ROOT = PACK.parents[2]
sys.path.insert(0, str(ROOT / "tvfree_screener"))
sys.path.insert(0, str(PACK))

import v9_conditional_quality_research as v9  # noqa: E402
import reproduce as legacy  # noqa: E402
import select_shadow_candidates as shadow  # noqa: E402


IDENTITY = "WEAK_EARLY_FIVE_CANDIDATE_FULL_PERIOD_V1"
DAILY_SHA256 = "6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0"
SOURCE_BLOBS = {
    "tvfree_screener/v7_full_tail_research.py": "f7f49ab2e09496494adfb365c94e969973c4070c",
    "tvfree_screener/v9_conditional_quality_research.py": "45a1272fe49c526bbf69956419e34e96d696f7d6",
    "tvfree_screener/run.py": "b639a6f6f33c643c2dcf09383ccf7dbfc7790cfa",
}
SELECTORS = list(shadow.EXPECTED_HISTORICAL_COUNTS)
RANK_HIGH = [
    "mean_pct",
    "median_pct",
    "win_pct",
    "top3_ex_mean_pct",
    "max_down_pct",
]
RANK_LOW = ["minus10_pct", "minus20_pct"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_daily(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["date"], dtype={"symbol": str})
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(
        subset=["date", "symbol", "open", "high", "low", "close", "volume"]
    ).sort_values(["symbol", "date"]).reset_index(drop=True)


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(
        path,
        index=False,
        encoding="utf-8",
        lineterminator="\n",
        date_format="%Y-%m-%d",
        float_format="%.12g",
    )


def select_with_endpoints(
    tail: pd.DataFrame,
    daily: pd.DataFrame,
    calendar: pd.DatetimeIndex,
) -> dict[str, pd.DataFrame]:
    safe = shadow.select_candidates(tail)
    outputs: dict[str, pd.DataFrame] = {}
    for selector in SELECTORS:
        identities = safe.loc[
            safe["selector"] == selector,
            ["date", "symbol", "rank_volr20", "rank_body_pct", "mean_rank"],
        ]
        picks = tail.merge(
            identities,
            on=["date", "symbol"],
            how="inner",
            validate="one_to_one",
        )
        outputs[selector] = legacy.attach_canonical_endpoint(picks, daily, calendar)
    return outputs


def rank_candidates(aggregate: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    frame = pd.DataFrame.from_dict(aggregate, orient="index")
    ordinal_columns = []
    for field in RANK_HIGH:
        column = f"rank__{field}"
        frame[column] = frame[field].rank(method="average", ascending=False)
        ordinal_columns.append(column)
    for field in RANK_LOW:
        column = f"rank__{field}"
        frame[column] = frame[field].rank(method="average", ascending=True)
        ordinal_columns.append(column)
    frame["ordinal_score"] = frame[ordinal_columns].mean(axis=1)
    frame["selector"] = frame.index
    frame = frame.sort_values(
        [
            "ordinal_score",
            "top3_ex_mean_pct",
            "mean_pct",
            "median_pct",
            "win_pct",
            "n",
        ],
        ascending=[True, False, False, False, False, False],
        kind="mergesort",
    ).reset_index(drop=True)
    frame["overall_rank"] = np.arange(1, len(frame) + 1)
    return frame[
        ["overall_rank", "selector", "ordinal_score"] + RANK_HIGH + RANK_LOW + ["n"]
    ].to_dict(orient="records")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--daily-corpus", type=Path, required=True)
    parser.add_argument("--historical-output-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--start", default="2026-01-01")
    parser.add_argument("--end", default="2026-09-11")
    parser.add_argument(
        "--reuse-tail",
        action="store_true",
        help="Reuse the already-generated reporting-only Tail CSV after a downstream failure.",
    )
    args = parser.parse_args()

    if sha256(args.daily_corpus) != DAILY_SHA256:
        raise RuntimeError("daily corpus SHA drift")
    contract_path = PACK / "FULL_PERIOD_RANKING_CONTRACT.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract["status"] != "FROZEN_BEFORE_2026_REPORTING_OPEN":
        raise RuntimeError("ranking contract is not frozen")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw = read_daily(args.daily_corpus)
    cutoff = pd.Timestamp(raw["date"].max())
    tail_path = args.output_dir / "causal_tail_pool_2026_reporting_only.csv"
    if args.reuse_tail:
        if not tail_path.exists():
            raise RuntimeError("--reuse-tail requested but Tail CSV is missing")
        tail = pd.read_csv(
            tail_path,
            parse_dates=["date", "target_end_date"],
            dtype={"symbol": str},
        )
    else:
        prepared = v9.prepare(raw)
        tail = v9.generate_tail_pool(prepared, args.start, args.end)
    if tail.empty:
        raise RuntimeError("no mature 2026 Tail rows")
    if tail["target_end_date"].max() > cutoff:
        raise RuntimeError("unmatured endpoint escaped the fixed daily cutoff")

    if not args.reuse_tail:
        write_csv(tail, tail_path)
    symbols = set(tail["symbol"].astype(str))
    endpoint_daily = raw.loc[raw["symbol"].isin(symbols), ["date", "symbol", "open", "close"]]
    calendar = pd.DatetimeIndex(sorted(pd.Timestamp(value) for value in raw["date"].unique()))
    rows_2026 = select_with_endpoints(tail, endpoint_daily, calendar)

    yearly_rows: list[dict[str, Any]] = []
    aggregate_pre: dict[str, dict[str, Any]] = {}
    aggregate_full: dict[str, dict[str, Any]] = {}
    output_hashes: dict[str, str] = {tail_path.name: sha256(tail_path)}
    for selector in SELECTORS:
        historical_path = args.historical_output_dir / f"canonical_trade_rows_{selector}.csv"
        historical = pd.read_csv(
            historical_path,
            parse_dates=["signal_date", "entry_date", "fifth_xtks_exit_date"],
            dtype={"symbol": str},
        )
        current = rows_2026[selector]
        current_path = args.output_dir / f"canonical_trade_rows_{selector}_2026.csv"
        write_csv(current, current_path)
        output_hashes[current_path.name] = sha256(current_path)
        combined = pd.concat([historical, current], ignore_index=True)
        if combined.duplicated(["signal_date", "symbol"]).any():
            raise RuntimeError(f"duplicate date+symbol rows: {selector}")
        for year in (2023, 2024, 2025, 2026):
            subset = combined[combined["signal_date"].dt.year == year]
            yearly_rows.append(
                {"selector": selector, "period": str(year), **legacy.metrics(subset)}
            )
        aggregate_pre[selector] = legacy.metrics(historical)
        aggregate_full[selector] = legacy.metrics(combined)
        yearly_rows.append(
            {"selector": selector, "period": "2023-2026", **aggregate_full[selector]}
        )

    normalized = pd.DataFrame(yearly_rows)
    normalized_path = args.output_dir / "normalized_yearly_and_total_metrics.csv"
    write_csv(normalized, normalized_path)
    output_hashes[normalized_path.name] = sha256(normalized_path)

    report = {
        "identity": IDENTITY,
        "status": "2026_REPORTING_ONLY_FIXED_RULES_NO_RETUNE",
        "input_cutoff": cutoff.strftime("%Y-%m-%d"),
        "tail_signal_date_min": tail["date"].min().strftime("%Y-%m-%d"),
        "tail_signal_date_max": tail["date"].max().strftime("%Y-%m-%d"),
        "tail_rows": int(len(tail)),
        "contract_sha256": sha256(contract_path),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "xgboost": xgboost.__version__,
        },
        "source_blobs": SOURCE_BLOBS,
        "daily_corpus_sha256": DAILY_SHA256,
        "pre_2026_ranking_2023_2025": rank_candidates(aggregate_pre),
        "descriptive_ranking_2023_2026": rank_candidates(aggregate_full),
        "yearly_and_total": yearly_rows,
        "outputs": output_hashes,
        "2022": {
            "status": "SUMMARY_ONLY_EXCLUDED_FROM_EXACT_TOTAL_AND_RANKING",
            "source": "research/WEAK_EARLY_PHASE2_2022_FRESH_VALIDATION_20260914.md",
            "reason": "historical 89-row Tail identity is not recovered",
        },
    }
    report_path = args.output_dir / "full_period_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
