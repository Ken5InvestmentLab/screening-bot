#!/usr/bin/env python3
"""Synthetic checks for coverage-matched overlay evaluation."""
from __future__ import annotations

import pandas as pd

import fundamental_overlay_evaluator as e


def main() -> None:
    rows = []
    for date in [
        "2024-03-01", "2024-09-02", "2025-03-03", "2025-09-01",
        "2026-05-01",
    ]:
        rows += [
            {"date": date, "symbol": "1111", "target5_no": 0.05},
            {"date": date, "symbol": "2222", "target5_no": -0.05},
            # Deliberately attractive unknown row. It must not inflate the
            # matched known baseline or enter any filtered overlay lane.
            {"date": date, "symbol": "9999", "target5_no": 0.20},
        ]
    signals = pd.DataFrame(rows)

    snapshots = pd.DataFrame([
        {
            "symbol":"1111", "available_date":"2023-12-01",
            "shares_outstanding":100, "remaining_warrant_shares":10,
            "ms_warrant_flag":False, "equity":50, "assets":100,
            "revenue":100, "operating_income":10, "net_income":8,
            "operating_cf":12,
        },
        {
            "symbol":"2222", "available_date":"2023-12-01",
            "shares_outstanding":100, "remaining_warrant_shares":80,
            "ms_warrant_flag":True, "equity":5, "assets":100,
            "revenue":100, "operating_income":-5, "net_income":-7,
            "operating_cf":-3,
        },
    ])

    report = e.evaluate(signals, snapshots, "target5_no")
    cov = report["coverage"]
    assert cov["valid_target_rows"] == 15
    assert cov["dilution_known_baseline"]["n"] == 10
    assert cov["dilution_unknown"]["n"] == 5
    assert cov["financial_known_baseline"]["n"] == 10
    assert cov["combined_known_baseline"]["n"] == 10

    for period in ["2024H1", "2024H2", "2025H1", "2025H2"]:
        comp = report["pre2026_research"]["dilution_le_0.35"]["periods"][period]
        assert comp["matched_baseline"]["n"] == 2
        assert comp["filtered"]["n"] == 1
        assert abs(comp["matched_baseline"]["mean"] - 0.0) < 1e-12
        assert abs(comp["filtered"]["mean"] - 0.05) < 1e-12
        assert abs(comp["retained_fraction"] - 0.5) < 1e-12
        assert abs(comp["delta_filtered_minus_baseline"]["mean"] - 0.05) < 1e-12

        fin = report["pre2026_research"]["financial_risk_filter"]["periods"][period]
        assert fin["matched_baseline"]["n"] == 2
        assert fin["filtered"]["n"] == 1

    # 2026 exists only in the explicitly labelled reporting section.
    assert "2026_MarAug_reporting_only" in (
        report["2026_reporting_only"]["dilution_le_0.35"]
    )
    assert "2026_MarAug_reporting_only" not in report["pre2026_research"]

    try:
        e.evaluate(signals.drop(columns=["target5_no"]), snapshots, "target5_no")
        raise AssertionError("missing target must fail")
    except ValueError:
        pass

    print("fundamental_overlay_evaluator_selftest: OK")


if __name__ == "__main__":
    main()
