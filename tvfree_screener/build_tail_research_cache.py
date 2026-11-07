#!/usr/bin/env python3
"""Build reusable causal V7 Tail-candidate research cache (TEST ONLY).

Uses the frozen run-80 daily dataset and the existing V7 monthly causal Tail
model. Saves extreme Tail candidates before one-per-day selection, including
signal-time features and matured outcome labels for historical research.

This cache does not alter production and does not choose any quality threshold.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import run as base
import v9_conditional_quality_research as v9

OUT = Path("tvfree_screener/out")

PERIODS = [
    ("2023", "2023-01-01", "2023-12-31"),
    ("2024", "2024-01-01", "2024-12-31"),
    ("2025", "2025-01-01", "2025-12-31"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(OUT / "tse_daily.csv"))
    args = ap.parse_args()

    raw = pd.read_csv(args.cache, parse_dates=["date"], dtype={"symbol": str})
    for c in ["open", "high", "low", "close", "volume"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw = raw.dropna(
        subset=["date", "symbol", "open", "high", "low", "close", "volume"]
    ).sort_values(["symbol", "date"]).reset_index(drop=True)

    q = v9.prepare(raw)
    parts = []
    counts = {}

    for label, start, end in PERIODS:
        z = v9.generate_tail_pool(q, start, end)
        if z.empty:
            counts[label] = 0
            continue
        z = z.copy()
        z["cache_period"] = label
        parts.append(z)
        counts[label] = int(len(z))

    if not parts:
        raise RuntimeError("no causal Tail candidates generated")

    out = pd.concat(parts, ignore_index=True)
    out = out.sort_values(["date", "tail_cdf", "tail_p"], ascending=[True, False, False])

    OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / "v7_causal_tail_cache_2023_2025.csv"
    out.to_csv(csv_path, index=False)

    feature_cols = [c for c in base.FEATURES if c in out.columns]
    meta = {
        "status": "research_only_no_production_writes",
        "source": "frozen run-80 daily dataset",
        "tail_detector": "V7 full 45-feature monthly causal top-0.25% model",
        "tail_gate": v9.TAIL_GATE,
        "period_counts": counts,
        "rows": int(len(out)),
        "columns": int(len(out.columns)),
        "signal_feature_columns": feature_cols,
        "contains_outcomes": [
            c for c in ["target5_no", "target_end_date", "y_hit20", "y_loss10"]
            if c in out.columns
        ],
        "warning": (
            "Outcome columns are research labels only. Any prediction-time use "
            "must restrict history to target_end_date before the prediction date."
        ),
    }
    (OUT / "v7_causal_tail_cache_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
