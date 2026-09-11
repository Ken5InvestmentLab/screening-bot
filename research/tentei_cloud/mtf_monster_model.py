#!/usr/bin/env python3
"""Causal MTF Monster research: compare reconstructed 4H-only vs 4H+1H context.

Research-only. No production writes.
Protocol is predeclared:
- Yahoo 1H data should start by 2024-09-16 for warmup.
- Reconstruct 2 session bars/day with split at 13:00 JST.
- Fixed TAIL gate (range >= 2% plus structure) defines candidate pool.
- Candidate pool gets 5BD same-symbol cooldown before modeling.
- Train/development: 2024-11-01 through 2025-06-30.
- Validation: 2025-07-01 through 2025-12-31.
- 2026 is reporting-only and only opened if the 2025 validation gate passes.
- Tail target is selected using TRAIN ONLY: choose the highest threshold in [20%,15%,10%,7.5%,5%] with >=8 positive and >=8 negative samples. No validation/2026 outcome is used for this choice. No loss probability is subtracted from rank.
- User-facing tiers use OOB training-score CDF: Watch q70, Prime q90.
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

from reconstruct_4h_from_1h import load, aggregate, enrich_session, add_daily_context, cooldown
from evaluate_1h_precursors import enrich as enrich_1h


TRAIN_START = "2024-11-01"
TRAIN_END = "2025-06-30"
VAL_START = "2025-07-01"
VAL_END = "2025-12-31"
REPORT_START = "2026-01-01"
TARGET_THRESHOLDS = [0.20, 0.15, 0.10, 0.075, 0.05]
MIN_CLASS_N = 8


FOUR_H_FEATURES = [
    "range_pct",
    "rsi12",
    "atr14_pct",
    "macd_hist_rel",
    "close_ema75_rel",
    "close_bbmid_rel",
    "body_pct",
    "session_volume_log",
    "prev_daily_volume_log",
    "session_prevday_vol_ratio",
]

ONE_H_FEATURES = [
    "oneh_ret3h",
    "oneh_rsi14",
    "oneh_vsurge",
    "oneh_bbpct",
    "oneh_range_pct",
    "oneh_drawdown7",
    "fast_count3",
    "fast_count7",
    "balanced_count3",
    "balanced_count7",
    "breakout_count3",
    "breakout_count7",
    "max_vsurge3",
    "max_vsurge7",
    "max_ret3h3",
    "max_ret3h7",
    "max_bbpct3",
    "max_bbpct7",
]


def prepare_1h(raw: pd.DataFrame) -> pd.DataFrame:
    h = enrich_1h(raw)
    out = []
    for _, g in h.groupby("symbol", sort=False):
        g = g.sort_values("timestamp").copy()
        g["oneh_ret3h"] = g["ret3h"]
        g["oneh_rsi14"] = g["rsi14"]
        g["oneh_vsurge"] = g["vsurge"]
        g["oneh_bbpct"] = g["bbpct"]
        g["oneh_range_pct"] = (g["high"] - g["low"]) / g["close"].replace(0, np.nan)
        g["oneh_drawdown7"] = g["close"] / g["high"].rolling(7, min_periods=3).max() - 1.0
        for col in ["fast", "balanced", "breakout"]:
            z = g[col].fillna(False).astype(int)
            g[f"{col}_count3"] = z.rolling(3, min_periods=1).sum()
            g[f"{col}_count7"] = z.rolling(7, min_periods=1).sum()
        g["max_vsurge3"] = g["vsurge"].rolling(3, min_periods=1).max()
        g["max_vsurge7"] = g["vsurge"].rolling(7, min_periods=1).max()
        g["max_ret3h3"] = g["ret3h"].rolling(3, min_periods=1).max()
        g["max_ret3h7"] = g["ret3h"].rolling(7, min_periods=1).max()
        g["max_bbpct3"] = g["bbpct"].rolling(3, min_periods=1).max()
        g["max_bbpct7"] = g["bbpct"].rolling(7, min_periods=1).max()
        out.append(g)
    cols = ["symbol", "timestamp"] + ONE_H_FEATURES
    return pd.concat(out, ignore_index=True)[cols].sort_values(["symbol", "timestamp"])


def attach_1h_context(cands: pd.DataFrame, h: pd.DataFrame) -> pd.DataFrame:
    # merge_asof with a by-key avoids an O(symbols * rows) repeated full scan.
    left = cands.copy()
    right = h.copy()
    left["symbol"] = left["symbol"].astype("string")
    right["symbol"] = right["symbol"].astype("string")
    left = left.sort_values(["last_ts", "symbol"]).reset_index(drop=True)
    right = right.sort_values(["timestamp", "symbol"]).reset_index(drop=True)
    return pd.merge_asof(
        left,
        right,
        left_on="last_ts",
        right_on="timestamp",
        by="symbol",
        direction="backward",
        allow_exact_matches=True,
    )


def add_4h_features(c: pd.DataFrame) -> pd.DataFrame:
    x = c.copy()
    x["macd_hist_rel"] = x["macd_hist"] / x["close"].replace(0, np.nan)
    x["close_ema75_rel"] = x["close"] / x["ema75"].replace(0, np.nan) - 1.0
    x["close_bbmid_rel"] = x["close"] / x["bb_mid"].replace(0, np.nan) - 1.0
    x["body_pct"] = (x["close"] - x["open"]) / x["close"].replace(0, np.nan)
    x["session_volume_log"] = np.log1p(x["volume"].clip(lower=0))
    x["prev_daily_volume_log"] = np.log1p(x["prev_daily_volume"].clip(lower=0))
    x["session_prevday_vol_ratio"] = x["volume"] / x["prev_daily_volume"].replace(0, np.nan)
    return x


def make_candidate_pool(raw: pd.DataFrame) -> pd.DataFrame:
    sessions = aggregate(raw, 780)
    sessions = enrich_session(sessions)
    sessions, dates = add_daily_context(sessions, raw)
    eligible = sessions[
        (sessions["prev_daily_close"] <= 1000)
        & (sessions["prev_daily_volume"] >= 10000)
        & (sessions["volume"] >= 5000)
    ].copy()
    gate = (
        (eligible["close"] <= eligible["ema75"])
        & (eligible["macd_hist"] <= 0)
        & (eligible["close"] > eligible["bb_mid"])
        & (eligible["close"] <= eligible["open"])
        & (eligible["range_pct"] >= 0.02)
    )
    c = cooldown(eligible[gate].copy(), dates, 5)
    c = add_4h_features(c)
    return c


def metrics(name: str, tier: str, period: str, q: pd.DataFrame, target_threshold: float) -> dict:
    r = q["ret5bd"].dropna().astype(float)
    ans = {"model": name, "tier": tier, "period": period, "n": int(len(r)), "target_threshold": target_threshold}
    if r.empty:
        for k in ["mean","median","win","ge10","ge20","ge30","ge_target","le10","max","top1_removed","top3_removed","top5_removed"]:
            ans[k] = None
        return ans
    rs = r.sort_values(ascending=False)
    ans.update({
        "mean": float(r.mean()),
        "median": float(r.median()),
        "win": float((r > 0).mean()),
        "ge10": float((r >= 0.10).mean()),
        "ge20": float((r >= 0.20).mean()),
        "ge30": float((r >= 0.30).mean()),
        "ge_target": float((r >= target_threshold).mean()),
        "le10": float((r <= -0.10).mean()),
        "max": float(r.max()),
        "top1_removed": float(rs.iloc[1:].mean()) if len(rs)>1 else None,
        "top3_removed": float(rs.iloc[3:].mean()) if len(rs)>3 else None,
        "top5_removed": float(rs.iloc[5:].mean()) if len(rs)>5 else None,
    })
    return ans


def choose_target(train: pd.DataFrame):
    counts = {}
    n = len(train)
    for t in TARGET_THRESHOLDS:
        pos = int((train["ret5bd"] >= t).sum())
        neg = int(n - pos)
        counts[f"{t:.3f}"] = {"positive": pos, "negative": neg, "rate": (pos / n if n else None)}
        if pos >= MIN_CLASS_N and neg >= MIN_CLASS_N:
            return t, counts
    raise RuntimeError(f"no statistically usable tail target in TRAIN only: n={n}, counts={counts}")


def fit_rf(train: pd.DataFrame, features: list[str], target_threshold: float, seed: int = 42):
    from sklearn.ensemble import RandomForestClassifier
    X = train[features].replace([np.inf,-np.inf], np.nan).copy()
    med = X.median(numeric_only=True)
    X = X.fillna(med).fillna(0.0)
    y = (train["ret5bd"] >= target_threshold).astype(int)
    if y.sum() < MIN_CLASS_N or (len(y)-y.sum()) < MIN_CLASS_N:
        raise RuntimeError(f"insufficient tail classes after TRAIN-only target selection: threshold={target_threshold}, positives={int(y.sum())}, n={len(y)}")
    model = RandomForestClassifier(
        n_estimators=500,
        max_depth=5,
        min_samples_leaf=4,
        max_features="sqrt",
        class_weight="balanced_subsample",
        bootstrap=True,
        oob_score=True,
        random_state=seed,
        n_jobs=-1,
    )
    model.fit(X, y)
    oob = model.oob_decision_function_
    if oob is None or oob.shape[1] < 2:
        raise RuntimeError("missing OOB probabilities")
    p = oob[:,1]
    good = np.isfinite(p)
    if good.sum() < 20:
        raise RuntimeError("too few finite OOB scores")
    q70 = float(np.nanquantile(p[good], 0.70))
    q90 = float(np.nanquantile(p[good], 0.90))
    return model, med, q70, q90, int(y.sum()), len(y)


def score(model, med, frame, features):
    X = frame[features].replace([np.inf,-np.inf], np.nan).copy()
    X = X.fillna(med).fillna(0.0)
    return model.predict_proba(X)[:,1]


def select(frame: pd.DataFrame, score_col: str, threshold: float) -> pd.DataFrame:
    return frame[frame[score_col] >= threshold].copy()


def validation_gate(base: dict, four_prime: dict, mtf_watch: dict, mtf_prime: dict) -> tuple[bool, list[str]]:
    reasons = []
    if mtf_watch["n"] < 15:
        reasons.append("watch_n<15")
    if mtf_prime["n"] < 8:
        reasons.append("prime_n<8")
    if mtf_watch["mean"] is None or base["mean"] is None or mtf_watch["mean"] < base["mean"]:
        reasons.append("watch_mean<base")
    if mtf_watch["ge_target"] is None or base["ge_target"] is None or mtf_watch["ge_target"] < base["ge_target"]:
        reasons.append("watch_target_hit_rate<base")
    if mtf_prime["mean"] is None or four_prime["mean"] is None or mtf_prime["mean"] <= four_prime["mean"]:
        reasons.append("prime_mean_not_better_than_4h")
    if mtf_prime["le10"] is None or base["le10"] is None or mtf_prime["le10"] > base["le10"] + 0.05:
        reasons.append("prime_loss10_too_high")
    return len(reasons)==0, reasons


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", action="append", required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)

    raw = load(a.inputs)
    if str(raw["date"].min()) > "2024-10-15":
        raise SystemExit(f"history too short for causal MTF protocol: starts {raw['date'].min()}")

    c = make_candidate_pool(raw)
    h = prepare_1h(raw)
    c = attach_1h_context(c, h)
    c["date_dt"] = pd.to_datetime(c["date"])
    c = c[c["ret5bd"].notna()].copy()

    train = c[(c["date"] >= TRAIN_START) & (c["date"] <= TRAIN_END)].copy()
    val = c[(c["date"] >= VAL_START) & (c["date"] <= VAL_END)].copy()
    report = c[c["date"] >= REPORT_START].copy()

    target_threshold, train_target_counts = choose_target(train)

    results = []
    model_info = {}
    for name, feats in [("4H_ONLY", FOUR_H_FEATURES), ("MTF", FOUR_H_FEATURES + ONE_H_FEATURES)]:
        model, med, q70, q90, pos, ntrain = fit_rf(train, feats, target_threshold, 42)
        model_info[name] = {
            "features": feats, "q70": q70, "q90": q90,
            "train_n": ntrain, "train_tail20": pos,
        }
        for frame_name, frame in [("TRAIN",train),("VALIDATION",val),("REPORT_2026",report)]:
            frame[f"score_{name}"] = score(model, med, frame, feats)

        for period, frame in [("TRAIN",train),("VALIDATION",val)]:
            results.append(metrics(name,"Watch",period,select(frame,f"score_{name}",q70),target_threshold))
            results.append(metrics(name,"Prime",period,select(frame,f"score_{name}",q90),target_threshold))

    base_val = metrics("BASE","TAIL_POOL","VALIDATION",val,target_threshold)
    four_prime_val = next(x for x in results if x["model"]=="4H_ONLY" and x["tier"]=="Prime" and x["period"]=="VALIDATION")
    mtf_watch_val = next(x for x in results if x["model"]=="MTF" and x["tier"]=="Watch" and x["period"]=="VALIDATION")
    mtf_prime_val = next(x for x in results if x["model"]=="MTF" and x["tier"]=="Prime" and x["period"]=="VALIDATION")
    passed, reasons = validation_gate(base_val, four_prime_val, mtf_watch_val, mtf_prime_val)

    results.insert(0, base_val)
    if passed:
        for name in ["4H_ONLY","MTF"]:
            info=model_info[name]
            results.append(metrics(name,"Watch","REPORT_2026",select(report,f"score_{name}",info["q70"]),target_threshold))
            results.append(metrics(name,"Prime","REPORT_2026",select(report,f"score_{name}",info["q90"]),target_threshold))

    summary = pd.DataFrame(results)
    summary.to_csv(out/"mtf_model_summary.csv",index=False)

    keep = [
        "date","session","session_time","last_ts","symbol","open","high","low","close","volume","range_pct",
        "rsi12","atr14_pct","macd_hist","ema75","bb_mid","target_date","target_close","ret5bd",
    ] + ONE_H_FEATURES
    for col in ["score_4H_ONLY","score_MTF"]:
        if col in val:
            keep.append(col)
    val[[x for x in keep if x in val.columns]].to_csv(out/"mtf_validation_candidates.csv",index=False)
    if passed:
        report[[x for x in keep if x in report.columns]].to_csv(out/"mtf_report_2026_candidates.csv",index=False)

    meta = {
        "raw_start": str(raw["date"].min()),
        "raw_end": str(raw["date"].max()),
        "candidate_pool_n": int(len(c)),
        "train_n": int(len(train)),
        "validation_n": int(len(val)),
        "report_2026_n": int(len(report)),
        "validation_gate_passed": bool(passed),
        "validation_gate_reasons": reasons,
        "train_only_target_threshold": target_threshold,
        "train_only_target_counts": train_target_counts,
        "model_info": model_info,
        "policy": {
            "candidate_gate": "reconstructed split-13:00 TAIL structure with range>=2%",
            "cooldown_business_days": 5,
            "tail_target": "TRAIN-only highest feasible threshold among +20/+15/+10/+7.5/+5%, requiring >=8 samples in each class",
            "watch_threshold": "70th percentile of OOB training probability",
            "prime_threshold": "90th percentile of OOB training probability",
            "2026": "reporting-only; not opened unless validation gate passes",
            "production_writes": False,
        },
    }
    (out/"mtf_model_meta.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")

    print(json.dumps(meta,ensure_ascii=False,indent=2))
    print(summary.to_string(index=False))


if __name__=="__main__":
    main()
