#!/usr/bin/env python3
"""V11 payoff-aware conditional kNN Quality for V7 Tail candidates (TEST ONLY).

Builds on V10's causal historical Tail-neighbor engine, but does not rank by
neighbor mean return. Instead it uses a payoff-aware local utility:

    utility = 2 * P(neighbor 5BD >= +20%) - P(neighbor 5BD <= -10%)

The 2:1 weight comes directly from the minimum outcome magnitudes (+20 vs -10),
not from fitting a coefficient to future results.

Protocol:
2023 warmup -> 2024 development -> top2 -> 2025 validation -> 2026 only after
a pass. No production writes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import v9_conditional_quality_research as v9
import v10_knn_quality_research as v10

OUT = Path("tvfree_screener/out")

DEV = {
    "2024H1": ("2024-01-01", "2024-06-30"),
    "2024H2": ("2024-07-01", "2024-12-31"),
}
VAL = {
    "2025H1": ("2025-01-01", "2025-06-30"),
    "2025H2": ("2025-07-01", "2025-12-31"),
}

VARIANTS = {
    "u20_rank": {"k": 20, "min_utility": None},
    "u20_pos": {"k": 20, "min_utility": 0.0},
    "u40_rank": {"k": 40, "min_utility": None},
    "u40_pos": {"k": 40, "min_utility": 0.0},
}


def add_utility(scored: pd.DataFrame) -> pd.DataFrame:
    z = scored.copy()
    for k in [20, 40]:
        z[f"knn{k}_utility"] = (
            2.0 * z[f"knn{k}_hit20"] - z[f"knn{k}_loss10"]
        )
    return z


def select_variant(
    scored: pd.DataFrame,
    name: str,
    trading_dates: pd.Index,
) -> pd.DataFrame:
    spec = VARIANTS[name]
    k = spec["k"]
    z = add_utility(scored)
    ucol = f"knn{k}_utility"
    if spec["min_utility"] is not None:
        z = z[z[ucol] > spec["min_utility"]].copy()
    if z.empty:
        return z

    date_idx = {
        pd.Timestamp(d): i
        for i, d in enumerate(pd.Index(trading_dates).sort_values())
    }
    rows = []
    last_symbol = None
    last_idx = None

    for date, day in z.groupby("date", sort=True):
        idx = date_idx[pd.Timestamp(date)]
        day = day.sort_values(
            [ucol, "tail_cdf", "tail_p"],
            ascending=False,
        )
        chosen = None
        for _, row in day.iterrows():
            if (
                last_idx is not None
                and idx == last_idx + 1
                and str(row["symbol"]) == last_symbol
            ):
                continue
            chosen = row
            break
        if chosen is not None:
            rows.append(chosen)
            last_symbol = str(chosen["symbol"])
            last_idx = idx

    return pd.DataFrame(rows).reset_index(drop=True)


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

    trading_dates = pd.Index(pd.to_datetime(raw["date"].unique())).sort_values()
    q = v9.prepare(raw)

    warm_tail = v9.generate_tail_pool(q, "2023-01-01", "2023-12-31")
    if warm_tail.empty:
        raise RuntimeError("V11 warmup tail pool is empty")

    dev_scored, tail_2024 = v10.score_period(
        q, warm_tail, "2024-01-01", "2024-12-31"
    )
    if dev_scored.empty:
        raise RuntimeError("V11 generated no 2024 kNN scores")

    candidates = {}
    for name in VARIANTS:
        picks = select_variant(dev_scored, name, trading_dates)
        dev = v9.period_stats(picks, DEV)
        pool = v9.summarize(
            picks[
                (picks["date"] >= "2024-01-01")
                & (picks["date"] <= "2024-12-31")
            ]["target5_no"]
        )
        candidates[name] = {
            "spec": VARIANTS[name],
            "development_2024": dev,
            "development_2024_pooled": pool,
            "development_utility": v9.development_utility(dev, pool),
        }

    ranked = sorted(
        [
            (v["development_utility"], name)
            for name, v in candidates.items()
            if v["development_utility"] is not None
        ],
        reverse=True,
    )
    opened = [name for _, name in ranked[:2]]
    accepted = []
    pre2026 = None
    tail_2025 = None

    if opened:
        val_scored, tail_2025 = v10.score_period(
            q, tail_2024, "2025-01-01", "2025-12-31"
        )
        pre2026 = pd.concat([dev_scored, val_scored], ignore_index=True)

        for name in opened:
            picks = select_variant(pre2026, name, trading_dates)
            val = v9.period_stats(picks, VAL)
            pool = v9.summarize(
                picks[
                    (picks["date"] >= "2025-01-01")
                    & (picks["date"] <= "2025-12-31")
                ]["target5_no"]
            )
            candidates[name]["validation_2025"] = val
            candidates[name]["validation_2025_pooled"] = pool
            candidates[name]["validation_pass"] = v9.validation_pass(val, pool)
            if candidates[name]["validation_pass"]:
                accepted.append((
                    min(val["2025H1"]["mean"], val["2025H2"]["mean"]),
                    pool["mean"],
                    name,
                ))

    locked = sorted(accepted, reverse=True)[0][2] if accepted else None
    fixed = None
    monthly = None

    if locked:
        future, _ = v10.score_period(
            q, tail_2025, "2026-01-01", "2026-08-31"
        )
        all_scored = pd.concat([pre2026, future], ignore_index=True)
        picks = select_variant(all_scored, locked, trading_dates)
        z = picks[
            (picks["date"] >= "2026-03-01")
            & (picks["date"] <= "2026-08-31")
        ].copy()
        fixed = v9.summarize(z["target5_no"])
        monthly = {
            str(month): v9.summarize(group["target5_no"])
            for month, group in z.groupby(z["date"].dt.to_period("M"))
        }
        z.to_csv(OUT / "v11_payoff_knn_locked_2026.csv", index=False)

    report = {
        "status": "research_only_no_production_writes",
        "component": "V7 extreme Tail + V11 payoff-aware conditional kNN",
        "tail_gate": v9.TAIL_GATE,
        "quality_utility": "2*P(5BD>=+20%) - P(5BD<=-10%)",
        "utility_rationale": (
            "fixed 2:1 coefficient from minimum payoff magnitudes +20% vs -10%"
        ),
        "entry": "next_session_open_to_5BD_close",
        "protocol": (
            "2023 Tail warmup -> 2024 development -> top2 -> "
            "2025 validation -> 2026 only after pass"
        ),
        "warmup_tail_candidates_2023": int(len(warm_tail)),
        "development_ranked": [
            {"name": name, "utility": float(score)}
            for score, name in ranked
        ],
        "validation_opened": opened,
        "locked_candidate": locked,
        "candidates": {},
    }

    for name, v in candidates.items():
        item = {
            "spec": v["spec"],
            "development_2024": v["development_2024"],
            "development_2024_pooled": v["development_2024_pooled"],
            "development_utility": v["development_utility"],
        }
        if name in opened:
            item.update({
                "validation_2025": v["validation_2025"],
                "validation_2025_pooled": v["validation_2025_pooled"],
                "validation_pass": v["validation_pass"],
            })
        if name == locked:
            item.update({
                "fixed_2026_MarAug": fixed,
                "fixed_2026_monthly": monthly,
            })
        report["candidates"][name] = item

    with open(OUT / "v11_payoff_knn_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
