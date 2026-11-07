#!/usr/bin/env python3
"""V10 conditional kNN Quality for V7 extreme-Tail candidates (TEST ONLY).

Materially different from V9:
- no outcome classifier;
- current Tail candidates are compared only with previously completed causal
  Tail candidates;
- robustly standardized signal-time features define similarity;
- neighbor future returns form the Quality estimate.

Protocol remains blind/staged:
2023 warmup -> 2024 development -> top2 -> 2025 validation -> 2026 only
after a pass. No production writes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import run as base
import v9_conditional_quality_research as v9

OUT = Path("tvfree_screener/out")
MIN_HISTORY = 120

DEV = {
    "2024H1": ("2024-01-01", "2024-06-30"),
    "2024H2": ("2024-07-01", "2024-12-31"),
}
VAL = {
    "2025H1": ("2025-01-01", "2025-06-30"),
    "2025H2": ("2025-07-01", "2025-12-31"),
}

DIST_FEATURES = [
    "ret5", "ret20", "ma20_gap", "volr20",
    "rsi14", "atr14p",
    "body_pct", "lower_wick", "upper_wick", "range_pct", "gap",
    "pos20", "dd20", "bounce20",
    "bbpct", "bbwidth", "volz20", "log_dv",
    "med_ret5", "breadth_ma20",
]

VARIANTS = {
    "knn20_rank": {"k": 20, "min_ret": None},
    "knn20_pos": {"k": 20, "min_ret": 0.0},
    "knn40_rank": {"k": 40, "min_ret": None},
    "knn40_pos": {"k": 40, "min_ret": 0.0},
}


def robust_matrix(hist: pd.DataFrame, cur: pd.DataFrame):
    h = hist[DIST_FEATURES].replace([np.inf, -np.inf], np.nan).copy()
    c = cur[DIST_FEATURES].replace([np.inf, -np.inf], np.nan).copy()

    med = h.median(numeric_only=True)
    q1 = h.quantile(0.25, numeric_only=True)
    q3 = h.quantile(0.75, numeric_only=True)
    scale = (q3 - q1).replace(0, np.nan).fillna(1.0)

    h = h.fillna(med).fillna(0.0)
    c = c.fillna(med).fillna(0.0)
    hs = ((h - med) / scale).clip(-5, 5).to_numpy(dtype=float)
    cs = ((c - med) / scale).clip(-5, 5).to_numpy(dtype=float)
    return hs, cs


def attach_knn(
    current: pd.DataFrame,
    history: pd.DataFrame,
    month_start: pd.Timestamp,
) -> pd.DataFrame:
    hist = history[
        (history["target_end_date"] < month_start)
        & history["target5_no"].notna()
    ].copy()
    cur = current.copy()

    if len(hist) < MIN_HISTORY or cur.empty:
        return pd.DataFrame()

    hs, cs = robust_matrix(hist, cur)
    y = (
        pd.to_numeric(hist["target5_no"], errors="coerce")
        .clip(-0.50, 1.50)
        .to_numpy(dtype=float)
    )
    hit20 = (y >= 0.20).astype(float)
    loss10 = (y <= -0.10).astype(float)

    out = cur.copy()
    for k in [20, 40]:
        kk = min(k, len(hist))
        exp_ret = []
        hit = []
        loss = []
        avg_dist = []

        for row in cs:
            # Mean squared robust distance; no future/current outcomes involved.
            dist = np.mean((hs - row) ** 2, axis=1)
            idx = np.argpartition(dist, kk - 1)[:kk]
            d = dist[idx]
            w = 1.0 / (0.25 + np.sqrt(np.maximum(d, 0)))
            w = w / w.sum()

            exp_ret.append(float(np.sum(w * y[idx])))
            hit.append(float(np.sum(w * hit20[idx])))
            loss.append(float(np.sum(w * loss10[idx])))
            avg_dist.append(float(np.sum(w * np.sqrt(np.maximum(d, 0)))))

        out[f"knn{k}_ret"] = exp_ret
        out[f"knn{k}_hit20"] = hit
        out[f"knn{k}_loss10"] = loss
        out[f"knn{k}_dist"] = avg_dist

    out["knn_hist_n"] = len(hist)
    return out


def select_variant(
    scored: pd.DataFrame,
    name: str,
    trading_dates: pd.Index,
) -> pd.DataFrame:
    spec = VARIANTS[name]
    k = spec["k"]
    z = scored.copy()
    if spec["min_ret"] is not None:
        z = z[z[f"knn{k}_ret"] > spec["min_ret"]].copy()
    if z.empty:
        return z

    # Reuse the same 1-day same-symbol cooldown semantics, but rank by neighbor
    # expected return first and original Tail score second.
    date_idx = {
        pd.Timestamp(d): i
        for i, d in enumerate(pd.Index(trading_dates).sort_values())
    }
    rows = []
    last_symbol = None
    last_idx = None

    for date, day in z.groupby("date", sort=True):
        idx = date_idx[pd.Timestamp(date)]
        day = day.sort_values(
            [f"knn{k}_ret", "tail_cdf", "tail_p"],
            ascending=False,
        )
        chosen = None
        for _, row in day.iterrows():
            if (
                last_idx is not None
                and idx == last_idx + 1
                and str(row["symbol"]) == last_symbol
            ):
                continue
            chosen = row
            break
        if chosen is not None:
            rows.append(chosen)
            last_symbol = str(chosen["symbol"])
            last_idx = idx

    return pd.DataFrame(rows).reset_index(drop=True)


def score_period(
    q: pd.DataFrame,
    history_tail: pd.DataFrame,
    start: str,
    end: str,
):
    parts = []
    hist = history_tail.copy()

    for month in pd.period_range(
        pd.Timestamp(start).to_period("M"),
        pd.Timestamp(end).to_period("M"),
        freq="M",
    ):
        cur = v9.score_tail_month(q, month)
        if cur.empty:
            continue
        qcur = attach_knn(cur, hist, month.start_time)
        print(
            f"knn {month}: tail={len(cur)} scored={len(qcur)} hist={len(hist)}"
        )
        if not qcur.empty:
            parts.append(qcur)
        hist = pd.concat([hist, cur], ignore_index=True)

    scored = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    return scored, hist


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(OUT / "tse_daily.csv"))
    args = ap.parse_args()

    raw = pd.read_csv(args.cache, parse_dates=["date"], dtype={"symbol": str})
    for c in ["open", "high", "low", "close", "volume"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw = raw.dropna(
        subset=["date", "symbol", "open", "high", "low", "close", "volume"]
    ).sort_values(["symbol", "date"]).reset_index(drop=True)

    trading_dates = pd.Index(pd.to_datetime(raw["date"].unique())).sort_values()
    q = v9.prepare(raw)

    warm_tail = v9.generate_tail_pool(q, "2023-01-01", "2023-12-31")
    if warm_tail.empty:
        raise RuntimeError("V10 warmup tail pool is empty")

    dev_scored, tail_2024 = score_period(
        q, warm_tail, "2024-01-01", "2024-12-31"
    )
    if dev_scored.empty:
        raise RuntimeError("V10 generated no 2024 kNN scores")

    candidates = {}
    for name in VARIANTS:
        picks = select_variant(dev_scored, name, trading_dates)
        dev = v9.period_stats(picks, DEV)
        pool = v9.summarize(
            picks[
                (picks["date"] >= "2024-01-01")
                & (picks["date"] <= "2024-12-31")
            ]["target5_no"]
        )
        candidates[name] = {
            "spec": VARIANTS[name],
            "development_2024": dev,
            "development_2024_pooled": pool,
            "development_utility": v9.development_utility(dev, pool),
        }

    ranked = sorted(
        [
            (v["development_utility"], name)
            for name, v in candidates.items()
            if v["development_utility"] is not None
        ],
        reverse=True,
    )
    opened = [name for _, name in ranked[:2]]
    accepted = []
    pre2026 = None
    tail_2025 = None

    if opened:
        val_scored, tail_2025 = score_period(
            q, tail_2024, "2025-01-01", "2025-12-31"
        )
        pre2026 = pd.concat([dev_scored, val_scored], ignore_index=True)

        for name in opened:
            picks = select_variant(pre2026, name, trading_dates)
            val = v9.period_stats(picks, VAL)
            pool = v9.summarize(
                picks[
                    (picks["date"] >= "2025-01-01")
                    & (picks["date"] <= "2025-12-31")
                ]["target5_no"]
            )
            candidates[name]["validation_2025"] = val
            candidates[name]["validation_2025_pooled"] = pool
            candidates[name]["validation_pass"] = v9.validation_pass(val, pool)
            if candidates[name]["validation_pass"]:
                accepted.append((
                    min(val["2025H1"]["mean"], val["2025H2"]["mean"]),
                    pool["mean"],
                    name,
                ))

    locked = sorted(accepted, reverse=True)[0][2] if accepted else None
    fixed = None
    monthly = None

    if locked:
        future, _ = score_period(q, tail_2025, "2026-01-01", "2026-08-31")
        all_scored = pd.concat([pre2026, future], ignore_index=True)
        picks = select_variant(all_scored, locked, trading_dates)
        z = picks[
            (picks["date"] >= "2026-03-01")
            & (picks["date"] <= "2026-08-31")
        ].copy()
        fixed = v9.summarize(z["target5_no"])
        monthly = {
            str(month): v9.summarize(group["target5_no"])
            for month, group in z.groupby(z["date"].dt.to_period("M"))
        }
        z.to_csv(OUT / "v10_knn_quality_locked_2026.csv", index=False)

    report = {
        "status": "research_only_no_production_writes",
        "component": "V7 extreme Tail + V10 conditional historical kNN Quality",
        "tail_gate": v9.TAIL_GATE,
        "distance_features": DIST_FEATURES,
        "entry": "next_session_open_to_5BD_close",
        "protocol": (
            "2023 Tail warmup -> 2024 development -> top2 -> "
            "2025 validation -> 2026 only after pass"
        ),
        "warmup_tail_candidates_2023": int(len(warm_tail)),
        "development_ranked": [
            {"name": name, "utility": float(score)}
            for score, name in ranked
        ],
        "validation_opened": opened,
        "locked_candidate": locked,
        "candidates": {},
    }

    for name, v in candidates.items():
        item = {
            "spec": v["spec"],
            "development_2024": v["development_2024"],
            "development_2024_pooled": v["development_2024_pooled"],
            "development_utility": v["development_utility"],
        }
        if name in opened:
            item.update({
                "validation_2025": v["validation_2025"],
                "validation_2025_pooled": v["validation_2025_pooled"],
                "validation_pass": v["validation_pass"],
            })
        if name == locked:
            item.update({
                "fixed_2026_MarAug": fixed,
                "fixed_2026_monthly": monthly,
            })
        report["candidates"][name] = item

    with open(OUT / "v10_knn_quality_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
