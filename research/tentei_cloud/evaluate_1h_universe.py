#!/usr/bin/env python3
"""Evaluate genuine Yahoo JPX 1h bars for Tentei Cloud research.

Research-only:
- no production Discord/Sheets writes
- fixed signal-time rules only
- 5BD outcome is reporting, never used in the signal
- user-facing lanes: Core / Monster Watch / Monster Prime
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd


def rsi_wilder(close: pd.Series, period: int = 12) -> pd.Series:
    d = close.diff()
    gain = d.clip(lower=0)
    loss = -d.clip(upper=0)
    ag = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    al = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = ag / al.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def load_inputs(patterns: list[str]) -> pd.DataFrame:
    files: list[str] = []
    for pat in patterns:
        files.extend(glob.glob(pat, recursive=True))
    files = sorted(dict.fromkeys(files))
    if not files:
        raise SystemExit("No 1H CSV inputs matched")
    frames = []
    for p in files:
        q = pd.read_csv(p)
        if not q.empty:
            q["_source"] = p
            frames.append(q)
    if not frames:
        raise SystemExit("All matched CSV inputs are empty")
    df = pd.concat(frames, ignore_index=True)
    need = {"timestamp", "symbol", "open", "high", "low", "close", "volume"}
    missing = need - set(df.columns)
    if missing:
        raise SystemExit(f"Missing columns: {sorted(missing)}")
    df["symbol"] = df["symbol"].astype(str).str.replace(".T", "", regex=False)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce").dt.tz_convert("Asia/Tokyo")
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["timestamp", "symbol", "open", "high", "low", "close"])
    df = df.sort_values(["symbol", "timestamp"]).drop_duplicates(["symbol", "timestamp"], keep="last")
    flat = (df["open"] == df["high"]) & (df["high"] == df["low"]) & (df["low"] == df["close"])
    late = ((df["timestamp"].dt.hour == 15) & (df["timestamp"].dt.minute >= 30)) | (df["timestamp"].dt.hour >= 16)
    df = df[~((df["volume"].fillna(0) == 0) & flat & late)].copy()
    df["date"] = df["timestamp"].dt.date.astype(str)
    return df


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    outs = []
    for _, g in df.groupby("symbol", sort=False):
        g = g.sort_values("timestamp").copy()
        c = g["close"]
        h = g["high"]
        l = g["low"]
        v = g["volume"].fillna(0)

        g["ema20"] = c.ewm(span=20, adjust=False).mean()
        g["ema75"] = c.ewm(span=75, adjust=False).mean()
        e12 = c.ewm(span=12, adjust=False).mean()
        e26 = c.ewm(span=26, adjust=False).mean()
        macd = e12 - e26
        g["macd_hist"] = macd - macd.ewm(span=9, adjust=False).mean()

        g["rsi12"] = rsi_wilder(c, 12)
        mid = c.rolling(20, min_periods=20).mean()
        sd = c.rolling(20, min_periods=20).std(ddof=0)
        g["bb_mid"] = mid
        g["bb_width"] = (4 * sd).replace(0, np.nan)
        g["bb_reclaim"] = (c - mid) / g["bb_width"]

        prev_c = c.shift(1)
        tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
        g["atr14_pct"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean() / c.replace(0, np.nan)
        g["range_pct"] = (h - l) / c.replace(0, np.nan)

        vbase = v.shift(1).rolling(20, min_periods=10).mean()
        g["vsurge"] = v / vbase.replace(0, np.nan)
        g["ret3h"] = c.pct_change(3)

        # Previous three completed 1H closes descending into the current bar.
        g["pre_down3"] = (c.shift(1) < c.shift(2)) & (c.shift(2) < c.shift(3))
        outs.append(g)
    return pd.concat(outs, ignore_index=True)


def add_daily_context(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    daily = (
        df.sort_values("timestamp")
        .groupby(["symbol", "date"], as_index=False)
        .agg(daily_close=("close", "last"), daily_volume=("volume", "sum"))
    )
    daily = daily.sort_values(["symbol", "date"])
    daily["prev_daily_close"] = daily.groupby("symbol")["daily_close"].shift(1)
    daily["prev_daily_volume"] = daily.groupby("symbol")["daily_volume"].shift(1)

    dates = sorted(daily["date"].unique().tolist())
    date_to_target = {d: (dates[i + 5] if i + 5 < len(dates) else None) for i, d in enumerate(dates)}
    target = daily[["symbol", "date", "daily_close"]].rename(columns={"date": "target_date", "daily_close": "target_close"})
    context = daily[["symbol", "date", "prev_daily_close", "prev_daily_volume"]]
    out = df.merge(context, on=["symbol", "date"], how="left")
    out["target_date"] = out["date"].map(date_to_target)
    out = out.merge(target, on=["symbol", "target_date"], how="left")
    out["ret5bd"] = out["target_close"] / out["close"] - 1.0
    return out, daily, dates


def cross_section_monster_score(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    # All inputs are signal-time only. Ranks are contemporaneous cross-sectional ranks.
    for c in ["range_pct", "vsurge", "bb_reclaim"]:
        d[f"{c}_rank"] = d.groupby("timestamp")[c].rank(pct=True, method="average")
    d["monster_score"] = (
        0.50 * d["range_pct_rank"].fillna(0)
        + 0.30 * d["vsurge_rank"].fillna(0)
        + 0.20 * d["bb_reclaim_rank"].fillna(0)
    )
    d["monster_pct"] = d.groupby("timestamp")["monster_score"].rank(pct=True, method="average")
    return d


def cooldown(picks: pd.DataFrame, market_dates: list[str], days: int = 5) -> pd.DataFrame:
    if picks.empty:
        return picks.copy()
    idx = {d: i for i, d in enumerate(market_dates)}
    keep = []
    last: dict[str, int] = {}
    for row_i, r in picks.sort_values(["timestamp", "symbol"]).iterrows():
        di = idx.get(r["date"])
        if di is None:
            continue
        prev = last.get(r["symbol"])
        if prev is None or di - prev >= days:
            keep.append(row_i)
            last[r["symbol"]] = di
    return picks.loc[keep].sort_values(["timestamp", "symbol"]).copy()


def summarize(name: str, picks: pd.DataFrame) -> dict:
    x = picks["ret5bd"].dropna().astype(float)
    out = {"lane": name, "n": int(len(x))}
    if x.empty:
        for k in ["mean", "median", "win", "ge10", "ge20", "ge30", "le10", "max", "top1_removed", "top3_removed", "top5_removed"]:
            out[k] = None
        return out
    out.update({
        "mean": float(x.mean()),
        "median": float(x.median()),
        "win": float((x > 0).mean()),
        "ge10": float((x >= 0.10).mean()),
        "ge20": float((x >= 0.20).mean()),
        "ge30": float((x >= 0.30).mean()),
        "le10": float((x <= -0.10).mean()),
        "max": float(x.max()),
    })
    xs = x.sort_values(ascending=False)
    for k in (1, 3, 5):
        out[f"top{k}_removed"] = float(xs.iloc[k:].mean()) if len(xs) > k else None
    return out


def add_period(rows: list[dict], lane: str, picks: pd.DataFrame, period: str, mask) -> None:
    s = summarize(lane, picks.loc[mask].copy())
    s["period"] = period
    rows.append(s)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", action="append", required=True, help="Glob; may be supplied multiple times")
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    raw = load_inputs(args.inputs)
    enriched = add_indicators(raw)
    full, daily, market_dates = add_daily_context(enriched)

    eligible = full[
        (full["prev_daily_close"] <= 1000)
        & (full["prev_daily_volume"] >= 10000)
        & (full["volume"] >= 5000)
    ].copy()

    core = eligible[
        (eligible["rsi12"] < 45)
        & eligible["pre_down3"].fillna(False)
        & (eligible["close"] > eligible["bb_mid"])
        & (eligible["atr14_pct"] < 0.05)
    ].copy()
    core = cooldown(core, market_dates, 5)
    core["lane"] = "Core"

    monster_pool = eligible[
        (eligible["close"] <= eligible["ema75"])
        & (eligible["macd_hist"] <= 0)
        & (eligible["close"] > eligible["bb_mid"])
        & (eligible["close"] <= eligible["open"])
        & (eligible["range_pct"] >= 0.02)
    ].copy()
    monster_pool = cross_section_monster_score(monster_pool)

    watch = monster_pool[monster_pool["monster_pct"] >= 0.70].copy()
    prime = monster_pool[monster_pool["monster_pct"] >= 0.90].copy()
    watch = cooldown(watch, market_dates, 5)
    prime = cooldown(prime, market_dates, 5)
    watch["lane"] = "Monster Watch"
    prime["lane"] = "Monster Prime"

    all_picks = pd.concat([core, watch, prime], ignore_index=True, sort=False)
    keep_cols = [
        "lane", "timestamp", "date", "symbol", "open", "high", "low", "close", "volume",
        "prev_daily_close", "prev_daily_volume", "rsi12", "ema75", "macd_hist", "bb_mid",
        "atr14_pct", "range_pct", "vsurge", "bb_reclaim", "monster_score", "monster_pct",
        "target_date", "target_close", "ret5bd",
    ]
    for c in keep_cols:
        if c not in all_picks.columns:
            all_picks[c] = np.nan
    all_picks[keep_cols].to_csv(outdir / "tentei_cloud_1h_picks.csv", index=False)

    rows: list[dict] = []
    lane_map = {"Core": core, "Monster Watch": watch, "Monster Prime": prime}
    for lane, picks in lane_map.items():
        add_period(rows, lane, picks, "ALL", pd.Series(True, index=picks.index))
        d = pd.to_datetime(picks["date"], errors="coerce")
        add_period(rows, lane, picks, "FEB-JUN", (d >= "2026-02-01") & (d <= "2026-06-30"))
        add_period(rows, lane, picks, "JUL-AUG", (d >= "2026-07-01") & (d <= "2026-08-31"))
        for month in sorted(d.dropna().dt.to_period("M").astype(str).unique()):
            add_period(rows, lane, picks, month, d.dt.to_period("M").astype(str) == month)

    summary = pd.DataFrame(rows)
    summary.to_csv(outdir / "tentei_cloud_1h_summary.csv", index=False)

    meta = {
        "raw_rows": int(len(raw)),
        "symbols": int(raw["symbol"].nunique()),
        "start": str(raw["date"].min()),
        "end": str(raw["date"].max()),
        "eligible_rows": int(len(eligible)),
        "monster_pool_rows_pre_cooldown": int(len(monster_pool)),
        "policy": {
            "entry": "candidate 1H bar close",
            "exit": "daily close on market date +5",
            "cooldown_business_days": 5,
            "watch_percentile": 0.70,
            "prime_percentile": 0.90,
            "outcomes_used_for_signal": False,
            "production_writes": False,
        },
    }
    (outdir / "tentei_cloud_1h_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
