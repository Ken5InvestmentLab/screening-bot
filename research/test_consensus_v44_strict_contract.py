from __future__ import annotations

import pandas as pd

import evaluate_consensus_v44_strict5 as strict5
import audit_consensus_v44_ties as ties
import verify_consensus_v44_acceptance as accept


def test_cooldown_reentry_exact_day5():
    dates = [f"2025-01-{d:02d}" for d in range(1, 7)]
    day_index = {d: i for i, d in enumerate(dates)}
    rows = []
    for d in dates:
        rows += [
            {"date": d, "session": 9, "symbol": "A", "candidate_rank": 1, "cons_min": 0.99},
            {"date": d, "session": 9, "symbol": "B", "candidate_rank": 2, "cons_min": 0.98},
        ]
    pool = pd.DataFrame(rows)
    out = strict5.select_with_replacement(pool, day_index, 5)
    got = list(zip(out["date"], out["symbol"]))
    assert got[0] == (dates[0], "A")
    assert got[1] == (dates[1], "B")
    # Both names are blocked on days 2-4.
    assert (dates[2], "A") not in got
    assert (dates[3], "A") not in got
    assert (dates[4], "A") not in got
    # A is eligible again exactly 5 trading-day indices later.
    assert (dates[5], "A") in got


def test_dev_eligibility_boundary_passes():
    result = {
        "development": {
            "0": {"mean_pct": 10.0, "max_symbol_share": 0.40},
            "5": {"mean_pct": 8.0, "max_symbol_share": 0.30},
        }
    }
    ok, receipt = strict5.dev_eligible(result)
    assert ok is True
    assert receipt["mean_retention_pass"] is True
    assert receipt["concentration_pass"] is True


def test_dev_eligibility_rejects_either_failure():
    result = {
        "development": {
            "0": {"mean_pct": 10.0, "max_symbol_share": 0.40},
            "5": {"mean_pct": 7.99, "max_symbol_share": 0.30},
        }
    }
    ok, _ = strict5.dev_eligible(result)
    assert ok is False

    result["development"]["5"] = {"mean_pct": 8.0, "max_symbol_share": 0.301}
    ok, _ = strict5.dev_eligible(result)
    assert ok is False


def test_h2_gate_all_conditions_required():
    base = {"mean_pct": 5.0, "max_symbol_share": 0.40}
    good = {
        "n": 20,
        "mean_pct": 4.0,
        "median_pct": 0.0,
        "top3_ex_mean_pct": 0.01,
        "max_symbol_share": 0.30,
    }
    assert strict5.h2_gate(base, good)["pass"] is True

    for key, bad_value in [
        ("n", 19),
        ("mean_pct", 3.99),
        ("median_pct", -0.001),
        ("top3_ex_mean_pct", 0.0),
        ("max_symbol_share", 0.301),
    ]:
        bad = dict(good)
        bad[key] = bad_value
        assert strict5.h2_gate(base, bad)["pass"] is False, key


def test_exact_tie_audit():
    pool = pd.DataFrame([
        {"date":"2025-01-01","session":9,"symbol":"A","cons_min":0.99,"candidate_rank":1},
        {"date":"2025-01-01","session":9,"symbol":"B","cons_min":0.99,"candidate_rank":2},
        {"date":"2025-01-01","session":9,"symbol":"C","cons_min":0.98,"candidate_rank":3},
        {"date":"2025-01-02","session":9,"symbol":"A","cons_min":0.97,"candidate_rank":1},
        {"date":"2025-01-02","session":9,"symbol":"B","cons_min":0.96,"candidate_rank":2},
    ])
    out = ties.exact_tie_counts(pool)
    assert out["groups"] == 2
    assert out["groups_with_top1_cons_min_tie"] == 1
    assert out["groups_with_any_tie_within_top10"] == 1
    assert out["candidate_rows_in_exact_cons_min_ties"] == 2


def test_v44_acceptance_guard_exact_boundaries():
    good = {
        "baseline_reproduction_receipt": {"passed": True},
        "hourly_fetch": {
            "requested_symbols": 1910,
            "ok_symbols": 1850,
            "candidate_symbols": 1793,
            "candidate_rows": 519163,
        },
        "nonchosen_validation_metrics_opened": False,
    }
    receipt = accept.evaluate_acceptance(good)
    assert receipt["accepted"] is True
    assert receipt["performance_fields_inspected"] is False

    cases = [
        ("requested_symbols", 1909),
        ("ok_symbols", 1849),
        ("candidate_symbols", 1792),
        ("candidate_rows", 519162),
    ]
    for key, bad in cases:
        q = {
            "baseline_reproduction_receipt": {"passed": True},
            "hourly_fetch": dict(good["hourly_fetch"]),
            "nonchosen_validation_metrics_opened": False,
        }
        q["hourly_fetch"][key] = bad
        assert accept.evaluate_acceptance(q)["accepted"] is False, key

    q = dict(good)
    q["baseline_reproduction_receipt"] = {"passed": False}
    assert accept.evaluate_acceptance(q)["accepted"] is False

    q = dict(good)
    q["nonchosen_validation_metrics_opened"] = True
    assert accept.evaluate_acceptance(q)["accepted"] is False


def main():
    tests = [
        test_cooldown_reentry_exact_day5,
        test_dev_eligibility_boundary_passes,
        test_dev_eligibility_rejects_either_failure,
        test_h2_gate_all_conditions_required,
        test_exact_tie_audit,
        test_v44_acceptance_guard_exact_boundaries,
    ]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(tests)}/{len(tests)} PASS")


if __name__ == "__main__":
    main()
