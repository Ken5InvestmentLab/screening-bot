#!/usr/bin/env python3
"""TV-Free V3 Swing research runner (TEST ONLY).

Uses the Yahoo daily cache produced by the isolated tvfree screener workflow.
No Discord/Sheets/production writes. All selection is based on next-session-open
entry and future close horizons, with one-trading-day same-symbol cooldown.

This file intentionally keeps rejected ML experiments out of the production
path. Current research candidates are cross-sectional/event engines so every
result is reproducible and probability calibration is irrelevant.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("tvfree_screener/out")

PRICE_FLOOR = 20.0
PRICE_CAP = 1000.0
PREV_VOLUME_MIN = 10_000.0
SIGNAL_VOLUME_MIN = 5_000.0

# Pre-2026 research constants. Do not retune these from 2026 results without
# explicitly documenting that 2026 is already a contaminated evaluation period.
MOMCROSS_RET5_MIN = 0.05
MOMCROSS_RET1_MIN = 0.03
MOMCROSS_POS60_MIN = 0.50
MOMCROSS_VOLR20_MIN = 0.80
MOMCROSS_VOLR20_MAX = 5.00
MOMCROSS_RSI14_MAX = 82.0


def summarize(x: pd.Series) -> dict:
    x = pd.to_numeric(x, errors="coerce").dropna()
    if x.empty:
        return {"n": 0}
    return {
        "n": int(len(x)),
        "mean": float(x.mean()),
        "median": float(x.median()),
        "win_rate": float((x > 0).mean()),
        "hit10_rate": float((x >= 0.10).mean()),
        "hit20_rate": float((x >= 0.20).mean()),
        "loss10_rate": float((x <= -0.10).mean()),
        "max": float(x.max()),
        "min": float(x.min()),
    }


def _features_one_batch(z: pd.DataFrame) -> pd.DataFrame:
    z = z.sort_values(["symbol", "date"]).copy()
    g = z.groupby("symbol", sort=False, group_keys=False)
    for n in [1, 3, 5, 10, 20, 40]:
        z[f"ret{n}"] = g["close"].pct_change(n, fill_method=None)
    for n in [5, 20, 40]:
        ma = g["close"].transform(lambda s: s.rolling(n, min_periods=n).mean())
        va = g["volume"].transform(lambda s: s.rolling(n, min_periods=n).mean())
        z[f"ma{n}_gap"] = z["close"] / ma - 1.0
        z[f"volr{n}"] = z["volume"] / va.replace(0, np.nan)

    delta = g["close"].diff()
    for n in [5, 14]:
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        ag = gain.groupby(z["symbol"]).transform(lambda s: s.rolling(n, min_periods=n).mean())
        al = loss.groupby(z["symbol"]).transform(lambda s: s.rolling(n, min_periods=n).mean())
        rs = ag / al.replace(0, np.nan)
        rsi = 100.0 - 100.0 / (1.0 + rs)
        rsi.loc[(al == 0) & (ag > 0)] = 100.0
        z[f"rsi{n}"] = rsi

    prev_close = g["close"].shift(1)
    tr = pd.concat(
        [(z.high - z.low), (z.high - prev_close).abs(), (z.low - prev_close).abs()], axis=1
    ).max(axis=1)
    z["atr14p"] = tr.groupby(z["symbol"]).transform(
        lambda s: s.rolling(14, min_periods=14).mean()
    ) / z["close"]

    for n in [20, 60]:
        hi = g["high"].transform(lambda s: s.rolling(n, min_periods=n).max())
        lo = g["low"].transform(lambda s: s.rolling(n, min_periods=n).min())
        z[f"pos{n}"] = (z["close"] - lo) / (hi - lo).replace(0, np.nan)

    z["prev_close"] = prev_close
    z["prev_volume"] = g["volume"].shift(1)
    z["next_open"] = g["open"].shift(-1)
    for h in [5, 10, 20, 40]:
        z[f"target{h}_no"] = g["close"].shift(-h) / z["next_open"] - 1.0
    z["target10_end"] = g["date"].shift(-10)

    for c in ["ret5", "volr20", "rsi5", "pos20", "ma20_gap"]:
        z[f"prev_{c}"] = g[c].shift(1)

    keep = [
        "date", "symbol", "open", "high", "low", "close", "volume",
        "prev_close", "prev_volume", "next_open",
        "ret1", "ret3", "ret5", "ret10", "ret20", "ret40",
        "ma5_gap", "ma20_gap", "ma40_gap", "volr5", "volr20", "volr40",
        "rsi5", "rsi14", "atr14p", "pos20", "pos60",
        "prev_ret5", "prev_volr20", "prev_rsi5", "prev_pos20", "prev_ma20_gap",
        "target5_no", "target10_no", "target20_no", "target40_no", "target10_end",
    ]
    return z[keep]


def build_candidates_lowmem(raw: pd.DataFrame, symbol_batch: int = 200) -> pd.DataFrame:
    """Feature engineering by symbol batches; retain only eligible candidate rows."""
    raw = raw.sort_values(["symbol", "date"]).copy()
    dates = raw[["date", "symbol", "close"]].copy()
    gg = dates.groupby("symbol", sort=False)
    dates["ret1_mkt"] = gg["close"].pct_change(fill_method=None)
    dates["ma20_mkt"] = gg["close"].transform(lambda s: s.rolling(20, min_periods=20).mean())
    breadth = dates.groupby("date").agg(
        breadth_ret1_pos=("ret1_mkt", lambda s: float((s > 0).mean())),
        med_ret1=("ret1_mkt", "median"),
    ).reset_index()
    dates["above_ma20"] = dates["close"] > dates["ma20_mkt"]
    b2 = dates.groupby("date")["above_ma20"].mean().rename("breadth_ma20").reset_index()
    breadth = breadth.merge(b2, on="date", how="left")

    symbols = raw["symbol"].drop_duplicates().tolist()
    parts = []
    required = ["ret40", "volr20", "rsi14", "atr14p", "pos60", "prev_ret5"]
    for i in range(0, len(symbols), symbol_batch):
        names = set(symbols[i:i + symbol_batch])
        z = _features_one_batch(raw[raw["symbol"].isin(names)])
        eligible = (
            (z["prev_volume"] >= PREV_VOLUME_MIN)
            & (z["volume"] >= SIGNAL_VOLUME_MIN)
            & (z["close"] >= PRICE_FLOOR)
            & (z["prev_close"] <= PRICE_CAP)
        )
        z = z.loc[eligible].dropna(subset=required)
        parts.append(z)
    q = pd.concat(parts, ignore_index=True)
    q = q.merge(breadth, on="date", how="left")
    return q.replace([np.inf, -np.inf], np.nan)


def add_cross_sectional_factors(q: pd.DataFrame) -> pd.DataFrame:
    q = q.copy()
    rank_cols = [
        "ret1", "ret5", "ret10", "ret20", "ret40", "volr5", "volr20", "volr40",
        "rsi5", "rsi14", "atr14p", "pos20", "pos60", "ma20_gap", "ma40_gap",
    ]
    for c in rank_cols:
        q[f"{c}_pct"] = q.groupby("date")[c].rank(pct=True, method="average")

    q["swing_core_score"] = (
        0.25 * q["ret10_pct"]
        + 0.20 * q["ret20_pct"]
        + 0.15 * q["pos60_pct"]
        + 0.20 * (1.0 - q["atr14p_pct"])
        + 0.10 * (1.0 - q["volr20_pct"])
        + 0.10 * q["ma20_gap_pct"]
    )

    q["momcross"] = (
        (q["prev_ret5"] <= 0.0)
        & (q["ret5"] >= MOMCROSS_RET5_MIN)
        & (q["ret1"] >= MOMCROSS_RET1_MIN)
        & (q["pos60"] >= MOMCROSS_POS60_MIN)
        & q["volr20"].between(MOMCROSS_VOLR20_MIN, MOMCROSS_VOLR20_MAX)
        & (q["rsi14"] <= MOMCROSS_RSI14_MAX)
    )
    q["swing_attack_score"] = q["swing_core_score"]
    return q


def select_one_per_day(q: pd.DataFrame, score: str, event_col: str | None = None) -> pd.DataFrame:
    """Select daily top candidate; block only a symbol selected on the prior trading date."""
    # Build the trading-date index before event filtering. Otherwise an Attack lane
    # with no event for several sessions would incorrectly treat its previous event
    # date as "yesterday" and apply an unintended long cooldown.
    all_dates = pd.Index(pd.to_datetime(q["date"].dropna().unique())).sort_values()
    date_idx = {pd.Timestamp(d): i for i, d in enumerate(all_dates)}
    z = q[q[event_col]].copy() if event_col else q.copy()
    out = []
    last_selected_idx: dict[str, int] = {}
    for date, day in z.sort_values(["date", score], ascending=[True, False]).groupby("date", sort=True):
        current_idx = date_idx[pd.Timestamp(date)]
        chosen = None
        for _, row in day.sort_values(score, ascending=False).iterrows():
            symbol = str(row.symbol)
            if last_selected_idx.get(symbol) == current_idx - 1:
                continue
            chosen = row
            break
        if chosen is not None:
            last_selected_idx[str(chosen.symbol)] = current_idx
            out.append(chosen)
    return pd.DataFrame(out).reset_index(drop=True)


def report_periods(sel: pd.DataFrame) -> dict:
    periods = {
        "2024H1": ("2024-01-01", "2024-06-30"),
        "2024H2": ("2024-07-01", "2024-12-31"),
        "2025H1": ("2025-01-01", "2025-06-30"),
        "2025H2_validation": ("2025-07-01", "2025-12-31"),
        "2026_JanFeb_contaminated": ("2026-01-01", "2026-02-28"),
        "2026_MarAug_contaminated": ("2026-03-01", "2026-08-31"),
    }
    out = {}
    for name, (a, b) in periods.items():
        x = sel[(sel.date >= a) & (sel.date <= b)]
        out[name] = {
            "10BD": summarize(x.get("target10_no", pd.Series(dtype=float))),
            "20BD": summarize(x.get("target20_no", pd.Series(dtype=float))),
            "40BD": summarize(x.get("target40_no", pd.Series(dtype=float))),
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default="tvfree_screener/out/tse_daily.csv")
    ap.add_argument("--symbol-batch", type=int, default=200)
    args = ap.parse_args()

    raw = pd.read_csv(args.cache, parse_dates=["date"], dtype={"symbol": str})
    for c in ["open", "high", "low", "close", "volume"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw = raw.dropna(subset=["date", "symbol", "close"])

    q = add_cross_sectional_factors(build_candidates_lowmem(raw, args.symbol_batch))
    core = select_one_per_day(q.dropna(subset=["target10_no"]), "swing_core_score")
    attack = select_one_per_day(q.dropna(subset=["target10_no"]), "swing_attack_score", "momcross")

    report = {
        "status": "research_only_no_production_writes",
        "entry": "next_session_open",
        "cooldown": "same symbol blocked only when selected on the immediately prior trading date",
        "universe": {
            "price_floor": PRICE_FLOOR,
            "prev_close_cap": PRICE_CAP,
            "prev_volume_min": PREV_VOLUME_MIN,
            "signal_volume_min": SIGNAL_VOLUME_MIN,
        },
        "notes": [
            "2026 has already been inspected in prior experiments and is not a pristine holdout.",
            "Rejected ML probability-threshold variants are intentionally not promoted here.",
            "Current Core is defensive; current Attack is a transition event and remains experimental.",
        ],
        "core": report_periods(core),
        "attack_momcross": report_periods(attack),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    core.to_csv(OUT / "v3_swing_core_picks.csv", index=False)
    attack.to_csv(OUT / "v3_swing_attack_picks.csv", index=False)
    with open(OUT / "v3_swing_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
