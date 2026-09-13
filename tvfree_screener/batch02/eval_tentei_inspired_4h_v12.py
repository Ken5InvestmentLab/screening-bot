from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tvfree_screener.batch02 import eval_causal_4h_scoring_v3 as v3

CHANGE_DATE = pd.Timestamp("2024-11-05").date()
BIN_ORDER = {"AM_09_13": 0, "PM_13_CLOSE": 1}
COHORTS = ("ALL", "RSI_RECOVERY", "TREND_FLIP", "EMERGENCY_REVERSAL")


def build_bins(pattern: str, max_date: str = "2025-12-31") -> pd.DataFrame:
    parts = []
    limit = pd.Timestamp(max_date).date()
    for path in sorted(glob.glob(pattern)):
        raw = pd.read_csv(path, dtype={"symbol": "string"})
        raw["ts"] = pd.to_datetime(raw["timestamp"], errors="coerce")
        raw = raw[raw["ts"].notna()].copy()
        raw["symbol"] = raw["symbol"].astype(str).str.replace(r"\.0$", "", regex=True).str.upper()
        raw["date"] = raw["ts"].dt.date
        raw = raw[raw["date"] <= limit].copy()
        raw["hour"] = raw["ts"].dt.hour
        pre = raw["date"] < CHANGE_DATE
        am = raw["hour"].isin([9, 10, 11, 12])
        pm = (pre & raw["hour"].isin([13, 14])) | (~pre & raw["hour"].isin([13, 14, 15]))
        raw = raw[am | pm].copy()
        raw["bin_name"] = np.where(raw["hour"].isin([9, 10, 11, 12]), "AM_09_13", "PM_13_CLOSE")
        raw = raw.sort_values(["symbol", "date", "ts"], kind="stable")
        out = raw.groupby(["symbol", "date", "bin_name"], sort=False).agg(
            row_count=("hour", "size"),
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        ).reset_index()
        pre_out = out["date"] < CHANGE_DATE
        expected = np.where(out["bin_name"].eq("AM_09_13"), 4, np.where(pre_out, 2, 3))
        out = out[out["row_count"].eq(expected)].copy()
        parts.append(out)
    if not parts:
        raise FileNotFoundError(pattern)
    bins = pd.concat(parts, ignore_index=True)
    bins["bin_ord"] = bins["bin_name"].map(BIN_ORDER)
    return bins.sort_values(["symbol", "date", "bin_ord"], kind="stable").reset_index(drop=True)


def _group_indicators(close: np.ndarray, high: np.ndarray, low: np.ndarray):
    n = len(close)
    series = pd.Series(close)
    mid = series.rolling(20, min_periods=20).mean().to_numpy()
    std = series.rolling(20, min_periods=20).std(ddof=0).to_numpy()

    rsi = np.full(n, np.nan)
    if n > 12:
        delta = np.diff(close)
        gains = np.maximum(delta, 0.0)
        losses = np.maximum(-delta, 0.0)
        avg_gain = gains[:12].mean()
        avg_loss = losses[:12].mean()
        rsi[12] = 100.0 if avg_loss == 0 and avg_gain > 0 else (50.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss))
        for i in range(13, n):
            avg_gain = (avg_gain * 11.0 + gains[i - 1]) / 12.0
            avg_loss = (avg_loss * 11.0 + losses[i - 1]) / 12.0
            rsi[i] = 100.0 if avg_loss == 0 and avg_gain > 0 else (50.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss))

    tr = np.empty(n, dtype=float)
    tr[0] = high[0] - low[0]
    if n > 1:
        tr[1:] = np.maximum.reduce([
            high[1:] - low[1:],
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1]),
        ])
    atr = np.full(n, np.nan)
    if n >= 14:
        value = tr[:14].mean()
        atr[13] = value
        for i in range(14, n):
            value = (value * 13.0 + tr[i]) / 14.0
            atr[i] = value

    width = 4.0 * std
    lower = mid - 2.0 * std
    band_pos = np.where(width > 0, (close - lower) / width, np.nan)

    prior5_low = np.full(n, np.nan)
    prior5_rsi_min = np.full(n, np.nan)
    prior5_band_min = np.full(n, np.nan)
    for i in range(5, n):
        prior5_low[i] = np.min(low[i - 5:i])
        rv = rsi[i - 5:i]
        bv = band_pos[i - 5:i]
        if np.isfinite(rv).any():
            prior5_rsi_min[i] = np.nanmin(rv)
        if np.isfinite(bv).any():
            prior5_band_min[i] = np.nanmin(bv)
    return mid, std, rsi, atr, prior5_low, prior5_rsi_min, prior5_band_min


