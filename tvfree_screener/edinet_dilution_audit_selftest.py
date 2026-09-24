#!/usr/bin/env python3
"""Synthetic checks for audit-first EDINET dilution evidence extraction."""
from __future__ import annotations

import pandas as pd

import edinet_dilution_audit as d


def main() -> None:
    facts = pd.DataFrame([
        {
            "element_id": "jpcrp_cor:ParticularsOfNewShareSubscriptionRightsTextBlock",
            "context_id": "FilingDateInstant",
            "source_member": "XBRL_TO_CSV/jpcrp.csv",
            "value": (
                "<table><tr><td>新株予約権の目的となる株式の種類、内容及び数</td>"
                "<td>普通株式 1,200,000株［900,000株］</td></tr></table>"
            ),
        },
        {
            "element_id": "jpcrp_cor:ExercisesEtcOfMovingStrikeConvertibleBondsEtcTextBlock",
            "context_id": "CurrentYearDuration",
            "source_member": "XBRL_TO_CSV/jpcrp.csv",
            "value": "行使価額修正条項付新株予約権の行使状況 500,000株",
        },
        {
            "element_id": "jppfs_cor:NetSales",
            "context_id": "CurrentYearDuration",
            "source_member": "XBRL_TO_CSV/jppfs.csv",
            "value": "無関係 999株",
        },
    ])
    doc = {
        "symbol": "9999",
        "doc_id": "S100SYNTH",
        "available_at": "2025-06-20 16:00:00",
        "available_date": "2025-06-20",
        "period_start": "2024-04-01",
        "period_end": "2025-03-31",
    }

    ev = d.extract_dilution_evidence(facts, doc)
    assert len(ev) == 3
    assert set(ev["doc_id"]) == {"S100SYNTH"}
    assert set(ev["symbol"]) == {"9999"}
    assert set(ev["share_count"].astype(int)) == {1_200_000, 900_000, 500_000}
    assert int((ev["candidate_role"] == "potential_share_candidate").sum()) >= 2

    moving = ev[ev["source_kind"] == "moving_strike_exercise_status"]
    assert len(moving) == 1
    assert bool(moving.iloc[0]["ms_warrant_evidence"])

    bracketed = ev[ev["share_count"] == 900_000]
    assert len(bracketed) == 1
    assert bool(bracketed.iloc[0]["bracketed_near_token"])

    # Core guardrail: extraction evidence is not an accepted residual-share fact.
    assert not bool(ev["accepted_remaining_potential_shares"].any())
    rep = d.evidence_report(ev)
    assert rep["share_count_candidates"] == 3
    assert rep["ms_warrant_evidence_rows"] == 1
    assert rep["accepted_remaining_potential_share_rows"] == 0

    assert d.parse_share_count("１，２３４") == 1234
    assert d.parse_share_count("abc") is None
    print("edinet_dilution_audit_selftest: OK")


if __name__ == "__main__":
    main()
