#!/usr/bin/env python3
"""Synthetic checks for delisted-price coverage diagnostics (TEST ONLY)."""
from __future__ import annotations

import pandas as pd

import delisted_price_coverage as d


def main() -> None:
    events = pd.DataFrame([
        {"event_date": "2024-06-28", "code": "A001", "event": "delisting"},
        {"event_date": "2023-03-31", "code": "B002", "event": "delisting"},
        {"event_date": "2024-09-02", "code": "B002", "event": "listing"},
        {"event_date": "2024-05-31", "code": "C003", "event": "delisting"},
    ])
    events["event_date"] = pd.to_datetime(events["event_date"])
    cand = d.build_delisting_candidates(
        events,
        current_codes={"B002", "C003"},
        start_date=pd.Timestamp("2022-01-01"),
    )
    a = cand[cand["code"] == "A001"].iloc[0]
    b = cand[cand["code"] == "B002"].iloc[0]
    c = cand[cand["code"] == "C003"].iloc[0]
    assert not bool(a["identity_quarantined"])
    assert bool(b["identity_quarantined"])
    assert "later_listing_event" in b["identity_reasons"]
    assert bool(c["identity_quarantined"])
    assert "code_currently_listed" in c["identity_reasons"]

    good_dates = pd.bdate_range("2024-06-10", "2024-06-28")
    good = pd.DataFrame({"date": good_dates, "close": 100.0})
    assessed = d.assess_price_frame(good, pd.Timestamp("2024-06-28"))
    assert assessed["coverage_status"] == "usable_near_delist"
    assert assessed["usable_near_delist"] is True
    assert assessed["last_price_gap_days"] == 0

    suspicious = pd.concat([
        good,
        pd.DataFrame({"date": [pd.Timestamp("2024-07-01")], "close": [101.0]}),
    ], ignore_index=True)
    assessed2 = d.assess_price_frame(suspicious, pd.Timestamp("2024-06-28"))
    assert assessed2["coverage_status"] == "suspicious_post_delist_data"
    assert assessed2["usable_near_delist"] is False

    old = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-04", "2024-01-05"]),
        "close": [100.0, 101.0],
    })
    assessed3 = d.assess_price_frame(old, pd.Timestamp("2024-06-28"))
    assert assessed3["coverage_status"] == "partial_old_or_sparse"
    assert assessed3["usable_near_delist"] is False

    empty = d.assess_price_frame(pd.DataFrame(), pd.Timestamp("2024-06-28"))
    assert empty["coverage_status"] == "missing"
    assert empty["usable_near_delist"] is False

    result = cand.copy()
    result["coverage_status"] = ["usable_near_delist", "identity_quarantined", "identity_quarantined"]
    result["usable_near_delist"] = [True, False, False]
    rep = d.summarize(result)
    assert rep["official_delisting_events"] == 3
    assert rep["identity_quarantined"] == 2
    assert rep["probed_events"] == 1
    assert rep["usable_near_delist"] == 1
    print("delisted_price_coverage_selftest: OK")


if __name__ == "__main__":
    main()
