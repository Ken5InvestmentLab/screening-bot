from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

FIT_END = "2025-06-30"
VALID_START = "2025-07-01"
ATR_QUANTILE = 0.90


def load_selected(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path)
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d["perf_5bd"] = pd.to_numeric(d["perf_5bd"], errors="coerce")
    d["market_median_atr"] = pd.to_numeric(d["market_median_atr"], errors="coerce")
    return d[d["date"].notna() & d["perf_5bd"].notna() & d["market_median_atr"].notna()].copy()


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


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Reproduce the research-only pre-2026 Consensus ATR regime guard."
    )
    ap.add_argument("--v43-min95", required=True, type=Path)
    ap.add_argument("--v42-min95", required=True, type=Path)
    ap.add_argument("--output", type=Path)
    a = ap.parse_args()

    y2025 = load_selected(a.v43_min95)
    y2026 = load_selected(a.v42_min95)

    fit = y2025[y2025["date"] <= FIT_END].copy()
    valid = y2025[y2025["date"] >= VALID_START].copy()
    if fit.empty or valid.empty:
        raise RuntimeError("expected both Jan-Jun fit and Jul-Dec validation rows")

    threshold = float(fit["market_median_atr"].quantile(ATR_QUANTILE))

    result = {
        "scope": "research-only selected-artifact audit; no production writes",
        "rule": "allow fixed-min95 Consensus only when market_median_atr <= frozen pre-2026 q90",
        "fit_end": FIT_END,
        "validation_start": VALID_START,
        "atr_quantile": ATR_QUANTILE,
        "threshold": threshold,
        "fit_baseline": stats(fit),
        "fit_gated": stats(fit[fit["market_median_atr"] <= threshold]),
        "validation_baseline": stats(valid),
        "validation_gated": stats(valid[valid["market_median_atr"] <= threshold]),
        "descriptive_2026_baseline": stats(y2026),
        "descriptive_2026_gated": stats(y2026[y2026["market_median_atr"] <= threshold]),
        "descriptive_2026_min_market_median_atr": float(y2026["market_median_atr"].min()),
        "production_writes": False,
    }

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
