from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import no_tv_v10_standalone as base
import no_tv_v11_independent_selector as v11
import no_tv_v11_1_risk_guard as risk
import no_tv_v17_unbiased_rolling as v17
import no_tv_v18_rank_rolling as v18

FOLDS = v17.FOLDS
SAMPLE_CUTOFF = v17.SAMPLE_CUTOFF
GUARDS = [
    {"id": "none"},
    {"id": "strict", "max_session_range": .12, "max_abs_session_ret": .10, "max_day_range": 12.0, "max_atr": 8.0},
]
SESSIONS = ["both", "9", "13"]
COOLDOWNS = [0, 3, 5]
THRESHOLDS = [.90, .93, .95, .97, .98]
TOPK = [1, 2]
MIN_VALID = 10


def verify_early_sample(watchlist_repo, codes):
    return v18.verify_early_sample(watchlist_repo, codes)


def fit_attach(train, valid, test):
    cols = v11.features()
    models = v11.fit_models(train, cols)
    return v11.attach(valid, models, cols), v11.attach(test, models, cols)


def session_filter(df, mode):
    return v18.session_filter(df, mode)


def add_consensus_scores(df, guard):
    x = risk.apply_guard(df, guard).copy()
    if x.empty:
        return x
    grp = ["date", "session"]
    x["r_win"] = x.groupby(grp).p_win.rank(pct=True, method="average")
    x["r_hit"] = x.groupby(grp).p_hit10.rank(pct=True, method="average")
    x["r_ret"] = x.groupby(grp).pred_ret.rank(pct=True, method="average")
    heads = x[["r_win", "r_hit", "r_ret"]]
    x["cons_min"] = heads.min(axis=1)
    x["cons_geo"] = (x.r_win * x.r_hit * x.r_ret).pow(1 / 3)
    x["cons_harm"] = 3.0 / (1.0 / x.r_win.clip(lower=1e-6) + 1.0 / x.r_hit.clip(lower=1e-6) + 1.0 / x.r_ret.clip(lower=1e-6))
    x["cons_spread"] = heads.mean(axis=1) - 0.5 * (heads.max(axis=1) - heads.min(axis=1))
    return x


def causal_topk(df, score_col, topk=1, cooldown=0):
    if df.empty:
        return df
    d = df.sort_values(["date", "session", score_col], ascending=[True, True, False]).copy()
    days = sorted(d.date.unique())
    day_ix = {x: i for i, x in enumerate(days)}
    last = {}
    keep = []
    for (dt, sess), g in d.groupby(["date", "session"], sort=True):
        di = day_ix[dt]
        taken = 0
        for idx, row in g.iterrows():
            sym = str(row.symbol)
            if cooldown and sym in last and di - last[sym] < cooldown:
                continue
            keep.append(idx)
            last[sym] = di
            taken += 1
            if taken >= topk:
                break
    return d.loc[keep].copy()


