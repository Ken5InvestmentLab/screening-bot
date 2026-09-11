#!/usr/bin/env python3
"""Evaluate genuine JPX 1h precursor timing for known 天底極致 Cloud Monster events.

Research-only. No production writes.
"""
from __future__ import annotations

import argparse
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
    ("6217", "2026-04-13 13:00:00+09:00", "Monster Prime", float("nan")),
]


def rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.fillna(100)


def enrich(g: pd.DataFrame) -> pd.DataFrame:
    g = g.sort_values("timestamp").copy()
    c = g["close"].astype(float)
    v = g["volume"].astype(float)

    g["ema20_1h"] = c.ewm(span=20, adjust=False).mean()
    g["ret1h"] = c.pct_change(1)
    g["ret3h"] = c.pct_change(3)
    g["ret6h"] = c.pct_change(6)
    g["rsi14_1h"] = rsi_wilder(c, 14)

    mid = c.rolling(20, min_periods=20).mean()
    sd = c.rolling(20, min_periods=20).std(ddof=0)
    lower = mid - 2 * sd
    upper = mid + 2 * sd
    width = (upper - lower).replace(0, np.nan)
    g["bbpct_1h"] = (c - lower) / width

    vbase = v.shift(1).rolling(20, min_periods=10).mean()
    g["vsurge_1h"] = v / vbase.replace(0, np.nan)

    prior_high20 = g["high"].astype(float).shift(1).rolling(20, min_periods=10).max()
    g["break20_1h"] = c > prior_high20
    g["above_ema20_1h"] = c > g["ema20_1h"]

    # Research candidate families. Thresholds are intentionally simple and fixed.
    g["trig_fast"] = (
        (g["ret3h"] >= 0.03)
        & (g["rsi14_1h"] >= 55)
        & g["above_ema20_1h"]
        & (g["vsurge_1h"] >= 1.20)
    )
    g["trig_balanced"] = (
        (g["ret3h"] >= 0.04)
        & (g["rsi14_1h"] >= 58)
        & (g["bbpct_1h"] >= 0.65)
        & (g["vsurge_1h"] >= 1.50)
    )
    g["trig_breakout"] = (
        g["break20_1h"]
        & (g["rsi14_1h"] >= 60)
        & (g["vsurge_1h"] >= 1.50)
        & (g["ret3h"] >= 0.02)
    )
    return g


def first_trigger(window: pd.DataFrame, col: str):
    q = window[window[col].fillna(False)]
    if q.empty:
        return None
    return q.iloc[0]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    df = pd.read_csv(args.input)
    if df.empty:
        raise SystemExit("1h input is empty")

    df["symbol"] = df["symbol"].astype(str)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("Asia/Tokyo")
    if "is_closing_snapshot" in df.columns:
        df = df[df["is_closing_snapshot"].fillna(0).astype(int) == 0].copy()

    enriched = []
    for sym, g in df.groupby("symbol", sort=False):
        enriched.append(enrich(g))
    full = pd.concat(enriched, ignore_index=True)

    rows = []
    for sym, ref_text, tier, ref_ret5 in REFERENCES:
        ref = pd.Timestamp(ref_text)
        g = full[full["symbol"] == sym].sort_values("timestamp")
        start = ref - pd.Timedelta(days=7)
        window = g[(g["timestamp"] >= start) & (g["timestamp"] <= ref)].copy()

        base = {
            "symbol": sym,
            "reference_time_4h": ref.isoformat(),
            "reference_tier": tier,
            "reference_ret5": ref_ret5,
            "bars_in_window": len(window),
        }

        for label, col in [
            ("fast", "trig_fast"),
            ("balanced", "trig_balanced"),
            ("breakout", "trig_breakout"),
        ]:
            hit = first_trigger(window, col)
            if hit is None:
                base[f"{label}_time"] = ""
                base[f"{label}_lead_hours"] = np.nan
                base[f"{label}_ret3h"] = np.nan
                base[f"{label}_rsi"] = np.nan
                base[f"{label}_vsurge"] = np.nan
                base[f"{label}_bbpct"] = np.nan
            else:
                t = hit["timestamp"]
                base[f"{label}_time"] = t.isoformat()
                base[f"{label}_lead_hours"] = (ref - t).total_seconds() / 3600.0
                base[f"{label}_ret3h"] = hit["ret3h"]
                base[f"{label}_rsi"] = hit["rsi14_1h"]
                base[f"{label}_vsurge"] = hit["vsurge_1h"]
                base[f"{label}_bbpct"] = hit["bbpct_1h"]
        rows.append(base)

    out = pd.DataFrame(rows)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)

    print(out.to_string(index=False))
    for label in ["fast", "balanced", "breakout"]:
        hits = out[f"{label}_lead_hours"].notna()
        if hits.any():
            print(
                f"{label}: hit {int(hits.sum())}/{len(out)}, "
                f"median lead={out.loc[hits, f'{label}_lead_hours'].median():.1f}h, "
                f"mean lead={out.loc[hits, f'{label}_lead_hours'].mean():.1f}h"
            )
        else:
            print(f"{label}: hit 0/{len(out)}")


if __name__ == "__main__":
    main()
