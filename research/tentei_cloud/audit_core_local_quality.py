#!/usr/bin/env python3
"""Local-quality audit for the fixed reconstructed 4H Core rule.

Research-only. No production writes.

Purpose:
Find whether a small set of candidate-local, signal-time features can improve the
already-fixed reconstructed Core without using broad-market gates and without
overlapping the separate V12/V15 event-representation work.

Fixed Core:
- previous daily close <= 1,000 JPY
- previous daily volume >= 10,000 shares
- candidate session volume >= 5,000 shares
- RSI(12) < 45
- previous three completed reconstructed session closes descending
- current close > Bollinger(20) midline
- ATR(14)/close < 5%
- 5-business-day same-symbol cooldown

Preregistered local features only:
- rsi12
- bb_reclaim = close / BB20_mid - 1
- atr14_pct
- session_prevday_vol_ratio = session volume / previous daily volume
- ema75_gap = close / EMA75 - 1

Selection protocol:
1) Build the fixed Core pool.
2) Use DEV only: 2024-11-01..2025-06-30.
3) Split DEV into DEV_A (2024-11-01..2025-02-28) and DEV_B
   (2025-03-01..2025-06-30).
4) For each feature, fit ONE threshold: the pooled DEV median of the feature
   values, without outcomes.
5) Compare LOW vs HIGH in both DEV halves.
6) A side qualifies only if, in BOTH DEV halves:
   - n >= 15,
   - its mean 5BD return is greater than the opposite side,
   - its median is no worse than the opposite side,
   - its <=-10% rate is no worse than the opposite side.
7) If multiple features qualify, choose the feature/side with the largest
   worst-half mean advantage. Feature name is the deterministic tie-break.
8) Freeze that single rule. Then report 2025H2 and 2026 only.
No secondary threshold sweep and no combinations are allowed.

Important:
2025H2/2026 have been inspected in prior research at aggregate level, so any
post-DEV reporting remains retrospective causal evidence rather than pristine OOS.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from reconstruct_4h_from_1h import load, aggregate, enrich_session, add_daily_context, cooldown
from mtf_monster_model import metrics

TARGET = 0.075

DEV_A = ("DEV_A", "2024-11-01", "2025-02-28")
DEV_B = ("DEV_B", "2025-03-01", "2025-06-30")
REPORT_PERIODS = [
    ("DEV", "2024-11-01", "2025-06-30"),
    ("2025H2", "2025-07-01", "2025-12-31"),
    ("2026_YTD", "2026-01-01", "2026-08-31"),
    ("2026_01_02", "2026-01-01", "2026-02-28"),
    ("2026_03_04", "2026-03-01", "2026-04-30"),
    ("2026_05_06", "2026-05-01", "2026-06-30"),
    ("2026_07_08", "2026-07-01", "2026-08-31"),
]

FEATURES = [
    "rsi12",
    "bb_reclaim",
    "atr14_pct",
    "session_prevday_vol_ratio",
    "ema75_gap",
]


def make_core_pool(raw: pd.DataFrame) -> pd.DataFrame:
    s = aggregate(raw, 780)
    s = enrich_session(s)
    s, dates = add_daily_context(s, raw)

    eligible = s[
        (s["prev_daily_close"] <= 1000)
        & (s["prev_daily_volume"] >= 10000)
        & (s["volume"] >= 5000)
    ].copy()

    core_gate = (
        (eligible["rsi12"] < 45)
        & eligible["pre_down3"].fillna(False)
        & (eligible["close"] > eligible["bb_mid"])
        & (eligible["atr14_pct"] < 0.05)
    )
    q = cooldown(eligible[core_gate].copy(), dates, 5)
    q = q[q["ret5bd"].notna()].copy()

    q["bb_reclaim"] = q["close"] / q["bb_mid"].replace(0, np.nan) - 1.0
    q["session_prevday_vol_ratio"] = q["volume"] / q["prev_daily_volume"].replace(0, np.nan)
    q["ema75_gap"] = q["close"] / q["ema75"].replace(0, np.nan) - 1.0
    q["date_dt"] = pd.to_datetime(q["date"], errors="coerce")
    return q


def period_mask(x: pd.DataFrame, start: str, end: str) -> pd.Series:
    return (x["date_dt"] >= pd.Timestamp(start)) & (x["date_dt"] <= pd.Timestamp(end))


def simple_metrics(q: pd.DataFrame) -> dict:
    r = q["ret5bd"].dropna().astype(float)
    if r.empty:
        return {"n": 0, "mean": None, "median": None, "win": None, "le10": None}
    return {
        "n": int(len(r)),
        "mean": float(r.mean()),
        "median": float(r.median()),
        "win": float((r > 0).mean()),
        "le10": float((r <= -0.10).mean()),
    }


def compare_feature(x: pd.DataFrame, feature: str, threshold: float, pname: str, start: str, end: str) -> list[dict]:
    pm = period_mask(x, start, end) & x[feature].notna()
    rows = []
    for side, sm in [
        ("LOW", x[feature] <= threshold),
        ("HIGH", x[feature] > threshold),
    ]:
        q = x[pm & sm].copy()
        m = simple_metrics(q)
        rows.append({
            "feature": feature,
            "threshold": float(threshold),
            "period": pname,
            "side": side,
            **m,
        })
    return rows


def qualifies(pair_a: dict, pair_b: dict, side: str) -> tuple[bool, dict]:
    other = "HIGH" if side == "LOW" else "LOW"
    a = pair_a[side]
    ao = pair_a[other]
    b = pair_b[side]
    bo = pair_b[other]

    checks = {
        "a_n": a["n"] >= 15,
        "b_n": b["n"] >= 15,
        "a_mean": a["mean"] is not None and ao["mean"] is not None and a["mean"] > ao["mean"],
        "b_mean": b["mean"] is not None and bo["mean"] is not None and b["mean"] > bo["mean"],
        "a_median": a["median"] is not None and ao["median"] is not None and a["median"] >= ao["median"],
        "b_median": b["median"] is not None and bo["median"] is not None and b["median"] >= bo["median"],
        "a_le10": a["le10"] is not None and ao["le10"] is not None and a["le10"] <= ao["le10"],
        "b_le10": b["le10"] is not None and bo["le10"] is not None and b["le10"] <= bo["le10"],
    }
    adv_a = (a["mean"] - ao["mean"]) if a["mean"] is not None and ao["mean"] is not None else None
    adv_b = (b["mean"] - bo["mean"]) if b["mean"] is not None and bo["mean"] is not None else None
    return all(checks.values()), {
        "checks": checks,
        "mean_advantage_dev_a": adv_a,
        "mean_advantage_dev_b": adv_b,
        "worst_half_mean_advantage": min(adv_a, adv_b) if adv_a is not None and adv_b is not None else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", action="append", required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()

    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)

    raw = load(a.inputs)
    x = make_core_pool(raw)

    dev_mask = period_mask(x, "2024-11-01", "2025-06-30")
    thresholds = {}
    for f in FEATURES:
        vals = x.loc[dev_mask, f].replace([np.inf, -np.inf], np.nan).dropna().astype(float)
        if vals.empty:
            raise RuntimeError(f"no DEV values for {f}")
        thresholds[f] = float(vals.median())

    discovery_rows = []
    candidates = []
    for f in FEATURES:
        t = thresholds[f]
        for p in [DEV_A, DEV_B]:
            discovery_rows.extend(compare_feature(x, f, t, *p))

        pa_rows = [r for r in discovery_rows if r["feature"] == f and r["period"] == DEV_A[0]]
        pb_rows = [r for r in discovery_rows if r["feature"] == f and r["period"] == DEV_B[0]]
        pa = {r["side"]: r for r in pa_rows}
        pb = {r["side"]: r for r in pb_rows}

        for side in ["LOW", "HIGH"]:
            ok, detail = qualifies(pa, pb, side)
            candidates.append({
                "feature": f,
                "threshold": t,
                "side": side,
                "qualifies": bool(ok),
                **detail,
            })

    discovery = pd.DataFrame(discovery_rows)
    discovery.to_csv(out / "core_local_quality_discovery.csv", index=False)

    cand_df = pd.DataFrame(candidates)
    cand_df.to_csv(out / "core_local_quality_candidates.csv", index=False)

    eligible = [c for c in candidates if c["qualifies"]]
    eligible = sorted(
        eligible,
        key=lambda z: (-z["worst_half_mean_advantage"], z["feature"], z["side"]),
    )

    freeze = None
    if eligible:
        freeze = {
            "feature": eligible[0]["feature"],
            "threshold": float(eligible[0]["threshold"]),
            "side": eligible[0]["side"],
            "selection_basis": "largest worst-half DEV mean advantage among preregistered qualifying single-feature median splits",
            "worst_half_mean_advantage": float(eligible[0]["worst_half_mean_advantage"]),
        }

    report_rows = []
    selected_export = pd.DataFrame()
    for pname, start, end in REPORT_PERIODS:
        pm = period_mask(x, start, end)
        base = x[pm].copy()
        b = metrics("CORE_LOCAL_QUALITY", "BASE", pname, base, TARGET)
        b["selection_feature"] = None
        b["selection_side"] = None
        b["selection_threshold"] = None
        report_rows.append(b)

        if freeze is not None:
            f = freeze["feature"]
            t = freeze["threshold"]
            sm = (x[f] <= t) if freeze["side"] == "LOW" else (x[f] > t)
            q = x[pm & sm.fillna(False)].copy()
            m = metrics("CORE_LOCAL_QUALITY", "FROZEN_SINGLE_FEATURE", pname, q, TARGET)
            m["selection_feature"] = f
            m["selection_side"] = freeze["side"]
            m["selection_threshold"] = t
            report_rows.append(m)

    report = pd.DataFrame(report_rows)
    report.to_csv(out / "core_local_quality_report.csv", index=False)

    if freeze is not None:
        f = freeze["feature"]
        t = freeze["threshold"]
        sm = (x[f] <= t) if freeze["side"] == "LOW" else (x[f] > t)
        selected_export = x[sm.fillna(False)].copy()
        keep = [
            "date", "session", "session_time", "symbol", "open", "high", "low", "close", "volume",
            "ret5bd", "target_date", "rsi12", "bb_reclaim", "atr14_pct",
            "session_prevday_vol_ratio", "ema75_gap",
        ]
        selected_export[[k for k in keep if k in selected_export.columns]].to_csv(
            out / "core_local_quality_selected.csv", index=False
        )

    meta = {
        "raw_start": str(raw["date"].min()),
        "raw_end": str(raw["date"].max()),
        "core_pool_n": int(len(x)),
        "features": FEATURES,
        "threshold_policy": "pooled DEV signal-time median only; no outcome-fitted threshold",
        "dev_a": DEV_A,
        "dev_b": DEV_B,
        "qualification_rule": (
            "same side must have n>=15, higher mean, no-worse median, and no-worse <=-10% rate "
            "than opposite side in BOTH DEV halves"
        ),
        "tie_break": "largest worst-half DEV mean advantage, then feature name, then side",
        "freeze": freeze,
        "reporting_status": "RETROSPECTIVE_CAUSAL_EVIDENCE; 2025H2/2026 previously inspected at aggregate level",
        "overlap_avoidance": "no gap-up continuation features; no V12/V15 event-representation features; no broad market regime gates",
        "production_writes": False,
    }
    (out / "core_local_quality_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print("\nDISCOVERY")
    print(discovery.to_string(index=False))
    print("\nCANDIDATES")
    print(cand_df.to_string(index=False))
    print("\nREPORT")
    print(report.to_string(index=False))


if __name__ == "__main__":
    main()
