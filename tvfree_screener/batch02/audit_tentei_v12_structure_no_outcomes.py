from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from tvfree_screener.batch02.eval_tentei_inspired_4h_v12 import add_v12_state, build_bins

PERIODS = {
    "H1": ("2025-03-01", "2025-06-30"),
    "H2_STRUCTURE_ONLY": ("2025-07-01", "2025-12-31"),
    "Y2025_STRUCTURE_ONLY": ("2025-01-01", "2025-12-31"),
}


def audit(pattern: str) -> dict:
    bins = add_v12_state(build_bins(pattern, max_date="2025-12-31"))
    bins["date_s"] = bins["date"].astype(str)
    bins["month"] = bins["date_s"].str[:7]
    bins["prev_signal_same_symbol"] = bins.groupby("symbol", sort=False)["signal"].shift(1).fillna(False).astype(bool)
    bins["prev_emergency_same_symbol"] = bins.groupby("symbol", sort=False)["emergency_reversal"].shift(1).fillna(False).astype(bool)

    result = {
        "audit_id": "TENTEI-V12-STRUCTURE-NO-OUTCOMES-20260913",
        "outcome_values_opened": False,
        "2026_strategy_outcomes_opened": False,
        "prior_daily_gate_applied": False,
        "cooldown_applied": False,
        "periods": {},
    }
    for name, (start, end) in PERIODS.items():
        frame = bins[(bins["date_s"] >= start) & (bins["date_s"] <= end)].copy()
        sig = frame[frame["signal"]].copy()
        path_count = sig[["rsi_recovery", "trend_flip", "emergency_reversal"]].sum(axis=1)
        combos = (
            sig[["rsi_recovery", "trend_flip", "emergency_reversal"]]
            .astype(int).astype(str).agg("".join, axis=1).value_counts().to_dict()
        )
        monthly = []
        for month, group in frame.groupby("month", sort=True):
            sg = group[group["signal"]]
            monthly.append({
                "month": month,
                "complete_bins": int(len(group)),
                "signals": int(len(sg)),
                "signal_rate_pct": float(100.0 * len(sg) / len(group)) if len(group) else None,
                "rsi_recovery": int(sg["rsi_recovery"].sum()),
                "trend_flip": int(sg["trend_flip"].sum()),
                "emergency_reversal": int(sg["emergency_reversal"].sum()),
            })
        result["periods"][name] = {
            "complete_bins": int(len(frame)),
            "signal_rows": int(len(sig)),
            "signal_rate_pct": float(100.0 * len(sig) / len(frame)) if len(frame) else None,
            "symbols": int(sig["symbol"].nunique()),
            "dates": int(sig["date_s"].nunique()),
            "am": int(sig["bin_name"].eq("AM_09_13").sum()),
            "pm": int(sig["bin_name"].eq("PM_13_CLOSE").sum()),
            "rsi_recovery": int(sig["rsi_recovery"].sum()),
            "trend_flip": int(sig["trend_flip"].sum()),
            "emergency_reversal": int(sig["emergency_reversal"].sum()),
            "single_path": int(path_count.eq(1).sum()),
            "multi_path": int(path_count.ge(2).sum()),
            "path_combo": {str(k): int(v) for k, v in combos.items()},
            "previous_complete_bin_also_signal": int(sig["prev_signal_same_symbol"].sum()),
            "previous_complete_bin_also_signal_pct": float(100.0 * sig["prev_signal_same_symbol"].mean()) if len(sig) else None,
            "emergency_with_previous_complete_bin_emergency": int((sig["emergency_reversal"] & sig["prev_emergency_same_symbol"]).sum()),
            "monthly": monthly,
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-glob", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = audit(args.raw_glob)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
