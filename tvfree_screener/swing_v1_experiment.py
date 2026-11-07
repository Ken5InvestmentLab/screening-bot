#!/usr/bin/env python3
"""10BD Swing research for the TradingView-free screener. TEST ONLY.

Design rules:
- Yahoo daily OHLCV only; no TradingView/Pine dependency.
- Actual-entry target is next-session open -> close 10 business days after signal.
- Model is frozen before validation: all training outcomes must end before 2025-07-01.
- 2025-H2 selects the method. 2026-03..08 is report-only fixed-side evaluation.
- Absolute probability thresholds are not used. Model outputs are converted to daily cross-sectional percentiles.
- Weekly schedules are causal: first/last trading session of a known calendar week only.

This is an experiment, not production selection logic.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
from xgboost import XGBClassifier, XGBRegressor

warnings.filterwarnings("ignore")

TRAIN_OUTCOME_CUTOFF = pd.Timestamp("2025-07-01")
VALID_START = pd.Timestamp("2025-07-01")
VALID_END = pd.Timestamp("2025-12-31")
TEST_START = pd.Timestamp("2026-03-01")
TEST_END = pd.Timestamp("2026-08-31")

FEATURES = [
    "ret1", "ret5", "ret10", "ret20", "ret40", "ret60",
    "ma5_gap", "ma20_gap", "ma40_gap", "ma60_gap",
    "volr5", "volr20", "volr40", "gap", "atr14p", "rsi5", "rsi14",
    "pos20", "pos60", "pos120", "dd20", "dd60", "dd120",
    "up5", "up10", "breadth_ret1_pos", "med_ret5", "med_ret20", "breadth_ma20",
]


def rolling_mean(a: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(a), np.nan)
    cs = np.r_[0.0, np.cumsum(np.nan_to_num(a, nan=0.0))]
    cnt = np.r_[0, np.cumsum(~np.isnan(a))]
    vals = cs[n:] - cs[:-n]
    counts = cnt[n:] - cnt[:-n]
    out[n - 1:] = np.where(counts == n, vals / n, np.nan)
    return out


def rolling_max(a: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(a), np.nan)
    if len(a) >= n:
        out[n - 1:] = np.nanmax(sliding_window_view(a, n), axis=1)
    return out


def rolling_min(a: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(a), np.nan)
    if len(a) >= n:
        out[n - 1:] = np.nanmin(sliding_window_view(a, n), axis=1)
    return out


def lag(a: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(a), np.nan)
    out[n:] = a[:-n]
    return out


def lead(a: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(a), np.nan)
    out[:-n] = a[n:]
    return out


def build_candidate_rows(daily: pd.DataFrame, price_cap: float) -> pd.DataFrame:
    daily = daily.sort_values(["symbol", "date"])
    parts: list[pd.DataFrame] = []

    for idx, (symbol, z) in enumerate(daily.groupby("symbol", sort=False), 1):
        close = z["close"].to_numpy(float)
        open_ = z["open"].to_numpy(float)
        high = z["high"].to_numpy(float)
        low = z["low"].to_numpy(float)
        volume = z["volume"].to_numpy(float)
        dates = z["date"].to_numpy(dtype="datetime64[ns]")
        n = len(z)

        feat: dict[str, object] = {
            "date": dates,
            "symbol": np.repeat(str(symbol), n),
            "close": close,
            "volume": volume,
        }
        for k in [1, 5, 10, 20, 40, 60]:
            feat[f"ret{k}"] = close / lag(close, k) - 1
        for k in [5, 20, 40, 60]:
            feat[f"ma{k}_gap"] = close / rolling_mean(close, k) - 1
        for k in [5, 20, 40]:
            feat[f"volr{k}"] = volume / rolling_mean(volume, k)

        prev_close = lag(close, 1)
        feat["gap"] = open_ / prev_close - 1
        tr = np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
        feat["atr14p"] = rolling_mean(tr, 14) / close

        delta = close - prev_close
        gain = np.where(delta > 0, delta, 0.0)
        loss = np.where(delta < 0, -delta, 0.0)
        for k in [5, 14]:
            ag = rolling_mean(gain, k)
            al = rolling_mean(loss, k)
            rs = ag / np.where(al == 0, np.nan, al)
            rsi = 100 - 100 / (1 + rs)
            rsi[(al == 0) & (ag > 0)] = 100
            feat[f"rsi{k}"] = rsi

        for k in [20, 60, 120]:
            hi = rolling_max(high, k)
            lo = rolling_min(low, k)
            feat[f"pos{k}"] = (close - lo) / (hi - lo)
            feat[f"dd{k}"] = close / hi - 1

        up = (delta > 0).astype(float)
        feat["up5"] = rolling_mean(up, 5) * 5
        feat["up10"] = rolling_mean(up, 10) * 10
        feat["prev_close"] = prev_close
        feat["prev_volume"] = lag(volume, 1)
        feat["next_open"] = lead(open_, 1)
        feat["target10_no"] = lead(close, 10) / feat["next_open"] - 1

        end_date = np.full(n, np.datetime64("NaT"), dtype="datetime64[ns]")
        if n > 10:
            end_date[:-10] = dates[10:]
        feat["target_end10"] = end_date

        x = pd.DataFrame(feat)
        mask = (
            (x["prev_volume"] >= 10_000)
            & (x["volume"] >= 5_000)
            & (x["close"] >= 20)
            & (x["date"] >= pd.Timestamp("2023-09-01"))
        )
        if price_cap > 0:
            mask &= x["prev_close"] <= price_cap
        parts.append(x.loc[mask])
        if idx % 700 == 0:
            print(f"feature symbols: {idx}")

    q = pd.concat(parts, ignore_index=True)
    q["breadth_ret1_pos"] = q.groupby("date")["ret1"].transform(lambda s: (s > 0).mean())
    q["med_ret5"] = q.groupby("date")["ret5"].transform("median")
    q["med_ret20"] = q.groupby("date")["ret20"].transform("median")
    q["breadth_ma20"] = q.groupby("date")["ma20_gap"].transform(lambda s: (s > 0).mean())
    return q.dropna(subset=FEATURES + ["target10_no", "target_end10"]).copy()


def classifier() -> XGBClassifier:
    return XGBClassifier(
        n_estimators=140, max_depth=3, learning_rate=0.045,
        subsample=0.8, colsample_bytree=0.8, min_child_weight=30,
        reg_lambda=6, reg_alpha=0.3, objective="binary:logistic",
        eval_metric="logloss", n_jobs=4, random_state=42,
    )


def rank_regressor() -> XGBRegressor:
    return XGBRegressor(
        n_estimators=220, max_depth=3, learning_rate=0.035,
        subsample=0.8, colsample_bytree=0.8, min_child_weight=30,
        reg_lambda=6, reg_alpha=0.3, objective="reg:squarederror",
        n_jobs=4, random_state=42,
    )


def split_frames(q: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    q["target_pct"] = q.groupby("date")["target10_no"].rank(pct=True)
    q["y_top10"] = (q["target_pct"] >= 0.90).astype("int8")
    q["y_top20"] = (q["target_pct"] >= 0.80).astype("int8")
    q["y_big10"] = (q["target10_no"] >= 0.10).astype("int8")
    q["y_big20"] = (q["target10_no"] >= 0.20).astype("int8")
    q["y_loss10"] = (q["target10_no"] <= -0.10).astype("int8")
    train = q[q["target_end10"] < TRAIN_OUTCOME_CUTOFF].copy()
    valid = q[(q["date"] >= VALID_START) & (q["date"] <= VALID_END)].copy()
    test = q[(q["date"] >= TEST_START) & (q["date"] <= TEST_END)].copy()
    return train, valid, test


def fit_classifier_heads(train: pd.DataFrame, frames: list[pd.DataFrame]) -> None:
    for head in ["top10", "top20", "big10", "big20", "loss10"]:
        m = classifier()
        m.fit(train[FEATURES], train[f"y_{head}"])
        for z in frames:
            z[f"p_{head}"] = m.predict_proba(z[FEATURES])[:, 1]
            z[f"r_{head}"] = z.groupby("date")[f"p_{head}"].rank(pct=True)
    for z in frames:
        z["score_A"] = z["r_top10"]
        z["score_D"] = (
            0.55 * z["r_top10"] + 0.20 * z["r_big20"] + 0.10 * z["r_big10"]
            + 0.15 * z["r_top20"] - 0.40 * z["r_loss10"]
        )


def fit_rank_regression(train: pd.DataFrame, frames: list[pd.DataFrame]) -> None:
    m = rank_regressor()
    m.fit(train[FEATURES], train["target_pct"])
    for z in frames:
        z["rankreg_raw"] = m.predict(z[FEATURES])
        z["score_rankreg"] = z.groupby("date")["rankreg_raw"].rank(pct=True)


def summarize(s: pd.Series) -> dict:
    s = s.dropna()
    if s.empty:
        return {"n": 0}
    return {
        "n": int(len(s)), "mean": float(s.mean()), "median": float(s.median()),
        "win_rate": float((s > 0).mean()), "hit10_rate": float((s >= 0.10).mean()),
        "hit20_rate": float((s >= 0.20).mean()), "loss10_rate": float((s <= -0.10).mean()),
        "max": float(s.max()), "min": float(s.min()),
    }


def select_schedule(z: pd.DataFrame, score: str, schedule: str) -> pd.DataFrame:
    daily = z.sort_values(["date", score], ascending=[True, False]).groupby("date").head(1).sort_values("date").copy()
    if schedule == "daily":
        return daily
    if schedule in {"first_week", "last_week"}:
        daily["week"] = daily["date"].dt.to_period("W-FRI")
        return daily.groupby("week", sort=True).head(1) if schedule == "first_week" else daily.groupby("week", sort=True).tail(1)
    if schedule == "every5":
        return daily.iloc[::5]
    raise ValueError(schedule)


def utility(stats: dict) -> float:
    return (
        stats["mean"] + 0.5 * stats["median"] + 0.03 * stats["win_rate"]
        + 0.04 * stats["hit10_rate"] - 0.08 * stats["loss10_rate"]
    )


def evaluate_family(valid: pd.DataFrame, test: pd.DataFrame, scores: list[str]) -> dict:
    rows = []
    for score in scores:
        for schedule in ["daily", "first_week", "last_week", "every5"]:
            p = select_schedule(valid, score, schedule)
            stats = summarize(p["target10_no"])
            rows.append({"score": score, "schedule": schedule, "validation": stats, "utility": utility(stats)})
    rows.sort(key=lambda r: r["utility"], reverse=True)
    eligible = [r for r in rows if r["validation"].get("n", 0) >= 20]
    locked = eligible[0]
    tp = select_schedule(test, locked["score"], locked["schedule"])
    locked = {**locked, "test_2026": summarize(tp["target10_no"])}
    return {"validation_ranking": rows, "locked_min20": locked}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default="tvfree_screener/out/tse_daily.csv")
    ap.add_argument("--price-cap", type=float, default=1000.0)
    ap.add_argument("--out", default="tvfree_screener/out/swing_v1_report.json")
    args = ap.parse_args()

    daily = pd.read_csv(args.cache, parse_dates=["date"], low_memory=False)
    q = build_candidate_rows(daily, args.price_cap)
    train, valid, test = split_frames(q)
    print(f"swing rows train={len(train)} validation={len(valid)} test={len(test)}")

    fit_classifier_heads(train, [valid, test])
    classifier_report = evaluate_family(valid, test, ["score_A", "score_D"])

    fit_rank_regression(train, [valid, test])
    rankreg_report = evaluate_family(valid, test, ["score_rankreg"])

    report = {
        "status": "research_only",
        "causality": "training outcomes end before 2025-07-01; 2025-H2 selects; 2026 is fixed-side report",
        "entry": "next_session_open",
        "horizon_bd": 10,
        "classifier_percentile": classifier_report,
        "rank_regression": rankreg_report,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
