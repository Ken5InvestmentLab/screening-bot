#!/usr/bin/env python3
"""Build a unified TEST-ONLY comparison from reproducible research reports.

Consumes reports already produced in tvfree_screener/out. Missing horizons/results
remain missing; this script never invents values. Historical Stable★6 and old
Short V3 references are clearly labelled as non-reproducible external reference
numbers rather than outputs of the TradingView-free runners.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

OUT = Path("tvfree_screener/out")
SHORT_REPORT = OUT / "v3_short_reconstruction_report.json"
SWING_REPORT = OUT / "v3_swing_v2_report.json"


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def row(lane: str, period: str, horizon: str, stats: dict[str, Any] | None,
        evidence: str, reproducible: bool | None) -> dict[str, Any]:
    s = stats or {}
    return {
        "lane": lane,
        "period": period,
        "horizon": horizon,
        "n": s.get("n"),
        "mean": s.get("mean"),
        "median": s.get("median"),
        "win_rate": s.get("win_rate"),
        "hit5_rate": s.get("hit5_rate"),
        "hit10_rate": s.get("hit10_rate"),
        "hit20_rate": s.get("hit20_rate"),
        "loss10_rate": s.get("loss10_rate"),
        "max": s.get("max"),
        "min": s.get("min"),
        "evidence": evidence,
        "reproducible_runner": reproducible,
    }


def historical_rows() -> list[dict[str, Any]]:
    rows = []
    stable5 = {
        "n": 55, "mean": 0.0659, "median": 0.0150, "win_rate": 0.564,
        "hit10_rate": 0.182, "loss10_rate": 0.109,
    }
    stable10 = {"mean": 0.0764, "win_rate": 0.574}
    old_short5 = {
        "n": 29, "mean": 0.0542, "median": 0.0206, "win_rate": 0.655,
        "hit10_rate": 0.138, "loss10_rate": 0.069,
    }
    rows.append(row(
        "Stable★6 historical reference", "2026_MarAug", "5BD", stable5,
        "historical reference supplied by existing system; not reproduced by this runner", False,
    ))
    rows.append(row(
        "Stable★6 historical reference", "2026_MarAug", "10BD", stable10,
        "historical reference supplied by existing system; incomplete fields remain blank", False,
    ))
    rows.append(row(
        "Old Short V3 historical reference", "2026_MarAug", "5BD", old_short5,
        "historical non-reproducible reference; exact old parameters were never committed", False,
    ))
    return rows


def add_short(rows: list[dict[str, Any]], report: dict[str, Any] | None) -> None:
    if report is None:
        rows.append(row(
            "Short Core", "report_missing", "5BD", None,
            "v3_short_reconstruction_report.json not available in this run", None,
        ))
        return
    mapping = {
        "2025H1_development": "2025H1_development",
        "2025H2_validation": "2025H2_validation",
        "2026_MarAug_contaminated_fixed": "2026_MarAug_contaminated_fixed",
    }
    for key, label in mapping.items():
        rows.append(row(
            "Short Core", label, "5BD", report.get("core", {}).get("periods", {}).get(key),
            "v3_short_reconstruction.py output", True,
        ))
        rows.append(row(
            "Short defensive market gate", label, "5BD",
            report.get("defensive_market_gate", {}).get("periods", {}).get(key),
            "v3_short_reconstruction.py output; supporting lane only", True,
        ))
    rows.append(row(
        "Short Attack", "current_decision", "5BD", None,
        "none/unaccepted after pre-2026 validation failures", True,
    ))


def add_swing(rows: list[dict[str, Any]], report: dict[str, Any] | None) -> None:
    if report is None:
        rows.append(row(
            "Swing S", "report_missing", "10BD", None,
            "v3_swing_v2_report.json not available in this run", None,
        ))
        return
    periods = report.get("periods", {})
    for period_name, horizons in periods.items():
        for horizon in ["5BD", "10BD", "20BD", "40BD"]:
            rows.append(row(
                "Swing S", period_name, horizon, horizons.get(horizon),
                "v3_swing_v2.py frozen runner output", True,
            ))
    rows.append(row(
        "Swing A", "current_decision", "10BD", None,
        "none/unaccepted; no pre-2026-stable Attack candidate", True,
    ))


def main() -> None:
    short = load_json(SHORT_REPORT)
    swing = load_json(SWING_REPORT)
    rows = historical_rows()
    add_short(rows, short)
    add_swing(rows, swing)

    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "v3_unified_comparison.csv", index=False)

    report = {
        "status": "research_only_no_production_writes",
        "principle": "missing metrics remain missing; historical references are never presented as reproduced runner outputs",
        "inputs": {
            "short_report_present": short is not None,
            "swing_report_present": swing is not None,
        },
        "rows": rows,
        "monthly": {
            "short_core_2026_MarAug": (short or {}).get("core", {}).get("2026_MarAug_monthly"),
            "short_defensive_2026_MarAug": (short or {}).get("defensive_market_gate", {}).get("2026_MarAug_monthly"),
            "swing_s_2026_MarAug_10BD": (swing or {}).get("2026_MarAug_monthly_10BD"),
        },
    }
    with (OUT / "v3_unified_comparison.json").open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
