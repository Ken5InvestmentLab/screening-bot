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
import no_tv_v25_consensus_expansion as v25
import no_tv_v26_safe_consensus as v26
import no_tv_v27_relative_target as v27
import no_tv_v29_purged_rolling as v29

FOLDS = v17.FOLDS


def split_known(data, fold):
    test_start = fold["test_start"]
    tr0 = data[data.date.between(fold["train_start"], fold["train_end"]) & data.perf_5bd.notna()].copy()
    va0 = data[data.date.between(fold["valid_start"], fold["valid_end"]) & data.perf_5bd.notna()].copy()
    te = data[data.date.between(fold["test_start"], fold["test_end"]) & data.perf_5bd.notna()].copy()
    tr = v29.known_by_test_start(tr0, test_start)
    va = v29.known_by_test_start(va0, test_start)
    if tr.empty or va.empty or te.empty:
        raise RuntimeError(f"empty purged split {fold['id']}")
    if not (tr.exit_date_norm < test_start).all() or not (va.exit_date_norm < test_start).all():
        raise RuntimeError(f"horizon purge invariant failed {fold['id']}")
    return tr0, va0, tr, va, te


def eval_v18(tr, va, te):
    v, t = v29.fit_attach(tr, va, te)
    p, trials = v18.choose_consensus(v)
    sel = v18.apply_consensus(t, p)
    return {"policy": p, "validation_top": trials[:10], "test": risk.risk_stats(sel)}, sel


def eval_v25(tr, va, te):
    v, t = v25.fit_attach(tr, va, te)
    p, trials = v25.choose_policy(v)
    sel = v25.apply_policy(t, p)
    bag_meta, bag = v25.build_bag(v, t, trials)
    return {
        "single": {"policy": p, "validation_top": trials[:10], "test": risk.risk_stats(sel)},
        "bag": bag_meta,
    }, {"single": sel, "bag": bag}


def eval_v26(tr, va, te):
    v, t = v26.fit_attach(tr, va, te)
    p, trials = v26.choose_policy(v)
    sel = v26.apply_policy(t, p)
    return {"policy": p, "validation_top": trials[:10], "test": risk.risk_stats(sel)}, sel


def eval_v27(tr, va, te):
    v, t = v27.fit_attach(tr, va, te)
    p, trials = v27.choose_policy(v)
    sel = v27.apply_policy(t, p)
    return {"policy": p, "validation_top": trials[:10], "test": risk.risk_stats(sel)}, sel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", required=True)
    ap.add_argument("--watchlist-repo", required=True)
    ap.add_argument("--max-symbols", type=int, default=350)
    ap.add_argument("--max-workers", type=int, default=16)
    ap.add_argument("--output-dir", default="research_artifacts/v30_purged_bakeoff")
    a = ap.parse_args()

    teacher, wstat, data, yahoo, codes = v17.build_dataset(a)
    v18.verify_early_sample(a.watchlist_repo, codes)
    data = v11.enrich_cross_sectional(data)

    rows = []
    parts = {"v18": [], "v25_single": [], "v25_bag": [], "v26": [], "v27": []}
    for fold in FOLDS:
        print(f"V30 purged bakeoff {fold['id']}", flush=True)
        tr0, va0, tr, va, te = split_known(data, fold)
        meta = {
            "fold": fold["id"], "test_start": fold["test_start"],
            "sizes": {"train_raw": len(tr0), "train_known": len(tr), "valid_raw": len(va0), "valid_known": len(va), "valid_purged": len(va0)-len(va), "test": len(te)},
            "latest_validation_exit_used": str(va.exit_date_norm.max()),
        }

        r18, s18 = eval_v18(tr, va, te)
        r25, s25 = eval_v25(tr, va, te)
        r26, s26 = eval_v26(tr, va, te)
        r27, s27 = eval_v27(tr, va, te)
        meta.update({"v18": r18, "v25": r25, "v26": r26, "v27": r27})
        rows.append(meta)

        parts["v18"].append(s18.assign(fold=fold["id"]))
        parts["v25_single"].append(s25["single"].assign(fold=fold["id"]))
        parts["v25_bag"].append(s25["bag"].assign(fold=fold["id"]))
        parts["v26"].append(s26.assign(fold=fold["id"]))
        parts["v27"].append(s27.assign(fold=fold["id"]))

    combined = {k: risk.risk_stats(pd.concat(v, ignore_index=True)) for k, v in parts.items()}
    result = {
        "scope": "Single-dataset fair bakeoff with leakage-free historical universe selection, intraday-causal 09/13 decisions and strict 5BD horizon purge. Prior outcome is usable only when exit_date_5bd < test_start. Jun-Aug is development OOS; final proof requires frozen live-forward data.",
        "purge_rule": "exit_date_5bd < test_start",
        "sampling": {"cutoff": v17.SAMPLE_CUTOFF, "max_symbols": a.max_symbols, "symbols": codes},
        "teacher_rows": len(teacher), "watchlists": wstat, "yahoo": yahoo,
        "folds": rows, "combined_test": combined, "current_champion": base.CHAMPION,
    }
    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "v30_purged_bakeoff.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"combined_test": combined, "folds": rows}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
