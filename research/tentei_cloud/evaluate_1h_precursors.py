#!/usr/bin/env python3
"""Evaluate 1H precursor families for known 4H Monster events and universe-wide selectivity.

Research-only. Descriptive 2026 study; not an untouched validation set.
No production writes.
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

REFERENCES = [
    ("6085", "2026-03-09 09:00:00+09:00", "Monster Prime", 1.236025),
    ("4052", "2026-07-31 09:00:00+09:00", "Monster Prime", 0.558480),
    ("8105", "2026-05-28 13:00:00+09:00", "Monster Prime", 0.827815),
    ("3444", "2026-04-16 09:00:00+09:00", "Monster Watch", 0.688755),
    ("5575", "2026-04-15 13:00:00+09:00", "Monster Watch", 0.297381),
    ("6666", "2026-03-05 09:00:00+09:00", "Monster Prime", 0.387247),
    ("2338", "2026-03-10 09:00:00+09:00", "Monster Prime", 0.398496),
    ("6217", "2026-04-13 13:00:00+09:00", "Monster Prime", np.nan),
]


def rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
    d = close.diff()
    gain = d.clip(lower=0)
    loss = -d.clip(upper=0)
    ag = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    al = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = ag / al.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def load(patterns: list[str]) -> pd.DataFrame:
    files: list[str] = []
    for pat in patterns:
        files.extend(glob.glob(pat, recursive=True))
    files = sorted(dict.fromkeys(files))
    if not files:
        raise SystemExit("No CSV inputs matched")
    frames = []
    for p in files:
        q = pd.read_csv(p, dtype={"symbol": "string"}, low_memory=False)
        if not q.empty:
            frames.append(q)
    if not frames:
        raise SystemExit("All CSV inputs are empty")
    d = pd.concat(frames, ignore_index=True)
    d["symbol"] = d["symbol"].astype("string").str.replace(".T", "", regex=False)
    d["timestamp"] = pd.to_datetime(d["timestamp"], utc=True, errors="coerce").dt.tz_convert("Asia/Tokyo")
    for c in ["open", "high", "low", "close", "volume"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["symbol", "timestamp", "open", "high", "low", "close"])
    d = d.sort_values(["symbol", "timestamp"]).drop_duplicates(["symbol", "timestamp"], keep="last")
    flat = (d["open"] == d["high"]) & (d["high"] == d["low"]) & (d["low"] == d["close"])
    late = ((d["timestamp"].dt.hour == 15) & (d["timestamp"].dt.minute >= 30)) | (d["timestamp"].dt.hour >= 16)
    d = d[~((d["volume"].fillna(0) == 0) & flat & late)].copy()
    d["date"] = d["timestamp"].dt.date.astype(str)
    return d


def enrich(d: pd.DataFrame) -> pd.DataFrame:
    out = []
    for _, g in d.groupby("symbol", sort=False):
        g = g.sort_values("timestamp").copy()
        c = g["close"]
        v = g["volume"].fillna(0)
        g["ema20"] = c.ewm(span=20, adjust=False).mean()
        g["ret3h"] = c.pct_change(3)
        g["rsi14"] = rsi_wilder(c, 14)

        mid = c.rolling(20, min_periods=20).mean()
        sd = c.rolling(20, min_periods=20).std(ddof=0)
        lower = mid - 2 * sd
        upper = mid + 2 * sd
        width = (upper - lower).replace(0, np.nan)
        g["bbpct"] = (c - lower) / width

        vbase = v.shift(1).rolling(20, min_periods=10).mean()
        g["vsurge"] = v / vbase.replace(0, np.nan)
        prior_high20 = g["high"].shift(1).rolling(20, min_periods=10).max()
        g["break20"] = c > prior_high20
        g["above_ema20"] = c > g["ema20"]

        g["fast"] = (
            (g["ret3h"] >= 0.03)
            & (g["rsi14"] >= 55)
            & g["above_ema20"]
            & (g["vsurge"] >= 1.20)
        )
        g["balanced"] = (
            (g["ret3h"] >= 0.04)
            & (g["rsi14"] >= 58)
            & (g["bbpct"] >= 0.65)
            & (g["vsurge"] >= 1.50)
        )
        g["breakout"] = (
            g["break20"]
            & (g["rsi14"] >= 60)
            & (g["vsurge"] >= 1.50)
            & (g["ret3h"] >= 0.02)
        )
        out.append(g)
    return pd.concat(out, ignore_index=True)


def add_daily_context(d: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    daily = (
        d.sort_values("timestamp")
        .groupby(["symbol", "date"], as_index=False)
        .agg(daily_close=("close", "last"), daily_volume=("volume", "sum"))
        .sort_values(["symbol", "date"])
    )
    daily["prev_daily_close"] = daily.groupby("symbol")["daily_close"].shift(1)
    daily["prev_daily_volume"] = daily.groupby("symbol")["daily_volume"].shift(1)

    dates = sorted(daily["date"].unique().tolist())
    target_map = {x: (dates[i + 5] if i + 5 < len(dates) else None) for i, x in enumerate(dates)}
    target = daily[["symbol", "date", "daily_close"]].rename(
        columns={"date": "target_date", "daily_close": "target_close"}
    )
    d = d.merge(
        daily[["symbol", "date", "prev_daily_close", "prev_daily_volume"]],
        on=["symbol", "date"], how="left"
    )
    d["target_date"] = d["date"].map(target_map)
    d = d.merge(target, on=["symbol", "target_date"], how="left")
    d["ret5bd"] = d["target_close"] / d["close"] - 1.0
    return d, dates


def cooldown(picks: pd.DataFrame, market_dates: list[str], days: int = 5) -> pd.DataFrame:
    if picks.empty:
        return picks.copy()
    pos = {d: i for i, d in enumerate(market_dates)}
    last: dict[str, int] = {}
    keep = []
    for idx, r in picks.sort_values(["timestamp", "symbol"]).iterrows():
        di = pos.get(r["date"])
        if di is None:
            continue
        p = last.get(str(r["symbol"]))
        if p is None or di - p >= days:
            keep.append(idx)
            last[str(r["symbol"])] = di
    return picks.loc[keep].sort_values(["timestamp", "symbol"]).copy()


def summarize(name: str, x: pd.DataFrame, eligible_count: int) -> dict:
    r = x["ret5bd"].dropna().astype(float)
    ans = {
        "trigger": name,
        "candidate_rows": int(len(x)),
        "matured_n": int(len(r)),
        "eligible_bar_rate": float(len(x) / eligible_count) if eligible_count else None,
        "unique_symbols": int(x["symbol"].nunique()) if len(x) else 0,
        "unique_days": int(x["date"].nunique()) if len(x) else 0,
    }
    if r.empty:
        ans.update({k: None for k in [
            "mean", "median", "win", "ge10", "ge20", "ge30", "le10", "max",
            "top1_removed", "top3_removed", "top5_removed"
        ]})
        return ans
    ans.update({
        "mean": float(r.mean()),
        "median": float(r.median()),
        "win": float((r > 0).mean()),
        "ge10": float((r >= 0.10).mean()),
        "ge20": float((r >= 0.20).mean()),
        "ge30": float((r >= 0.30).mean()),
        "le10": float((r <= -0.10).mean()),
        "max": float(r.max()),
    })
    rs = r.sort_values(ascending=False)
    for k in (1, 3, 5):
        ans[f"top{k}_removed"] = float(rs.iloc[k:].mean()) if len(rs) > k else None
    return ans


def reference_hits(d: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sym, ref_text, tier, ret5 in REFERENCES:
        ref = pd.Timestamp(ref_text)
        g = d[d["symbol"].astype(str) == sym].sort_values("timestamp")
        w = g[(g["timestamp"] >= ref - pd.Timedelta(days=7)) & (g["timestamp"] <= ref)].copy()
        row = {
            "symbol": sym,
            "reference_time_4h": ref.isoformat(),
            "reference_tier": tier,
            "reference_ret5": ret5,
            "bars_in_window": int(len(w)),
        }
        for col in ("fast", "balanced", "breakout"):
            hit = w[w[col].fillna(False)]
            if hit.empty:
                row[f"{col}_time"] = ""
                row[f"{col}_lead_hours"] = np.nan
            else:
                h = hit.iloc[0]
                row[f"{col}_time"] = h["timestamp"].isoformat()
                row[f"{col}_lead_hours"] = (ref - h["timestamp"]).total_seconds() / 3600
                row[f"{col}_ret3h"] = h["ret3h"]
                row[f"{col}_rsi14"] = h["rsi14"]
                row[f"{col}_vsurge"] = h["vsurge"]
                row[f"{col}_bbpct"] = h["bbpct"]
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", action="append", required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()

    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    raw = load(a.inputs)
    full = enrich(raw)
    full, market_dates = add_daily_context(full)

    eligible = full[
        (full["prev_daily_close"] <= 1000)
        & (full["prev_daily_volume"] >= 10000)
        & (full["volume"] >= 5000)
    ].copy()

    summaries = []
    picks_all = []
    for col in ("fast", "balanced", "breakout"):
        q = eligible[eligible[col].fillna(False)].copy()
        q = cooldown(q, market_dates, 5)
        q["trigger"] = col
        summaries.append(summarize(col, q, len(eligible)))
        picks_all.append(q)

    ref = reference_hits(full)
    ref.to_csv(outdir / "known_monster_precursor_hits.csv", index=False)

    picks = pd.concat(picks_all, ignore_index=True, sort=False) if picks_all else pd.DataFrame()
    keep = [
        "trigger", "timestamp", "date", "symbol", "open", "high", "low", "close", "volume",
        "prev_daily_close", "prev_daily_volume", "ret3h", "rsi14", "vsurge", "bbpct",
        "break20", "target_date", "target_close", "ret5bd"
    ]
    for c in keep:
        if c not in picks:
            picks[c] = np.nan
    picks[keep].to_csv(outdir / "precursor_picks.csv", index=False)

    s = pd.DataFrame(summaries)
    s.to_csv(outdir / "precursor_summary.csv", index=False)

    ref_summary = []
    for col in ("fast", "balanced", "breakout"):
        hit = ref[f"{col}_lead_hours"].notna()
        ref_summary.append({
            "trigger": col,
            "known_monster_hits": int(hit.sum()),
            "known_monster_total": int(len(ref)),
            "known_monster_hit_rate": float(hit.mean()),
            "median_lead_hours": float(ref.loc[hit, f"{col}_lead_hours"].median()) if hit.any() else None,
            "mean_lead_hours": float(ref.loc[hit, f"{col}_lead_hours"].mean()) if hit.any() else None,
        })
    ref_s = pd.DataFrame(ref_summary)
    ref_s.to_csv(outdir / "known_monster_precursor_summary.csv", index=False)

    meta = {
        "raw_rows": int(len(raw)),
        "symbols": int(raw["symbol"].nunique()),
        "eligible_rows": int(len(eligible)),
        "start": str(raw["date"].min()),
        "end": str(raw["date"].max()),
        "known_monster_reference_count": len(REFERENCES),
        "warning": "2026 is already inspected; these are descriptive research results, not untouched validation.",
        "production_writes": False,
    }
    (outdir / "precursor_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print("\nUNIVERSE PRECURSOR SUMMARY")
    print(s.to_string(index=False))
    print("\nKNOWN MONSTER PRECURSOR SUMMARY")
    print(ref_s.to_string(index=False))
    print("\nKNOWN MONSTER DETAILS")
    print(ref.to_string(index=False))


if __name__ == "__main__":
    main()
