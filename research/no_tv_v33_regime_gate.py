from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import no_tv_v10_standalone as base
import no_tv_v11_independent_selector as v11
import no_tv_v11_1_risk_guard as risk
import no_tv_v18_rank_rolling as v18
import no_tv_v29_purged_rolling as v29
import no_tv_v31_prequential as v31
import no_tv_v32_watchlist_authoritative as v32

TEST_START = "2026-06-01"
TEST_END = "2026-08-31"
BASE_POLICY = v29.FIXED_POLICIES["fixed_min98_both"]

GATE_FEATURES = [
    "session13",
    "market_median_ret1d", "market_median_ret5d", "market_median_gap",
    "market_median_session_ret", "market_median_vol_ratio", "market_median_atr",
    "market_breadth_ema25", "market_breadth_macd", "market_breadth_stoch75",
    "market_breadth_bb80", "market_candidate_count",
    "market_std_ret1d", "market_iqr_ret1d",
    "market_std_ret5d", "market_iqr_ret5d",
    "market_std_session_ret", "market_iqr_session_ret",
    "market_std_atr", "market_iqr_atr",
    "market_up_breadth_1d", "market_up_breadth_session",
    "market_extreme_down_breadth", "market_extreme_up_breadth",
]


def _iqr(s: pd.Series) -> float:
    a = pd.to_numeric(s, errors="coerce").dropna().to_numpy(float)
    if not len(a):
        return np.nan
    return float(np.quantile(a, .75) - np.quantile(a, .25))


def add_regime_features(data: pd.DataFrame) -> pd.DataFrame:
    d = data.copy()
    grp = ["date", "session"]
    g = d.groupby(grp, sort=False)
    d["session13"] = (d.session.astype(int) == 13).astype(float)
    d["market_std_ret1d"] = g.ret_1d.transform("std").fillna(0.0)
    d["market_iqr_ret1d"] = g.ret_1d.transform(_iqr)
    d["market_std_ret5d"] = g.ret_5d.transform("std").fillna(0.0)
    d["market_iqr_ret5d"] = g.ret_5d.transform(_iqr)
    d["market_std_session_ret"] = g.session_ret.transform("std").fillna(0.0)
    d["market_iqr_session_ret"] = g.session_ret.transform(_iqr)
    d["market_std_atr"] = g.atr14_pct.transform("std").fillna(0.0)
    d["market_iqr_atr"] = g.atr14_pct.transform(_iqr)
    d["market_up_breadth_1d"] = g.ret_1d.transform(lambda x: float(np.mean(pd.to_numeric(x, errors="coerce") > 0)))
    d["market_up_breadth_session"] = g.session_ret.transform(lambda x: float(np.mean(pd.to_numeric(x, errors="coerce") > 0)))
    d["market_extreme_down_breadth"] = g.session_ret.transform(lambda x: float(np.mean(pd.to_numeric(x, errors="coerce") < -.03)))
    d["market_extreme_up_breadth"] = g.session_ret.transform(lambda x: float(np.mean(pd.to_numeric(x, errors="coerce") > .03)))
    return d


def session_table(known: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (dt, sess), g in known.groupby(["date", "session"], sort=True):
        perf = pd.to_numeric(g.perf_5bd, errors="coerce").dropna().to_numpy(float)
        if len(perf) < 10:
            continue
        r = {"date": str(dt), "session": int(sess)}
        for c in GATE_FEATURES:
            r[c] = float(pd.to_numeric(g[c], errors="coerce").median())
        r["target_median"] = float(np.median(perf))
        r["target_mean_clip"] = float(np.mean(np.clip(perf, -.20, .30)))
        r["target_good"] = int(r["target_median"] > 0.0)
        r["n_candidates"] = int(len(perf))
        rows.append(r)
    return pd.DataFrame(rows)


def fit_gate(known: pd.DataFrame):
    st = session_table(known)
    if len(st) < 25:
        raise RuntimeError(f"not enough known session contexts for regime gate: {len(st)}")
    X = st[GATE_FEATURES].astype(float)
    y = st.target_good.to_numpy(int)
    if len(np.unique(y)) < 2:
        raise RuntimeError("regime gate target has one class")
    logit = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("model", LogisticRegression(C=.35, class_weight="balanced", max_iter=2000, random_state=331)),
    ])
    ridge = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("model", Ridge(alpha=8.0)),
    ])
    logit.fit(X, y)
    ridge.fit(X, st.target_median.to_numpy(float))
    return logit, ridge, st


