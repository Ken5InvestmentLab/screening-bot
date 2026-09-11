from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import no_tv_v11_independent_selector as v11
import no_tv_v11_1_risk_guard as risk
import no_tv_v18_rank_rolling as v18
import no_tv_v29_purged_rolling as v29
import no_tv_v31_prequential as v31
import no_tv_v32_watchlist_authoritative as v32

FIXED_POLICIES = v29.FIXED_POLICIES


def monthly_stats(parts):
    x = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    if x.empty:
        return {}
    return {
        str(m): risk.risk_stats(g)
        for m, g in x.groupby(x.date.astype(str).str[:7])
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", required=True)
    ap.add_argument("--watchlist-repo", required=True)
    ap.add_argument("--max-symbols", type=int, default=0)
    ap.add_argument("--max-workers", type=int, default=24)
    ap.add_argument("--output-dir", default="research_artifacts/v40_full_universe_fixed")
    a = ap.parse_args()

    teacher, wstat, data, yahoo, codes = v32.build_dataset_authoritative(a)
    data = v11.enrich_cross_sectional(data)

    blocks = v31.build_blocks(data)
    rows = []
    parts = {k: [] for k in FIXED_POLICIES}

    for dates in blocks:
        block_start = dates[0]
        available = v31.available_before(data, block_start)
        block = data[data.date.isin(dates) & data.perf_5bd.notna()].copy()
        if available.empty or block.empty:
            continue

        models = v11.fit_models(available, v11.features())
        scored = v11.attach(block, models, v11.features())

        fixed_stats = {}
        for name, policy in FIXED_POLICIES.items():
            sel = v18.apply_consensus(scored, policy)
            sel = sel.assign(block_start=block_start)
            parts[name].append(sel)
            fixed_stats[name] = risk.risk_stats(sel)

        rows.append({
            "block_start": block_start,
            "block_end": dates[-1],
            "test_days": len(dates),
            "known_rows": len(available),
            "latest_known_exit": str(available.exit_date_norm.max()),
            "fixed_test": fixed_stats,
        })
        print(
            f"V40 {block_start}..{dates[-1]} known={len(available)} "
            + " ".join(f"{k}={len(parts[k][-1])}" for k in FIXED_POLICIES),
            flush=True,
        )

    combined = {}
    monthly = {}
    for name, frames in parts.items():
        cat = pd.concat(frames, ignore_index=True) if frames else data.iloc[0:0]
        combined[name] = risk.risk_stats(cat)
        monthly[name] = monthly_stats(frames)

    result = {
        "scope": (
            "Full historical eligible-watchlist-union prequential audit of the two "
            "fixed V31 consensus policies. Historical watchlist membership is used "
            "only as authoritative evidence that prior-close<=1000 and prior-volume>=10000 "
            "were satisfied at that time. No TradingView indicator signal is used."
        ),
        "purge_rule": "exit_date_5bd < block_start",
        "block_days": v31.BLOCK_DAYS,
        "fixed_policies": FIXED_POLICIES,
        "sampling": {
            "max_symbols": a.max_symbols,
            "symbol_count": len(codes),
            "symbols": codes,
        },
        "teacher_rows_eval_only": len(teacher),
        "watchlists": wstat,
        "yahoo": yahoo,
        "blocks": rows,
        "combined_test": combined,
        "monthly_test": monthly,
        "production_writes": False,
        "warning": (
            "2026 has already been inspected in prior research; this is a sample-bias "
            "and standalone-feasibility audit, not a fresh blind promotion test."
        ),
    }

    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "v40_full_universe_fixed.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    for name, frames in parts.items():
        if frames:
            pd.concat(frames, ignore_index=True).to_csv(
                out / f"v40_{name}_selected.csv", index=False
            )
    print(json.dumps({
        "symbol_count": len(codes),
        "combined_test": combined,
        "monthly_test": monthly,
    }, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
