#!/usr/bin/env python3
"""Synthetic checks for point_in_time_universe.py. TEST ONLY."""
from __future__ import annotations

import pandas as pd

import point_in_time_universe as pit


def main() -> None:
    anchor = pd.Timestamp("2025-12-31")
    current = {"A001", "C003"}
    events = pd.DataFrame([
        {"event_date": pd.Timestamp("2023-04-03"), "code": "C003", "event": "listing"},
        {"event_date": pd.Timestamp("2024-06-28"), "code": "B002", "event": "delisting"},
    ])

    # At the anchor, use the exact current snapshot.
    assert pit.members_as_of(current, events, anchor, anchor) == {"A001", "C003"}
    # Before B002 delisted, restore it; C003 still exists after its listing.
    assert pit.members_as_of(current, events, pd.Timestamp("2024-01-31"), anchor) == {"A001", "B002", "C003"}
    # Before C003 listed, undo that listing too.
    assert pit.members_as_of(current, events, pd.Timestamp("2022-12-30"), anchor) == {"A001", "B002"}

    # Code reuse is handled if events are temporally ordered: undo later listing,
    # then restore the older delisted episode when travelling further backwards.
    reuse = pd.DataFrame([
        {"event_date": pd.Timestamp("2023-03-31"), "code": "D004", "event": "delisting"},
        {"event_date": pd.Timestamp("2024-09-02"), "code": "D004", "event": "listing"},
    ])
    assert pit.members_as_of({"D004"}, reuse, pd.Timestamp("2024-01-31"), anchor) == set()
    assert pit.members_as_of({"D004"}, reuse, pd.Timestamp("2022-12-30"), anchor) == {"D004"}

    unknown = pd.DataFrame(columns=["event_date", "code", "event", "market", "source_url"])
    v = pit.validate_events(events.assign(market="プライム", source_url="x"), unknown)
    assert v["valid_for_membership_reconstruction"] is True

    collision_events = pd.DataFrame([
        {"event_date": pd.Timestamp("2024-01-01"), "code": "X999", "event": "listing"},
        {"event_date": pd.Timestamp("2024-01-01"), "code": "X999", "event": "delisting"},
    ])
    v2 = pit.validate_events(collision_events, unknown)
    assert v2["valid_for_membership_reconstruction"] is False
    assert v2["same_day_code_collisions"] == 1

    print("point-in-time universe self-test: PASS")


if __name__ == "__main__":
    main()
