from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import no_tv_v43_2025_uncapped as v43

REF_START = "2025-01-06"
REF_END = "2025-06-30"
OLD_SELECTED_CONTEXT_CAP = 2.8640659721217943
EXPECTED_REQUESTED_SYMBOLS = 1910
V43_CANDIDATE_SYMBOLS = 1793
MIN_COVERAGE_FRAC = 0.95


def quantiles(x: pd.Series) -> dict:
    v = pd.to_numeric(x, errors="coerce").dropna().to_numpy(float)
    if not len(v):
        return {"n": 0}
    return {
        "n": int(len(v)),
        "q50": float(np.quantile(v, 0.50)),
        "q85": float(np.quantile(v, 0.85)),
        "q90": float(np.quantile(v, 0.90)),
        "q95": float(np.quantile(v, 0.95)),
        "min": float(np.min(v)),
        "max": float(np.max(v)),
    }


def build_contexts(data: pd.DataFrame) -> pd.DataFrame:
    x = data.loc[
        pd.to_datetime(data["date"]).between(REF_START, REF_END),
        ["date", "session", "market_median_atr", "market_candidate_count"],
    ].copy()
    x["date"] = pd.to_datetime(x["date"]).dt.strftime("%Y-%m-%d")
    x["market_median_atr"] = pd.to_numeric(x["market_median_atr"], errors="coerce")
    x["market_candidate_count"] = pd.to_numeric(x["market_candidate_count"], errors="coerce")
    x = x.dropna(subset=["market_median_atr", "market_candidate_count"])

    check = x.groupby(["date", "session"], sort=False).agg(
        atr_nunique=("market_median_atr", "nunique"),
        count_nunique=("market_candidate_count", "nunique"),
    )
    if (check["atr_nunique"] != 1).any() or (check["count_nunique"] != 1).any():
        raise RuntimeError("date/session market context is not internally constant")

    return (
        x.drop_duplicates(["date", "session"])
        .sort_values(["date", "session"])
        .reset_index(drop=True)
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frozen-daily", required=True)
    ap.add_argument("--max-workers", type=int, default=16)
    ap.add_argument("--output-dir", default="research_artifacts/v45_full_context_atr")
    a = ap.parse_args()

    data, prefilter, fetch = v43.build_dataset(a.frozen_daily, a.max_workers)
    contexts = build_contexts(data)

    if int(fetch.get("requested_symbols", -1)) != EXPECTED_REQUESTED_SYMBOLS:
        raise RuntimeError(
            f"universe drift: requested_symbols={fetch.get('requested_symbols')} "
            f"expected={EXPECTED_REQUESTED_SYMBOLS}"
        )
    coverage = float(fetch.get("candidate_symbols", 0)) / V43_CANDIDATE_SYMBOLS
    if coverage < MIN_COVERAGE_FRAC:
        raise RuntimeError(
            f"coverage too low vs V43 receipt: {coverage:.4f} < {MIN_COVERAGE_FRAC:.4f}"
        )

    contexts["month"] = contexts["date"].str[:7]
    monthly = {
        str(m): {
            **quantiles(g["market_median_atr"]),
            "candidate_count_median": float(g["market_candidate_count"].median()),
        }
        for m, g in contexts.groupby("month", sort=True)
    }

    expanding = {}
    months = sorted(contexts["month"].unique())
    for m in months:
        g = contexts[contexts["month"] <= m]
        expanding[str(m)] = quantiles(g["market_median_atr"])

    overall = quantiles(contexts["market_median_atr"])
    full_q90 = float(overall["q90"])

    result = {
        "audit_id": "CONSENSUS-V45-FULL-CONTEXT-ATR-REFERENCE-20260914",
        "scope": "outcome-free distribution audit; one full eligible date/session context = one vote",
        "reference_period": [REF_START, REF_END],
        "prefilter": prefilter,
        "hourly_fetch": fetch,
        "coverage_fraction_vs_v43_candidate_symbols": coverage,
        "context_rows": int(len(contexts)),
        "unique_dates": int(contexts["date"].nunique()),
        "sessions": sorted(int(v) for v in contexts["session"].unique()),
        "full_context_atr": overall,
        "monthly": monthly,
        "expanding_by_month": expanding,
        "candidate_count": quantiles(contexts["market_candidate_count"]),
        "comparison_only": {
            "old_selected_context_q90_cap_pct": OLD_SELECTED_CONTEXT_CAP,
            "full_context_q90_pct": full_q90,
            "absolute_difference_pct_points": full_q90 - OLD_SELECTED_CONTEXT_CAP,
            "relative_difference": full_q90 / OLD_SELECTED_CONTEXT_CAP - 1.0,
        },
        "strategy_return_columns_read": False,
        "2025H2_outcomes_opened": False,
        "2026_outcomes_opened": False,
        "decision": "DISTRIBUTION_ONLY_DO_NOT_PROMOTE_OR_RETUNE",
        "production_writes": False,
    }

    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    contexts.drop(columns=["month"]).to_csv(out / "v45_full_context_atr.csv", index=False)
    (out / "v45_full_context_atr.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
