from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import no_tv_v47_daily_materializer as v47


def test_membership_reverse():
    current = {"1000"}
    events = pd.DataFrame([
        {"event_date": pd.Timestamp("2025-02-01"), "code": "2000", "event": "delisting"},
        {"event_date": pd.Timestamp("2025-06-01"), "code": "3000", "event": "listing"},
    ])
    assert v47.members_as_of(current, events, pd.Timestamp("2025-01-15")) == {"1000", "2000"}
    assert v47.members_as_of(current, events, pd.Timestamp("2025-07-01")) == {"1000"}


def test_split_factor_boundaries():
    sm = {"X": [
        (pd.Timestamp("2025-04-01"), 10.0),
        (pd.Timestamp("2026-01-01"), 2.0),
    ]}
    assert math.isclose(v47.split_factor(sm, "X", pd.Timestamp("2025-03-31")), 20.0)
    assert math.isclose(v47.split_factor(sm, "X", pd.Timestamp("2025-04-01")), 2.0)
    assert math.isclose(v47.split_factor(sm, "X", pd.Timestamp("2026-01-01")), 1.0)


def test_price_policy_arms_and_membership():
    daily = pd.DataFrame({
        "date": pd.to_datetime([
            "2025-01-06", "2025-01-07",
            "2025-01-06", "2025-01-07",
            "2025-01-06", "2025-01-07",
        ]),
        "open": [100,110, 500,520, 200,210],
        "high": [105,115, 510,530, 205,215],
        "low": [95,105, 490,510, 195,205],
        "close": [100,110, 500,520, 200,210],
        "volume": [20000,20000, 300000,300000, 40000,40000],
        "symbol": ["A","A","B","B","C","C"],
    })
    memberships = {
        "2025-01-06": {"A","B"},
        "2025-01-07": {"A","B"},
    }
    sm = {
        "B": [(pd.Timestamp("2025-04-01"), 10.0)],
    }
    events = pd.DataFrame(columns=["event_date","code","event"])
    out, stats = v47.materialize_daily_candidates(daily, memberships, sm, events)
    d = out[out["date_s"] == "2025-01-07"].set_index("symbol")
    assert bool(d.loc["A","eligible_nocap_daily"]) is True
    assert bool(d.loc["A","eligible_cap1000_daily"]) is True
    assert bool(d.loc["B","eligible_nocap_daily"]) is True
    assert bool(d.loc["B","eligible_cap1000_daily"]) is False
    assert "C" not in d.index
    assert stats["NOCAP"]["unique_symbols"] == 2
    assert stats["CAP1000_PIT"]["unique_symbols"] == 1


def test_cap_is_subset_of_nocap():
    daily = pd.DataFrame({
        "date": pd.to_datetime(["2025-01-06","2025-01-07"]*3),
        "open": [1,1,1,1,1,1],
        "high": [1,1,1,1,1,1],
        "low": [1,1,1,1,1,1],
        "close": [500,500,1500,1500,900,900],
        "volume": [20000]*6,
        "symbol": ["A","A","B","B","C","C"],
    })
    memberships={"2025-01-06":{"A","B","C"},"2025-01-07":{"A","B","C"}}
    events = pd.DataFrame(columns=["event_date","code","event"])
    out,_=v47.materialize_daily_candidates(daily,memberships,{},events)
    assert not ((out["eligible_cap1000_daily"]) & (~out["eligible_nocap_daily"])).any()




def test_listing_epoch_resets_prior_close_and_volume():
    daily = pd.DataFrame({
        "date": pd.to_datetime([
            "2025-05-30",
            "2025-06-02",
            "2025-06-03",
        ]),
        "open":[500,100,105],
        "high":[510,110,115],
        "low":[490,95,100],
        "close":[500,105,110],
        "volume":[50000,20000,30000],
        "symbol":["S","S","S"],
    })
    events = pd.DataFrame([
        {
            "event_date": pd.Timestamp("2025-06-02"),
            "code":"S",
            "event":"listing",
        }
    ])
    memberships={
        "2025-05-30":set(),
        "2025-06-02":{"S"},
        "2025-06-03":{"S"},
    }
    out,_=v47.materialize_daily_candidates(
        daily,
        memberships,
        {},
        events,
    )
    # Listing day must not inherit the pre-listing stitched row.
    assert "2025-06-02" not in set(out["date_s"])
    # The following day may use the first post-listing completed day.
    d=out[out["date_s"]=="2025-06-03"].iloc[0]
    assert float(d["prev_close_adjusted"])==105.0
    assert float(d["prev_volume_pit"])==20000.0



def test_split_adjusted_daily_volume_is_restored_before_gate():
    daily = pd.DataFrame({
        "date": pd.to_datetime(["2025-01-06","2025-01-07"]),
        "open":[100,105],
        "high":[110,115],
        "low":[95,100],
        "close":[100,105],
        "volume":[50000,60000],
        "symbol":["X","X"],
    })
    memberships={
        "2025-01-06":{"X"},
        "2025-01-07":{"X"},
    }
    splits={"X":[(pd.Timestamp("2025-04-01"),10.0)]}
    events=pd.DataFrame(columns=["event_date","code","event"])
    out,_=v47.materialize_daily_candidates(
        daily,memberships,splits,events
    )
    # 50,000 present-basis shares / 10 = 5,000 PIT shares,
    # so the Jan-7 row must fail the >=10,000 prior-volume gate.
    assert "2025-01-07" not in set(out["date_s"])


def test_terminal_404_is_not_retried():
    calls={"n":0}
    original=v47.requests.get

    class Resp:
        status_code=404
        def raise_for_status(self):
            raise AssertionError("terminal 404 should return before raise_for_status")

    def fake_get(*args,**kwargs):
        calls["n"]+=1
        return Resp()

    v47.requests.get=fake_get
    try:
        fr,sp,err=v47.fetch_restored_one("9999")
    finally:
        v47.requests.get=original

    assert calls["n"]==1
    assert fr.empty
    assert sp==[]
    assert err=="http_404_terminal"


def main():
    tests=[
        test_membership_reverse,
        test_split_factor_boundaries,
        test_price_policy_arms_and_membership,
        test_cap_is_subset_of_nocap,
        test_listing_epoch_resets_prior_close_and_volume,
        test_split_adjusted_daily_volume_is_restored_before_gate,
        test_terminal_404_is_not_retried,
    ]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(tests)}/{len(tests)} PASS")


if __name__ == "__main__":
    main()
