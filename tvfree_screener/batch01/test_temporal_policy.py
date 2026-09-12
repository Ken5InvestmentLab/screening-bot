from __future__ import annotations

import unittest

import pandas as pd

from .temporal_policy import (
    assert_report_only_dates,
    purge_training_rows,
    validate_period_access,
)


class TemporalPolicyTests(unittest.TestCase):
    def test_discovery_is_the_only_model_selection_period(self) -> None:
        result = validate_period_access(
            intent="select_candidate",
            start="2022-07-01",
            end="2023-12-29",
            spec_sha256="spec-a",
        )
        self.assertEqual(result["access"], "DISCOVERY_SELECTION")
        with self.assertRaisesRegex(ValueError, "limited to 2022H2-2023"):
            validate_period_access(
                intent="select_features",
                start="2023-01-01",
                end="2026-08-31",
                spec_sha256="spec-a",
            )

    def test_historical_confirmation_uses_actual_freeze_before_phase_open(self) -> None:
        common = {
            "spec_sha256": "frozen-a",
            "frozen_spec_sha256": "frozen-a",
            "spec_frozen_at": "2026-01-01T00:00:00Z",
            "phase_opened_at": "2026-01-01T00:00:01Z",
        }
        result = validate_period_access(
            intent="locked_validation", start="2024-01-04", end="2024-12-30", **common,
        )
        self.assertEqual(result["access"], "LOCKED_CONFIRMATION")
        replay = validate_period_access(
            intent="replay_2025", start="2025-01-06", end="2025-12-30", **common,
        )
        self.assertEqual(replay["access"], "LOCKED_HISTORICAL_REPLAY")
        changed = dict(common, frozen_spec_sha256="other-spec")
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_period_access(
                intent="locked_validation", start="2024-01-04", end="2024-12-30", **changed,
            )
        late_frozen = dict(common, spec_frozen_at="2026-01-01T00:00:02Z")
        with self.assertRaisesRegex(ValueError, "frozen before the phase is opened"):
            validate_period_access(
                intent="replay_2025", start="2025-01-06", end="2025-12-30", **late_frozen,
            )
        with self.assertRaisesRegex(ValueError, "same timezone"):
            validate_period_access(
                intent="locked_validation", start="2024-01-04", end="2024-12-30",
                **dict(common, phase_opened_at="2026-01-01T00:00:01"),
            )

    def test_2026_is_report_only_and_requires_pre_2026_fit(self) -> None:
        common = {
            "spec_sha256": "frozen-a",
            "frozen_spec_sha256": "frozen-a",
            "spec_frozen_at": "2026-01-01T00:00:00Z",
            "phase_opened_at": "2026-01-01T00:00:01Z",
        }
        result = validate_period_access(
            intent="report_2026", start="2026-01-05", end="2026-08-31",
            model_fit_through="2025-12-31", **common,
        )
        self.assertEqual(result["access"], "REPORT_ONLY_FROZEN")
        with self.assertRaisesRegex(ValueError, "later than 2025-12-31"):
            validate_period_access(
                intent="report_2026", start="2026-01-05", end="2026-08-31",
                model_fit_through="2026-01-01", **common,
            )
        with self.assertRaisesRegex(ValueError, "2026 reporting helper"):
            assert_report_only_dates(["2025-12-30", "2026-01-05"])
        assert_report_only_dates(["2026-01-05", "2026-08-31"])

    def test_date_only_labels_are_purged_for_same_prediction_date(self) -> None:
        labels = pd.DataFrame({
            "symbol": ["prior", "same-day", "future"],
            "label_available_at": ["2024-01-04", "2024-01-05", "2024-01-08"],
        })
        eligible = purge_training_rows(labels, prediction_timestamp="2024-01-05")
        self.assertEqual(eligible.symbol.tolist(), ["prior"])

    def test_timestamp_precision_is_kept_and_timezone_mismatch_fails_closed(self) -> None:
        labels = pd.DataFrame({
            "symbol": ["already-known", "not-yet-known"],
            "label_available_at": pd.to_datetime([
                "2024-01-05T14:59:00+09:00", "2024-01-05T15:30:00+09:00",
            ]),
        })
        eligible = purge_training_rows(
            labels, prediction_timestamp="2024-01-05T15:00:00+09:00",
        )
        self.assertEqual(eligible.symbol.tolist(), ["already-known"])
        with self.assertRaisesRegex(ValueError, "same timezone"):
            purge_training_rows(labels, prediction_timestamp="2024-01-05T15:00:00Z")

    def test_invalid_dates_and_unknown_intents_reject(self) -> None:
        with self.assertRaisesRegex(ValueError, "start must not be after"):
            validate_period_access(
                intent="select_candidate", start="2023-12-31", end="2023-01-01", spec_sha256="x",
            )
        with self.assertRaisesRegex(ValueError, "unknown temporal access intent"):
            validate_period_access(
                intent="guess", start="2022-07-01", end="2022-07-05", spec_sha256="x",
            )


if __name__ == "__main__":
    unittest.main()
