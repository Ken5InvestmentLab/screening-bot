from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import no_tv_v10_standalone as base
import no_tv_v11_independent_selector as v11
import no_tv_v11_1_risk_guard as risk
import no_tv_v17_unbiased_rolling as v17
import no_tv_v18_rank_rolling as v18
import no_tv_v29_purged_rolling as v29

TEST_START = "2026-06-01"
TEST_END = "2026-08-31"
BLOCK_DAYS = 5
VALID_SIGNAL_DAYS = 20
FIXED_POLICIES = v29.FIXED_POLICIES


def attach_with_models(train, frames):
    cols = v11.features()
    models = v11.fit_models(train, cols)
    return [v11.attach(f, models, cols) for f in frames]


def build_blocks(data):
    dates = sorted(data.loc[data.date.between(TEST_START, TEST_END), "date"].unique())
    return [dates[i:i + BLOCK_DAYS] for i in range(0, len(dates), BLOCK_DAYS) if dates[i:i + BLOCK_DAYS]]


def available_before(data, block_start):
    x = data[(data.date < block_start) & data.perf_5bd.notna()].copy()
    x = v29.known_by_test_start(x, block_start)
    if not x.empty and not (x.exit_date_norm < block_start).all():
        raise RuntimeError("prequential horizon purge invariant failed")
    return x


def dynamic_policy(available):
    signal_dates = sorted(available.date.unique())
    if len(signal_dates) <= VALID_SIGNAL_DAYS + 5:
        raise RuntimeError(f"not enough known history for dynamic validation: {len(signal_dates)} days")
    valid_dates = set(signal_dates[-VALID_SIGNAL_DAYS:])
    tr = available[~available.date.isin(valid_dates)].copy()
    va = available[available.date.isin(valid_dates)].copy()
    attached_valid = attach_with_models(tr, [va])[0]
    p, trials = v18.choose_consensus(attached_valid)
    return p, trials, len(tr), len(va), min(valid_dates), max(valid_dates)


def month_stats(parts):
    all_rows = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    if all_rows.empty:
        return {}
    out = {}
    for month, g in all_rows.groupby(all_rows.date.astype(str).str[:7]):
        out[str(month)] = risk.risk_stats(g)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", required=True)
    ap.add_argument("--watchlist-repo", required=True)
    ap.add_argument("--max-symbols", type=int, default=350)
    ap.add_argument("--max-workers", type=int, default=16)
    ap.add_argument("--output-dir", default="research_artifacts/v31_prequential")
    a = ap.parse_args()

    teacher, wstat, data, yahoo, codes = v17.build_dataset(a)
    v18.verify_early_sample(a.watchlist_repo, codes)
    data = v11.enrich_cross_sectional(data)

    blocks = build_blocks(data)
    rows = []
    parts = {"dynamic": [], **{k: [] for k in FIXED_POLICIES}}

    for dates in blocks:
        block_start = dates[0]
        available = available_before(data, block_start)
        block = data[data.date.isin(dates) & data.perf_5bd.notna()].copy()
        if available.empty or block.empty:
            continue

        p, trials, dyn_train_n, dyn_valid_n, vd0, vd1 = dynamic_policy(available)

        # After policy selection, refit the predictor on every label known at block_start.
        scored_block = attach_with_models(available, [block])[0]
        sel_dynamic = v18.apply_consensus(scored_block, p)
        parts["dynamic"].append(sel_dynamic.assign(block_start=block_start))

        fixed_stats = {}
        for name, fp in FIXED_POLICIES.items():
            sel = v18.apply_consensus(scored_block, fp)
            parts[name].append(sel.assign(block_start=block_start))
            fixed_stats[name] = risk.risk_stats(sel)

        rows.append({
            "block_start": block_start, "block_end": dates[-1], "test_days": len(dates),
            "known_rows": len(available), "latest_known_exit": str(available.exit_date_norm.max()),
            "dynamic_policy_train_n": dyn_train_n, "dynamic_policy_valid_n": dyn_valid_n,
            "dynamic_valid_signal_dates": [vd0, vd1],
            "dynamic_policy": p, "dynamic_test": risk.risk_stats(sel_dynamic),
            "fixed_test": fixed_stats, "validation_top": trials[:10],
        })
        print(f"block {block_start}..{dates[-1]} known={len(available)} dynamic={risk.risk_stats(sel_dynamic)}", flush=True)

    combined = {}
    monthly = {}
    for k, ps in parts.items():
        cat = pd.concat(ps, ignore_index=True) if ps else data.iloc[0:0]
        combined[k] = risk.risk_stats(cat)
        monthly[k] = month_stats(ps)

    result = {
        "scope": "Prequential 5-business-day-block backtest. At each block start, only rows with exit_date_5bd < block_start are available. Universe sampling is Mar05-Apr30 only; 09/13 decisions are session-causal. Dynamic policy uses last 20 fully-known signal dates, then predictor refits on all fully-known rows. Fixed policies never use outcome-based policy tuning.",
        "purge_rule": "exit_date_5bd < block_start",
        "block_days": BLOCK_DAYS, "valid_signal_days": VALID_SIGNAL_DAYS,
        "sampling": {"cutoff": v17.SAMPLE_CUTOFF, "max_symbols": a.max_symbols, "symbols": codes},
        "teacher_rows": len(teacher), "watchlists": wstat, "yahoo": yahoo,
        "blocks": rows, "combined_test": combined, "monthly_test": monthly,
        "current_champion": base.CHAMPION,
    }
    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "v31_prequential.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"combined_test": combined, "monthly_test": monthly}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