def add_v12_state(bins: pd.DataFrame) -> pd.DataFrame:
    out = bins.copy()
    n = len(out)
    arrays = [np.full(n, np.nan) for _ in range(7)]
    for _, group in out.groupby("symbol", sort=False):
        idx = group.index.to_numpy()
        vals = _group_indicators(
            group["close"].to_numpy(float),
            group["high"].to_numpy(float),
            group["low"].to_numpy(float),
        )
        for target, values in zip(arrays, vals):
            target[idx] = values
    out["bb_mid"], out["bb_std"], out["rsi12"], out["atr14"], out["prior5_low"], out["prior5_rsi_min"], out["prior5_band_min"] = arrays
    out["bb_slope"] = out.groupby("symbol", sort=False)["bb_mid"].diff()
    out["prev_bb_slope"] = out.groupby("symbol", sort=False)["bb_slope"].shift(1)
    out["prev_rsi12"] = out.groupby("symbol", sort=False)["rsi12"].shift(1)
    out["setup"] = (out["prior5_rsi_min"] <= 35.0) | (out["prior5_band_min"] <= 0.18)
    out["rsi_recovery"] = (out["rsi12"] > 35.0) & (out["prev_rsi12"] <= 35.0)
    out["trend_flip"] = (out["bb_slope"] > 0.0) & (out["prev_bb_slope"] <= 0.0) & (out["rsi12"] > 50.0) & (out["prev_rsi12"] <= 50.0)
    out["emergency_reversal"] = out["close"] > out["prior5_low"] + 2.5 * out["atr14"]
    out["signal"] = out["setup"] & (out["rsi_recovery"] | out["trend_flip"] | out["emergency_reversal"])
    return out


def attach_gates_and_labels(signals: pd.DataFrame, daily_path: str):
    daily = v3.load_daily(Path(daily_path))
    sessions = sorted(daily["date"].dropna().unique().tolist())
    prior_map = {sessions[i]: sessions[i - 1] for i in range(1, len(sessions))}
    s = signals.copy()
    s["date"] = s["date"].astype(str)
    s["prior_date"] = s["date"].map(prior_map)
    prior = daily[["symbol", "date", "close", "volume"]].rename(
        columns={"date": "prior_date", "close": "prior_daily_close", "volume": "prior_daily_volume"}
    )
    s = s.merge(prior, on=["symbol", "prior_date"], how="left")
    s = s[(s["prior_daily_close"] <= 1000) & (s["prior_daily_volume"] >= 10000)].copy()
    s, session_idx = v3.attach_endpoint_labels(s, daily)
    return s, session_idx


def cooldown(rows: pd.DataFrame, session_idx: dict[str, int]) -> pd.DataFrame:
    ordered = rows.sort_values(["date", "bin_ord", "symbol"], kind="stable")
    blocked = {}
    keep = []
    for idx, row in ordered.iterrows():
        di = session_idx.get(row["date"])
        if di is None:
            continue
        symbol = str(row["symbol"])
        if blocked.get(symbol, -999999) > di:
            continue
        keep.append(idx)
        blocked[symbol] = di + 5
    return ordered.loc[keep].copy()


def passes_monster(metrics: dict) -> bool:
    return (
        metrics.get("resolved", 0) >= 30
        and metrics.get("net_mean", -999.0) > 0
        and metrics.get("gross_ge20_rate", -1.0) >= 0.10
        and metrics.get("top1_removed_net_mean", -999.0) > 0
        and metrics.get("gross_le10_rate", 999.0) <= 0.40
    )


def evaluate(signals: pd.DataFrame, session_idx: dict[str, int], start: str, end: str):
    period = signals[(signals["date"] >= start) & (signals["date"] <= end)].copy()
    result = {"raw_signal_rows": int(len(period)), "cohorts": {}}
    masks = {
        "ALL": period["signal"],
        "RSI_RECOVERY": period["setup"] & period["rsi_recovery"],
        "TREND_FLIP": period["setup"] & period["trend_flip"],
        "EMERGENCY_REVERSAL": period["setup"] & period["emergency_reversal"],
    }
    for name in COHORTS:
        selected = cooldown(period[masks[name]], session_idx)
        m = v3.metrics(selected, 0.005)
        m["passes_monster_gate"] = passes_monster(m)
        m["cost0"] = v3.metrics(selected, 0.0)
        m["cost1pct"] = v3.metrics(selected, 0.01)
        result["cohorts"][name] = m
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--raw-glob", required=True)
    p.add_argument("--daily", required=True)
    p.add_argument("--period", choices=["h1", "h2"], required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    bins = add_v12_state(build_bins(args.raw_glob))
    signals = bins[bins["signal"]].copy()
    signals, session_idx = attach_gates_and_labels(signals, args.daily)
    if args.period == "h1":
        start, end = "2025-03-01", "2025-06-30"
    else:
        start, end = "2025-07-01", "2025-12-31"
    result = {
        "experiment_id": "TENTEI-INSPIRED-4H-V12-STATE-REVERSAL-20260913",
        "classification": "INDEPENDENT_TENTEI_INSPIRED_NOT_EXACT_REPLICATION",
        "period": args.period,
        "candidate_rows_2025_after_prior_day_gates": int(((signals["date"] >= "2025-01-01") & (signals["date"] <= "2025-12-31")).sum()),
        "2026_outcomes_opened": False,
        "production_modified": False,
        "evaluation": evaluate(signals, session_idx, start, end),
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
