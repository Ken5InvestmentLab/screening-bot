from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import no_tv_v11_independent_selector as v11
import no_tv_v18_rank_rolling as v18
import select_consensus_v47_price_policy as price_policy

EVAL_START = "2025-01-06"
EVAL_END = "2025-06-30"
COST = 0.005
POLICY = {
    "type": "consensus",
    "mode": "min",
    "threshold": 0.95,
    "guard": {"id": "none"},
    "sessions": "both",
    "cooldown_days": 0,
}


def blocks(data: pd.DataFrame) -> list[list[str]]:
    dates = sorted(
        data.loc[data["date"].between(EVAL_START, EVAL_END), "date"].unique()
    )
    return [dates[i:i+5] for i in range(0, len(dates), 5) if dates[i:i+5]]


def available_before(data: pd.DataFrame, block_start: str) -> pd.DataFrame:
    x = data[
        (data["date"] < block_start)
        & data["perf_5bd"].notna()
        & data["exit_date_5bd"].notna()
    ].copy()
    x = x[x["exit_date_5bd"].astype(str) < block_start].copy()
    if len(x) and not (x["exit_date_5bd"].astype(str) < block_start).all():
        raise RuntimeError("purge invariant failed")
    return x


def prequential_select(data: pd.DataFrame, arm: str) -> pd.DataFrame:
    if pd.to_datetime(data["date"]).max() > pd.Timestamp(EVAL_END):
        raise RuntimeError(f"{arm}: H2 rows supplied to development evaluator")
    d = data.copy()
    d["date"] = d["date"].astype(str).str[:10]
    d["exit_date_5bd"] = d["exit_date_5bd"].astype(str).str[:10]
    d["perf_5bd"] = pd.to_numeric(d["canonical_ret_5bd"], errors="coerce")

    parts = []
    for dates in blocks(d):
        block_start = dates[0]
        train = available_before(d, block_start)
        test = d[d["date"].isin(dates) & d["perf_5bd"].notna()].copy()
        if train.empty or test.empty:
            continue
        if len(train) < 1000:
            raise RuntimeError(
                f"{arm}: too little purged training data before {block_start}: {len(train)}"
            )
        models = v11.fit_models(train, v11.features())
        scored = v11.attach(test, models, v11.features())
        sel = v18.apply_consensus(scored, POLICY).copy()
        if len(sel):
            sel["block_start"] = block_start
            parts.append(sel)
        print(
            f"{arm} {block_start}..{dates[-1]} "
            f"train={len(train)} test={len(test)} selected={len(sel)}",
            flush=True,
        )
    return pd.concat(parts, ignore_index=True) if parts else d.iloc[0:0].copy()


def trading_day_index(frozen_daily: Path) -> dict[str, int]:
    d = pd.read_csv(frozen_daily, usecols=["date"])
    dates = sorted(
        pd.to_datetime(d["date"], errors="coerce")
        .dropna()
        .dt.strftime("%Y-%m-%d")
        .unique()
    )
    return {x: i for i, x in enumerate(dates)}


def strict5_no_replacement(
    selected: pd.DataFrame,
    day_ix: dict[str, int],
) -> pd.DataFrame:
    if selected.empty:
        return selected
    last: dict[str, int] = {}
    keep = []
    x = selected.sort_values(
        ["date", "session", "cons_min", "symbol"],
        ascending=[True, True, False, True],
    )
    for idx, row in x.iterrows():
        dt = str(row["date"])[:10]
        sym = str(row["symbol"])
        if dt not in day_ix:
            raise RuntimeError(f"missing trading day {dt}")
        di = day_ix[dt]
        prior = last.get(sym)
        if prior is not None and di - prior < 5:
            continue
        keep.append(idx)
        last[sym] = di
    return x.loc[keep].copy()


def stats(selected: pd.DataFrame) -> dict:
    r = pd.to_numeric(selected["canonical_ret_5bd"], errors="coerce").dropna().to_numpy(float)
    if not len(r):
        return {"n": 0}
    net = r - COST
    s = np.sort(net)
    counts = selected.loc[
        pd.to_numeric(selected["canonical_ret_5bd"], errors="coerce").notna(),
        "symbol",
    ].astype(str).value_counts()
    return {
        "n": int(len(net)),
        "mean_net_0p5_pct": float(np.mean(net) * 100),
        "median_net_0p5_pct": float(np.median(net) * 100),
        "top3_ex_net_0p5_pct": (
            float(np.mean(s[:-3]) * 100) if len(s) > 3 else None
        ),
        "win_net_0p5_pct": float(np.mean(net > 0) * 100),
        "hit10_net_pct": float(np.mean(net >= 0.10) * 100),
        "hit20_net_pct": float(np.mean(net >= 0.20) * 100),
        "loss10_net_pct": float(np.mean(net <= -0.10) * 100),
        "loss20_net_pct": float(np.mean(net <= -0.20) * 100),
        "unique_symbols": int(len(counts)),
        "max_symbol_share": float(counts.iloc[0] / len(net)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nocap-dev", required=True, type=Path)
    ap.add_argument("--cap1000-dev", required=True, type=Path)
    ap.add_argument("--frozen-daily", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    a = ap.parse_args()

    day_ix = trading_day_index(a.frozen_daily)
    inputs = {
        "NOCAP": pd.read_parquet(a.nocap_dev),
        "CAP1000_PIT": pd.read_parquet(a.cap1000_dev),
    }

    selected = {}
    metrics = {}
    for arm, data in inputs.items():
        raw_sel = prequential_select(data, arm)
        strict = strict5_no_replacement(raw_sel, day_ix)
        selected[arm] = strict
        metrics[arm] = stats(strict)

    decision = price_policy.choose_dev(metrics)

    out = a.output_dir
    out.mkdir(parents=True, exist_ok=True)
    for arm, d in selected.items():
        d.to_csv(out / f"v47_dev_selected_{arm.lower()}.csv", index=False)

    payload = {
        "scope": "clean PIT V47B development-only price-policy decision",
        "development_period": [EVAL_START, EVAL_END],
        "target": "next official XTKS open -> D+5 close",
        "cost_round_trip": COST,
        "strict_same_symbol_cooldown_sessions": 5,
        "replacement": False,
        "development": metrics,
        "decision": decision,
        "h2_opened": False,
        "2026_opened": False,
        "production_writes": False,
    }
    (out / "v47_dev_price_policy.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
