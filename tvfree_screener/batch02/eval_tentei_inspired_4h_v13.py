from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tvfree_screener.batch02 import eval_causal_4h_scoring_v3 as v3
from tvfree_screener.batch02 import eval_tentei_inspired_4h_v12 as v12

TOP_NS = [1, 2, 3, 5]
BINS = ["AM_09_13", "PM_13_CLOSE"]


def pareto_front(group: pd.DataFrame) -> pd.DataFrame:
    g = group.sort_values(["q90", "q10", "symbol"], ascending=[False, False, True], kind="stable").copy()
    q90 = g["q90"].to_numpy(float)
    q10 = g["q10"].to_numpy(float)
    keep = np.zeros(len(g), dtype=bool)
    best_q10 = -np.inf
    last_pair = None
    for i, pair in enumerate(zip(q90, q10)):
        hi, lo = pair
        if lo > best_q10:
            keep[i] = True
            best_q10 = lo
        elif last_pair is not None and pair == last_pair:
            keep[i] = True
        last_pair = pair
    return g.loc[keep]


def build_v12_signal_keys(raw_glob: str, daily_path: str) -> tuple[pd.DataFrame, dict[str, int]]:
    bins = v12.add_v12_state(v12.build_bins(raw_glob))
    signals = bins[bins["signal"]].copy()
    signals, session_idx = v12.attach_gates_and_labels(signals, daily_path)
    keys = signals[["symbol", "date", "bin_name", "bin_ord"]].drop_duplicates().copy()
    return keys, session_idx


def select(scored: pd.DataFrame, session_idx: dict[str, int], n: int) -> pd.DataFrame:
    fronts = [pareto_front(g) for _, g in scored.groupby(["date", "bin_name"], sort=False)]
    x = pd.concat(fronts, ignore_index=True) if fronts else scored.iloc[0:0].copy()
    x = x.sort_values(["date", "bin_name", "q90", "q10", "symbol"], ascending=[True, True, False, False, True], kind="stable")
    groups = {(d, b): g.to_dict("records") for (d, b), g in x.groupby(["date", "bin_name"], sort=False)}
    blocked: dict[str, int] = {}
    rows: list[dict[str, object]] = []
    for day in sorted(scored["date"].astype(str).unique()):
        di = session_idx[day]
        for bin_name in BINS:
            picked = 0
            for row in groups.get((day, bin_name), ()):
                symbol = str(row["symbol"])
                if blocked.get(symbol, -999999) > di:
                    continue
                rows.append(row)
                blocked[symbol] = di + 5
                picked += 1
                if picked >= n:
                    break
    return pd.DataFrame(rows)


def passes(m: dict[str, object]) -> bool:
    return (
        m.get("resolved", 0) >= 30
        and m.get("net_mean", -999.0) > 0
        and m.get("gross_ge20_rate", -1.0) >= 0.10
        and m.get("top1_removed_net_mean", -999.0) > 0
        and m.get("gross_le10_rate", 999.0) <= 0.40
    )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--raw-glob", required=True)
    p.add_argument("--daily", required=True)
    p.add_argument("--scored-glob", required=True)
    p.add_argument("--period", choices=["h1", "h2"], required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    keys, session_idx = build_v12_signal_keys(args.raw_glob, args.daily)
    files = sorted(glob.glob(args.scored_glob))
    if not files:
        raise FileNotFoundError(args.scored_glob)
    scored = pd.concat([pd.read_csv(f, dtype={"symbol": "string"}) for f in files], ignore_index=True)
    scored["symbol"] = scored["symbol"].astype(str).str.replace(r"\.0$", "", regex=True).str.upper()
    scored["date"] = scored["date"].astype(str).str[:10]
    merged = scored.merge(keys, on=["symbol", "date", "bin_name"], how="inner")

    out = {
        "experiment_id": "TENTEI-INSPIRED-4H-V13-V6-QUANTILE-RANK-20260913",
        "period": args.period,
        "v12_scored_rows": int(len(merged)),
        "2026_outcomes_opened": False,
        "production_modified": False,
        "results": {},
    }
    for n in TOP_NS:
        chosen = select(merged, session_idx, n)
        m = v3.metrics(chosen, 0.005)
        m["passes_v13_gate"] = passes(m)
        m["cost0"] = v3.metrics(chosen, 0.0)
        m["cost1pct"] = v3.metrics(chosen, 0.01)
        out["results"][str(n)] = m

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
