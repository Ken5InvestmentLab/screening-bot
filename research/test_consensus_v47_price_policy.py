from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import select_consensus_v47_price_policy as v47


def s(n, mean, top3, median):
    return {
        "n": n,
        "mean_net_0p5_pct": mean,
        "top3_ex_net_0p5_pct": top3,
        "median_net_0p5_pct": median,
    }


def test_clear_mean_win():
    d = {
        "NOCAP": s(50, 4.0, 2.0, 1.0),
        "CAP1000_PIT": s(40, 3.0, 3.0, 2.0),
    }
    assert v47.choose_dev(d)["winner"] == "NOCAP"


def test_top3_breaks_mean_tie():
    d = {
        "NOCAP": s(50, 4.0, 2.5, 1.0),
        "CAP1000_PIT": s(40, 3.7, 1.5, 5.0),
    }
    assert v47.choose_dev(d)["winner"] == "NOCAP"


def test_median_breaks_deep_tie():
    d = {
        "NOCAP": s(50, 4.0, 2.0, 1.0),
        "CAP1000_PIT": s(40, 3.8, 2.1, 2.0),
    }
    assert v47.choose_dev(d)["winner"] == "CAP1000_PIT"


def test_full_tie_prefers_nocap():
    d = {
        "NOCAP": s(50, 4.0, 2.0, 1.0),
        "CAP1000_PIT": s(40, 4.0, 2.0, 1.0),
    }
    assert v47.choose_dev(d)["winner"] == "NOCAP"


def test_small_n_fails_closed():
    d = {
        "NOCAP": s(19, 4.0, 2.0, 1.0),
        "CAP1000_PIT": s(40, 3.0, 1.0, 0.0),
    }
    try:
        v47.choose_dev(d)
    except RuntimeError:
        return
    raise AssertionError("expected fail closed")


def test_validation_requires_same_arm_and_positive_mean():
    ok = v47.validate_winner(
        "NOCAP",
        {
            "arm": "NOCAP",
            "mean_net_0p5_pct": 0.1,
            "median_net_0p5_pct": -1.0,
            "top3_ex_net_0p5_pct": -0.2,
        },
    )
    assert ok["continued_research_pass"] is True

    bad = v47.validate_winner(
        "CAP1000_PIT",
        {
            "arm": "CAP1000_PIT",
            "mean_net_0p5_pct": -0.01,
        },
    )
    assert bad["continued_research_pass"] is False


def main():
    tests = [
        test_clear_mean_win,
        test_top3_breaks_mean_tie,
        test_median_breaks_deep_tie,
        test_full_tie_prefers_nocap,
        test_small_n_fails_closed,
        test_validation_requires_same_arm_and_positive_mean,
    ]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(tests)}/{len(tests)} PASS")


if __name__ == "__main__":
    main()