def split_half_stats(sel):
    if sel.empty:
        z = risk.risk_stats(sel)
        return z, z
    dates = sorted(sel.date.unique())
    mid = max(1, len(dates) // 2)
    left_dates = set(dates[:mid])
    right_dates = set(dates[mid:])
    return risk.risk_stats(sel[sel.date.isin(left_dates)]), risk.risk_stats(sel[sel.date.isin(right_dates)])


def objective(st, h1, h2):
    if st["n"] < MIN_VALID or h1["n"] < 3 or h2["n"] < 3:
        return -999.0
    # Require the policy not to be catastrophically dependent on one half of validation.
    if h1["robust_avg"] < -0.04 or h2["robust_avg"] < -0.04:
        return -999.0
    tail = .22 * min(0.0, st["p10"]) + .05 * min(0.0, st["min"]) - .02 * st["loss20"]
    stability = .20 * min(h1["robust_avg"], h2["robust_avg"]) + .05 * min(h1["median"], h2["median"])
    return (
        .38 * st["robust_avg"] + .22 * st["avg"] + .13 * st["median"]
        + .015 * (st["wr"] - .5) + .025 * st["target_rate"]
        + tail + stability + .001 * np.log1p(st["n"])
    )


def apply_policy(df, p):
    x = add_consensus_scores(df, p["guard"])
    if x.empty:
        return x
    col = p["score_col"]
    x = x[x[col] >= float(p["threshold"])].copy()
    x = session_filter(x, p["sessions"])
    return causal_topk(x, col, int(p["topk"]), int(p["cooldown_days"]))


def choose_policy(valid):
    trials = []
    for guard in GUARDS:
        scored = add_consensus_scores(valid, guard)
        for col in ("cons_min", "cons_geo", "cons_harm", "cons_spread"):
            for th in THRESHOLDS:
                q = scored[scored[col] >= th].copy()
                for sm in SESSIONS:
                    sf = session_filter(q, sm)
                    for topk in TOPK:
                        for cd in COOLDOWNS:
                            sel = causal_topk(sf, col, topk, cd)
                            st = risk.risk_stats(sel)
                            h1, h2 = split_half_stats(sel)
                            o = objective(st, h1, h2)
                            trials.append({
                                "score_col": col, "threshold": th, "guard": guard,
                                "sessions": sm, "topk": topk, "cooldown_days": cd,
                                "objective": float(o), "stats": st, "half1": h1, "half2": h2,
                            })
    trials.sort(key=lambda r: (r["objective"], r["stats"]["n"]), reverse=True)
    return trials[0], trials


def build_bag(valid, test, trials):
    # Policy bagging: only prior-validation-ranked policies vote. No test result is used.
    eligible = [p for p in trials if p["objective"] > -900][:12]
    if not eligible:
        return {"policy_count": 0, "min_votes": 0, "topk": 0, "validation": risk.risk_stats(valid.iloc[0:0]), "test": risk.risk_stats(test.iloc[0:0])}, test.iloc[0:0]

    def vote_frame(frame):
        votes = pd.Series(0, index=frame.index, dtype=int)
        for p in eligible:
            sel = apply_policy(frame, p)
            if len(sel):
                votes.loc[sel.index] += 1
        core = add_consensus_scores(frame, {"id": "none"})
        core["votes"] = votes.reindex(core.index).fillna(0).astype(int)
        core["bag_score"] = core["votes"].astype(float) + core["cons_min"]
        return core

    vv = vote_frame(valid)
    tt = vote_frame(test)
    best = None
    for mv in (2, 3, 4):
        for tk in (1, 2):
            sv = causal_topk(vv[vv.votes >= mv].copy(), "bag_score", tk, 0)
            st = risk.risk_stats(sv)
            h1, h2 = split_half_stats(sv)
            o = objective(st, h1, h2)
            rec = {"min_votes": mv, "topk": tk, "objective": float(o), "stats": st, "half1": h1, "half2": h2}
            if best is None or (o, st["n"]) > (best["objective"], best["stats"]["n"]):
                best = rec
    chosen = best or {"min_votes": 2, "topk": 1, "objective": -999., "stats": risk.risk_stats(valid.iloc[0:0])}
    stest = causal_topk(tt[tt.votes >= int(chosen["min_votes"])].copy(), "bag_score", int(chosen["topk"]), 0)
    return {"policy_count": len(eligible), **chosen, "test": risk.risk_stats(stest)}, stest


def evaluate(data, fold):
    train = data[data.date.between(fold["train_start"], fold["train_end"]) & data.perf_5bd.notna()].copy()
    valid = data[data.date.between(fold["valid_start"], fold["valid_end"]) & data.perf_5bd.notna()].copy()
    test = data[data.date.between(fold["test_start"], fold["test_end"]) & data.perf_5bd.notna()].copy()
    va, te = fit_attach(train, valid, test)
    best, trials = choose_policy(va)
    single = apply_policy(te, best)
    bag_meta, bag = build_bag(va, te, trials)
    return {
        "fold": fold["id"],
        "sizes": {"train": len(train), "valid": len(valid), "test": len(test)},
        "single": {"policy": best, "test": risk.risk_stats(single)},
        "bag": bag_meta,
        "selected_single": single.assign(fold=fold["id"]),
        "selected_bag": bag.assign(fold=fold["id"]),
        "validation_top": trials[:15],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", required=True)
    ap.add_argument("--watchlist-repo", required=True)
    ap.add_argument("--max-symbols", type=int, default=350)
    ap.add_argument("--max-workers", type=int, default=16)
    ap.add_argument("--output-dir", default="research_artifacts/v25_consensus_expansion")
    a = ap.parse_args()

    teacher, wstat, data, yahoo, codes = v17.build_dataset(a)
    verify_early_sample(a.watchlist_repo, codes)
    data = v11.enrich_cross_sectional(data)

    rows = []
    singles = []
    bags = []
    for fold in FOLDS:
        print(f"evaluate V25 {fold['id']}", flush=True)
        r = evaluate(data, fold)
        singles.append(r.pop("selected_single"))
        bags.append(r.pop("selected_bag"))
        rows.append(r)

    combined = {
        "single": risk.risk_stats(pd.concat(singles, ignore_index=True)),
        "bag": risk.risk_stats(pd.concat(bags, ignore_index=True)),
    }
    result = {
        "scope": "V25 development rolling OOS. Leakage-free universe, intraday-causal 09/13 decisions, V13 multi-head consensus expansion with validation-half stability and policy bagging. Jun-Aug has been used for research iteration and is not a pristine final holdout.",
        "sampling": {"cutoff": SAMPLE_CUTOFF, "max_symbols": a.max_symbols, "symbols": codes},
        "teacher_rows": len(teacher), "watchlists": wstat, "yahoo": yahoo,
        "folds": rows, "combined_test": combined, "current_champion": base.CHAMPION,
    }
    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "v25_consensus_expansion.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"combined_test": combined, "folds": rows}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
