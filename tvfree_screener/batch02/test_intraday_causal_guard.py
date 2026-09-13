from __future__ import annotations

import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from tvfree_screener.batch02.intraday_causal_guard import (
    classify_causal_use,
    classify_materialized_feature_input,
)

JST = ZoneInfo("Asia/Tokyo")


class IntradayCausalGuardTests(unittest.TestCase):
    def dt(self, hour: int, minute: int = 0, day: int = 11) -> datetime:
        return datetime(2026, 9, day, hour, minute, tzinfo=JST)

    def test_raw_observation_before_cutoff_is_allowed(self):
        self.assertTrue(classify_causal_use(
            observation_timestamp=self.dt(10),
            feature_cutoff_timestamp=self.dt(13),
        ).eligible)

    def test_observation_after_cutoff_is_rejected(self):
        self.assertFalse(classify_causal_use(
            observation_timestamp=self.dt(14),
            feature_cutoff_timestamp=self.dt(13),
        ).eligible)

    def test_same_session_daily_anchor_with_unknown_availability_is_rejected(self):
        decision = classify_causal_use(
            observation_timestamp=self.dt(10),
            feature_cutoff_timestamp=self.dt(16),
            uses_final_daily_anchor=True,
            anchor_session_date=date(2026, 9, 11),
        )
        self.assertEqual(decision.status, "SAME_SESSION_FINAL_DAILY_AVAILABILITY_UNKNOWN")

    def test_same_session_daily_anchor_published_after_cutoff_is_rejected(self):
        decision = classify_causal_use(
            observation_timestamp=self.dt(10),
            feature_cutoff_timestamp=self.dt(15, 45),
            uses_final_daily_anchor=True,
            anchor_session_date=date(2026, 9, 11),
            daily_available_at=self.dt(16),
        )
        self.assertFalse(decision.eligible)

    def test_same_session_daily_anchor_explicitly_available_by_cutoff_is_allowed(self):
        decision = classify_causal_use(
            observation_timestamp=self.dt(10),
            feature_cutoff_timestamp=self.dt(16),
            uses_final_daily_anchor=True,
            anchor_session_date=date(2026, 9, 11),
            daily_available_at=self.dt(15, 40),
        )
        self.assertTrue(decision.eligible)

    def test_prior_completed_session_daily_anchor_is_allowed(self):
        decision = classify_causal_use(
            observation_timestamp=self.dt(10),
            feature_cutoff_timestamp=self.dt(13),
            uses_final_daily_anchor=True,
            anchor_session_date=date(2026, 9, 10),
        )
        self.assertTrue(decision.eligible)

    def test_impossible_preclose_daily_finalization_is_rejected(self):
        decision = classify_causal_use(
            observation_timestamp=self.dt(10),
            feature_cutoff_timestamp=self.dt(16),
            uses_final_daily_anchor=True,
            anchor_session_date=date(2026, 9, 11),
            daily_available_at=self.dt(15),
        )
        self.assertFalse(decision.eligible)

    def test_materialized_daily_fallback_is_rejected_at_4h_boundary(self):
        decision = classify_materialized_feature_input({
            "resolution": "1D",
            "source_tag": "C_DAILY_RESOLUTION_FALLBACK",
            "causal_use": "DAILY_ONLY_AFTER_FINAL_AVAILABLE",
        })
        self.assertFalse(decision.eligible)
        self.assertEqual(decision.status, "DAILY_RESOLUTION_NOT_INTRADAY")

    def test_materialized_postclose_reconstruction_is_rejected_at_4h_boundary(self):
        decision = classify_materialized_feature_input({
            "resolution": "1H",
            "causal_signal_eligibility": "POSTCLOSE_RECON_ONLY",
        })
        self.assertFalse(decision.eligible)

    def test_materialized_raw_causal_intraday_is_allowed(self):
        decision = classify_materialized_feature_input({
            "resolution": "1H",
            "causal_signal_eligibility": "RAW_CAUSAL_INTRADAY",
        })
        self.assertTrue(decision.eligible)

    def test_unknown_materialized_status_fails_closed(self):
        decision = classify_materialized_feature_input({"resolution": "1H"})
        self.assertFalse(decision.eligible)
        self.assertEqual(decision.status, "UNKNOWN_CAUSAL_MATERIALIZATION_STATUS")


if __name__ == "__main__":
    unittest.main()
