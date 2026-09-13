import unittest
from datetime import date, timedelta

from tvfree_screener.batch02.prospective_shadow_maturity_gate import MaturityPolicy, evaluate_maturity


def make_rows(n_dates: int, rows_per_date: int = 2, status: str = "RESOLVED"):
    start = date(2026, 9, 1)
    rows = []
    for i in range(n_dates):
        d = start + timedelta(days=i * 2)
        for j in range(rows_per_date):
            rows.append({
                "status": status,
                "signal_date": d.isoformat(),
                "symbol": f"{1000+i:04d}",
                "bin_name": "PM" if j % 2 else "AM",
                "net_return": 999.0,
                "score": 999.0,
            })
    return rows


class ProspectiveShadowMaturityGateTests(unittest.TestCase):
    def test_return_and_score_values_do_not_affect_gate(self):
        policy = MaturityPolicy(min_resolved=4, min_distinct_signal_dates=2, min_calendar_span_days=1, min_distinct_months=1)
        rows = make_rows(2, 2)
        a = evaluate_maturity(rows, policy)
        for row in rows:
            row["net_return"] = -999.0
            row["score"] = -999.0
        b = evaluate_maturity(rows, policy)
        self.assertEqual(a, b)
        self.assertTrue(a["mature"])

    def test_pending_rows_do_not_count_as_resolved(self):
        policy = MaturityPolicy(min_resolved=2, min_distinct_signal_dates=1, min_calendar_span_days=0, min_distinct_months=1)
        rows = make_rows(1, 1, "RESOLVED") + make_rows(10, 3, "PENDING_5BD")
        result = evaluate_maturity(rows, policy)
        self.assertFalse(result["mature"])
        self.assertEqual(result["counts"]["resolved_rows"], 1)

    def test_requires_time_span_not_just_sample_count(self):
        policy = MaturityPolicy(min_resolved=6, min_distinct_signal_dates=3, min_calendar_span_days=20, min_distinct_months=1)
        rows = make_rows(3, 2)
        result = evaluate_maturity(rows, policy)
        self.assertFalse(result["mature"])
        self.assertFalse(result["checks"]["calendar_span_days"])

    def test_pass_only_authorizes_review_not_promotion(self):
        policy = MaturityPolicy(min_resolved=4, min_distinct_signal_dates=2, min_calendar_span_days=1, min_distinct_months=1)
        result = evaluate_maturity(make_rows(2, 2), policy)
        self.assertEqual(result["decision"], "EVIDENCE_MATURE_FOR_REVIEW")
        self.assertFalse(result["integrity"]["promotion_authorized"])
        self.assertFalse(result["integrity"]["uses_return_values"])


if __name__ == "__main__":
    unittest.main()
