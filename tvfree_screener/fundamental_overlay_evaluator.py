#!/usr/bin/env python3
"""Coverage-matched fundamental/dilution overlay evaluator (TEST ONLY).

This evaluator never compares a filter against an unmatched all-signal
population. Each overlay is measured against the exact population for which the
required source data is known, preventing missing-data selection from appearing
as alpha.

2024H1/H2 and 2025H1/H2 are pre-2026 research periods. 2026 is emitted in a
separate reporting-only section and is never used to select a threshold here.

No production writes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import fundamental_overlay as fo

OUT = Path("tvfree_screener/out")

RESEARCH_PERIODS = {
    "2024H1": ("2024-01-01", "2024-06-30"),
    "2024H2": ("2024-07-01", "2024-12-31"),
    "2025H1": ("2025-01-01", "2025-06-30"),
    "2025H2": ("2025-07-01", "2025-12-31"),
}
REPORTING_PERIODS = {
    "2026_MarAug_reporting_only": ("2026-03-01", "2026-08-31"),
}


def stats(df: pd.DataFrame, target: str) -> dict:
    x = pd.to_numeric(df.get(target), errors="coerce").dropna()
    if x.empty:
        return {"n": 0}
    return {
        "n": int(len(x)),
        "mean": float(x.mean()),
        "median": float(x.median()),
        "win_rate": float((x > 0).mean()),
        "hit10_rate": float((x >= 0.10).mean()),
        "loss10_rate": float((x <= -0.10).mean()),
    }


def _slice(df: pd.DataFrame, a: str, b: str) -> pd.DataFrame:
    return df[(df["date"] >= pd.Timestamp(a)) & (df["date"] <= pd.Timestamp(b))]


def compare_pair(
    baseline: pd.DataFrame,
    filtered: pd.DataFrame,
    target: str,
    periods: dict[str, tuple[str, str]],
) -> dict:
    out = {}
    for name, (a, b) in periods.items():
        base = stats(_slice(baseline, a, b), target)
        filt = stats(_slice(filtered, a, b), target)
        n0 = base.get("n", 0)
        n1 = filt.get("n", 0)
        delta = {}
        for metric in ["mean", "median", "win_rate", "hit10_rate", "loss10_rate"]:
            bv = base.get(metric)
            fv = filt.get(metric)
            delta[metric] = None if bv is None or fv is None else float(fv - bv)
        out[name] = {
            "matched_baseline": base,
            "filtered": filt,
            "retained_fraction": None if n0 == 0 else float(n1 / n0),
            "delta_filtered_minus_baseline": delta,
        }
    return out


def coverage_summary(lanes: dict[str, pd.DataFrame], target: str) -> dict:
    base = lanes["baseline"].copy()
    valid = base[pd.to_numeric(base[target], errors="coerce").notna()]
    total = len(valid)
    out = {"valid_target_rows": int(total)}
    for key in [
        "dilution_known_baseline",
        "financial_known_baseline",
        "combined_known_baseline",
        "dilution_unknown",
        "financial_unknown",
        "combined_unknown",
    ]:
        z = lanes[key]
        n = int(pd.to_numeric(z[target], errors="coerce").notna().sum())
        out[key] = {
            "n": n,
            "fraction_of_all_valid": None if total == 0 else float(n / total),
        }
    return out


def evaluate(
    signals: pd.DataFrame,
    snapshots: pd.DataFrame,
    target: str,
) -> dict:
    s = signals.copy()
    s["date"] = pd.to_datetime(s["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    if s["date"].isna().any():
        raise ValueError("signals contain invalid date")
    if target not in s.columns:
        raise ValueError(f"signals missing target column: {target}")

    lanes = fo.build_lanes(s, snapshots)
    pairs = {
        f"dilution_le_{limit:.2f}": (
            "dilution_known_baseline",
            f"dilution_le_{limit:.2f}",
        )
        for limit in fo.DILUTION_LIMITS
    }
    pairs.update({
        "financial_risk_filter": ("financial_known_baseline", "financial_risk_filter"),
        "combined_dilution35_finrisk": (
            "combined_known_baseline",
            "combined_dilution35_finrisk",
        ),
    })

    research = {}
    reporting = {}
    for label, (baseline_name, filtered_name) in pairs.items():
        research[label] = {
            "baseline_lane": baseline_name,
            "filtered_lane": filtered_name,
            "periods": compare_pair(
                lanes[baseline_name], lanes[filtered_name], target, RESEARCH_PERIODS
            ),
        }
        reporting[label] = compare_pair(
            lanes[baseline_name], lanes[filtered_name], target, REPORTING_PERIODS
        )

    return {
        "status": "research_only_no_production_writes",
        "target": target,
        "availability_policy": "fundamental_overlay default prior_day_only",
        "coverage": coverage_summary(lanes, target),
        "pre2026_research": research,
        "2026_reporting_only": reporting,
        "selection_policy": (
            "This evaluator reports every predeclared dilution threshold and does not "
            "select a winner. Any later acceptance must be based on robustness across "
            "2024H1/H2 and 2025H1/H2, retained sample size, and extraction coverage."
        ),
        "missing_data_policy": (
            "Every filtered lane is compared only with its coverage-matched known baseline; "
            "unknown rows cannot enter the filtered lane."
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--signals", required=True)
    ap.add_argument("--snapshots", required=True)
    ap.add_argument("--target", default="target5_no")
    ap.add_argument("--out", default=str(OUT / "fundamental_overlay_evaluation.json"))
    args = ap.parse_args()

    signals = pd.read_csv(args.signals, dtype={"symbol": str})
    snapshots = pd.read_csv(args.snapshots, dtype={"symbol": str})
    report = evaluate(signals, snapshots, args.target)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