def attach_gate(df: pd.DataFrame, models) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    logit, ridge = models
    o = df.copy()
    X = o[GATE_FEATURES].astype(float)
    o["regime_p_good"] = logit.predict_proba(X)[:, 1]
    o["regime_pred_median"] = ridge.predict(X)
    return o


def monthly_stats(parts):
    x = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    if x.empty:
        return {}
    return {str(m): risk.risk_stats(g) for m, g in x.groupby(x.date.astype(str).str[:7])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", required=True)
    ap.add_argument("--watchlist-repo", required=True)
    ap.add_argument("--max-symbols", type=int, default=350)
    ap.add_argument("--max-workers", type=int, default=16)
    ap.add_argument("--output-dir", default="research_artifacts/v33_regime_gate")
    a = ap.parse_args()

    teacher, wstat, data, yahoo, codes = v32.build_dataset_authoritative(a)
    v18.verify_early_sample(a.watchlist_repo, codes)
    data = v11.enrich_cross_sectional(data)
    data = add_regime_features(data)

    blocks = v31.build_blocks(data)
    rows = []
    parts = {"base_fixed98": [], "gate_logit": [], "gate_ridge": [], "gate_both": []}

    for dates in blocks:
        block_start = dates[0]
        known = v31.available_before(data, block_start)
        block = data[data.date.isin(dates) & data.perf_5bd.notna()].copy()
        if known.empty or block.empty:
            continue
        if not (known.exit_date_norm < block_start).all():
            raise RuntimeError("V33 horizon purge invariant failed")

        predictor = v11.fit_models(known, v11.features())
        scored = v11.attach(block, predictor, v11.features())
        base_sel = v18.apply_consensus(scored, BASE_POLICY)

        logit, ridge, gate_train = fit_gate(known)
        gated = attach_gate(base_sel, (logit, ridge))
        variants = {
            "base_fixed98": gated,
            "gate_logit": gated[gated.regime_p_good >= .50].copy(),
            "gate_ridge": gated[gated.regime_pred_median > 0.0].copy(),
            "gate_both": gated[(gated.regime_p_good >= .50) & (gated.regime_pred_median > 0.0)].copy(),
        }
        for name, frame in variants.items():
            parts[name].append(frame.assign(block_start=block_start))

        rows.append({
            "block_start": block_start, "block_end": dates[-1], "known_rows": len(known),
            "gate_train_sessions": len(gate_train),
            "gate_train_good_rate": float(gate_train.target_good.mean()),
            "latest_known_exit": str(known.exit_date_norm.max()),
            "base_candidates": len(base_sel),
            "tests": {k: risk.risk_stats(v) for k, v in variants.items()},
        })
        print(f"V33 {block_start}..{dates[-1]} base={len(base_sel)} both={len(variants['gate_both'])}", flush=True)

    combined = {}
    monthly = {}
    keep_rates = {}
    base_n = sum(len(x) for x in parts["base_fixed98"])
    for name, frames in parts.items():
        cat = pd.concat(frames, ignore_index=True) if frames else data.iloc[0:0]
        combined[name] = risk.risk_stats(cat)
        monthly[name] = monthly_stats(frames)
        keep_rates[name] = (len(cat) / base_n) if base_n else None

    result = {
        "scope": "Yahoo-only opportunity/regime gate research. Base stock selector is fixed min-98% multi-head consensus. Every 5-business-day block refits only from 5BD labels known before block start. Regime features are contemporaneous market breadth/dispersion only; no TV/BOTTOM label is a gate input.",
        "purge_rule": "exit_date_5bd < block_start",
        "base_policy": BASE_POLICY,
        "gate_features": GATE_FEATURES,
        "gate_thresholds": {"logit": "p_good >= 0.50", "ridge": "predicted market median 5BD > 0", "both": "both fixed tests"},
        "sampling": {"cutoff": "2026-04-30", "max_symbols": a.max_symbols, "symbols": codes},
        "teacher_rows_eval_only": len(teacher), "watchlists": wstat, "yahoo": yahoo,
        "blocks": rows, "combined_test": combined, "monthly_test": monthly,
        "keep_rates_vs_base": keep_rates,
        "current_champion_reference": base.CHAMPION,
    }
    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "v33_regime_gate.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"combined_test": combined, "monthly_test": monthly, "keep_rates": keep_rates}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
