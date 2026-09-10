from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

import no_tv_v10_standalone as base
import no_tv_v11_independent_selector as v11
import no_tv_v11_1_risk_guard as risk
import no_tv_v13_official_daily as v13
import no_tv_v17_unbiased_rolling as v17
import no_tv_v18_rank_rolling as v18
import no_tv_v29_purged_rolling as v29


def build_dataset_authoritative(a):
    teacher = base.load_teacher(a.teacher)
    wl, _, wstat = base.load_exact_watchlists(a.watchlist_repo, base.TRAIN_START, base.TEST_END)

    union = set()
    monitor_keys = set()
    early_freq = {}
    for d, syms in wl.items():
        if base.TRAIN_START <= d <= base.TEST_END:
            union.update(syms)
            monitor_keys.update(f"{d}|{s}" for s in syms)
        if base.TRAIN_START <= d <= v17.SAMPLE_CUTOFF:
            for s in syms:
                early_freq[s] = early_freq.get(s, 0) + 1

    if a.max_symbols:
        codes = sorted(union, key=lambda s: (-early_freq.get(s, 0), s))[:a.max_symbols]
        universe = set(codes)
        monitor_keys = {k for k in monitor_keys if k.split("|", 1)[1] in universe}
    else:
        codes = sorted(union)
        universe = set(codes)

    teacher["monitor_key"] = teacher.signal_date + "|" + teacher.symbol_code
    teacher_mon = teacher[
        teacher.monitor_key.isin(monitor_keys)
        & teacher.signal_date.between(base.TRAIN_START, base.TEST_END)
    ].copy()
    positive_keys = set(teacher_mon.key)

    frames = []
    errors = {}
    failed = []
    ok = 0
    with ThreadPoolExecutor(max_workers=a.max_workers) as ex:
        fut = {
            ex.submit(v13.fetch_one, c, base.TRAIN_START, base.FETCH_END, False): c
            for c in codes
        }
        for i, f in enumerate(as_completed(fut), 1):
            code = fut[f]
            try:
                fr, err = f.result()
            except Exception as e:
                fr, err = None, type(e).__name__
            if fr is not None:
                ok += 1
                if not fr.empty:
                    frames.append(fr)
            elif err:
                errors[err] = errors.get(err, 0) + 1
                failed.append({"symbol": code, "error": err})
            if i % 100 == 0:
                print(f"authoritative progress {i}/{len(codes)} frames={len(frames)}", flush=True)

    if not frames:
        raise RuntimeError("no authoritative candidate data")
    d = pd.concat(frames, ignore_index=True)
    d["monitor_key"] = d.date.astype(str) + "|" + d.symbol.astype(str)
    d = d[d.monitor_key.isin(monitor_keys) & d.date.between(base.TRAIN_START, base.TEST_END)].copy()
    d["key"] = d.symbol.astype(str) + "|" + d.date.astype(str) + "|" + d.session.astype(int).astype(str)
    d["label"] = d.key.isin(positive_keys).astype(int)

    observed_positive_keys = set(d.loc[d.label == 1, "key"])
    missing_positive = sorted(positive_keys - observed_positive_keys)
    coverage = {
        "teacher_monitored_positive_keys": len(positive_keys),
        "observed_positive_keys": len(observed_positive_keys),
        "missing_positive_keys": len(missing_positive),
        "recall": len(observed_positive_keys) / len(positive_keys) if positive_keys else None,
        "missing_examples": missing_positive[:50],
    }
    return teacher, wstat, d, {
        "requested": len(codes), "ok": ok, "errors": errors,
        "failed": failed, "positive_coverage": coverage,
    }, codes


def coverage_by_month(data, teacher, codes, watchlist_repo):
    universe = set(codes)
    wl, _, _ = base.load_exact_watchlists(watchlist_repo, base.TRAIN_START, base.TEST_END)
    mk = set()
    for d, syms in wl.items():
        if base.TRAIN_START <= d <= base.TEST_END:
            mk.update(f"{d}|{s}" for s in syms if s in universe)
    t = teacher.copy()
    t["monitor_key"] = t.signal_date + "|" + t.symbol_code
    t = t[t.monitor_key.isin(mk) & t.signal_date.between(base.TRAIN_START, base.TEST_END)].copy()
    seen = set(data.loc[data.label == 1, "key"])
    out = {}
    for month, g in t.groupby(t.signal_date.str[:7]):
        keys = set(g.key)
        hit = len(keys & seen)
        out[str(month)] = {"teacher": len(keys), "observed": hit, "recall": hit / len(keys) if keys else None}
    return out


def evaluate_purged(data, fold):
    test_start = fold["test_start"]
    tr0 = data[data.date.between(fold["train_start"], fold["train_end"]) & data.perf_5bd.notna()].copy()
    va0 = data[data.date.between(fold["valid_start"], fold["valid_end"]) & data.perf_5bd.notna()].copy()
    te = data[data.date.between(fold["test_start"], fold["test_end"]) & data.perf_5bd.notna()].copy()
    tr = v29.known_by_test_start(tr0, test_start)
    va = v29.known_by_test_start(va0, test_start)
    av, at = v29.fit_attach(tr, va, te)
    p, trials = v18.choose_consensus(av)
    sel = v18.apply_consensus(at, p)
    return {
        "fold": fold["id"],
        "sizes": {"train": len(tr), "valid_raw": len(va0), "valid_known": len(va), "valid_purged": len(va0)-len(va), "test": len(te)},
        "policy": p, "test": risk.risk_stats(sel), "selected": sel.assign(fold=fold["id"]),
        "validation_top": trials[:10],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", required=True)
    ap.add_argument("--watchlist-repo", required=True)
    ap.add_argument("--max-symbols", type=int, default=350)
    ap.add_argument("--max-workers", type=int, default=16)
    ap.add_argument("--output-dir", default="research_artifacts/v32_watchlist_authoritative")
    a = ap.parse_args()

    teacher, wstat, data, yahoo, codes = build_dataset_authoritative(a)
    v18.verify_early_sample(a.watchlist_repo, codes)
    data = v11.enrich_cross_sectional(data)

    rows, parts = [], []
    for fold in v17.FOLDS:
        print(f"V32 authoritative purged {fold['id']}", flush=True)
        r = evaluate_purged(data, fold)
        parts.append(r.pop("selected"))
        rows.append(r)

    combined = risk.risk_stats(pd.concat(parts, ignore_index=True))
    result = {
        "scope": "Historical exact watchlist is authoritative for previous-close/previous-volume eligibility; Yahoo does not re-filter those two historical fields. Session volume>=5000 remains required. Evaluation is intraday-causal and 5BD-horizon-purged.",
        "sampling": {"cutoff": v17.SAMPLE_CUTOFF, "max_symbols": a.max_symbols, "symbols": codes},
        "teacher_rows": len(teacher), "watchlists": wstat, "yahoo": yahoo,
        "positive_coverage_by_month": coverage_by_month(data, teacher, codes, a.watchlist_repo),
        "folds": rows, "combined_test": combined, "current_champion": base.CHAMPION,
    }
    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "v32_watchlist_authoritative.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"positive_coverage": yahoo["positive_coverage"], "by_month": result["positive_coverage_by_month"], "combined_test": combined}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
