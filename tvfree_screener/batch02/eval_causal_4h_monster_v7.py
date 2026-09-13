from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import pandas as pd

from tvfree_screener.batch02 import eval_causal_4h_scoring_v3 as v3

TOP_NS = [1, 2, 3, 5]
BINS = ["AM_09_13", "PM_13_CLOSE"]


def select(scored: pd.DataFrame, session_idx: dict[str, int], n: int) -> pd.DataFrame:
    x = scored[pd.to_numeric(scored["q50"], errors="coerce") >= 0].copy()
    x = x.sort_values(
        ["date", "bin_name", "q90", "q50", "symbol"],
        ascending=[True, True, False, False, True],
        kind="stable",
    )
    groups = {(d, b): g.to_dict("records") for (d, b), g in x.groupby(["date", "bin_name"], sort=False)}
    blocked: dict[str, int] = {}
    rows: list[dict[str, object]] = []
    for day in sorted(scored["date"].unique()):
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


def passes(metrics: dict[str, object]) -> bool:
    return (
        metrics.get("resolved", 0) >= 30
        and metrics.get("net_mean", -999.0) > 0
        and metrics.get("gross_ge20_rate", -1.0) >= 0.10
        and metrics.get("top1_removed_net_mean", -999.0) > 0
        and metrics.get("gross_le10_rate", 999.0) <= 0.40
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scored-glob", required=True)
    parser.add_argument("--daily", required=True)
    parser.add_argument("--period", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    files = sorted(glob.glob(args.scored_glob))
    if not files:
        raise FileNotFoundError(args.scored_glob)
    scored = pd.concat([pd.read_csv(f, dtype={"symbol": "string"}) for f in files], ignore_index=True)
    scored["symbol"] = scored["symbol"].astype(str)
    scored["date"] = scored["date"].astype(str).str[:10]
    daily = v3.load_daily(Path(args.daily))
    sessions = sorted(daily["date"].dropna().unique().tolist())
    session_idx = {day: i for i, day in enumerate(sessions)}

    viable = pd.to_numeric(scored["q50"], errors="coerce") >= 0
    result = {
        "experiment_id": "CAUSAL-4H-MONSTER-V7-MEDIAN-VIABILITY-TAIL-20260913",
        "period": args.period,
        "input_rows": int(len(scored)),
        "viable_rows": int(viable.sum()),
        "viable_rate": float(viable.mean()),
        "2026_outcomes_opened": False,
        "production_modified": False,
        "results": {},
    }
    for n in TOP_NS:
        chosen = select(scored, session_idx, n)
        m = v3.metrics(chosen, 0.005)
        m["passes_v7_gates"] = passes(m)
        m["cost0"] = v3.metrics(chosen, 0.0)
        m["cost1pct"] = v3.metrics(chosen, 0.01)
        result["results"][str(n)] = m

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
