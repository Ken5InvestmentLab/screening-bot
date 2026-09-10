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

FOLDS = v17.FOLDS
SAMPLE_CUTOFF = v17.SAMPLE_CUTOFF

# Fixed policies are diagnostic only: they do not use prior-month outcome statistics
# to choose threshold/session/guard. They reduce meta-selection risk.
FIXED_POLICIES = {
    "fixed_min97_both": {
        "type": "consensus", "mode": "min", "threshold": .97,
        "guard": {"id": "none"}, "sessions": "both", "cooldown_days": 0,
    },
    "fixed_min98_both": {
        "type": "consensus", "mode": "min", "threshold": .98,
        "guard": {"id": "none"}, "sessions": "both", "cooldown_days": 0,
    },
}


def known_by_test_start(df: pd.DataFrame, test_start: str) -> pd.DataFrame:
    """Keep only labels whose 5BD exit close was known before the test session starts."""
    if "exit_date_5bd" not in df.columns:
        raise RuntimeError("exit_date_5bd missing: cannot enforce horizon purge")
    x = df.copy()
    x["exit_date_norm"] = pd.to_datetime(x["exit_date_5bd"], errors="coerce").dt.strftime("%Y-%m-%d")
    return x[x["exit_date_norm"].notna() & (x["exit_date_norm"] < test_start)].copy()


def fit_attach(train, valid, test):
    cols = v11.features()
    models = v11.fit_models(train, cols)
    return v11.attach(valid, models, cols), v11.attach(test, models, cols)


def evaluate(data, fold):
    test_start = fold["test_start"]

    # Model train window is already one full calendar month behind test and therefore
    # should be label-safe; still enforce exit-date availability explicitly.
    train_raw = data[
        data.date.between(fold["train_start"], fold["train_end"]) & data.perf_5bd.notna()
    ].copy()
    train = known_by_test_start(train_raw, test_start)

    valid_raw = data[
        data.date.between(fold["valid_start"], fold["valid_end"]) & data.perf_5bd.notna()
    ].copy()
    valid = known_by_test_start(valid_raw, test_start)

    test = data[
        data.date.between(fold["test_start"], fold["test_end"]) & data.perf_5bd.notna()
    ].copy()

    if train.empty or valid.empty or test.empty:
        raise RuntimeError(f"empty purged split in {fold['id']}")
    if not (valid.exit_date_norm < test_start).all():
        raise RuntimeError(f"purge invariant failed in {fold['id']}")

    va, te = fit_attach(train, valid, test)

    # Dynamic policy: selected only from labels actually known before test_start.
    dynamic, trials = v18.choose_consensus(va)
    selected_dynamic = v18.apply_consensus(te, dynamic)

    fixed = {}
    fixed_parts = {}
    for name, policy in FIXED_POLICIES.items():
        sel = v18.apply_consensus(te, policy)
        fixed[name] = risk.risk_stats(sel)
        fixed_parts[name] = sel.assign(fold=fold["id"])

    return {
        "fold": fold["id"],
        "test_start": test_start,
        "sizes": {
            "train_raw": len(train_raw), "train_known": len(train),
            "valid_raw": len(valid_raw), "valid_known": len(valid),
            "valid_purged": len(valid_raw) - len(valid),
            "test": len(test),
        },
        "latest_validation_exit_used": str(valid.exit_date_norm.max()),
        "dynamic": {"policy": dynamic, "test": risk.risk_stats(selected_dynamic)},
        "fixed": fixed,
        "selected_dynamic": selected_dynamic.assign(fold=fold["id"]),
        "selected_fixed": fixed_parts,
        "validation_top": trials[:15],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", required=True)
    ap.add_argument("--watchlist-repo", required=True)
    ap.add_argument("--max-symbols", type=int, default=350)
    ap.add_argument("--max-workers", type=int, default=16)
    ap.add_argument("--output-dir", default="research_artifacts/v29_purged_rolling")
    a = ap.parse_args()

    teacher, wstat, data, yahoo, codes = v17.build_dataset(a)
    v18.verify_early_sample(a.watchlist_repo, codes)
    data = v11.enrich_cross_sectional(data)

    rows = []
    dynamic_parts = []
    fixed_parts = {k: [] for k in FIXED_POLICIES}
    for fold in FOLDS:
        print(f"evaluate V29 purged {fold['id']}", flush=True)
        r = evaluate(data, fold)
        dynamic_parts.append(r.pop("selected_dynamic"))
        sf = r.pop("selected_fixed")
        for k, frame in sf.items():
            fixed_parts[k].append(frame)
        rows.append(r)

    combined = {
        "dynamic_purged": risk.risk_stats(pd.concat(dynamic_parts, ignore_index=True)),
        "fixed": {
            k: risk.risk_stats(pd.concat(parts, ignore_index=True))
            for k, parts in fixed_parts.items()
        },
    }

    result = {
        "scope": "Horizon-purged leakage-free rolling OOS. A prior signal's perf_5bd may influence model/policy selection only when exit_date_5bd is strictly before test_start. 09:00 and 13:00 decisions remain intraday-causal. 350-symbol sample uses only Mar05-Apr30 watchlist frequency.",
        "purge_rule": "exit_date_5bd < test_start",
        "sampling": {"cutoff": SAMPLE_CUTOFF, "max_symbols": a.max_symbols, "symbols": codes},
        "teacher_rows": len(teacher), "watchlists": wstat, "yahoo": yahoo,
        "folds": rows, "combined_test": combined, "current_champion": base.CHAMPION,
    }
    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "v29_purged_rolling.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps({"combined_test": combined, "folds": rows}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
