from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tvfree_screener.batch02 import eval_causal_4h_scoring_v3 as v3
from tvfree_screener.batch02.eval_tentei_inspired_4h_v12 import (
    BIN_ORDER,
    add_v12_state,
    build_bins,
)

WARMUP_START = "2024-12-01"
H1_START = "2025-03-01"
H1_END = "2025-06-30"


def build_state_entries(pattern: str) -> pd.DataFrame:
    bins = build_bins(pattern, max_date=H1_END)
    bins["date_s"] = bins["date"].astype(str)
    bins = bins[bins["date_s"] >= WARMUP_START].copy()
    bins = add_v12_state(bins)
    bins["prev_signal_same_symbol"] = (
        bins.groupby("symbol", sort=False)["signal"].shift(1).fillna(False).astype(bool)
    )
    bins["state_entry"] = bins["signal"] & ~bins["prev_signal_same_symbol"]
    return bins[bins["state_entry"]].copy()


def attach_prior_gate_and_labels(entries: pd.DataFrame, daily_path: str):
    daily = v3.load_daily(Path(daily_path))
    sessions = sorted(daily["date"].dropna().unique().tolist())
    prior_map = {sessions[i]: sessions[i - 1] for i in range(1, len(sessions))}
    out = entries.copy()
    out["date"] = out["date"].astype(str)
    out["prior_date"] = out["date"].map(prior_map)
    prior = daily[["symbol", "date", "close", "volume"]].rename(
        columns={
            "date": "prior_date",
            "close": "prior_daily_close",
            "volume": "prior_daily_volume",
        }
    )
    out = out.merge(prior, on=["symbol", "prior_date"], how="left")
    out = out[
        (out["prior_daily_close"] <= 1000)
        & (out["prior_daily_volume"] >= 10000)
    ].copy()
    out, session_idx = v3.attach_endpoint_labels(out, daily)
    return out, session_idx


def cooldown(rows: pd.DataFrame, session_idx: dict[str, int]) -> pd.DataFrame:
    ordered = rows.sort_values(["date", "bin_ord", "symbol"], kind="stable")
    blocked: dict[str, int] = {}
    keep: list[int] = []
    for idx, row in ordered.iterrows():
        di = session_idx.get(row["date"])
        if di is None:
            continue
        symbol = str(row["symbol"])
        if blocked.get(symbol, -999999) > di:
            continue
        keep.append(idx)
        blocked[symbol] = di + 5
    return ordered.loc[keep].copy()


def passes_monster(metrics: dict) -> bool:
    return (
        metrics.get("resolved", 0) >= 30
        and metrics.get("net_mean", -999.0) > 0
        and metrics.get("gross_ge20_rate", -1.0) >= 0.10
        and metrics.get("top1_removed_net_mean", -999.0) > 0
        and metrics.get("gross_le10_rate", 999.0) <= 0.40
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-glob", required=True)
    parser.add_argument("--daily", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    entries = build_state_entries(args.raw_glob)
    h1_entries = entries[
        (entries["date_s"] >= H1_START) & (entries["date_s"] <= H1_END)
    ].copy()

    gated, session_idx = attach_prior_gate_and_labels(h1_entries, args.daily)
    selected = cooldown(gated, session_idx)

    m005 = v3.metrics(selected, 0.005)
    result = {
        "experiment_id": "TENTEI-STATE-ENTRY-REPRESENTATION-20260913",
        "classification": "RETROSPECTIVE_H1_ONLY_FROZEN_STATE_ENTRY",
        "period": [H1_START, H1_END],
        "warmup_start": WARMUP_START,
        "state_entry_rows_before_prior_daily_gate": int(len(h1_entries)),
        "rows_after_prior_daily_gate_before_cooldown": int(len(gated)),
        "rows_after_5_xtks_session_cooldown": int(len(selected)),
        "metrics_cost_0_5pct": m005,
        "metrics_cost_0": v3.metrics(selected, 0.0),
        "metrics_cost_1pct": v3.metrics(selected, 0.01),
        "passes_monster_gate": passes_monster(m005),
        "h2_outcomes_opened": False,
        "2026_strategy_outcomes_opened": False,
        "production_modified": False,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
