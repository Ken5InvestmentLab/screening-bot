from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

FIT_END = "2025-06-30"
VALID_START = "2025-07-01"
ATR_QUANTILE = 0.90


def load_selected(path: Path, label: str) -> pd.DataFrame:
    d = pd.read_csv(path)
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d["perf_5bd"] = pd.to_numeric(d["perf_5bd"], errors="coerce")
    d["market_median_atr"] = pd.to_numeric(d["market_median_atr"], errors="coerce")
    d = d[d["date"].notna() & d["perf_5bd"].notna() & d["market_median_atr"].notna()].copy()
    d["cohort"] = label
    return d.sort_values(["date", "session"]).reset_index(drop=True)


def stats(d: pd.DataFrame) -> dict:
    r = d["perf_5bd"].to_numpy(float)
    if len(r) == 0:
        return {"n": 0}
    s = np.sort(r)
    return {
        "n": int(len(r)),
        "mean_pct": float(np.mean(r) * 100),
        "median_pct": float(np.median(r) * 100),
        "win_pct": float(np.mean(r > 0) * 100),
        "hit10_pct": float(np.mean(r >= 0.10) * 100),
        "hit20_pct": float(np.mean(r >= 0.20) * 100),
        "loss10_pct": float(np.mean(r <= -0.10) * 100),
        "loss20_pct": float(np.mean(r <= -0.20) * 100),
        "top3_ex_mean_pct": float(np.mean(s[:-3]) * 100) if len(s) > 3 else None,
    }


def causal_dynamic_gate(d: pd.DataFrame, window: int | None, min_history: int = 30) -> pd.DataFrame:
    vals: list[float] = []
    keep: list[bool] = []
    thresholds: list[float] = []
    for row in d.itertuples(index=False):
        hist = vals[-window:] if window else vals
        if len(hist) < min_history:
            threshold = np.nan
            allowed = True
        else:
            threshold = float(np.quantile(np.asarray(hist, float), ATR_QUANTILE))
            allowed = float(row.market_median_atr) <= threshold
        thresholds.append(threshold)
        keep.append(allowed)
        vals.append(float(row.market_median_atr))
    out = d.copy()
    out["dynamic_atr_cap"] = thresholds
    out["dynamic_keep"] = keep
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Reproduce frozen-vs-adaptive Consensus ATR regime-gate research."
    )
    ap.add_argument("--v43-min95", required=True, type=Path)
    ap.add_argument("--v42-min95", required=True, type=Path)
    ap.add_argument("--output", type=Path)
    a = ap.parse_args()

    y2025 = load_selected(a.v43_min95, "2025")
    y2026 = load_selected(a.v42_min95, "2026")
    fit = y2025[y2025["date"] <= FIT_END].copy()
    valid = y2025[y2025["date"] >= VALID_START].copy()
    if fit.empty or valid.empty:
        raise RuntimeError("expected both Jan-Jun fit and Jul-Dec validation rows")

    frozen_cap = float(fit["market_median_atr"].quantile(ATR_QUANTILE))

    combined = pd.concat([y2025, y2026], ignore_index=True).sort_values(["date", "session"])
    adaptive = {}
    for name, window in {
        "expanding": None,
        "rolling_30": 30,
        "rolling_60": 60,
        "rolling_90": 90,
        "rolling_120": 120,
    }.items():
        x = causal_dynamic_gate(combined, window=window)
        t = x[x["cohort"] == "2026"].copy()
        kept = t[t["dynamic_keep"]].copy()
        adaptive[name] = {
            "window": window,
            "2026": stats(kept),
            "threshold_min": float(t["dynamic_atr_cap"].min()),
            "threshold_max": float(t["dynamic_atr_cap"].max()),
        }

    sensitivity = {}
    for cap in [2.80, 2.85, 2.86, 2.87, 2.90, 2.95, 3.00, 3.05]:
        sensitivity[f"{cap:.2f}"] = {
            "validation": stats(valid[valid["market_median_atr"] <= cap]),
            "descriptive_2026": stats(y2026[y2026["market_median_atr"] <= cap]),
        }

    neighboring_quantiles = {}
    for q in [0.85, 0.90, 0.95]:
        cap = float(fit["market_median_atr"].quantile(q))
        neighboring_quantiles[f"q{int(q*100)}"] = {
            "cap": cap,
            "validation": stats(valid[valid["market_median_atr"] <= cap]),
            "descriptive_2026": stats(y2026[y2026["market_median_atr"] <= cap]),
        }

    result = {
        "scope": "research-only selected-artifact audit; no production writes",
        "frozen_rule": "allow fixed-min95 Consensus only when market_median_atr <= frozen pre-deployment q90",
        "fit_end": FIT_END,
        "validation_start": VALID_START,
        "atr_quantile": ATR_QUANTILE,
        "frozen_cap": frozen_cap,
        "fit_baseline": stats(fit),
        "fit_frozen_gated": stats(fit[fit["market_median_atr"] <= frozen_cap]),
        "validation_baseline": stats(valid),
        "validation_frozen_gated": stats(valid[valid["market_median_atr"] <= frozen_cap]),
        "descriptive_2026_baseline": stats(y2026),
        "descriptive_2026_frozen_gated": stats(y2026[y2026["market_median_atr"] <= frozen_cap]),
        "adaptive_q90_audit": adaptive,
        "fixed_cap_sensitivity": sensitivity,
        "neighboring_quantiles": neighboring_quantiles,
        "decision": "Do not adapt the ATR cap online. Treat it as a model-frozen OOD circuit breaker.",
        "production_writes": False,
    }

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
