#!/usr/bin/env python3
"""Synthetic guardrails for V4 event-quality research (TEST ONLY)."""
from __future__ import annotations

import pandas as pd

import v4_event_quality_research as v4


def main() -> None:
    spec = {"ret": 1.0, "hit10": 0.0, "loss10": 1.0, "gate": -2.0}
    trading_dates = pd.to_datetime([
        "2025-01-10",  # Friday
        "2025-01-14",  # next TSE session in this synthetic calendar
        "2025-01-15",
    ])

    scored = pd.DataFrame([
        # Friday: AAA wins.
        {"date":"2025-01-10","symbol":"AAA","cdf_ret":0.90,"cdf_hit10":0.5,"cdf_loss10":0.10},
        {"date":"2025-01-10","symbol":"BBB","cdf_ret":0.70,"cdf_hit10":0.5,"cdf_loss10":0.20},
        # Next trading day: AAA is still top but must be blocked, so BBB wins.
        {"date":"2025-01-14","symbol":"AAA","cdf_ret":0.95,"cdf_hit10":0.5,"cdf_loss10":0.05},
        {"date":"2025-01-14","symbol":"BBB","cdf_ret":0.80,"cdf_hit10":0.5,"cdf_loss10":0.20},
        # Following session: AAA was not selected on the immediately prior session,
        # so it becomes eligible again.
        {"date":"2025-01-15","symbol":"AAA","cdf_ret":0.96,"cdf_hit10":0.5,"cdf_loss10":0.04},
        {"date":"2025-01-15","symbol":"CCC","cdf_ret":0.60,"cdf_hit10":0.5,"cdf_loss10":0.20},
    ])
    scored["date"] = pd.to_datetime(scored["date"])

    picks = v4.select_variant(scored, spec, pd.Index(trading_dates))
    assert list(picks["symbol"]) == ["AAA", "BBB", "AAA"]

    # A missing prediction date in the supplied trading calendar must fail closed.
    bad = scored.iloc[[0]].copy()
    bad["date"] = pd.Timestamp("2025-01-13")
    try:
        v4.select_variant(bad, spec, pd.Index(trading_dates))
        raise AssertionError("missing trading date must fail closed")
    except RuntimeError:
        pass

    # 2025 validation gate is deterministic and does not depend on 2026.
    good = {"n":20, "mean":0.01, "loss10_rate":0.05}
    bad_mean = {"n":20, "mean":0.0, "loss10_rate":0.05}
    bad_loss = {"n":20, "mean":0.01, "loss10_rate":0.11}
    assert v4.validation_pass(good, good)
    assert not v4.validation_pass(bad_mean, good)
    assert not v4.validation_pass(bad_loss, good)

    print("v4_event_quality_selftest: OK")


if __name__ == "__main__":
    main()
