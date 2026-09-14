from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import no_tv_v47_dev_price_policy as dev


def gross_stats(selected: pd.DataFrame) -> dict:
    r = pd.to_numeric(selected["canonical_ret_5bd"], errors="coerce").dropna().to_numpy(float)
    if not len(r):
        return {"n": 0}
    s = np.sort(r)
    symbols = selected.loc[
        pd.to_numeric(selected["canonical_ret_5bd"], errors="coerce").notna(),
        "symbol",
    ].astype(str)
    counts = symbols.value_counts()
    return {
        "n": int(len(r)),
        "mean_pct": float(np.mean(r) * 100),
        "median_pct": float(np.median(r) * 100),
        "win_pct": float(np.mean(r > 0) * 100),
        "hit10_pct": float(np.mean(r >= 0.10) * 100),
        "hit20_pct": float(np.mean(r >= 0.20) * 100),
        "hit50_pct": float(np.mean(r >= 0.50) * 100),
        "loss10_pct": float(np.mean(r <= -0.10) * 100),
        "loss20_pct": float(np.mean(r <= -0.20) * 100),
        "top1_ex_pct": float(np.mean(s[:-1]) * 100) if len(s) > 1 else None,
        "top3_ex_pct": float(np.mean(s[:-3]) * 100) if len(s) > 3 else None,
        "unique_symbols": int(len(counts)),
        "max_symbol_share": float(counts.iloc[0] / len(r)) if len(counts) else None,
    }


def evaluate_arm(data: pd.DataFrame, arm: str, day_ix: dict[str, int]) -> tuple[pd.DataFrame, dict]:
    raw_sel = dev.prequential_select(data, arm)
    strict = dev.strict5_no_replacement(raw_sel, day_ix)
    return strict, gross_stats(strict)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nocap-dev", required=True, type=Path)
    ap.add_argument("--cap1000-dev", required=True, type=Path)
    ap.add_argument("--frozen-daily", required=True, type=Path)
    ap.add_argument("--coverage-json", required=True, type=Path)
    ap.add_argument("--preopen-spec", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    a = ap.parse_args()

    coverage = json.loads(a.coverage_json.read_text(encoding="utf-8"))
    spec = json.loads(a.preopen_spec.read_text(encoding="utf-8"))
    if spec.get("label") != "MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE":
        raise RuntimeError("missing diagnostic-only label")
    if spec.get("cost_round_trip") != 0.0:
        raise RuntimeError("midterm diagnostic must use cost 0%")
    if coverage.get("promotion_grade") is not False:
        raise RuntimeError("coverage receipt must be non-promotion")

    day_ix = dev.trading_day_index(a.frozen_daily)
    inputs = {
        "NOCAP": pd.read_parquet(a.nocap_dev),
        "CAP1000_PIT": pd.read_parquet(a.cap1000_dev),
    }

    selected = {}
    metrics = {}
    for arm, data in inputs.items():
        strict, st = evaluate_arm(data, arm, day_ix)
        selected[arm] = strict
        metrics[arm] = st

    out = a.output_dir
    out.mkdir(parents=True, exist_ok=True)
    for arm, d in selected.items():
        d.to_csv(out / f"v47_midterm_selected_{arm.lower()}.csv", index=False)

    payload = {
        "label": "MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE",
        "development_period": [dev.EVAL_START, dev.EVAL_END],
        "endpoint": "next official XTKS open -> D+5 close",
        "cost_round_trip": 0.0,
        "win_definition": "gross canonical_ret_5bd > 0",
        "policy": dev.POLICY,
        "strict_same_symbol_cooldown_sessions": 5,
        "replacement": False,
        "coverage": coverage,
        "development": metrics,
        "h1_now_opened_for_diagnostic": True,
        "h1_remains_untouched_holdout": False,
        "h2_opened": False,
        "2026_opened": False,
        "retune_same_family_after_open": False,
        "promotion_evidence": False,
        "production_writes": False,
    }
    (out / "v47_midterm_diagnostic.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
