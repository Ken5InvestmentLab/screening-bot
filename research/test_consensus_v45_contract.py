from __future__ import annotations

import pandas as pd

import no_tv_v45_full_context_atr as v45


def test_build_contexts_one_vote_per_date_session():
    d = pd.DataFrame([
        {"date":"2025-01-06","session":9,"market_median_atr":2.0,"market_candidate_count":100},
        {"date":"2025-01-06","session":9,"market_median_atr":2.0,"market_candidate_count":100},
        {"date":"2025-01-06","session":13,"market_median_atr":2.2,"market_candidate_count":95},
        {"date":"2025-01-07","session":9,"market_median_atr":2.4,"market_candidate_count":90},
    ])
    out = v45.build_contexts(d, "2025-01-06", "2025-01-07")
    assert len(out) == 3
    assert list(out["session"]) == [9,13,9]


def test_build_contexts_rejects_inconsistent_group_context():
    d = pd.DataFrame([
        {"date":"2025-01-06","session":9,"market_median_atr":2.0,"market_candidate_count":100},
        {"date":"2025-01-06","session":9,"market_median_atr":2.1,"market_candidate_count":100},
    ])
    try:
        v45.build_contexts(d, "2025-01-06", "2025-01-06")
    except RuntimeError as e:
        assert "not internally constant" in str(e)
    else:
        raise AssertionError("expected inconsistent context to fail")


def test_quantiles_are_unweighted_by_candidate_count():
    s = pd.Series([1.0,2.0,3.0,4.0,5.0])
    q = v45.quantiles(s)
    assert q["n"] == 5
    assert q["q50"] == 3.0
    assert q["q90"] == 4.6


def test_fetch_receipt_pass_and_fail():
    ok = {
        "requested_symbols": v45.EXPECTED_REQUESTED_SYMBOLS,
        "candidate_symbols": v45.V43_CANDIDATE_SYMBOLS,
    }
    cov = v45.validate_fetch_receipt(ok)
    assert cov == 1.0

    bad_universe = dict(ok)
    bad_universe["requested_symbols"] -= 1
    try:
        v45.validate_fetch_receipt(bad_universe)
    except RuntimeError as e:
        assert "universe drift" in str(e)
    else:
        raise AssertionError("expected universe drift failure")

    bad_cov = dict(ok)
    bad_cov["candidate_symbols"] = int(v45.V43_CANDIDATE_SYMBOLS * 0.94)
    try:
        v45.validate_fetch_receipt(bad_cov)
    except RuntimeError as e:
        assert "coverage too low" in str(e)
    else:
        raise AssertionError("expected coverage failure")


def main():
    tests=[
        test_build_contexts_one_vote_per_date_session,
        test_build_contexts_rejects_inconsistent_group_context,
        test_quantiles_are_unweighted_by_candidate_count,
        test_fetch_receipt_pass_and_fail,
    ]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(tests)}/{len(tests)} PASS")


if __name__=="__main__":
    main()
