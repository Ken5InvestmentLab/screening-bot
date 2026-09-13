from __future__ import annotations

import argparse, glob, json
from pathlib import Path
import pandas as pd
from tvfree_screener.batch02 import eval_causal_4h_scoring_v3 as v3
from tvfree_screener.batch02 import eval_causal_4h_scoring_v4 as v4
from tvfree_screener.batch02 import eval_causal_4h_scoring_v5 as v5

KEEP_COLS = [
    "symbol", "date", "bin_name", "endpoint_status", "ret5bd_gross",
    "q10", "q50", "q90", "score_core", "score_monster", "quantile_crossed_raw",
]


def month_bounds(month: str) -> tuple[str, str]:
    p = pd.Period(month, freq="M")
    return p.start_time.date().isoformat(), p.end_time.date().isoformat()


def prepare(candidates_pattern: str, daily_path: str | Path):
    daily_path = Path(daily_path)
    expected = "6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0"
    actual = v3.sha256_file(daily_path)
    if actual != expected:
        raise RuntimeError(f"daily SHA mismatch: {actual}")
    cand = v4.load_candidates(candidates_pattern)
    daily = v3.load_daily(daily_path)
    cand, session_idx = v3.attach_endpoint_labels(cand, daily)
    return cand, session_idx, actual


def score_month(cand: pd.DataFrame, month: str) -> tuple[pd.DataFrame, dict]:
    start, end = month_bounds(month)
    train = cand[
        (cand["date"] >= "2025-01-01")
        & (cand["date"] < start)
        & (cand["exit_date"] < start)
        & (cand["endpoint_status"] == "RESOLVED")
    ].copy()
    valid = cand[(cand["date"] >= start) & (cand["date"] <= end)].copy()
    if train.empty or valid.empty:
        raise RuntimeError(f"empty train/valid for {month}: {len(train)}/{len(valid)}")
    scored = v5.score_period(train, valid)
    meta = {
        "month": month,
        "month_start": start,
        "month_end": end,
        "train_rows": int(len(train)),
        "eval_rows": int(len(valid)),
        "train_max_candidate_date": str(train["date"].max()),
        "train_max_exit_date": str(train["exit_date"].max()),
        "quantile_crossing_raw_rate": float(scored["quantile_crossed_raw"].mean()),
    }
    return scored[KEEP_COLS].copy(), meta


def aggregate_scored(scored: pd.DataFrame, session_idx: dict[str, int]) -> dict:
    scored = scored.sort_values(["date", "bin_name", "symbol"], kind="stable").reset_index(drop=True)
    results = {}
    for head in ["core", "monster"]:
        results[head] = {}
        for n in v3.TOP_NS:
            sel = v5.select_policy(scored, session_idx, head, n)
            m = v3.metrics(sel, .005)
            m["passes_comparability_gates"] = v3.passes(head, m)
            m["cost0"] = v3.metrics(sel, 0)
            m["cost1pct"] = v3.metrics(sel, .01)
            results[head][str(n)] = m
    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["month", "aggregate"], required=True)
    p.add_argument("--candidates", default="")
    p.add_argument("--daily", required=True)
    p.add_argument("--month")
    p.add_argument("--scored-output")
    p.add_argument("--meta-output")
    p.add_argument("--scored-glob")
    p.add_argument("--period-name")
    p.add_argument("--output")
    a = p.parse_args()

    if a.mode == "month":
        cand, _, daily_sha = prepare(a.candidates, a.daily)
        scored, meta = score_month(cand, a.month)
        Path(a.scored_output).parent.mkdir(parents=True, exist_ok=True)
        scored.to_csv(a.scored_output, index=False, compression="gzip" if str(a.scored_output).endswith(".gz") else None)
        meta["daily_sha256"] = daily_sha
        meta["2026_outcomes_opened"] = False
        Path(a.meta_output).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        return

    files = sorted(glob.glob(a.scored_glob))
    if not files:
        raise FileNotFoundError(a.scored_glob)
    scored = pd.concat([pd.read_csv(f, dtype={"symbol": "string"}) for f in files], ignore_index=True)
    daily = v3.load_daily(Path(a.daily))
    sessions = sorted(daily["date"].dropna().unique().tolist())
    session_idx = {d: i for i, d in enumerate(sessions)}
    result = {
        "experiment_id": "CAUSAL-4H-SCORING-V6-MONTHLY-WALKFORWARD-20260913",
        "period": a.period_name,
        "months": [Path(f).stem.split("scored_")[-1].replace(".csv", "") for f in files],
        "rows": int(len(scored)),
        "results": aggregate_scored(scored, session_idx),
        "2026_outcomes_opened": False,
        "production_modified": False,
    }
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    Path(a.output).write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
